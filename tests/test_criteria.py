import copy
import dataclasses
import functools
import pickle
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar, cast
from unittest import mock

import pytest

import classic.criteria
from classic.criteria import (
    And,
    BinaryCriteria,
    CompositeCriteria,
    Criteria,
    CriteriaNotSatisfied,
    Invert,
    Or,
    ReturnsFalse,
    ReturnsTrue,
    UnaryCriteria,
    Xor,
    criteria,
)


class SomeEntity:
    def __init__(self, value: int | None) -> None:
        self.value = value

    @criteria
    def with_param(self, value: int) -> bool:
        return self.value == value

    @criteria
    def without_param(self) -> bool:
        return self.value is not None

    rule = without_param() & with_param(1)


class CriteriaWithParam(Criteria[SomeEntity]):
    def __init__(self, value: int) -> None:
        self.value = value

    def is_satisfied_by(self, candidate: SomeEntity) -> bool:
        return self.value == candidate.value


class CriteriaWithoutParam(Criteria[SomeEntity]):
    def is_satisfied_by(self, candidate: SomeEntity) -> bool:
        return candidate.value is not None


@criteria
def with_param(entity: SomeEntity, value: int) -> bool:
    return entity.value == value


@criteria
def without_param(entity: SomeEntity) -> bool:
    return entity.value is not None


@pytest.fixture
def entity() -> SomeEntity:
    return SomeEntity(1)


def test_instance(entity: SomeEntity):
    assert entity.with_param(1) is True
    assert entity.with_param.is_satisfied(1) is True
    entity.with_param.must_be_satisfied(1)

    assert entity.without_param() is True
    assert entity.without_param.is_satisfied() is True
    entity.without_param.must_be_satisfied()

    assert entity.rule() is True
    assert entity.rule.is_satisfied() is True
    entity.rule.must_be_satisfied()

    with pytest.raises(CriteriaNotSatisfied):
        entity.with_param.must_be_satisfied(2)


@pytest.mark.parametrize(
    "criteria_",
    [
        SomeEntity.with_param(1),
        SomeEntity.with_param(1) & SomeEntity.without_param(),
        SomeEntity.with_param(1) & with_param(1),
        SomeEntity.with_param(1) & without_param(),
        SomeEntity.with_param(1) & SomeEntity.rule,
        CriteriaWithParam(1),
        CriteriaWithParam(1) & CriteriaWithoutParam(),
        CriteriaWithParam(1) & SomeEntity.with_param(1),
    ],
)
def test_class_criteria(criteria_: Criteria[SomeEntity], entity: SomeEntity):
    assert criteria_(entity) is True
    assert criteria_.is_satisfied_by(entity) is True
    criteria_.must_be_satisfied_by(entity)


def test_method_without_params(entity: SomeEntity):
    assert entity.without_param() is True

    with pytest.raises(CriteriaNotSatisfied):
        SomeEntity.without_param().must_be_satisfied_by(SomeEntity(None))


def test_and_does_not_mutate_operands(entity: SomeEntity):
    first = CriteriaWithParam(1)
    second = CriteriaWithoutParam()
    third = CriteriaWithParam(2)
    a = first & second
    assert isinstance(a, And)

    b = a & third

    assert a.nested == (first, second)
    assert b is not a
    assert isinstance(b, And)
    assert b.nested == (first, second, third)
    assert a(entity) is True
    assert b(entity) is False


def test_or_does_not_mutate_operands(entity: SomeEntity):
    first = CriteriaWithParam(2)
    second = CriteriaWithParam(3)
    third = CriteriaWithParam(1)
    a = first | second
    assert isinstance(a, Or)

    b = a | third

    assert a.nested == (first, second)
    assert b is not a
    assert isinstance(b, Or)
    assert b.nested == (first, second, third)
    assert a(entity) is False
    assert b(entity) is True


def test_and_flattens_right_operand_without_mutation():
    c1, c2, c3, c4 = (CriteriaWithParam(i) for i in range(4))
    left = And(c1, c2)
    right = And(c3, c4)

    result = left & right

    assert isinstance(result, And)
    assert result.nested == (c1, c2, c3, c4)
    assert left.nested == (c1, c2)
    assert right.nested == (c3, c4)


