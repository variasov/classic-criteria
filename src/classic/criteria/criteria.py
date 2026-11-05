"""Базовый класс критериев, составные критерии и их привязка к объектам."""

from collections import Counter
from typing import Generic, Optional, Protocol, TypeVar, Union, cast, overload

from .errors import CriteriaNotSatisfied

Object = TypeVar("Object")
CriteriaNodeObj = TypeVar(
    "CriteriaNodeObj",
    contravariant=True,
)


class CriteriaNode(Protocol[CriteriaNodeObj]):
    """Протокол узла дерева критериев: всё, что умеет проверять кандидата."""

    def is_satisfied_by(self, candidate: CriteriaNodeObj) -> bool:
        """Возвращает True, если кандидат удовлетворяет критерию."""
        ...

    def must_be_satisfied_by(self, candidate: CriteriaNodeObj) -> None:
        """Бросает `CriteriaNotSatisfied`, если кандидат не удовлетворяет."""
        ...


class Criteria(Generic[Object]):
    """Базовый класс критериев (спецификаций).

    Критерий описывает условие на объект. Им можно проверить объект
    в памяти (`is_satisfied_by`) или оттранслировать его в запрос, например
    в SQL через classic-db-tools: там макрос ищется по имени класса критерия
    (для критериев из `@criteria` - по имени функции).

    Чтобы определить свой критерий, наследуйтесь от `Criteria` и переопределите
    `is_satisfied_by`. Критерии комбинируются операторами: `&` даёт `And`,
    `|` - `Or`, `^` - `Xor`, `~` - `Invert`. Операнды при этом не изменяются,
    возвращается новый критерий.

    Критерий можно вызвать как функцию (`criteria(candidate)`), что удобно
    для `filter`. Если критерий объявлен атрибутом класса, то на экземпляре
    он превращается в `BoundFormedCriteria` (`entity.rule()`,
    `entity.rule.is_satisfied()`, `entity.rule.must_be_satisfied()`),
    а на самом классе остаётся самим критерием.

    Составные критерии (`And`, `Or`, `Xor`, `Invert`) сравниваются
    и хешируются структурно. Для `And` и `Or` порядок операндов
    не важен (`Open() & Obsolete(3) == Obsolete(3) & Open()`),
    для `Xor` и `Invert` - важен. Сам `Criteria` сравнивается
    по идентичности, если подкласс не задаёт `__eq__`
    (например, через `@dataclass`).

    Критерии immutable: составные критерии хранят операнды в кортеже
    `nested` и не дают переприсвоить атрибуты после создания, критерии
    из `@criteria` - frozen dataclass. Операторы `&`, `|`, `^`, `~`
    строят новое дерево, не трогая операнды. Хеш согласован с равенством
    и требует хешируемости вложенных критериев (например, `@dataclass`
    без `frozen=True` нехешируем).

    Example:
        >>> from dataclasses import dataclass
        >>> @dataclass
        ... class Task:
        ...     number: int
        ...     days: int
        >>> @dataclass
        ... class Longer(Criteria[Task]):
        ...     limit: int
        ...     def is_satisfied_by(self, task: Task) -> bool:
        ...         return task.days > self.limit
        >>> @dataclass
        ... class Numbered(Criteria[Task]):
        ...     number: int
        ...     def is_satisfied_by(self, task: Task) -> bool:
        ...         return task.number == self.number
        >>> tasks = [Task(1, 5), Task(2, 1), Task(3, 9)]
        >>> rule = Longer(3) & ~Numbered(1)
        >>> rule
        And(Longer(limit=3), Invert(Numbered(number=1)))
        >>> rule.is_satisfied_by(tasks[2])
        True
        >>> rule(tasks[0])
        False
        >>> list(filter(rule, tasks))
        [Task(number=3, days=9)]
        >>> rule.must_be_satisfied_by(tasks[1])  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        CriteriaNotSatisfied: Criteria not satisfied: Longer(limit=3)
        >>> rule.remainder_unsatisfied_by(tasks[1])
        Longer(limit=3)

        Критерий как атрибут класса:

        >>> @dataclass
        ... class Job:
        ...     days: int
        ...     is_long = Longer(3)
        >>> Job(5).is_long()
        True
        >>> Job.is_long
        Longer(limit=3)

    """

    def __and__(
        self,
        other: "Criteria[Object]",
    ) -> "Criteria[Object]":
        """Возвращает `And(self, other)`."""
        return And(self, other)

    def __or__(
        self,
        other: "Criteria[Object]",
    ) -> "Criteria[Object]":
        """Возвращает `Or(self, other)`."""
        return Or(self, other)

    def __xor__(
        self,
        other: "Criteria[Object]",
    ) -> "Criteria[Object]":
        """Возвращает `Xor(self, other)`."""
        return Xor(self, other)

    def __invert__(
        self: "Criteria[Object]",
    ) -> "Criteria[Object]":
        """Возвращает `Invert(self)`."""
        return Invert(self)

    def is_satisfied_by(self, candidate: Object) -> bool:
        """Проверяет, удовлетворяет ли кандидат критерию.

        Подклассы должны переопределить метод.

        Args:
            candidate: Проверяемый объект.

        Returns:
            True, если кандидат удовлетворяет критерию.

        Raises:
            NotImplementedError: Метод не переопределён.

        """
        raise NotImplementedError

    def __call__(self, candidate: Object) -> bool:
        """Алиас `is_satisfied_by`, удобен для `filter`."""
        return self.is_satisfied_by(candidate)

    def must_be_satisfied_by(self, candidate: Object) -> None:
        """Проверяет кандидата и бросает исключение, если критерий не выполнен.

        Args:
            candidate: Проверяемый объект.

        Raises:
            CriteriaNotSatisfied: Критерий не выполнен; в `criteria` лежит
                невыполненная часть (`remainder_unsatisfied_by`).

        """
        remainder = self.remainder_unsatisfied_by(candidate)
        if remainder is not None:
            raise CriteriaNotSatisfied(remainder)

    def remainder_unsatisfied_by(
        self, candidate: Object
    ) -> Optional["Criteria[Object]"]:
        """Возвращает невыполненную часть критерия.

        Args:
            candidate: Проверяемый объект.

        Returns:
            None, если кандидат удовлетворяет критерию, иначе та часть
            критерия, которая не выполнена (по умолчанию - сам критерий).

        """
        if self.is_satisfied_by(candidate):
            return None
        return self

    @overload
    def __get__(
        self,
        instance: Object,
        _owner: type[Object],
    ) -> "BoundFormedCriteria[Object]": ...

    @overload
    def __get__(
        self,
        instance: None,
        _owner: type[Object],
    ) -> "Criteria[Object]": ...

    def __get__(
        self,
        instance: Object | None,
        _owner: type[Object],
    ) -> Union[
        "BoundFormedCriteria[Object]",
        "Criteria[Object]",
    ]:
        """Дескриптор: на экземпляре даёт `BoundFormedCriteria`, на классе - себя."""
        if instance is not None:
            return BoundFormedCriteria(instance, self)
        return self


