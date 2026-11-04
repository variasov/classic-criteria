import inspect

from dataclasses import make_dataclass, field
from typing import Callable, ClassVar, Concatenate, ParamSpec, Any, Generic, TypeVar, Union, cast, overload

from .criteria import Criteria


Object = TypeVar('Object')
Params = ParamSpec('Params')
Predicate = Callable[Concatenate[Object, Params], bool]


class PredicateCriteria(Criteria[Object], Generic[Object, Params]):
    predicate: Predicate[Object, Params]
    _positional: ClassVar[tuple[str, ...]]
    _keyword: ClassVar[tuple[str, ...]]

    def __init__(self, *args, **kwargs):
        raise NotImplementedError

    def is_satisfied_by(self, candidate: Object) -> bool:
        predicate = cast(Any, self.predicate)
        return predicate(
            candidate,
            *[getattr(self, name) for name in self._positional],
            **{name: getattr(self, name) for name in self._keyword},
        )

    def __str__(self) -> str:
        return self.predicate.__name__


class BoundUnformedCriteria(Generic[Object, Params]):
    instance: Object
    criteria_cls: type[PredicateCriteria[Object, Params]]

    def __init__(
        self, instance: Object,
        criteria_cls: type[PredicateCriteria[Object, Params]],
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


class CriteriaDescriptor(Generic[Object, Params]):
    criteria_cls: type[PredicateCriteria[Object, Params]]

    def __init__(
        self, criteria_cls: type[PredicateCriteria[Object, Params]],
    ) -> None:
        self.criteria_cls = criteria_cls

    def __call__(
        self, *args: Params.args, **kwargs: Params.kwargs,
    ) -> Criteria[Object]:
        return self.criteria_cls(*args, **kwargs)

    @overload
    def __get__(
        self, instance: Object,
        owner: type[Object],
    ) -> BoundUnformedCriteria[Object, Params]:
        ...

    @overload
    def __get__(
        self, instance: None,
        owner: type[Object],
    ) -> 'CriteriaDescriptor[Object, Params]':
        ...

    def __get__(
        self, instance: Object | None,
        owner: type[Object],
    ) -> Union[
         BoundUnformedCriteria[Object, Params],
         'CriteriaDescriptor[Object, Params]',
    ]:
        if instance is not None:
            return BoundUnformedCriteria(instance, self.criteria_cls)
        return self


def make_predicate_criteria(
    fn: Predicate[Object, Params],
) -> type[PredicateCriteria[Object, Params]]:
    annotations: list[tuple[Any, ...]] = []
    positional: list[str] = []
    keyword: list[str] = []
    signature = inspect.signature(fn)
    parameters = list(signature.parameters.items())
    for name, param in parameters[1:]:
        if param.annotation is param.empty:
            annotation = Any
        else:
            annotation = param.annotation

        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            raise TypeError(
                f'Критерий {fn.__name__!r}: параметр {name!r} '
                f'({param.kind.description}) не поддерживается, '
                f'так как не может быть полем критерия'
            )

        kw_only = param.kind is param.KEYWORD_ONLY
        (keyword if kw_only else positional).append(name)
        if param.default is not param.empty:
            annotations.append((
                name, annotation,
                field(default=param.default, kw_only=kw_only),
            ))
        elif kw_only:
            annotations.append((name, annotation, field(kw_only=True)))
        else:
            annotations.append((name, annotation))

    new_cls = make_dataclass(
        fn.__name__,
        annotations,
        bases=(PredicateCriteria,),
        namespace={
            'predicate': staticmethod(fn),
            '_positional': tuple(positional),
            '_keyword': tuple(keyword),
        },
    )
    return cast(
        type[PredicateCriteria[Object, Params]],
        new_cls,
    )


def criteria(
    fn: Predicate[Object, Params],
) -> CriteriaDescriptor[Object, Params]:
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

    return CriteriaDescriptor[Object, Params](
        make_predicate_criteria(fn)
    )