def test_or_flattens_right_operand_without_mutation():
    c1, c2, c3, c4 = (CriteriaWithParam(i) for i in range(4))
    left = Or(c1, c2)
    right = Or(c3, c4)

    result = left | right

    assert isinstance(result, Or)
    assert result.nested == (c1, c2, c3, c4)
    assert left.nested == (c1, c2)
    assert right.nested == (c3, c4)


def test_class_attribute_criteria_is_not_changed(entity: SomeEntity):
    rule = SomeEntity.rule
    assert isinstance(rule, And)
    nested_before = rule.nested

    extended = SomeEntity.rule & CriteriaWithParam(2)

    assert SomeEntity.rule is rule
    assert rule.nested == nested_before
    assert len(rule.nested) == 2
    assert extended is not rule
    assert rule(entity) is True
    assert extended(entity) is False


@dataclass
class Period:
    start: int
    end: int


class Event:
    def __init__(self, day: int) -> None:
        self.day = day

    @criteria
    def in_period(self, period: Period) -> bool:
        assert isinstance(period, Period)
        return period.start <= self.day <= period.end


@criteria
def in_period(event: Event, period: Period) -> bool:
    assert isinstance(period, Period)
    return period.start <= event.day <= period.end


def test_dataclass_param_is_passed_as_is():
    period = Period(1, 5)
    received: list[Period] = []

    @criteria
    def spy(_event: Event, period: Period) -> bool:
        received.append(period)
        return True

    spy(period).is_satisfied_by(Event(3))
    assert received[0] is period


def test_dataclass_param_on_class_and_instance():
    event = Event(3)
    assert Event.in_period(Period(1, 5)).is_satisfied_by(event) is True
    assert Event.in_period(Period(4, 5)).is_satisfied_by(event) is False
    assert event.in_period(Period(1, 5)) is True
    assert in_period(Period(1, 5)).is_satisfied_by(event) is True


def test_list_param_is_not_copied():
    items = [1, 2]
    received: list[list[int]] = []

    @criteria
    def spy(_event: Event, items: list[int]) -> bool:
        received.append(items)
        return True

    spy(items).is_satisfied_by(Event(1))
    assert received[0] is items


def test_instance_attributes_and_class_name():
    period = Period(1, 5)
    c = in_period(period)
    assert type(c).__name__ == "in_period"
    assert cast("Any", c).period is period


class KwEntity:
    @criteria
    def kw_default(self, *, x: int = 0) -> bool:
        return x == 7

    @criteria
    def kw_required(self, a: int = 1, *, b: int) -> bool:
        return (a, b) == (1, 2)

    @criteria
    def pos_only(self, a: int, /) -> bool:
        return a == 3


def test_keyword_only_with_default():
    entity = KwEntity()
    assert KwEntity.kw_default(x=7).is_satisfied_by(entity) is True
    assert KwEntity.kw_default().is_satisfied_by(entity) is False
    assert entity.kw_default(x=7) is True
    with pytest.raises(TypeError):
        KwEntity.kw_default(7)  # pyright: ignore[reportCallIssue]


def test_keyword_only_without_default():
    entity = KwEntity()
    assert KwEntity.kw_required(b=2).is_satisfied_by(entity) is True
    assert entity.kw_required(b=2) is True
    assert entity.kw_required(5, b=2) is False
    with pytest.raises(TypeError):
        KwEntity.kw_required(1, 2)  # pyright: ignore[reportCallIssue]
    with pytest.raises(TypeError):
        KwEntity.kw_required()  # pyright: ignore[reportCallIssue]


def test_positional_only():
    entity = KwEntity()
    assert KwEntity.pos_only(3).is_satisfied_by(entity) is True
    assert entity.pos_only(4) is False


def test_var_args_are_rejected():
    def with_args(entity: Event, *args: int) -> bool:  # noqa: ARG001
        return True

    def with_kwargs(entity: Event, **kwargs: int) -> bool:  # noqa: ARG001
        return True

    with pytest.raises(TypeError, match="args"):
        criteria(with_args)

    with pytest.raises(TypeError, match="kwargs"):
        criteria(with_kwargs)


