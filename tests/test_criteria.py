import copy
import pickle
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar, cast
from unittest import mock

import classic.criteria
import pytest
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

    assert a.nested == [first, second]
    assert b is not a
    assert isinstance(b, And)
    assert b.nested == [first, second, third]
    assert a(entity) is True
    assert b(entity) is False


def test_or_does_not_mutate_operands(entity: SomeEntity):
    first = CriteriaWithParam(2)
    second = CriteriaWithParam(3)
    third = CriteriaWithParam(1)
    a = first | second
    assert isinstance(a, Or)

    b = a | third

    assert a.nested == [first, second]
    assert b is not a
    assert isinstance(b, Or)
    assert b.nested == [first, second, third]
    assert a(entity) is False
    assert b(entity) is True


def test_and_flattens_right_operand_without_mutation():
    c1, c2, c3, c4 = (CriteriaWithParam(i) for i in range(4))
    left = And(c1, c2)
    right = And(c3, c4)

    result = left & right

    assert isinstance(result, And)
    assert result.nested == [c1, c2, c3, c4]
    assert left.nested == [c1, c2]
    assert right.nested == [c3, c4]


def test_or_flattens_right_operand_without_mutation():
    c1, c2, c3, c4 = (CriteriaWithParam(i) for i in range(4))
    left = Or(c1, c2)
    right = Or(c3, c4)

    result = left | right

    assert isinstance(result, Or)
    assert result.nested == [c1, c2, c3, c4]
    assert left.nested == [c1, c2]
    assert right.nested == [c3, c4]


def test_class_attribute_criteria_is_not_changed(entity: SomeEntity):
    rule = SomeEntity.rule
    assert isinstance(rule, And)
    nested_before = list(rule.nested)

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
    assert info.value.criteria.nested == [b, c]  # pyright: ignore[reportUnknownMemberType]


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
    assert with_param(1) & with_param(2) != with_param(2) & with_param(1)
    assert with_param(1) & with_param(2) != with_param(1) | with_param(2)
    assert with_param(1) & with_param(2) != with_param(1) & with_param(3)
    assert with_param(1) & with_param(2) != with_param(1)
    assert And(with_param(1)) != Or(with_param(1))


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


def test_hash_with_criteria_decorator_is_unhashable():
    with pytest.raises(TypeError):
        hash(with_param(1) & with_param(2))
    with pytest.raises(TypeError):
        hash(~with_param(1))
    with pytest.raises(TypeError):
        hash(with_param(1) ^ with_param(2))


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