class BoundFormedCriteria(Generic[Object]):
    """Готовый критерий, привязанный к экземпляру, которому он принадлежит.

    Возникает при обращении к критерию-атрибуту класса через экземпляр.
    """

    instance: Object
    _criteria: object

    def __init__(
        self,
        instance: Object,
        criteria: Criteria[Object],
    ) -> None:
        """Привязывает критерий к экземпляру."""
        self.instance = instance
        self._criteria = criteria

    @property
    def criteria(self) -> CriteriaNode[Object]:
        """Привязанный критерий."""
        return cast("CriteriaNode[Object]", self._criteria)  # pragma: no mutate

    def __call__(self) -> bool:
        """Алиас `is_satisfied`."""
        return self.is_satisfied()

    def is_satisfied(self) -> bool:
        """Проверяет экземпляр критерием."""
        return self.criteria.is_satisfied_by(self.instance)

    def must_be_satisfied(self) -> None:
        """Проверяет экземпляр критерием.

        Raises:
            CriteriaNotSatisfied: Критерий не выполнен.

        """
        self.criteria.must_be_satisfied_by(self.instance)


def _same_multiset(
    left: tuple[Criteria[Object], ...],
    right: tuple[Criteria[Object], ...],
) -> bool:
    """Сравнивает вложенные критерии как мультимножество (без порядка).

    Вложенные критерии могут быть нехешируемыми, поэтому используется
    жадное сравнение с попарным поглощением, а не Counter.
    """
    if len(left) != len(right):
        return False
    rest = list(right)
    for criteria_ in left:
        matched = next(
            (i for i, other in enumerate(rest) if criteria_ == other),
            None,
        )
        if matched is None:
            return False
        rest.pop(matched)
    return True