def test_not_satisfied_is_regular_exception():
    assert issubclass(CriteriaNotSatisfied, Exception)
    with pytest.raises(Exception) as info:  # noqa: PT011
        CriteriaWithParam(2).must_be_satisfied_by(SomeEntity(1))
    assert isinstance(info.value, CriteriaNotSatisfied)


def test_not_satisfied_single_criteria(entity: SomeEntity):
    crit = CriteriaWithParam(2)
    with pytest.raises(CriteriaNotSatisfied) as info:
        crit.must_be_satisfied_by(entity)
    assert info.value.criteria is crit


def test_not_satisfied_contains_only_unsatisfied_part(entity: SomeEntity):
    a = CriteriaWithParam(1)
    b = CriteriaWithParam(2)
    c = CriteriaWithParam(3)

    with pytest.raises(CriteriaNotSatisfied) as info:
        (a & b & CriteriaWithoutParam()).must_be_satisfied_by(entity)
    assert info.value.criteria is b

    with pytest.raises(CriteriaNotSatisfied) as info:
        (a & b & c).must_be_satisfied_by(entity)
    assert isinstance(info.value.criteria, And)
    assert info.value.criteria.nested == (b, c)  # pyright: ignore[reportUnknownMemberType]


def test_not_satisfied_bound(entity: SomeEntity):
    with pytest.raises(CriteriaNotSatisfied) as info:
        entity.with_param.must_be_satisfied(2)
    assert info.value.criteria == SomeEntity.with_param(2)

    with pytest.raises(CriteriaNotSatisfied) as info:
        SomeEntity(None).rule.must_be_satisfied()
    assert info.value.criteria is SomeEntity.rule


def test_not_satisfied_message(entity: SomeEntity):
    crit = CriteriaWithParam(2)
    with pytest.raises(CriteriaNotSatisfied) as info:
        crit.must_be_satisfied_by(entity)
    assert str(info.value).startswith("Criteria not satisfied: ")
    assert repr(crit) in str(info.value)


def test_not_satisfied_pickle(entity: SomeEntity):
    crit = CriteriaWithParam(2)
    with pytest.raises(CriteriaNotSatisfied) as info:
        crit.must_be_satisfied_by(entity)
    restored = pickle.loads(pickle.dumps(info.value))  # noqa: S301
    assert isinstance(restored, CriteriaNotSatisfied)
    assert isinstance(restored.criteria, CriteriaWithParam)
    assert restored.criteria.value == 2


def test_predicate_called_once_on_must_be_satisfied(entity: SomeEntity):
    calls: list[int] = []

    @criteria
    def counted(_e: SomeEntity) -> bool:
        calls.append(1)
        return False

    with pytest.raises(CriteriaNotSatisfied):
        counted().must_be_satisfied_by(entity)
    assert len(calls) == 1

    calls.clear()
    with pytest.raises(CriteriaNotSatisfied):
        (counted() & CriteriaWithParam(1)).must_be_satisfied_by(entity)
    assert len(calls) == 1


def test_repr_composite():
    assert repr(with_param(1) & with_param(2)) == (
        "And(with_param(value=1), with_param(value=2))"
    )
    assert repr(with_param(1) | without_param()) == (
        "Or(with_param(value=1), without_param())"
    )
    assert repr(And[SomeEntity]()) == "And()"


def test_repr_unary_and_binary():
    assert repr(~with_param(1)) == "Invert(with_param(value=1))"
    assert repr(with_param(1) ^ with_param(2)) == (
        "Xor(with_param(value=1), with_param(value=2))"
    )


def test_repr_nested_combination():
    a, b, c = with_param(1), with_param(2), with_param(3)
    assert repr(~(a & b) | c) == (
        "Or(Invert(And(with_param(value=1), with_param(value=2))), with_param(value=3))"
    )


def test_repr_returns_constants_and_subclass_name():
    assert repr(ReturnsTrue[SomeEntity]()) == "ReturnsTrue()"
    assert repr(ReturnsFalse[SomeEntity]()) == "ReturnsFalse()"

    class MyAnd(And[SomeEntity]):
        pass

    assert repr(MyAnd(with_param(1))) == "MyAnd(with_param(value=1))"


