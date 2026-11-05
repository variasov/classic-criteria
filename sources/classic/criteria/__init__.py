"""Спецификации (критерии) в духе DDD.

Критерий описывает условие на объект: им можно проверить объект
(`is_satisfied_by`, `must_be_satisfied_by`), скомбинировать с другими
операторами `&`, `|`, `^`, `~` и оттранслировать в запрос, например в SQL
через classic-db-tools (макрос ищется по имени класса критерия, для `@criteria`
- по имени функции).

Example:
    >>> from classic.criteria import criteria
    >>> @criteria
    ... def positive(number):
    ...     return number > 0
    >>> @criteria
    ... def even(number):
    ...     return number % 2 == 0
    >>> list(filter(positive() & ~even(), [-1, 1, 2, 3]))
    [1, 3]

"""

from .criteria import (
    And,
    BinaryCriteria,
    CompositeCriteria,
    Criteria,
    CriteriaNode,
    Invert,
    Or,
    ReturnsFalse,
    ReturnsTrue,
    UnaryCriteria,
    Xor,
)
from .errors import CriteriaNotSatisfied
from .predicate_wrapping import Predicate, PredicateCriteria, criteria

__all__ = (
    "And",
    "BinaryCriteria",
    "CompositeCriteria",
    "Criteria",
    "CriteriaNode",
    "CriteriaNotSatisfied",
    "Invert",
    "Or",
    "Predicate",
    "PredicateCriteria",
    "ReturnsFalse",
    "ReturnsTrue",
    "UnaryCriteria",
    "Xor",
    "criteria",
)
