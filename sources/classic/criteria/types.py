from typing import TypeVar, ParamSpec, Callable


DomainObject = TypeVar('DomainObject')
Params = ParamSpec('Params')
Predicate = Callable[[DomainObject, Params], bool]