def test_repr_user_criteria_keeps_default():
    assert repr(CriteriaWithParam(1) & with_param(1)).startswith("And(<")
    assert repr(CriteriaWithParam(1) & with_param(1)).endswith(", with_param(value=1))")


def test_eq_composite():
    assert with_param(1) & with_param(2) == with_param(1) & with_param(2)
    assert with_param(1) | with_param(2) == with_param(1) | with_param(2)
    assert not (with_param(1) & with_param(2) != with_param(1) & with_param(2))  # noqa: SIM202


def test_not_eq_composite():
    assert with_param(1) & with_param(2) != with_param(1) & with_param(3)
    assert with_param(1) & with_param(2) != with_param(1) | with_param(2)
    assert with_param(1) & with_param(2) != with_param(1)
    assert And(with_param(1)) != Or(with_param(1))


def test_eq_composite_order_independent():
    # порядок операндов не влияет на равенство And и Or
    assert with_param(1) & with_param(2) == with_param(2) & with_param(1)
    assert with_param(1) | with_param(2) == with_param(2) | with_param(1)
    # с учётом кратности
    a, b = with_param(1), with_param(2)
    assert And(a, a, b) == And(b, a, a)
    assert And(a, a, b) != And(a, b, b)
    assert And(a, b) != And(a, a, b)
    # Xor и Invert остаются порядко-зависимыми
    assert (with_param(1) ^ with_param(2)) != (with_param(2) ^ with_param(1))
    assert ~with_param(1) != ~with_param(2)
    # нехешируемые вложенные тоже сравниваются без порядка
    unhashable = CriteriaWithParam(1)
    assert And(unhashable, b) == And(b, unhashable)


def test_composite_is_immutable():
    crit = And[SomeEntity](with_param(1), without_param())

    # кортеж нельзя изменить
    assert isinstance(crit.nested, tuple)
    with pytest.raises(TypeError, match="item assignment"):
        crit.nested[0] = with_param(2)  # type: ignore[index]

    # nested нельзя переприсвоить
    with pytest.raises(AttributeError, match="immutable"):
        crit.nested = (with_param(2),)  # type: ignore[misc]
    with pytest.raises(AttributeError, match="immutable"):
        crit.nested += (with_param(2),)  # type: ignore[operator]
    with pytest.raises(AttributeError, match="immutable"):
        crit.is_satisfied_by = with_param(2)  # type: ignore[method-assign]

    # дерево не изменилось
    assert crit.nested == (with_param(1), without_param())

    # то же для Or
    or_crit = Or[SomeEntity](with_param(1), without_param())
    with pytest.raises(AttributeError, match="immutable"):
        or_crit.nested = ()  # type: ignore[misc]


