import inspect

from dataclasses import make_dataclass, field, astuple
from typing import Any, Generic, Union, cast, overload

from .criteria import Criteria, DomainObject
from .types import Params, Predicate


class PredicateCriteria(Criteria[DomainObject], Generic[DomainObject, Params]):
    predicate: Predicate[DomainObject, Params]

    def __init__(self, *args, **kwargs):
        raise NotImplementedError

    def is_satisfied_by(self, candidate: DomainObject) -> bool:
        predicate = cast(Any, self.predicate)
        return predicate(candidate, *astuple(cast(Any, self)))

    def __str__(self) -> str:
        return self.predicate.__name__


class BoundUnformedCriteria(Generic[DomainObject, Params]):
    instance: DomainObject
    criteria_cls: type[PredicateCriteria[DomainObject, Params]]

    def __init__(
        self, instance: DomainObject,
        criteria_cls: type[PredicateCriteria[DomainObject, Params]],
    ) -> None:
        self.instance = instance
        self.criteria_cls = criteria_cls

    def __call__(self, *args: Params.args, **kwargs: Params.kwargs) -> bool:
        return self.is_satisfied(*args, **kwargs)

    def is_satisfied(self, *args: Params.args, **kwargs: Params.kwargs) -> bool:
        return self.criteria_cls(
            *args, **kwargs,
        ).is_satisfied_by(self.instance)

    def must_be_satisfied(
        self, *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> None:
        self.criteria_cls(
            *args, **kwargs,
        ).must_be_satisfied_by(self.instance)


class CriteriaDescriptor(Generic[DomainObject, Params]):
    criteria_cls: type[PredicateCriteria[DomainObject, Params]]

    def __init__(
        self, criteria_cls: type[PredicateCriteria[DomainObject, Params]],
    ) -> None:
        self.criteria_cls = criteria_cls

    def __call__(
        self, *args: Params.args, **kwargs: Params.kwargs,
    ) -> Criteria[DomainObject]:
        return self.criteria_cls(*args, **kwargs)

    @overload
    def __get__(
        self, instance: DomainObject,
        owner: type[DomainObject],
    ) -> BoundUnformedCriteria[DomainObject, Params]:
        ...

    @overload
    def __get__(
        self, instance: None,
        owner: type[DomainObject],
    ) -> 'CriteriaDescriptor[DomainObject, Params]':
        ...

    def __get__(
        self, instance: DomainObject | None,
        owner: type[DomainObject],
    ) -> Union[
         BoundUnformedCriteria[DomainObject, Params],
         'CriteriaDescriptor[DomainObject, Params]',
    ]:
        if instance is not None:
            return BoundUnformedCriteria(instance, self.criteria_cls)
        return self


def make_predicate_criteria(
    fn: Predicate[DomainObject, Params],
) -> type[PredicateCriteria[DomainObject, Params]]:
    annotations: list[tuple[Any, ...]] = []
    signature = inspect.signature(fn)
    parameters = list(signature.parameters.items())
    for name, param in parameters[1:]:
        if param.annotation is param.empty:
            annotation = Any
        else:
            annotation = param.annotation

        if param.default is not param.empty:
            annotations.append((name, annotation, field(default=param.default)))
        else:
            annotations.append((name, annotation))

    new_cls = make_dataclass(
        fn.__name__,
        annotations,
        bases=(PredicateCriteria,),
        namespace={'predicate': staticmethod(fn)},
    )
    return cast(
        type[PredicateCriteria[DomainObject, Params]],
        new_cls,
    )


def criteria(
    fn: Predicate[DomainObject, Params],
) -> CriteriaDescriptor[DomainObject, Params]:
    """
    Декоратор для удобного описания правила через функции:

    Пример:
    >>> from dataclasses import dataclass
    ... from classic.criteria import criteria
    ...
    ... @dataclass
    ... class Book:
    ...     author: str
    ...
    ... @criteria
    ... def can_edit_book(book, user):
    ...     return book.author == user
    ...
    ... some_book = Book('Ivan')
    ... can_edit_book('Ivan').is_satisfied_by(some_book)
    True

    Также можно оборачивать методы в классе:
    >>> from dataclasses import dataclass
    ... from classic.criteria import criteria
    ...
    ... @dataclass
    ... class Book:
    ...     author: str
    ...
    ...     @criteria
    ...     def can_edit(self, user):
    ...         return self.author == user
    ...
    ... some_book = Book('Ivan')
    ... Book.can_edit('Ivan').is_satisfied_by(some_book)
    True
    >>> some_book.can_edit('Ivan')
    True
    """
    assert callable(fn)

    return CriteriaDescriptor[DomainObject, Params](
        make_predicate_criteria(fn)
    )
