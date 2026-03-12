# Classic Criteria

Основывается на книге Эрика Эванса 
"Domain Driven Design: tackling complexity in the heart of software".

Предоставляет базовый примитив для описания языка 
предметной области - Criteria (Критерий).

Критерий нужен для описания выборки объектов. Есть два пути использования - 
через определение класса, и через декоратор.

## Установка
```shell
pip install classic-criteria
```

## Критерии-классы

Представим себе, что у нас класс,
олицетворяющий понятие из предметной области - задачу:

Также, представим себе, что в предметной области задача называется открытой,
если нет времени завершения и просроченной, если больше работа не завершена 
больше какого-то количества дней.

Также представим, что нам необходимо получать из некоторого хранилища задачи,
соответствующие этим критериям.

Задачу можно описать обычным датаклассом, а состояния задач - критериями.
У критериев можно определить метод is_satisfied_by, которые будут определять,
подходит ли объект под этот критерий или нет:

```python
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from classic.criteria import Criteria


@dataclass
class Task:
    created_at: datetime
    finished_at: Optional[datetime] = None


@dataclass
class Open(Criteria[Task]):
    """Критерий для открытых задач"""

    def is_satisfied_by(self, candidate: Task) -> bool:
        return candidate.finished_at is None

    
@dataclass
class Obsolete(Criteria[Task]):
    """Критерий для просроченных задач"""
    days_to_work: int

    def is_satisfied_by(self, candidate: Task) -> bool:
        return (
            candidate.finished_at is not None and
            (candidate.created_at - candidate.finished_at).days > self.days_to_work
        )
```

Затем описанные критерии можно использовать в разных сценариях.

### Прямое использование
```python
from datetime import datetime

some_task = Task(created_at=datetime(2025, 1, 1))
is_open = Open()

is_open.is_satisfied_by(some_task)
# True
```

### Булева алгебра

Критерии можно связать логическими условиями:
```python
from datetime import datetime

some_task = Task(created_at=datetime(2025, 1, 1))
some_crit = Open() | Obsolete(3)

some_crit.is_satisfied_by(some_task)
# True
```

### Фильтрация
У критерия метод `__call__` определен как алиас для `is_satisfied_by`.
Это придает лаконичности при использовании критерия для фильтрации списка:
```python
from datetime import datetime

tasks = [
    Task(created_at=datetime(2025, 1, 1)),
    Task(created_at=datetime(2025, 1, 1),
         finished_at=datetime(2025, 1, 5)),
    Task(created_at=datetime(2025, 1, 1),
         finished_at=datetime(2025, 1, 2)),
] 
some_crit = Open() | Obsolete(3)

filtered_tasks = filter(some_crit, tasks)
# True
```

## Критерии-методы
Критерии можно определить как методы у класса (например, у самой сущности),
используя декоратор `criteria`:
```python
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from classic.criteria import criteria


@dataclass
class Task:
    created_at: datetime
    finished_at: Optional[datetime] = None
    
    @criteria
    def open(self) -> bool:
        return self.finished_at is None
    
    @criteria
    def obsolete(self, days_to_work: int) -> bool:
        return (
            self.finished_at is not None and
            (self.created_at - self.finished_at).days > days_to_work
        )
```

У таких критериев есть две группы сценариев использования,
использование на инстансах, и использование на классах.

Далее будут примеры с инстансами, аналогичные примерам выше.

### Прямое использование
```python
from datetime import datetime

some_task = Task(created_at=datetime(2025, 1, 1))

some_task.open()
# True
```

### Булева алгебра:
```python
from datetime import datetime

some_task = Task(created_at=datetime(2025, 1, 1))

some_task.open() or some_task.obsolete()
# True
```

Обратите внимание, что булева алгебра используется с `and`, 'or' и `not`.

## Критерии-методы с классами

Критериев-методы можно использовать без инстансов, обращаясь к классам.
При таком применении не произойдет проверки критерия. Полученный объект-критерий
предоставляет собой отложенное условие:
```python
from datetime import datetime

is_open = Task.open()  # Отложенная проверка

some_task = Task(created_at=datetime(2025, 1, 1))

is_open.is_satisfied_by(some_task)
# True
```

### Фильтрация
Отложенные критерии также можно использовать для фильтрации списка:
```python
from datetime import datetime

some_crit = Task.open() | Task.obsolete()

tasks = [
    Task(created_at=datetime(2025, 1, 1)),
    Task(created_at=datetime(2025, 1, 1),
         finished_at=datetime(2025, 1, 5)),
    Task(created_at=datetime(2025, 1, 1),
         finished_at=datetime(2025, 1, 2)),
]

filtered_tasks = filter(some_crit, tasks)
# True
```

### Критерии-функции
Также можно использовать декоратор `criteria` на обычных функциях.
Все свойства таких критериев абсолютно аналогичны варианту с методами:

```python
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from classic.criteria import criteria


@dataclass
class Task:
    created_at: datetime
    finished_at: Optional[datetime] = None
    

@criteria
def task_open(task: Task) -> bool:
    return task.finished_at is None


@criteria
def task_is_obsolete(task: Task, days_to_work: int) -> bool:
    return (
        task.finished_at is not None and
        (task.created_at - task.finished_at).days > days_to_work
    )
```

### Выборки в БД
Также, критерии можно использовать для построения запросов к БД.

Пример рендера и обхода дерева можно увидеть в [classic-db-tools](https://github.com/variasov/classic-db-tools).