def test_predicate_criteria_fields_are_frozen():
    crit = with_param(1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        cast("Any", crit).value = 2

    composite = And[SomeEntity](with_param(1), without_param())
    leaf = cast("Any", composite.nested[0])
    with pytest.raises(dataclasses.FrozenInstanceError):
        leaf.value = 2


def test_composite_usable_as_set_and_dict_key():
    left = with_param(1) & with_param(2)
    right = with_param(2) & with_param(1)

    assert len({left, right}) == 1
    assert {left: "rule"}[right] == "rule"
    assert {right, left, with_param(1) & with_param(3)} == {
        left,
        with_param(1) & with_param(3),
    }

    # And и Or не смешиваются
    assert len({left, with_param(1) | with_param(2)}) == 2


def test_empty_composites():
    empty_and = And[SomeEntity]()
    empty_or = Or[SomeEntity]()

    assert empty_and == And[SomeEntity]()
    assert empty_or == Or[SomeEntity]()
    assert empty_and != empty_or
    assert empty_and != And[SomeEntity](with_param(1))
    assert hash(empty_and) == hash(And[SomeEntity]())
    assert len({empty_and, empty_or, And[SomeEntity]()}) == 2
    # all([]) и any([])
    entity = SomeEntity(1)
    assert empty_and.is_satisfied_by(entity) is True
    assert empty_or.is_satisfied_by(entity) is False


def test_order_independent_deep_in_tree():
    left = (with_param(1) & with_param(2)) | (with_param(3) & with_param(4))
    right = (with_param(4) & with_param(3)) | (with_param(2) & with_param(1))
    assert left == right
    assert hash(left) == hash(right)

    # And внутри Invert: порядок тоже не важен
    assert ~(with_param(1) & with_param(2)) == ~(with_param(2) & with_param(1))


def test_copy_and_deepcopy_composite():
    original = And[SomeEntity](with_param(1), with_param(2))

    shallow = copy.copy(original)
    deep = copy.deepcopy(original)

    assert shallow == original
    assert deep == original
    assert shallow is not original
    assert deep is not original
    # shallow делит листья, deep копирует
    assert shallow.nested[0] is original.nested[0]
    assert deep.nested[0] is not original.nested[0]

    # копия остаётся иммутабельной
    with pytest.raises(AttributeError, match="immutable"):
        deep.nested = ()  # type: ignore[misc]


def test_subclass_extra_attrs_and_eq_caveat():
    class WeightedAnd(And[SomeEntity]):
        def __init__(self, weight: int, *criteria_: Criteria[SomeEntity]) -> None:
            self.weight = weight  # до super(): nested ещё не установлен
            super().__init__(*criteria_)

    a = WeightedAnd(5, with_param(1), with_param(2))
    b = WeightedAnd(5, with_param(2), with_param(1))

    # доп. атрибуты работают, равенство унаследовано (только nested)
    assert a.weight == 5
    assert a == b

    # после super() присваивать нельзя
    class Late(And[SomeEntity]):
        def __init__(self, *criteria_: Criteria[SomeEntity]) -> None:
            super().__init__(*criteria_)
            with pytest.raises(AttributeError, match="immutable"):
                self.is_satisfied_by = None  # type: ignore[method-assign]

    Late(with_param(1))

    # caveat: weight не участвует в унаследованном __eq__
    assert WeightedAnd(5, with_param(1)) == WeightedAnd(6, with_param(1))


def test_eq_unary_and_binary():
    assert ~with_param(1) == ~with_param(1)
    assert ~with_param(1) != ~with_param(2)
    assert ~with_param(1) != with_param(1)
    assert (with_param(1) ^ with_param(2)) == (with_param(1) ^ with_param(2))
    assert (with_param(1) ^ with_param(2)) != (with_param(2) ^ with_param(1))
    assert (with_param(1) ^ with_param(2)) != (with_param(1) ^ with_param(3))
    assert (with_param(1) ^ with_param(2)) != (with_param(1) | with_param(2))


def test_eq_returns_constants():
    assert ReturnsTrue[SomeEntity]() == ReturnsTrue[SomeEntity]()
    assert ReturnsFalse[SomeEntity]() == ReturnsFalse[SomeEntity]()
    assert ReturnsTrue[SomeEntity]() != ReturnsFalse[SomeEntity]()


def test_eq_with_non_criteria():
    for crit in (
        with_param(1) & with_param(2),
        ~with_param(1),
        with_param(1) ^ with_param(2),
        ReturnsTrue[SomeEntity](),
    ):
        assert crit != 1
        assert not crit == "text"  # noqa: SIM201
        assert crit != None  # noqa: E711


def test_eq_subclass_is_not_equal():
    class MyAnd(And[SomeEntity]):
        pass

    assert MyAnd(with_param(1)) != And(with_param(1))


def test_hash_of_user_criteria():
    a = CriteriaWithParam(1)
    b = CriteriaWithParam(2)

    assert hash(a & b) == hash(a & b)
    assert hash(~a) == hash(~a)
    assert hash(a ^ b) == hash(a ^ b)
    assert hash(ReturnsTrue[SomeEntity]()) == hash(ReturnsTrue[SomeEntity]())
    assert hash(ReturnsTrue[SomeEntity]()) != hash(ReturnsFalse[SomeEntity]())
    assert {a & b, a & b, b & a} == {a & b, b & a}
    assert len({a & b, a & b, a | b}) == 2


def test_hash_with_criteria_decorator():
    # frozen dataclass: хешируем, если хешируемы значения полей
    assert hash(with_param(1) & with_param(2)) == hash(with_param(2) & with_param(1))
    assert hash(~with_param(1)) == hash(~with_param(1))
    assert hash(with_param(1) ^ with_param(2)) == hash(with_param(1) ^ with_param(2))
    assert len({with_param(1) & with_param(2), with_param(2) & with_param(1)}) == 1


def test_hash_unhashable_field_raises():
    @criteria
    def with_list(_entity: SomeEntity, items: list[int]) -> bool:
        return bool(items)  # pragma: no cover

    with pytest.raises(TypeError):
        hash(with_list([1, 2]))
    with pytest.raises(TypeError):
        hash(with_list([1, 2]) & with_param(1))


def test_mock_assert_called_with_composite_criteria():
    repo = mock.Mock()

    repo.find(with_param(1) & without_param())

    repo.find.assert_called_once_with(with_param(1) & without_param())
    with pytest.raises(AssertionError):
        repo.find.assert_called_once_with(with_param(2) & without_param())


def test_exports():
    for name in (
        "ReturnsTrue",
        "ReturnsFalse",
        "CompositeCriteria",
        "UnaryCriteria",
        "BinaryCriteria",
    ):
        assert name in classic.criteria.__all__
    assert list(classic.criteria.__all__) == sorted(
        classic.criteria.__all__,
        key=lambda n: (n[0].islower(), n),
    )
    assert issubclass(And, CompositeCriteria)
    assert issubclass(Invert, UnaryCriteria)
    assert issubclass(Xor, BinaryCriteria)


def test_returns_constants_hash_and_type_equality():
    assert hash(ReturnsFalse[SomeEntity]()) == hash(ReturnsFalse[SomeEntity]())

    class MyTrue(ReturnsTrue[SomeEntity]):
        pass

    assert MyTrue() != ReturnsTrue[SomeEntity]()


def test_criteria_rejects_non_callable():
    with pytest.raises(TypeError, match="callable"):
        criteria(1)  # type: ignore[call-overload]


def reserved_predicate(_entity: SomeEntity, predicate: int) -> bool:  # noqa: ARG001
    return True


def reserved_positional(_entity: SomeEntity, _positional: int) -> bool:
    return True


def reserved_keyword(_entity: SomeEntity, *, _keyword: int) -> bool:
    return True


@pytest.mark.parametrize(
    ("fn", "name"),
    [
        (reserved_predicate, "predicate"),
        (reserved_positional, "_positional"),
        (reserved_keyword, "_keyword"),
    ],
)
def test_reserved_parameter_names(
    fn: Callable[..., bool],
    name: str,
):
    with pytest.raises(TypeError, match=name):
        criteria(fn)


def test_and_is_satisfied_by(entity: SomeEntity):
    assert And(CriteriaWithParam(1), CriteriaWithoutParam())(entity) is True
    assert And(CriteriaWithParam(2), CriteriaWithoutParam())(entity) is False


_T = TypeVar("_T")


def _roundtrip(obj: _T) -> _T:
    restored = cast("_T", pickle.loads(pickle.dumps(obj)))  # noqa: S301
    assert restored == obj
    return restored


def test_pickle_module_function_criteria():
    original = with_param(2)
    restored = _roundtrip(original)
    assert type(restored) is type(original)
    assert cast("Any", restored).value == 2
    assert type(original).__module__ == __name__


def test_pickle_method_criteria():
    original = SomeEntity.with_param(2)
    restored = _roundtrip(original)
    assert type(restored) is type(original)
    assert restored.is_satisfied_by(SomeEntity(2)) is True


def test_pickle_keyword_only_criteria():
    original = KwEntity.kw_required(b=2)
    restored = _roundtrip(original)
    assert type(restored) is type(original)
    assert restored.is_satisfied_by(KwEntity()) is True
    restored = _roundtrip(KwEntity.kw_required(5, b=3))
    assert (cast("Any", restored).a, cast("Any", restored).b) == (5, 3)


def test_pickle_composite_criteria():
    original = with_param(1) & ~without_param()
    restored = _roundtrip(original)
    assert isinstance(restored, And)
    assert type(restored.nested[0]) is type(with_param(1))


def test_not_satisfied_pickle_decorated(entity: SomeEntity):
    crit = with_param(2)
    with pytest.raises(CriteriaNotSatisfied) as info:
        crit.must_be_satisfied_by(entity)
    restored = pickle.loads(pickle.dumps(info.value))  # noqa: S301
    assert isinstance(restored, CriteriaNotSatisfied)
    assert type(restored.criteria) is type(crit)
    assert restored.criteria == crit


def test_deepcopy_decorated_criteria():
    original = with_param(2)
    copied = copy.deepcopy(original)
    assert copied == original
    assert copied is not original
    assert type(copied) is type(original)


def test_pickle_local_criteria_raises():
    @criteria
    def local(_entity: SomeEntity) -> bool:
        return True

    with pytest.raises(pickle.PicklingError, match="local"):
        pickle.dumps(local())


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (1, 1, False),
        (1, 2, True),
        (2, 1, True),
        (2, 2, False),
    ],
)
def test_xor_truth_table(entity: SomeEntity, left: int, right: int, expected: object):
    # entity.value == 1: CriteriaWithParam(1) is True, CriteriaWithParam(2) is False
    crit = CriteriaWithParam(left) ^ CriteriaWithParam(right)
    assert isinstance(crit, Xor)
    assert crit.is_satisfied_by(entity) is expected
    assert crit(entity) is expected
    assert crit.is_satisfied_by(SomeEntity(2)) is (left != right)


