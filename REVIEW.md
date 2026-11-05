# Ревью classic-criteria 0.2.1

Ревью от 2026-11-04 по ветке `main` (`e48a768`). Код совпадает с версией 0.2.1 на PyPI.
Проверка: чтение кода, пробы на Python 3.14, pyright strict (0 ошибок на пакете и на типичном использовании).

## Замечания к коду

1. **`&` и `|` изменяют левый операнд.** [высокая]
   - Где: `criteria.py:187-192` (`And.__and__`), `:225-230` (`Or.__or__`) — `self.nested += ...; return self`.
   - Последствие (проверено): после `b = a & Task.gt(10)` меняется и `a` (`len(a.nested) == 3`, результат `a(t)` другой).
     Составной критерий, сохранённый в переменной или атрибуте класса, «портится» при повторном использовании.

2. **Параметры предиката собираются через `astuple`.** [высокая]
   - Где: `predicate_wrapping.py:22` — `predicate(candidate, *astuple(self))`. `astuple` рекурсивно разворачивает dataclass-поля.
   - Последствие (проверено): критерий `in_period(self, p: Period)` получает `tuple` вместо `Period` → `AttributeError`.

3. **Keyword-only параметры предиката не работают.** [средняя]
   - Где: тот же вызов — все поля передаются позиционно.
   - Последствие (проверено): `def kw(self, *, x: int = 0)` → `TypeError: takes 1 positional argument but 2 were given`.

4. **`CriteriaNotSatisfied` унаследован от `BaseException`.** [средняя]
   - Где: `errors.py:3`.
   - Последствие: не ловится `except Exception` — ни обработчиками ошибок HTTP, ни `run_job` планировщика, ни большинством кода.
     В исключении не сказано, какой критерий не выполнен.

5. **Устаревший extra.** [средняя]
   - Где: `pyproject.toml` — `db-tools = ["classic-db-tools~=1.0", ...]`: `pip install classic-criteria[db-tools]` ставит db-tools 1.x
     (актуальная — 3.3). При этом сам classic-db-tools объявляет extra `criteria` в обратную сторону.

6. **Нет `__repr__` и `__eq__` у составных критериев.** [низкая]
   - `repr(Task.gt(1) & Task.gt(2))` → `<...And object at 0x...>`; два одинаковых `And` не равны — трудно отлаживать и сравнивать в тестах.

7. **`py.typed` в корне namespace.** [низкая]
   - Файл ставится как `classic/py.typed`, а не `classic/criteria/py.typed`. Он «помечает» типизированными все пакеты `classic.*`
     и конфликтует с другими пакетами namespace.

8. **Мелочи.** [низкая]
   - `Or.remainder_unsatisfied_by` не переопределён — возвращает весь `Or` (по смыслу допустимо, но не описано).
   - `ReturnsTrue`/`ReturnsFalse`, `CompositeCriteria`, `UnaryCriteria`, `BinaryCriteria` не экспортированы.
   - `PredicateCriteria.__init__` бросает `NotImplementedError` — сбивает с толку (реальный `__init__` даёт `make_dataclass`).
   - `assert callable(fn)` в `criteria` исчезает при `-O`.
   - Строка `return all((            criteria...` (`criteria.py:195`) — форматирование.

9. **Тесты.** [средняя]
   - 3 теста. Нет тестов на `|`, `^`, `~`, `remainder_unsatisfied_by`, мутацию операндов, параметры-объекты, keyword-only, функции-критерии.

## Замечания к документации

- Пример `Obsolete`: `candidate.created_at - candidate.finished_at` — даты вычитаются в обратном порядке.
- `filtered_tasks = filter(some_crit, tasks)  # True` — `filter` возвращает итератор, не `True`.
- `some_task.obsolete()` и `Task.obsolete()` вызываются без обязательного аргумента `days_to_work`.
- «Булева алгебра используется с `and`, 'or' и `not`» — для инстансов; для критериев на классах — `&`, `|`, `~`, `^`; это не разведено.
- Doctest-примеры в docstring (`criteria.py:32-72`, `predicate_wrapping.py:130-162`) нерабочие: `Task(1)` без полей, неверный формат.
- Не описаны: `must_be_satisfied`/`must_be_satisfied_by`, `remainder_unsatisfied_by`, `~`, `^`, `CriteriaNotSatisfied`,
  `is_satisfied` у bound-критериев.
- Раздел «Выборки в БД» отсылает в README classic-db-tools, где пример тоже нерабочий (`Eq`, `Gt`); не сказано,
  что макрос ищется по имени класса критерия (для `@criteria` — по имени функции).

## План задач

| # | Задача | Объём | Статус |
|---|---|---|---|
| 1 | Операторы `&`, `|` возвращают новый объект, без мутации | S | сделано (`5af2d47`) |
| 2 | Параметры предиката через `getattr` по полям вместо `astuple` | S | сделано (`ee3d051`) |
| 3 | Поддержка keyword-only параметров | S | сделано (`ee3d051`) |
| 4 | `CriteriaNotSatisfied(Exception)` с указанием критерия | S | сделано (`60be3e5`) |
| 5 | `__repr__` и `__eq__` для составных критериев | S | сделано (`a64addf`), плюс `__hash__` |
| 6 | Исправить extra `db-tools`, перенести `py.typed` в `classic/criteria/` | S | сделано (`95b6b49`): extra удалён |
| 7 | Тесты на алгебру, мутацию, параметры | M | частично: регрессионные тесты к шагам 1-6; дополнить по итогам mutmut |
| 8 | README и docstring: исправить примеры, описать API | S | docstring сделаны (`33ec8de`), README впереди |
| 9 | Мелочи из п. 8 замечаний: экспорт, `__init__` с `NotImplementedError`, `assert`, форматирование; pickle критериев из `@criteria`; зарезервированные имена параметров | S | сделано (`fde1ca1`) |
| 10 | Линтеры: ruff ALL, ruff format, pyright strict, vulture | M | сделано (`8b7290c`, `27968f8`) |
| 11 | CI: `checks.yml`, `publish.yml` с `needs: checks` | S | |
| 12 | Каталог `src/`, mutmut, тесты по выжившим мутантам | M | |
| 13 | Версия 1.0.0 и CHANGELOG | S | |

### Решения (2026-11-04)

- Ветка `v1`, следующая версия 1.0.0: меняются поведение и API.
- Extra `db-tools` удалён: связка ставится через `classic-db-tools[criteria]`.
- `CriteriaNotSatisfied` наследуется от `Exception`, атрибут `criteria` содержит невыполненную часть (`remainder_unsatisfied_by`), кандидат не хранится.
- Составные критерии: структурные `__eq__` и `__hash__`, хеш как у tuple (`TypeError` при нехешируемом вложенном критерии).
- Экспортируются `ReturnsTrue`, `ReturnsFalse`, `CompositeCriteria`, `UnaryCriteria`, `BinaryCriteria`.
- Имена классов, `nested`, `left`/`right` и поля критериев из `@criteria` не менялись: совместимость с `traverse` из classic-db-tools.
- Стиль кавычек: двойные, как в эталоне. `N818` и `PLC0105` в ignore. Сообщения исключений на английском, докстринги и комментарии на русском.
- В classic-db-tools после выпуска 1.0 нужно расширить диапазон `classic-criteria~=0.1` в extra `criteria`.
