"""Декоратор `@criteria` и вспомогательные классы для критериев-функций."""

import importlib
import inspect
import pickle
from collections.abc import Callable
from dataclasses import field, make_dataclass
from typing import (
    Any,
    ClassVar,
    Concatenate,
    Generic,
    ParamSpec,
    TypeVar,
    Union,
    cast,
    overload,
)

from .criteria import Criteria

Object = TypeVar("Object")
Params = ParamSpec("Params")
Predicate = Callable[Concatenate[Object, Params], bool]

# Служебные атрибуты PredicateCriteria, не могут быть именами параметров.
_RESERVED_NAMES = ("predicate", "_positional", "_keyword")


class PredicateCriteria(Criteria[Object], Generic[Object, Params]):
    """Базовый класс критериев, порождаемых `@criteria` из функции.

    Класс-наследник создаётся как dataclass: параметры функции после
    кандидата становятся полями, сама функция лежит в `predicate`.
    """

    predicate: Predicate[Object, Params]
    _positional: ClassVar[tuple[str, ...]]
    _keyword: ClassVar[tuple[str, ...]]

    def is_satisfied_by(self, candidate: Object) -> bool:
        """Вызывает функцию-предикат с кандидатом и параметрами критерия."""
        predicate = cast("Any", self.predicate)  # pragma: no mutate
        return predicate(
            candidate,
            *[getattr(self, name) for name in self._positional],
            **{name: getattr(self, name) for name in self._keyword},
        )

    def __str__(self) -> str:
        """Возвращает имя функции-предиката."""
        return self.predicate.__name__

    def __reduce__(self) -> tuple[Any, ...]:
        """Поддержка pickle: критерий восстанавливается по пути к функции."""
        module = self.predicate.__module__
        qualname = self.predicate.__qualname__
        descriptor = _find_descriptor(module, qualname)
        if descriptor is None or descriptor.criteria_cls is not type(self):
            raise pickle.PicklingError(
                f"Can't pickle criteria {qualname!r}: {module}.{qualname} "
                f"is not the criteria descriptor of this class "
                f"(local function or rebound name)"
            )
        return (
            _restore_predicate_criteria,
            (
                module,
                qualname,
                tuple(getattr(self, name) for name in self._positional),
                {name: getattr(self, name) for name in self._keyword},
            ),
        )