def _and(
    left: Criteria[SomeEntity],
    right: Criteria[SomeEntity],
) -> Criteria[SomeEntity]:
    return left & right


def test_returns_constants_results():
    assert ReturnsTrue[SomeEntity]().is_satisfied_by(SomeEntity(1)) is True
    assert ReturnsFalse[SomeEntity]().is_satisfied_by(SomeEntity(1)) is False


def test_reduce_with_returns_true_as_initial_value(entity: SomeEntity):
    empty: list[Criteria[SomeEntity]] = []
    parts: list[Criteria[SomeEntity]] = [CriteriaWithParam(1), CriteriaWithParam(2)]

    union_empty = functools.reduce(_and, empty, ReturnsTrue[SomeEntity]())
    assert union_empty.is_satisfied_by(entity) is True

    all_of = functools.reduce(_and, parts, ReturnsTrue[SomeEntity]())
    assert all_of.is_satisfied_by(entity) is False
    assert all_of.is_satisfied_by(SomeEntity(2)) is False
    only_first = functools.reduce(_and, parts[:1], ReturnsTrue[SomeEntity]())
    assert only_first.is_satisfied_by(entity) is True
    assert only_first.is_satisfied_by(SomeEntity(2)) is False


def test_bound_keyword_only_kwargs_are_passed():
    entity = KwEntity()

    entity.kw_required.must_be_satisfied(b=2)
    assert entity.kw_required.is_satisfied(b=2) is True
    assert entity.kw_required(b=2) is True

    with pytest.raises(CriteriaNotSatisfied):
        entity.kw_required.must_be_satisfied(b=3)
    assert entity.kw_required.is_satisfied(b=3) is False
    assert entity.kw_required(b=3) is False


