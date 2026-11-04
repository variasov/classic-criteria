import pytest

from classic.criteria import And, Criteria, CriteriaNotSatisfied, Or, criteria


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


@pytest.mark.parametrize('criteria_', (
    SomeEntity.with_param(1),
    SomeEntity.with_param(1) & SomeEntity.without_param(),
    SomeEntity.with_param(1) & with_param(1),
    SomeEntity.with_param(1) & without_param(),
    SomeEntity.with_param(1) & SomeEntity.rule,
    CriteriaWithParam(1),
    CriteriaWithParam(1) & CriteriaWithoutParam(),
    CriteriaWithParam(1) & SomeEntity.with_param(1),
))
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

    assert result.nested == [c1, c2, c3, c4]
    assert left.nested == [c1, c2]
    assert right.nested == [c3, c4]


def test_or_flattens_right_operand_without_mutation():
    c1, c2, c3, c4 = (CriteriaWithParam(i) for i in range(4))
    left = Or(c1, c2)
    right = Or(c3, c4)

    result = left | right

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
