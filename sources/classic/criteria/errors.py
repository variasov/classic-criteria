from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .criteria import Criteria


class CriteriaNotSatisfied(Exception):
    """Критерий не выполнен; в `criteria` лежит невыполненный критерий."""

    criteria: Criteria[Any]

    def __init__(self, criteria: Criteria[Any]) -> None:
        super().__init__(criteria)
        self.criteria = criteria

    def __str__(self) -> str:
        return f"Критерий не выполнен: {self.criteria!r}"
