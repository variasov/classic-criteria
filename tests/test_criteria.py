import pytest

from classic.criteria import Criteria, criteria, CriteriaNotSatisfied
from classic.criteria import DomainObject


class SomeEntity:

    def __init__(self, value):
        self.value = value

    @criteria
    def with_param(self, value):
        return self.value == value

    @criteria
    def without_param(self):
        return self.value is not None

    rule = without_param() & with_param(1)


class CriteriaWithParam(Criteria[SomeEntity]):

    def __init__(self, value):
        self.value = value

    def is_satisfied_by(self, candidate: DomainObject) -> bool:
        return self.value == candidate.value


class CriteriaWithoutParam(Criteria[SomeEntity]):

    def is_satisfied_by(self, candidate: DomainObject) -> bool:
        return candidate.value is not None


@criteria
def with_param(entity, value):
    return entity.value == value


@criteria
def without_param(entity):
    return entity.value is not None


@pytest.fixture
def entity():
    return SomeEntity(1)


def test_instance(entity: SomeEntity):
    assert entity.with_param(1) is True
    assert entity.with_param.is_satisfied(1) is True
    assert entity.with_param.must_be_satisfied(1) is None

    assert entity.without_param() is True
    assert entity.without_param.is_satisfied() is True
    assert entity.without_param.must_be_satisfied() is None

    assert entity.rule() is True
    assert entity.rule.is_satisfied() is True
    assert entity.rule.must_be_satisfied() is None

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