class CompositeCriteria(Criteria[Object]):
    """Критерий с неограниченным количеством вложенных критериев.

    Вложенные критерии лежат в кортеже `nested`; его читает обход дерева,
    например traverse из classic-db-tools. Критерий неизменяем:
    `nested` нельзя переприсвоить после создания, а сам кортеж нельзя
    изменить. Равенство и хеш структурные, порядок вложенных критериев
    не важен (сравнение как мультимножество, с учётом повторов); хеш
    считается как у frozenset, поэтому при нехешируемом вложенном
    критерии (например, из `@dataclass` без `frozen=True`) бросается
    `TypeError`.

    Подклассам: свои атрибуты присваивайте до `super().__init__(...)` —
    после инициализации любые присваивания дают `AttributeError`.
    Унаследованный `__eq__` сравнивает только `nested`: если у подкласса
    есть дополнительные поля, переопределите и `__eq__`, и `__hash__`.
    """

    nested: tuple[Criteria[Object], ...]

    def __init__(self, *criteria: Criteria[Object]) -> None:
        """Создаёт критерий из вложенных критериев."""
        self.nested = tuple(criteria)

    def __setattr__(self, name: str, value: object) -> None:
        """Запрещает менять атрибуты после создания: критерий неизменяем."""
        if "nested" in self.__dict__:
            raise AttributeError(
                f"{type(self).__name__} is immutable, can't set {name!r}",
            )
        super().__setattr__(name, value)

    def __repr__(self) -> str:
        """Возвращает вид `And(<вложенный>, ...)`."""
        nested = ", ".join(repr(criteria) for criteria in self.nested)
        return f"{type(self).__name__}({nested})"

    def __eq__(self, other: object) -> bool:
        """Равенство мультимножеств: тот же тип и равные вложенные в любом порядке."""
        if type(self) is not type(other):
            return NotImplemented
        other_ = cast("CompositeCriteria[Object]", other)  # pragma: no mutate
        return _same_multiset(self.nested, other_.nested)

    def __hash__(self) -> int:
        """Хеш по типу и мультимножеству вложенных критериев."""
        return hash((type(self), frozenset(Counter(self.nested).items())))

    def is_satisfied_by(self, candidate: Object) -> bool:
        """Должен быть переопределён в подклассе."""
        raise NotImplementedError


