"""Исключения библиотеки."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .criteria import Criteria


class CriteriaNotSatisfied(Exception):
    """Критерий не выполнен.

    Атрибут `criteria` содержит невыполненную часть критерия.
    Проверяемый кандидат в исключении не хранится.
    """

    criteria: Criteria[Any]

    def __init__(self, criteria: Criteria[Any]) -> None:
        """Создаёт исключение с невыполненной частью критерия."""
        super().__init__(criteria)
        self.criteria = criteria

    def __str__(self) -> str:
        """Возвращает сообщение с repr невыполненного критерия."""
        return f"Criteria not satisfied: {self.criteria!r}"