def test_not_satisfied_args_contain_criteria(entity: SomeEntity):
    crit = CriteriaWithParam(2)
    with pytest.raises(CriteriaNotSatisfied) as info:
        crit.must_be_satisfied_by(entity)
    assert info.value.args == (crit,)
    assert CriteriaNotSatisfied(crit).args == (crit,)


def test_hash_differs_for_different_node_types():
    a = CriteriaWithParam(1)
    b = CriteriaWithParam(2)

    class MyInvert(Invert[SomeEntity]):
        pass

    class MyXor(Xor[SomeEntity]):
        pass

    class MyAnd(And[SomeEntity]):
        pass

    assert hash(a & b) != hash(a | b)
    assert hash(And(a, b)) != hash(MyAnd(a, b))
    assert hash(~a) != hash(MyInvert(a))
    assert hash(a ^ b) != hash(MyXor(a, b))


def _fields(crit: object) -> dict[str, dataclasses.Field[Any]]:
    return {f.name: f for f in dataclasses.fields(cast("Any", type(crit)))}


def test_make_predicate_criteria_field_types():
    def typed_and_untyped(
        _e: SomeEntity,
        a,  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        b: int,
        *,
        c,  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        d: str = "x",
    ) -> bool:
        return bool((a, b, c, d))  # pyright: ignore[reportUnknownArgumentType]

    fields = _fields(criteria(typed_and_untyped)(1, 2, c=3))  # pyright: ignore[reportUnknownArgumentType]

    assert fields["a"].type is Any
    assert fields["b"].type is int
    assert fields["c"].type is Any
    assert fields["d"].type is str


