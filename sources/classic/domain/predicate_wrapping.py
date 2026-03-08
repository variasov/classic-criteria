from typing import Callable, cast, ParamSpec, Generic, overload

from .criteria import Criteria, DomainObject


Params = ParamSpec('Params')
Predicate = Callable[[DomainObject, Params], bool]


class PredicateCriteria(Criteria[DomainObject], Generic[DomainObject, Params]):
    predicate: Predicate[DomainObject, Params]
    args: Params.args
    kwargs: Params.kwargs

    def __init__(self, *args: Params.args, **kwargs: Params.kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    def is_satisfied_by(self, candidate: DomainObject) -> bool:
        return self.predicate(candidate, *self.args, **self.kwargs)

    def __str_(self) -> str:
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
    ):
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
    ) -> type[PredicateCriteria[DomainObject, Params]]:
        ...

    def __get__(
        self, instance: DomainObject | None,
        owner: type[DomainObject] | None,
    ):
        if instance:
            return BoundUnformedCriteria(instance, self.criteria_cls)
        else:
            return self.criteria_cls


def make_predicate_criteria(
    fn: Predicate[DomainObject, Params],
) -> type[PredicateCriteria[DomainObject, Params]]:

    new_cls = type(
        fn.__name__,
        (PredicateCriteria,),
        {'predicate': staticmethod(fn)},
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
    ... from classic.domain import criteria
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
    ... from classic.domain import criteria
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