class BoundUnformedCriteria(Generic[Object, Params]):
    """Критерий-функция, привязанный к экземпляру, но ещё без параметров.

    Вызов с параметрами сразу проверяет экземпляр и возвращает bool.
    """

    instance: Object
    criteria_cls: type[PredicateCriteria[Object, Params]]

    def __init__(
        self,
        instance: Object,
        criteria_cls: type[PredicateCriteria[Object, Params]],
    ) -> None:
        """Привязывает класс критерия к экземпляру."""
        self.instance = instance
        self.criteria_cls = criteria_cls

    def __call__(self, *args: Params.args, **kwargs: Params.kwargs) -> bool:
        """Алиас `is_satisfied`."""
        return self.is_satisfied(*args, **kwargs)

    def is_satisfied(self, *args: Params.args, **kwargs: Params.kwargs) -> bool:
        """Создаёт критерий из параметров и проверяет им экземпляр."""
        return self.criteria_cls(
            *args,
            **kwargs,
        ).is_satisfied_by(self.instance)

    def must_be_satisfied(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> None:
        """Создаёт критерий из параметров и проверяет им экземпляр.

        Raises:
            CriteriaNotSatisfied: Критерий не выполнен.

        """
        self.criteria_cls(
            *args,
            **kwargs,
        ).must_be_satisfied_by(self.instance)


class CriteriaDescriptor(Generic[Object, Params]):
    """Результат `@criteria`: создаёт критерий, а на экземпляре проверяет сразу.

    На классе или модуле вызов возвращает критерий (отложенная проверка),
    на экземпляре - `BoundUnformedCriteria`.
    """

    criteria_cls: type[PredicateCriteria[Object, Params]]

    def __init__(
        self,
        criteria_cls: type[PredicateCriteria[Object, Params]],
    ) -> None:
        """Запоминает класс критерия."""
        self.criteria_cls = criteria_cls

    def __call__(
        self,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> Criteria[Object]:
        """Создаёт критерий с заданными параметрами."""
        return self.criteria_cls(*args, **kwargs)

    @overload
    def __get__(
        self,
        instance: Object,
        _owner: type[Object],
    ) -> BoundUnformedCriteria[Object, Params]: ...

    @overload
    def __get__(
        self,
        instance: None,
        _owner: type[Object],
    ) -> "CriteriaDescriptor[Object, Params]": ...

    def __get__(
        self,
        instance: Object | None,
        _owner: type[Object],
    ) -> Union[
        BoundUnformedCriteria[Object, Params],
        "CriteriaDescriptor[Object, Params]",
    ]:
        """Дескриптор: на экземпляре даёт `BoundUnformedCriteria`, на классе - себя."""
        if instance is not None:
            return BoundUnformedCriteria(instance, self.criteria_cls)
        return self


def _find_descriptor(
    module: str,
    qualname: str,
) -> "CriteriaDescriptor[Any, ...] | None":
    """Находит CriteriaDescriptor по пути module.qualname или None."""
    try:
        obj: Any = importlib.import_module(module)
        for part in qualname.split("."):
            obj = getattr(obj, part)
    except (ImportError, AttributeError):
        return None
    if not isinstance(obj, CriteriaDescriptor):
        return None
    return cast("CriteriaDescriptor[Any, ...]", obj)  # pragma: no mutate


def _restore_predicate_criteria(
    module: str,
    qualname: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> PredicateCriteria[Any, Any]:
    """Восстанавливает критерий при unpickle."""
    descriptor = _find_descriptor(module, qualname)
    if descriptor is None:
        raise pickle.UnpicklingError(
            f"Criteria {module}.{qualname} not found"
        )  # pragma: no mutate
    return descriptor.criteria_cls(*args, **kwargs)


def make_predicate_criteria(
    fn: Predicate[Object, Params],
) -> type[PredicateCriteria[Object, Params]]:
    """Строит класс-критерий (dataclass) из функции-предиката.

    Параметры функции после первого становятся полями dataclass.

    Args:
        fn: Функция `fn(candidate, *params)`.

    Returns:
        Класс-наследник `PredicateCriteria` с именем функции.

    Raises:
        TypeError: Есть `*args`/`**kwargs` или имя параметра
            `predicate`, `_positional`, `_keyword`.

    """
    annotations: list[tuple[Any, ...]] = []
    positional: list[str] = []
    keyword: list[str] = []
    signature = inspect.signature(fn)
    parameters = list(signature.parameters.items())
    for name, param in parameters[1:]:
        annotation = Any if param.annotation is param.empty else param.annotation

        if name in _RESERVED_NAMES:
            raise TypeError(
                f"Criteria {fn.__name__!r}: parameter name {name!r} "
                f"is reserved (reserved names: "
                f"{', '.join(_RESERVED_NAMES)})"  # pragma: no mutate
            )

        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            raise TypeError(
                f"Criteria {fn.__name__!r}: parameter {name!r} "
                f"({param.kind.description}) is not supported, "
                f"it can't be a criteria field"
            )

        kw_only = param.kind is param.KEYWORD_ONLY
        (keyword if kw_only else positional).append(name)
        if param.default is not param.empty:
            annotations.append(
                (
                    name,
                    annotation,
                    field(default=param.default, kw_only=kw_only),
                )
            )
        elif kw_only:
            annotations.append((name, annotation, field(kw_only=True)))
        else:
            annotations.append((name, annotation))

    new_cls = make_dataclass(
        fn.__name__,
        annotations,
        bases=(PredicateCriteria,),
        namespace={
            "predicate": staticmethod(fn),
            "_positional": tuple(positional),
            "_keyword": tuple(keyword),
        },
    )
    new_cls.__module__ = fn.__module__
    return cast(
        "type[PredicateCriteria[Object, Params]]",  # pragma: no mutate
        new_cls,
    )


def criteria(
    fn: Predicate[Object, Params],
) -> CriteriaDescriptor[Object, Params]:
    """Превращает функцию-предикат в критерий.

    Функция или метод `fn(candidate, *params)` становится классом-критерием
    (dataclass): имя класса совпадает с именем функции, параметры после
    кандидата - поля. Поддерживаются keyword-only параметры и значения
    по умолчанию. Параметры `*args`/`**kwargs` и имена `predicate`,
    `_positional`, `_keyword` не допускаются.

    На классе или модуле вызов создаёт критерий (отложенная проверка,
    его можно комбинировать и передавать в запросы), на экземпляре -
    сразу проверяет и возвращает bool; доступны также `.is_satisfied(...)`
    и `.must_be_satisfied(...)`. Pickle работает для функций уровня модуля
    и методов классов уровня модуля. Критерии из `@criteria` не хешируются
    (dataclass с `eq=True`).

    Args:
        fn: Функция `fn(candidate, *params) -> bool`.

    Returns:
        Дескриптор, создающий критерий.

    Raises:
        TypeError: `fn` не вызываема, либо у неё недопустимые параметры.

    Example:
        >>> from dataclasses import dataclass
        >>> @criteria
        ... def older_than(age, limit):
        ...     return age > limit
        >>> older_than(18)
        older_than(limit=18)
        >>> older_than(18).is_satisfied_by(20)
        True

        Метод класса:

        >>> @dataclass
        ... class Task:
        ...     days: int
        ...     @criteria
        ...     def obsolete(self, limit, *, strict=False):
        ...         return self.days >= limit if not strict else self.days > limit
        >>> Task.obsolete(3)
        obsolete(limit=3, strict=False)
        >>> Task.obsolete(3).is_satisfied_by(Task(3))
        True
        >>> task = Task(3)
        >>> task.obsolete(3)
        True
        >>> task.obsolete(3, strict=True)
        False
        >>> task.obsolete.must_be_satisfied(5)  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        CriteriaNotSatisfied: Criteria not satisfied: obsolete(limit=5, ...)

    """
    if not callable(fn):
        raise TypeError(f"criteria expects a callable, got {fn!r}")

    return CriteriaDescriptor[Object, Params](make_predicate_criteria(fn))
