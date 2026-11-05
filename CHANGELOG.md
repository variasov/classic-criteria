# Changelog

## v1.0.0

### Несовместимые изменения

- **`CriteriaNotSatisfied` унаследован от `Exception`** вместо `BaseException`: теперь его
  ловит `except Exception`. Конструктор требует невыполненный критерий, он доступен
  в атрибуте `criteria`; для `And` это только невыполненная часть (`remainder_unsatisfied_by`).
  Сообщение: `Criteria not satisfied: <repr критерия>`.
- **Удалён extra `db-tools`**: он ставил устаревший `classic-db-tools~=1.0`.
  Связку ставит `classic-db-tools[criteria]`.
- **`py.typed` перенесён** из корня namespace `classic/` в `classic/criteria/`.
- **`@criteria` проверяет сигнатуру**: `*args`, `**kwargs` и имена параметров
  `predicate`, `_positional`, `_keyword` дают `TypeError`; `criteria` от невызываемого
  объекта тоже даёт `TypeError` (раньше `assert`, который исчезал при `-O`).
- **Составные критерии сравниваются по структуре**: `And`, `Or`, `Xor`, `Invert`,
  `ReturnsTrue`, `ReturnsFalse` равны при совпадении типа и вложенных критериев;
  для `And` и `Or` порядок операндов не важен (сравнение как мультимножество,
  с учётом повторов), для `Xor` и `Invert` — важен. Хеш согласован с равенством
  и, как у `frozenset`, бросает `TypeError`, если вложенный критерий нехешируемый.
- **Критерии immutable**: составные критерии хранят операнды в кортеже `nested`
  (раньше список) и не дают переприсвоить атрибуты после создания (`AttributeError`),
  критерии из `@criteria` — frozen dataclass (раньше обычный): изменение поля
  даёт `FrozenInstanceError`. Критерии из `@criteria` хешируемы, если хешируемы
  значения полей.
- Удалён `PredicateCriteria.__init__`, бросавший `NotImplementedError`.

### Исправлено

- **`&` и `|` больше не изменяют левый операнд**: возвращается новый `And`/`Or`.
  Раньше `a & b` дописывал `b` в `a`, что портило критерии, сохранённые в переменных
  и атрибутах класса.
- **Параметры предиката передаются как есть**: значения-dataclass больше не превращаются
  в `tuple`, списки и словари не копируются (`astuple` заменён на `getattr` по полям).
- **Keyword-only параметры** в функциях с `@criteria`, в том числе без значения
  по умолчанию после параметра со значением.
- **`pickle` и `copy.deepcopy`** для критериев из `@criteria` на функциях и методах
  уровня модуля; для локальных функций `PicklingError` бросается сразу при сериализации.

### Добавлено

- `__repr__` у составных критериев в виде вызова конструктора:
  `And(Open(), Invert(Obsolete(days_to_work=3)))`.
- Экспорт `ReturnsTrue`, `ReturnsFalse`, `CompositeCriteria`, `UnaryCriteria`,
  `BinaryCriteria` из `classic.criteria`.
- Докстринги публичного API с примерами (проверяются как doctest).
- README: исправлены примеры, описаны `must_be_satisfied*`, `remainder_unsatisfied_by`,
  `^`, `~`, параметры критериев, ссылка на трансляцию в SQL в classic-db-tools.

### Инфраструктура

- Исходники в `src/`, lint и тесты: ruff (`ALL`), `ruff format`, pyright strict, vulture,
  mutmut. CI проверяет pull request и выкладку на PyPI, тесты на Python 3.10–3.14.