class And(CompositeCriteria[Object]):
    """Критерий, проверяющий, что все вложенные критерии удовлетворяются.

    Результат оператора `&`. При `&` с другим `And` вложенные критерии
    сплющиваются в один `And`. Порядок операндов сохраняется в `nested`
    (слева направо), но на равенство и хеш не влияет. Обычно вручную
    не создаётся.

    Example:
        >>> a, b, c = ReturnsTrue(), ReturnsFalse(), ReturnsTrue()
        >>> (a & b) & c
        And(ReturnsTrue(), ReturnsFalse(), ReturnsTrue())
        >>> a & b == b & a  # порядок не важен
        True
        >>> (a & b).remainder_unsatisfied_by(None)
        ReturnsFalse()
        >>> (b & b & a).remainder_unsatisfied_by(None)
        And(ReturnsFalse(), ReturnsFalse())

    """

    def __and__(self, other: Criteria[Object]) -> Criteria[Object]:
        """Возвращает `And` с вложенными критериями обоих операндов."""
        other_nested: tuple[Criteria[Object], ...] = (
            other.nested if isinstance(other, And) else (other,)
        )
        return And(*self.nested, *other_nested)

    def is_satisfied_by(self, candidate: Object) -> bool:
        """Истина, если выполнены все вложенные критерии."""
        return all(criteria.is_satisfied_by(candidate) for criteria in self.nested)

    def remainder_unsatisfied_by(
        self,
        candidate: Object,
    ) -> Criteria[Object] | None:
        """Возвращает только невыполненные вложенные критерии.

        Args:
            candidate: Проверяемый объект.

        Returns:
            None, если выполнены все; единственный невыполненный критерий;
            иначе `And` из невыполненных.

        """
        non_satisfied = tuple(
            criteria
            for criteria in self.nested
            if not criteria.is_satisfied_by(candidate)
        )
        if not non_satisfied:
            return None
        if len(non_satisfied) == 1:
            return non_satisfied[0]
        if len(non_satisfied) == len(self.nested):
            return self
        return And(*non_satisfied)


class Or(CompositeCriteria[Object]):
    """Критерий, проверяющий, что выполнен хотя бы один вложенный критерий.

    Результат оператора `|`. При `|` с другим `Or` вложенные критерии
    сплющиваются в один `Or`. Порядок операндов сохраняется в `nested`
    (слева направо), но на равенство и хеш не влияет. Если не выполнены
    все ветки, `remainder_unsatisfied_by` возвращает весь `Or`. Обычно
    вручную не создаётся.

    Example:
        >>> (ReturnsFalse() | ReturnsFalse()) | ReturnsTrue()
        Or(ReturnsFalse(), ReturnsFalse(), ReturnsTrue())
        >>> ReturnsFalse() | ReturnsTrue() == ReturnsTrue() | ReturnsFalse()
        True
        >>> (ReturnsFalse() | ReturnsFalse()).remainder_unsatisfied_by(None)
        Or(ReturnsFalse(), ReturnsFalse())

    """

    def __or__(self, other: Criteria[Object]) -> Criteria[Object]:
        """Возвращает `Or` с вложенными критериями обоих операндов."""
        other_nested: tuple[Criteria[Object], ...] = (
            other.nested if isinstance(other, Or) else (other,)
        )
        return Or(*self.nested, *other_nested)

    def is_satisfied_by(self, candidate: Object) -> bool:
        """Истина, если выполнен хотя бы один вложенный критерий."""
        return any(criteria.is_satisfied_by(candidate) for criteria in self.nested)


class UnaryCriteria(Criteria[Object]):
    """Критерий с одним вложенным критерием, доступным как `nested`.

    Равенство и хеш структурные.
    """

    _nested: object

    def __init__(self, criteria: Criteria[Object]) -> None:
        """Создаёт критерий над вложенным критерием."""
        self._nested = criteria

    def __repr__(self) -> str:
        """Возвращает вид `Invert(<вложенный>)`."""
        return f"{type(self).__name__}({self._nested!r})"

    def __eq__(self, other: object) -> bool:
        """Структурное равенство: тот же тип и равный вложенный критерий."""
        if type(self) is not type(other):
            return NotImplemented
        other_ = cast("UnaryCriteria[Object]", other)  # pragma: no mutate
        return self._nested == other_._nested

    def __hash__(self) -> int:
        """Хеш по типу и вложенному критерию."""
        return hash((type(self), self._nested))

    @property
    def nested(self) -> CriteriaNode[Object]:
        """Вложенный критерий."""
        return cast("CriteriaNode[Object]", self._nested)  # pragma: no mutate