def test_make_predicate_criteria_kw_only_flags():
    def mixed(_e: SomeEntity, a: int, b: int = 0, *, c: int, d: int = 0) -> bool:
        return bool(a + b + c + d)

    fields = _fields(criteria(mixed)(1, c=3))

    assert fields["a"].kw_only is False
    assert fields["b"].kw_only is False
    assert fields["c"].kw_only is True
    assert fields["d"].kw_only is True


def test_make_predicate_criteria_kw_only_call_forms():
    def kw(entity: SomeEntity, a: int = 5, *, b: int, c: int = 10) -> bool:
        return entity.value == a + b + c

    factory = criteria(kw)
    crit = factory(b=2)
    assert cast("Any", crit).a == 5
    assert cast("Any", crit).b == 2
    assert cast("Any", crit).c == 10
    assert crit.is_satisfied_by(SomeEntity(17)) is True
    assert crit.is_satisfied_by(SomeEntity(18)) is False

    assert factory(1, b=2, c=3).is_satisfied_by(SomeEntity(6)) is True
    assert factory(1, c=3, b=2).is_satisfied_by(SomeEntity(7)) is False
    with pytest.raises(TypeError):
        factory(1, 2)  # pyright: ignore[reportCallIssue]
    with pytest.raises(TypeError):
        factory()  # pyright: ignore[reportCallIssue]
    with pytest.raises(TypeError):
        factory(b=2, a=1, d=0)  # pyright: ignore[reportCallIssue]


def test_make_predicate_criteria_passes_kw_only_by_name():
    received: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def spy(_e: SomeEntity, a: int, *, b: int, c: int = 0) -> bool:
        received.append(((a,), {"b": b, "c": c}))
        return b > a

    assert spy(SomeEntity(1), 1, b=2) is True  # direct call keeps function intact
    received.clear()

    crit = criteria(spy)(1, b=2, c=3)
    assert crit.is_satisfied_by(SomeEntity(1)) is True
    assert received == [((1,), {"b": 2, "c": 3})]
    assert criteria(spy)(3, b=2).is_satisfied_by(SomeEntity(1)) is False


def test_make_predicate_criteria_defaults():
    def with_defaults(entity: SomeEntity, a: int = 4, *, b: int = 6) -> bool:
        return entity.value == a * b

    factory = criteria(with_defaults)
    crit = factory()
    fields = _fields(crit)

    assert fields["a"].default == 4
    assert fields["b"].default == 6
    assert crit.is_satisfied_by(SomeEntity(24)) is True
    assert crit.is_satisfied_by(SomeEntity(1)) is False
    assert factory(2).is_satisfied_by(SomeEntity(12)) is True
    assert factory(b=2).is_satisfied_by(SomeEntity(8)) is True
    assert fields["a"].default is not dataclasses.MISSING


def test_make_predicate_criteria_required_fields_have_no_default():
    def required(_e: SomeEntity, a: int, *, b: int) -> bool:  # noqa: ARG001
        return True

    fields = _fields(criteria(required)(1, b=2))

    assert fields["a"].default is dataclasses.MISSING
    assert fields["b"].default is dataclasses.MISSING


def test_make_predicate_criteria_module_and_name():
    def local_rule(_e: SomeEntity) -> bool:
        return True

    crit = criteria(local_rule)()

    assert type(crit).__module__ == local_rule.__module__ == __name__
    assert type(crit).__name__ == local_rule.__name__ == "local_rule"
    assert str(crit) == "local_rule"


def test_make_predicate_criteria_positional_only():
    def pos_only(_e: SomeEntity, a: int, /) -> bool:
        return a == 3

    factory = criteria(pos_only)
    assert factory(3).is_satisfied_by(SomeEntity(1)) is True
    assert factory(4).is_satisfied_by(SomeEntity(1)) is False
