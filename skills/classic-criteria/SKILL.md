---
name: classic-criteria
description: Справка по API библиотеки classic-criteria 1.x (classic.criteria) - декоратор @criteria, две формы вызова (на инстансе и ленивая на классе), Criteria[T], комбинации &, |, ~, is_satisfied_by, сравнение и repr, типизация. Загружать перед написанием кода с classic.criteria. Как критерии применяются в архитектуре - в python-classic-domain, трансляция в SQL - в classic-db-tools.
license: MIT
---

# classic-criteria 1.x: API

Только API, сверенный с версией 1.0. Правила применения (когда какая форма, имена) - в `python-classic-domain`.

## Объявление
```python
from dataclasses import dataclass
from datetime import date

from classic.criteria import Criteria, criteria


@dataclass
class Loan:
    due: date
    returned_at: date | None = None

    @criteria
    def overdue(self, on: date) -> bool:
        return self.returned_at is None and self.due < on

    @criteria
    def returned(self) -> bool:
        return self.returned_at is not None
```
- Первый параметр - кандидат (`self`), остальные - параметры критерия; из них строится frozen-датакласс критерия. Поддерживаются дефолты, keyword-only и positional-only. Нельзя `*args`, `**kwargs` и имена `predicate`, `_positional`, `_keyword` - `TypeError`.
- Сгенерированный класс критерия называется как функция (`overdue`). По этому имени `traverse` в classic-db-tools ищет SQL-макрос.

## Две формы вызова
| Вызов | Результат |
|---|---|
| `loan.overdue(on=today)` | `bool` - проверка сразу |
| `Loan.overdue(on=today)` | `Criteria[Loan]` - ленивый объект, ничего не проверяет |

Ленивый объект:
- `crit.is_satisfied_by(loan) -> bool`; `crit(loan)` - то же (удобно для `filter(crit, loans)`);
- параметры доступны атрибутами: `Loan.overdue(on=today).on`; изменить нельзя (`FrozenInstanceError`);
- `crit.must_be_satisfied_by(loan)` бросает `CriteriaNotSatisfied` (наследник `Exception`, атрибут `.criteria` - невыполненная часть); `crit.remainder_unsatisfied_by(loan)` - то же без исключения.

На инстансе также есть `loan.overdue.is_satisfied(on=today)` и `loan.overdue.must_be_satisfied(on=today)`.

## Комбинации
```python
crit = Loan.overdue(on=today) & ~Loan.returned()
crit = Reader.membership_active(on=today) | Reader.vip()
```
- `&` → `And`, `|` → `Or`, `~` → `Invert`, `^` → `Xor`; результат - снова `Criteria[T]`, операнды не меняются.
- Узлы: `And.nested` / `Or.nested` - кортеж вложенных, `Invert.nested` - один вложенный.
- Комбинации работают только для ленивой формы. На инстансе результат - `bool`, комбинируй через `and`/`or`/`not`.
- `ReturnsTrue()` - нейтральный старт для сборки фильтра по частям: `crit = ReturnsTrue(); crit &= ...`.
- Составной критерий можно объявить атрибутом класса: `stale = overdue(3) & ~returned()` внутри тела класса; на инстансе `loan.stale()` - `bool`.

## Сравнение и repr
- Критерии сравниваются по структуре: `Loan.overdue(on=d) == Loan.overdue(on=d)`; для `And`/`Or` порядок операндов не важен. Это удобно в тестах: `assert repo.find_called_with == Loan.overdue(on=today) & ~Loan.returned()`.
- `repr`: `And(overdue(on=datetime.date(...)), Invert(returned()))`.
- Критерии из `@criteria` хешируемы, если хешируемы их параметры.

## Типизация
- В сигнатурах портов - `Criteria[Loan]`: `def find(self, criteria: Criteria[Loan]) -> list[Loan]: ...`.
- In-memory реализация: `[l for l in items if criteria.is_satisfied_by(l)]`.

## Критерии-классы (альтернатива декоратору)
```python
@dataclass(frozen=True)
class Overdue(Criteria[Loan]):
    on: date

    def is_satisfied_by(self, candidate: Loan) -> bool:
        return candidate.returned_at is None and candidate.due < self.on
```
Используются, когда критерий не принадлежит одному классу. В домене демо - декоратор на методах агрегата.