class Invert(UnaryCriteria[Object]):
    """Критерий, проверяющий, что вложенный критерий не выполняется.

    Результат оператора `~`. Обычно вручную не создаётся.

    Example:
        >>> ~ReturnsTrue()
        Invert(ReturnsTrue())
        >>> (~ReturnsTrue()).is_satisfied_by(None)
        False

    """

    def is_satisfied_by(self, candidate: Object) -> bool:
        """Истина, если вложенный критерий не выполнен."""
        return not self.nested.is_satisfied_by(candidate)


class BinaryCriteria(Criteria[Object]):
    """Критерий с двумя вложенными критериями `left` и `right`.

    Нужен для операций, где важен порядок операндов. Равенство и хеш
    структурные: `Xor(a, b) != Xor(b, a)`.
    """

    _left: object
    _right: object

    def __init__(
        self,
        left: Criteria[Object],
        right: Criteria[Object],
    ) -> None:
        """Создаёт критерий из левого и правого операндов."""
        self._left = left
        self._right = right

    def __repr__(self) -> str:
        """Возвращает вид `Xor(<левый>, <правый>)`."""
        return f"{type(self).__name__}({self._left!r}, {self._right!r})"

    def __eq__(self, other: object) -> bool:
        """Структурное равенство: тот же тип и равные операнды по порядку."""
        if type(self) is not type(other):
            return NotImplemented
        other_ = cast("BinaryCriteria[Object]", other)  # pragma: no mutate
        return self._left == other_._left and self._right == other_._right

    def __hash__(self) -> int:
        """Хеш по типу и операндам."""
        return hash((type(self), self._left, self._right))

    @property
    def left(self) -> CriteriaNode[Object]:
        """Левый операнд."""
        return cast("CriteriaNode[Object]", self._left)  # pragma: no mutate

    @property
    def right(self) -> CriteriaNode[Object]:
        """Правый операнд."""
        return cast("CriteriaNode[Object]", self._right)  # pragma: no mutate

    def is_satisfied_by(self, candidate: Object) -> bool:
        """Должен быть переопределён в подклассе."""
        raise NotImplementedError


class Xor(BinaryCriteria[Object]):
    """Критерий, проверяющий, что выполнен ровно один из двух критериев.

    Результат оператора `^`. Обычно вручную не создаётся.

    Example:
        >>> (ReturnsTrue() ^ ReturnsFalse()).is_satisfied_by(None)
        True
        >>> (ReturnsTrue() ^ ReturnsTrue()).is_satisfied_by(None)
        False

    """

    def is_satisfied_by(self, candidate: Object) -> bool:
        """Истина, если выполнен ровно один из операндов."""
        return self.left.is_satisfied_by(candidate) ^ self.right.is_satisfied_by(
            candidate
        )


class _ConstantCriteria(Criteria[Object]):
    """Общая часть критериев-констант: repr, равенство и хеш по точному типу."""

    def __repr__(self) -> str:
        """Возвращает вид `ReturnsTrue()`."""
        return f"{type(self).__name__}()"

    def __eq__(self, other: object) -> bool:
        """Равны все экземпляры одного и того же типа."""
        if type(self) is not type(other):
            return NotImplemented
        return True

    def __hash__(self) -> int:
        """Хеш по типу."""
        return hash(type(self))


class ReturnsTrue(_ConstantCriteria[Object]):
    """Критерий, которому удовлетворяет любой объект.

    Нейтральный элемент для `&`; удобен как начальное значение при сборке
    фильтра.

    Example:
        >>> import functools, operator
        >>> parts = [ReturnsTrue(), ReturnsFalse()]
        >>> all_of = functools.reduce(operator.and_, parts, ReturnsTrue())
        >>> all_of.is_satisfied_by(1)
        False

    """

    def is_satisfied_by(self, candidate: Object) -> bool:  # noqa: ARG002
        """Всегда True."""
        return True


class ReturnsFalse(_ConstantCriteria[Object]):
    """Критерий, которому не удовлетворяет ни один объект.

    Нейтральный элемент для `|`.
    """

    def is_satisfied_by(self, candidate: Object) -> bool:  # noqa: ARG002
        """Всегда False."""
        return False
