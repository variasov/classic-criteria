# Classic Criteria

Критерии (спецификации) из книги Эрика Эванса
"Domain Driven Design: tackling complexity in the heart of software".

Критерий описывает условие на объект предметной области. Его можно:

- проверить на объекте в памяти;
- скомбинировать с другими критериями через `&`, `|`, `^`, `~`;
- передать в хранилище и превратить в запрос, например в SQL-условие
  через [classic-db-tools](#выборки-в-бд).

Критерий можно описать двумя способами: классом или декоратором `criteria`
на функции или методе.

## Установка

```shell
pip install classic-criteria
```

## Критерии-классы

Пусть есть задача. Задача открыта, если у неё нет времени завершения,
и просрочена, если на неё ушло больше заданного числа дней:

```python
from dataclasses import dataclass
from datetime import datetime

from classic.criteria import Criteria


@dataclass
class Task:
    created_at: datetime
    finished_at: datetime | None = None


@dataclass
class Open(Criteria[Task]):
    """Открытая задача."""

    def is_satisfied_by(self, candidate: Task) -> bool:
        return candidate.finished_at is None


@dataclass
class Obsolete(Criteria[Task]):
    """Задача, на которую ушло больше `days_to_work` дней."""

    days_to_work: int

    def is_satisfied_by(self, candidate: Task) -> bool:
        return (
            candidate.finished_at is not None
            and (candidate.finished_at - candidate.created_at).days
            > self.days_to_work
        )
```

### Проверка

```python
task = Task(created_at=datetime(2025, 1, 1))

Open().is_satisfied_by(task)
# True

Open()(task)  # __call__ — синоним is_satisfied_by
# True
```

### Комбинирование

| Оператор | Результат | Выполнен, если |
|---|---|---|
| `a & b` | `And` | выполнены все |
| `a \| b` | `Or` | выполнен хотя бы один |
| `a ^ b` | `Xor` | выполнен ровно один |
| `~a` | `Invert` | `a` не выполнен |

Операторы возвращают новый критерий и не изменяют операнды, поэтому
составной критерий можно сохранить в переменной и использовать повторно:

```python
open_or_obsolete = Open() | Obsolete(3)

open_or_obsolete.is_satisfied_by(task)
# True

stale = open_or_obsolete & ~Open()  # open_or_obsolete не изменился
stale.is_satisfied_by(task)
# False
```

### Фильтрация

Критерий можно вызвать как функцию, поэтому его удобно передавать
в `filter`:

```python
tasks = [
    Task(created_at=datetime(2025, 1, 1)),
    Task(created_at=datetime(2025, 1, 1), finished_at=datetime(2025, 1, 5)),
    Task(created_at=datetime(2025, 1, 1), finished_at=datetime(2025, 1, 2)),
]

list(filter(Open() | Obsolete(3), tasks))
# [Task(created_at=datetime.datetime(2025, 1, 1, 0, 0), finished_at=None),
#  Task(created_at=..., finished_at=datetime.datetime(2025, 1, 5, 0, 0))]
```

### Обязательная проверка

`must_be_satisfied_by` бросает `CriteriaNotSatisfied`, если критерий
не выполнен. В атрибуте `criteria` исключения лежит невыполненная часть:
для `And` — только невыполненные критерии, для остальных — весь критерий.
Сам проверяемый объект в исключении не хранится.

```python
from classic.criteria import CriteriaNotSatisfied

done = Task(created_at=datetime(2025, 1, 1), finished_at=datetime(2025, 1, 2))

try:
    (Obsolete(0) & Open()).must_be_satisfied_by(done)
except CriteriaNotSatisfied as error:
    error.criteria
    # Open()
```

Невыполненную часть можно получить и без исключения:

```python
(Obsolete(0) & Open()).remainder_unsatisfied_by(done)
# Open()

(Obsolete(0) & Open()).remainder_unsatisfied_by(task)
# Obsolete(days_to_work=0)
```

`CriteriaNotSatisfied` унаследован от `Exception`.

### Сравнение и отладка

Составные критерии сравниваются по структуре и выводятся в `repr`
в виде вызова конструкторов. Это удобно в логах и в тестах,
например в `mock.assert_called_once_with(...)`. Для `And` и `Or`
порядок операндов не важен, для `Xor` и `Invert` — важен:

```python
Open() & Obsolete(3) == Open() & Obsolete(3)
# True

Open() & Obsolete(3) == Obsolete(3) & Open()  # порядок не важен
# True

repr(Open() & ~Obsolete(3))
# 'And(Open(), Invert(Obsolete(days_to_work=3)))'
```

Критерии неизменяемы: составные хранят операнды в кортеже `nested`
и не дают переприсвоить атрибуты после создания, критерии из `@criteria` —
frozen dataclass (изменение поля даёт `FrozenInstanceError`). Поэтому
деревья критериев можно класть в множества и использовать как ключи
словарей, если листья тоже хешируемы (`@dataclass(frozen=True)`, критерии
из `@criteria`); обычный `@dataclass` без `frozen=True` нехешируем:

```python
@dataclass(frozen=True)
class Open(Criteria[Task]):
    ...


rules = {Open() & Obsolete(3), Obsolete(3) & Open()}
len(rules)
# 1

{Open() & Obsolete(3): "правило"}[Obsolete(3) & Open()]
# 'правило'
```

Сравнение без порядка работает и с нехешируемыми листьями —
для `==` хешируемость не нужна, `TypeError` даёт только `hash()`
и добавление в `set`/`dict`.

`ReturnsTrue` и `ReturnsFalse` всегда выполнены и всегда не выполнены
соответственно. Их удобно брать начальным значением при сборке фильтра
из частей:

```python
import functools
import operator

from classic.criteria import ReturnsTrue

parts = [Open(), ~Obsolete(3)]
functools.reduce(operator.and_, parts, ReturnsTrue())
# And(ReturnsTrue(), Open(), Invert(Obsolete(days_to_work=3)))
```

## Критерии-методы

Критерий можно описать методом класса, например самой сущности,
с декоратором `criteria`. Первый параметр — проверяемый объект (`self`),
остальные — параметры критерия:

```python
from dataclasses import dataclass
from datetime import datetime

from classic.criteria import criteria


@dataclass
class Task:
    created_at: datetime
    finished_at: datetime | None = None

    @criteria
    def open(self) -> bool:
        return self.finished_at is None

    @criteria
    def obsolete(self, days_to_work: int) -> bool:
        return (
            self.finished_at is not None
            and (self.finished_at - self.created_at).days > days_to_work
        )
```

### На экземпляре: немедленная проверка

На экземпляре вызов сразу проверяет условие и возвращает `bool`.
Такие результаты комбинируются обычными `and`, `or`, `not`:

```python
task = Task(created_at=datetime(2025, 1, 1))

task.open()
# True

task.open() or task.obsolete(3)
# True

task.obsolete.is_satisfied(3)
# False

task.obsolete.must_be_satisfied(3)
# CriteriaNotSatisfied: Criteria not satisfied: obsolete(days_to_work=3)
```

### На классе: отложенный критерий

На классе вызов ничего не проверяет, а создаёт объект-критерий.
Он ведёт себя так же, как критерии-классы: комбинируется через
`&`, `|`, `^`, `~`, передаётся в `filter` или в хранилище:

```python
is_stale = Task.obsolete(3) & ~Task.open()

is_stale
# And(obsolete(days_to_work=3), Invert(open()))

tasks = [
    Task(created_at=datetime(2025, 1, 1)),
    Task(created_at=datetime(2025, 1, 1), finished_at=datetime(2025, 1, 5)),
]
list(filter(is_stale, tasks))
# [Task(created_at=..., finished_at=datetime.datetime(2025, 1, 5, 0, 0))]
```

Составной критерий можно объявить атрибутом класса. На экземпляре он тоже
проверяется сразу:

```python
@dataclass
class Task:
    created_at: datetime
    finished_at: datetime | None = None

    @criteria
    def open(self) -> bool:
        return self.finished_at is None

    @criteria
    def obsolete(self, days_to_work: int) -> bool:
        return (
            self.finished_at is not None
            and (self.finished_at - self.created_at).days > days_to_work
        )

    stale = obsolete(3) & ~open()


Task(created_at=datetime(2025, 1, 1)).stale()
# False
```

### Параметры

Критерий из `criteria` — это dataclass. Имя класса совпадает с именем
функции, параметры становятся полями и доступны как атрибуты:

```python
crit = Task.obsolete(days_to_work=3)

type(crit).__name__
# 'obsolete'

crit.days_to_work
# 3
```

Поддерживаются значения по умолчанию, keyword-only и positional-only
параметры. Значения передаются в функцию как есть, без копирования.
Нельзя использовать `*args`, `**kwargs` и имена параметров `predicate`,
`_positional`, `_keyword`: декоратор бросит `TypeError`.

## Критерии-функции

Декоратор работает и на обычных функциях. Такие критерии ведут себя так же,
как критерии-методы на классе:

```python
@criteria
def task_open(task: Task) -> bool:
    return task.finished_at is None


@criteria
def task_obsolete(task: Task, *, days_to_work: int) -> bool:
    return (
        task.finished_at is not None
        and (task.finished_at - task.created_at).days > days_to_work
    )


(task_open() | task_obsolete(days_to_work=3)).is_satisfied_by(task)
# True
```

Критерии из функций и методов уровня модуля поддерживают `pickle`
и `copy.deepcopy`.

## Выборки в БД

Критерии можно превращать в запросы к БД. Как транслировать их в SQL,
рассказано в разделе
[«Динамические фильтры (Criteria)»](https://github.com/variasov/classic-db-tools#динамические-фильтры-criteria)
README classic-db-tools.
