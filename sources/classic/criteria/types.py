from typing import Callable, Concatenate, ParamSpec, TypeVar


DomainObject = TypeVar('DomainObject')
Params = ParamSpec('Params')
Predicate = Callable[Concatenate[DomainObject, Params], bool]
