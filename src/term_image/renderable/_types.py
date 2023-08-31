"""
.. Custom data types for the Renderable API
"""

from __future__ import annotations

__all__ = (
    "Frame",
    "RenderArgs",
    "RenderData",
)

from inspect import Parameter, signature
from types import MappingProxyType
from typing import Any, ClassVar, Iterator, Mapping, NamedTuple, Type

from .. import geometry
from ..utils import arg_type_error, arg_type_error_msg
from ._exceptions import RenderableError


# ==================== Classes ====================


class Frame(NamedTuple):
    """A rendered frame.

    NOTE:
        Arguments are not validated since instances are only meant to be created
        internally.

    TIP:
        - Instances are immutable and hashable.
        - Instances with equal fields compare equal.

    WARNING:
        Even though this class inherits from :py:class:`tuple`, the class and its
        instances should not be used as such, because:

        * this is an implementation detail,
        * the number or order of fields may change.

        Any change to this aspect of the interface may happen without notice and will
        not be considered a breaking change.
    """

    number: int
    """Frame number

    Zero, if the frame belongs to a non-animated renderable or one with
    :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` frame count.
    Otherwise, a non-negative integer.
    """

    duration: int | None
    """Frame duration (in **milliseconds**)

    ``None``, if the frame belongs to a non-animated renderable. Otherwise, a positive
    integer.
    """

    size: geometry.Size
    """Frame :term:`render size`"""

    render: str
    """Frame :term:`render output`"""

    def __str__(self) -> str:
        """Returns the frame :term:`render output`.

        Returns:
            The frame render output, :py:attr:`render`.
        """
        return self.render


class RenderArgsData:
    """Render arguments/data baseclass."""

    __slots__ = ("render_cls", "_namespaces")

    def __init__(
        self,
        render_cls: type[Renderable],
        namespaces: dict[type[Renderable], RenderArgsData.Namespace],
    ) -> None:
        self.render_cls = render_cls
        self._namespaces = MappingProxyType(namespaces)

    def __repr__(self) -> str:
        return "".join(
            (
                f"{type(self).__name__}({self.render_cls.__name__}",
                ", " if self._namespaces else "",
                ", ".join(map(repr, self._namespaces.values())),
                ")",
            )
        )

    class _NamespaceMeta(type):
        """Metaclass of render argument/data namespaces."""

        _FIELDS: MappingProxyType[str, Any]

        # Set by `RenderableMeta` for associated instances
        _RENDER_CLS: type[Renderable] | None = None

        def __new__(
            cls,
            name,
            bases,
            namespace,
            *,
            inherit: bool = True,
            _base: bool = False,
            **kwargs,
        ):
            if _base:
                namespace["__slots__"] = ()
            else:
                namespace_bases = [cls for cls in bases if isinstance(cls, __class__)]
                if len(namespace_bases) > 1:
                    raise RenderArgsDataError("Multiple namespace baseclasses")

                base_has_fields = hasattr(namespace_bases[0], "_FIELDS")
                inheriting = base_has_fields and inherit
                fields = namespace.get("__annotations__", ())

                if inheriting:
                    if fields:
                        raise RenderArgsDataError(
                            "Cannot both inherit and define fields"
                        )
                else:
                    if not fields:
                        raise RenderArgsDataError("No field defined or to inherit")

                    namespace["_FIELDS"] = MappingProxyType(dict.fromkeys(fields))
                    if base_has_fields:
                        namespace["_RENDER_CLS"] = None

                for attr in fields:
                    namespace.pop(attr, None)
                namespace["__slots__"] = tuple(fields)

            new_cls = super().__new__(cls, name, bases, namespace, **kwargs)

            if not _base:
                for method_name in ("__new__", "__init__"):
                    method = getattr(new_cls, method_name)
                    parameters = iter(signature(method).parameters.items())

                    next(parameters)  # skip first parameter (cls, self)
                    for param_name, param in parameters:
                        if param.default is Parameter.empty and (
                            Parameter.VAR_POSITIONAL
                            is not param.kind
                            is not Parameter.VAR_KEYWORD
                        ):
                            raise TypeError(
                                f"'{new_cls.__qualname__}.{method_name}' has a "
                                f"required parameter {param_name!r}"
                            )

            return new_cls

    class Namespace(metaclass=_NamespaceMeta, _base=True):
        """:term:`Render class`\\ -specific argument/data namespace."""

        def __new__(cls, *args, **kwargs):
            if cls._RENDER_CLS is None:
                raise TypeError(
                    "Cannot instantiate a render argument/data namespace class "
                    "that is not associated with a render class"
                )

            return super().__new__(cls)

        def __init__(self, fields: Mapping[str, Any]) -> None:
            for name in type(self)._FIELDS:
                # Subclass(es) redefine `__setattr__()`
                __class__.__setattr__(self, name, fields[name])

        def __delattr__(self, _):
            raise AttributeError("Cannot delete field")

        def as_dict(self) -> dict[str, Any]:
            """Converts the namespace to a dictionary.

            Returns:
                A dictionary mapping field names to their values.

            WARNING:
                The number and order of fields is guaranteed to be the same for a
                subclass that defines fields, its subclasses (that inherit its fields)
                and all their instances but beyond this, should not be relied upon as
                the details (such as the specific number or order) may change without
                notice.

                The order is an implementation detail of the Render Arguments/Data API
                and the number should be considered an implementation detail of the
                specific namespace subclass.
            """
            return {name: getattr(self, name) for name in type(self)._FIELDS}

        @classmethod
        def get_fields(cls) -> Mapping[str, Any]:
            """Returns the field definitions.

            Returns:
                A mapping of field names to their default values.

            WARNING:
                The number and order of fields is guaranteed to be the same for a
                subclass that defines fields, its subclasses (that inherit its fields)
                and all their instances but beyond this, should not be relied upon as
                the details (such as the specific number or order) may change without
                notice.

                The order is an implementation detail of the Render Arguments/Data API
                and the number should be considered an implementation detail of the
                specific namespace subclass.
            """
            return cls._FIELDS

        @classmethod
        def get_render_cls(cls) -> Type[Renderable] | None:
            """Returns the associated :term:`render class`.

            Returns:
                The associated render class, if the namespace class has been
                associated. Otherwise, ``None``.
            """
            return cls._RENDER_CLS


class RenderArgs(RenderArgsData):
    """RenderArgs(render_cls, /, *namespaces)
    RenderArgs(render_cls, init_render_args, /, *namespaces)

    Render arguments.

    Args:
        render_cls: A :term:`render class`.
        init_render_args (RenderArgs | None): A set of render arguments.
          If not ``None``,

          * it must be compatible [#ra1]_ with *render_cls*,
          * it'll be used to initialize the render arguments.

        namespaces: Render argument namespaces compatible [#ran2]_ with *render_cls*.

          .. note:: If multiple namespaces associated with the same :term:`render
             class` are given, the last of them takes precedence.

    Raises:
        TypeError: An argument is of an inappropriate type.
        term_image.exceptions.RenderArgsError: *init_render_args* is incompatible
          [#ra1]_ with *render_cls*.
        term_image.exceptions.RenderArgsError: Incompatible [#ran2]_ render argument
          namespace.

    A set of render arguments (an instance of this class) is basically a container of
    render argument namespaces (instances of :py:class:`RenderArgs.Namespace`); one for
    each :term:`render class`, which defines render arguments, in the Method Resolution
    Order of its associated [#ra2]_ render class.

    The namespace for each render class is derived from the following sources, in
    [descending] order of precedence:

    * *namespaces*
    * *init_render_args*
    * default render argument namespaces

    NOTE:
        Instances are immutable but updated copies can be created via :py:meth:`update`.

    TIP:
        See the ``Args`` attribute (subclass of :py:class:`RenderArgs.Namespace`)
        of :term:`render classes`, if not ``None``, for their respective render
        argument namespaces.

    .. Completed in /docs/source/api/renderable.rst
    """

    __slots__ = ()

    __interned: ClassVar[dict[type[Renderable], RenderArgs]] = {}

    # Instance Attributes

    render_cls: Type[Renderable]
    """The associated :term:`render class`"""

    # Special Methods

    def __new__(
        cls,
        render_cls: type[Renderable],
        init_or_namespace: RenderArgs | RenderArgs.Namespace | None = None,
        *namespaces: RenderArgs.Namespace,
    ) -> RenderArgs:
        if init_or_namespace is None:
            init_render_args = None
        elif isinstance(init_or_namespace, cls):
            init_render_args = init_or_namespace
        elif isinstance(init_or_namespace, __class__.Namespace):
            init_render_args = None
            namespaces = (init_or_namespace, *namespaces)
        else:
            raise arg_type_error_msg(
                "Invalid type for the second argument", init_or_namespace
            )

        if init_render_args:
            if not isinstance(render_cls, RenderableMeta):
                raise arg_type_error("render_cls", render_cls)

            if not issubclass(render_cls, init_render_args.render_cls):
                raise RenderArgsError(
                    f"'init_render_args' is incompatible with {render_cls.__name__!r} "
                    f"(got: {init_render_args!r})"
                )

        # has default values only
        if not namespaces and (
            not init_render_args
            or init_render_args is BASE_RENDER_ARGS
            or cls.__interned.get(init_render_args.render_cls) is init_render_args
        ):
            try:
                return cls.__interned[render_cls]
            except KeyError:
                pass

        if (
            init_render_args
            and init_render_args.render_cls is render_cls
            and not namespaces
        ):
            return init_render_args

        return super().__new__(cls)

    def __init__(
        self,
        render_cls: type[Renderable],
        init_or_namespace: RenderArgs | RenderArgs.Namespace | None = None,
        *namespaces: RenderArgs.Namespace,
    ) -> None:
        # `init_or_namespace` is validated in `__new__()`.
        # `render_cls` is validated in `__new__()`, if and only if `init_or_namespace`
        # is a `RenderArgs` instance.

        if init_or_namespace is None:
            init_render_args = None
        elif isinstance(init_or_namespace, type(self)):
            init_render_args = init_or_namespace
        else:
            init_render_args = None
            namespaces = (init_or_namespace, *namespaces)

        # has default values only
        if not namespaces and (
            not init_render_args
            or init_render_args is BASE_RENDER_ARGS
            or (
                type(self).__interned.get(init_render_args.render_cls)
                is init_render_args
            )
        ):
            if render_cls in type(self).__interned:  # has been initialized
                return
            intern = True
        else:
            intern = False

        if init_render_args:
            if init_render_args.render_cls is render_cls and not namespaces:
                return
        # `render_cls` wasn't validated in `__new__()`
        elif not isinstance(render_cls, RenderableMeta):
            raise arg_type_error("render_cls", render_cls)

        namespaces_dict = render_cls._ALL_DEFAULT_ARGS.copy()

        # if non-default
        if init_render_args and BASE_RENDER_ARGS is not init_render_args is not (
            type(self).__interned.get(init_render_args.render_cls)
        ):
            namespaces_dict.update(init_render_args._namespaces)

        for index, namespace in enumerate(namespaces):
            if not isinstance(namespace, __class__.Namespace):
                raise arg_type_error(f"namespaces[{index}]", namespace)
            if namespace._RENDER_CLS not in render_cls._ALL_DEFAULT_ARGS:
                raise RenderArgsError(
                    f"'namespaces[{index}]' is incompatible with "
                    f"{render_cls.__name__!r} (got: {namespace!r})"
                )
            namespaces_dict[namespace._RENDER_CLS] = namespace

        super().__init__(render_cls, namespaces_dict)

        if intern:
            type(self).__interned[render_cls] = self

    def __init_subclass__(cls, **kwargs) -> None:
        cls.__interned = {}
        super().__init_subclass__(**kwargs)

    def __eq__(self, other: RenderArgs) -> bool:
        """Compares this set of render arguments with another.

        Args:
            other: Another set of render arguments.

        Returns:
            ``True`` if both are associated with the same :term:`render class`
            and have equal argument values. Otherwise, ``False``.
        """
        if isinstance(other, type(self)):
            return (
                self is other
                or self.render_cls is other.render_cls
                and self._namespaces == other._namespaces
            )

        return NotImplemented

    def __getitem__(self, render_cls: Type[Renderable]) -> RenderArgs.Namespace:
        """Returns a constituent namespace.

        Args:
            render_cls: A :term:`render class` of which :py:attr:`render_cls` is a
              subclass (which may be :py:attr:`render_cls` itself) and which defines
              render arguments.

        Returns:
            The constituent namespace associated with *render_cls*.

        Raises:
            TypeError: An argument is of an inappropriate type.
            term_image.exceptions.RenderArgsError: *render_cls* defines no render
              arguments.
            term_image.exceptions.RenderArgsError: :py:attr:`render_cls` is not a
              subclass of *render_cls*.
        """
        try:
            return self._namespaces[render_cls]
        except (TypeError, KeyError):
            if not isinstance(render_cls, RenderableMeta):
                raise arg_type_error("render_cls", render_cls) from None

            if issubclass(self.render_cls, render_cls):
                raise RenderArgsError(
                    f"{render_cls.__name__!r} defines no render arguments"
                ) from None

            raise RenderArgsError(
                f"{self.render_cls.__name__!r} is not a subclass of "
                f"{render_cls.__name__!r}"
            ) from None

    def __hash__(self) -> int:
        """Computes the hash of the render arguments.

        Returns:
            The computed hash.

        IMPORTANT:
            Like tuples, an instance is hashable if and only if the constituent
            namespaces are hashable.
        """
        # Namespaces are always in the same order, wrt their respective associated
        # render classes, for all instances associated with the same render class.
        return hash((self.render_cls, tuple(self._namespaces.values())))

    def __iter__(self) -> Iterator[RenderArgs.Namespace]:
        """Returns an iterator that yields the constituent namespaces.

        Returns:
            An iterator that yields the constituent namespaces.

        WARNING:
            The number and order of namespaces is guaranteed to be the same across all
            instances associated [#ra2]_ with the same :term:`render class` but beyond
            this, should not be relied upon as the details (such as the specific
            number or order) may change without notice.

            The order is an implementation detail of the Renderable API and the number
            should be considered alike with respect to the associated render class.
        """
        return iter(self._namespaces.values())

    # Public Methods

    def convert(self, render_cls: Type[Renderable]) -> RenderArgs:
        """Converts the set of render arguments to one for a related render class.

        Args:
            render_cls: A :term:`render class` of which :py:attr:`render_cls` is a
              parent or child (which may be :py:attr:`render_cls` itself).

        Returns:
            A set of render arguments associated [#ra2]_ with *render_cls* and
            initialized with all constituent namespaces (of this set of render
            arguments, *self*) that are compatible [#ran2]_ with *render_cls*.

        Raises:
            TypeError: An argument is of an inappropriate type.
            RenderArgsError: *render_cls* is not a parent or child of
              :py:attr:`render_cls`.
        """
        if render_cls is self.render_cls:
            return self

        if not isinstance(render_cls, RenderableMeta):
            raise arg_type_error("render_cls", render_cls)

        if issubclass(render_cls, self.render_cls):
            return type(self)(render_cls, self)

        if issubclass(self.render_cls, render_cls):
            render_cls_args_mro = render_cls._ALL_DEFAULT_ARGS
            return type(self)(
                render_cls,
                *[
                    namespace
                    for cls, namespace in self._namespaces.items()
                    if cls in render_cls_args_mro
                ],
            )

        raise RenderArgsError(
            f"{render_cls.__name__!r} is not a parent or child of "
            f"{self.render_cls.__name__!r}"
        )

    def update(
        self,
        render_cls_or_namespace: Type[Renderable] | RenderArgs.Namespace,
        *namespaces: RenderArgs.Namespace,
        **fields: Any,
    ) -> RenderArgs:
        """update(namespace, /, *namespaces) -> RenderArgs
        update(render_cls, /, **fields) -> RenderArgs

        Replaces or updates render argument namespaces.

        Args:
            namespaces: Render argument namespaces compatible [#ran2]_ with
              :py:attr:`render_cls`.

              .. note:: If multiple namespaces associated with the same :term:`render
                 class` are given, the last of them takes precedence.

            render_cls (Type[Renderable]): A :term:`render class` of which
              :py:attr:`render_cls` is a subclass (which may be :py:attr:`render_cls`
              itself) and which defines render arguments.
            fields: Render argument fields.

              The keywords must be names of render argument fields for *render_cls*.

        Returns:
            For the **first** form, an instance with the namespaces for the respective
            associated :term:`render classes` of the given namespaces replaced.

            For the **second** form, an instance with the given render argument fields
            for *render_cls* updated, if any.

        Raises:
            TypeError: An argument is of an inappropriate type.
            TypeError: The arguments given do not conform to any of the expected forms.

        Propagates exceptions raised by:

        * the class constructor, for the **first** form.
        * :py:meth:`__getitem__` and :py:meth:`RenderArgs.Namespace.update`, for the
          **second** form.
        """
        if isinstance(render_cls_or_namespace, RenderableMeta):
            if namespaces:
                raise TypeError(
                    "No other positional argument is expected when the first argument "
                    "is a render class"
                )
            render_cls = render_cls_or_namespace
        elif isinstance(render_cls_or_namespace, __class__.Namespace):
            if fields:
                raise TypeError(
                    "No keyword argument is expected when the first argument is "
                    "a render argument namespace"
                )
            render_cls = None
            namespaces = (render_cls_or_namespace, *namespaces)
        else:
            raise arg_type_error_msg(
                "Invalid type for the first argument", render_cls_or_namespace
            )

        return type(self)(
            self.render_cls,
            self,
            *((self[render_cls].update(**fields),) if render_cls else namespaces),
        )

    # Inner Classes

    class _NamespaceMeta(RenderArgsData._NamespaceMeta):
        """Metaclass of render argument namespaces."""

        def __new__(cls, name, bases, namespace, *, _base: bool = False, **kwargs):
            if not _base:
                try:
                    defaults = {
                        name: namespace[name]
                        for name in namespace.get("__annotations__", ())
                    }
                except KeyError as e:
                    raise RenderArgsError(
                        f"Field {e.args[0]!r} has no default value"
                    ) from None

            new_cls = super().__new__(
                cls, name, bases, namespace, _base=_base, **kwargs
            )

            if not _base and "_FIELDS" in new_cls.__dict__:
                new_cls._FIELDS = MappingProxyType(defaults)

            return new_cls

    class Namespace(RenderArgsData.Namespace, metaclass=_NamespaceMeta, _base=True):
        """Namespace(*values, **fields)

        :term:`Render class`\\ -specific render argument namespace.

        Args:
            values: Render argument field values.

              The values are mapped to fields in the order in which the fields were
              defined.

            fields: Render argument fields.

              The keywords must be names of render argument fields for the associated
              [#ran1]_ render class.

        Raises:
            TypeError: The [sub]class being instantiated is not associated [#ran1]_
              with a render class.
            TypeError: More values (positional arguments) than there are fields.
            term_image.exceptions.RenderArgsError: Unknown field name(s).
            TypeError: Multiple values given for a field.

        If no value is given for a field, its default value is used.

        NOTE:
            * Fields are exposed as instance attributes.
            * Instances are immutable but updated copies can be created via
              :py:meth:`update`.
            * Each subclass may be associated [#ran1]_ with **only one** render class.

        .. Completed in /docs/source/api/renderable.rst
        """

        def __init__(self, *values: Any, **fields: Any) -> None:
            default_fields = type(self)._FIELDS

            if len(values) > len(default_fields):
                raise TypeError(
                    f"{type(self)._RENDER_CLS.__name__!r} defines "
                    f"{len(default_fields)} render argument field(s) but "
                    f"{len(values)} values were given"
                )
            value_fields = dict(zip(default_fields, values))

            unknown = fields.keys() - default_fields.keys()
            if unknown:
                raise RenderArgsError(
                    f"Unknown render argument fields {tuple(unknown)} for "
                    f"{type(self)._RENDER_CLS.__name__!r}"
                )
            multiple = fields.keys() & value_fields.keys()
            if multiple:
                raise TypeError(
                    f"Got multiple values for render argument fields "
                    f"{tuple(multiple)} of {type(self)._RENDER_CLS.__name__!r}"
                )

            super().__init__({**default_fields, **value_fields, **fields})

        def __repr__(self) -> str:
            return "".join(
                (
                    f"{type(self)._RENDER_CLS.__name__}.Args(",
                    ", ".join(
                        f"{name}={getattr(self, name)!r}" for name in type(self)._FIELDS
                    ),
                    ")",
                )
            )

        def __getattr__(self, attr):
            raise AttributeError(
                f"Unknown render argument field {attr!r} for "
                f"{type(self)._RENDER_CLS.__name__!r}"
            )

        def __setattr__(self, *_):
            raise AttributeError(
                "Cannot modify render argument fields, use the `update()` method "
                "of the namespace or the containing `RenderArgs` instance, as "
                "applicable, instead"
            )

        def __eq__(self, other: RenderArgs.Namespace) -> bool:
            """Compares the namespace with another.

            Args:
                other: Another render argument namespace.

            Returns:
                ``True`` if both operands are associated with the same
                :term:`render class` and have equal field values.
                Otherwise, ``False``.
            """
            if type(other) is type(self):
                return self is other or all(
                    getattr(self, name) == getattr(other, name)
                    for name in type(self)._FIELDS
                )

            return NotImplemented

        def __hash__(self) -> int:
            """Computes the hash of the namespace.

            Returns:
                The computed hash.

            IMPORTANT:
                Like tuples, an instance is hashable if and only if the field values
                are hashable.
            """
            # Field names and their order is the same for all instances associated
            # with the same render class.
            return hash(
                (
                    type(self)._RENDER_CLS,
                    tuple([getattr(self, field) for field in type(self)._FIELDS]),
                )
            )

        def __or__(self, other: RenderArgs.Namespace | RenderArgs) -> RenderArgs:
            """Derives a set of render arguments from the combination of both operands.

            Args:
                other: Another render argument namespace or a set of render arguments.

            Returns:
                A set of render arguments associated with the **most derived** one
                of the associated :term:`render classes` of both operands.

            Raises:
                term_image.exceptions.RenderArgsError: Neither operand is compatible
                  [#ran2]_ with the associated :term:`render class` of the other.

            NOTE:
                * If *other* is a render argument namespace associated with the
                  same :term:`render class` as *self*, *other* takes precedence.
                * If *other* is a set of render arguments that contains a namespace
                  associated with the same :term:`render class` as *self*, *self* takes
                  precedence.
            """
            self_render_cls = type(self)._RENDER_CLS

            if isinstance(other, __class__):
                other_render_cls = type(other)._RENDER_CLS
                if self_render_cls is other_render_cls:
                    return RenderArgs(other_render_cls, other)
                if issubclass(self_render_cls, other_render_cls):
                    return RenderArgs(self_render_cls, self, other)
                if issubclass(other_render_cls, self_render_cls):
                    return RenderArgs(other_render_cls, self, other)
                raise RenderArgsError(
                    f"Render argument namespaces for {self_render_cls.__name__!r} "
                    f"and {other_render_cls.__name__!r} are incompatible with each "
                    "other."
                )

            if isinstance(other, RenderArgs):
                other_render_cls = other.render_cls
                if issubclass(self_render_cls, other_render_cls):
                    return RenderArgs(self_render_cls, other, self)
                if issubclass(other_render_cls, self_render_cls):
                    return RenderArgs(other_render_cls, other, self)
                raise RenderArgsError(
                    f"Render argument namespace for {self_render_cls.__name__!r} "
                    f"and render arguments for {other_render_cls.__name__!r} are "
                    "incompatible with each other."
                )

            return NotImplemented

        def __pos__(self) -> RenderArgs:
            """Creates a set of render arguments from the namespace.

            Returns:
                A set of render arguments associated with the same :term:`render class`
                as the namespace and initialized with the namespace.

            TIP:
                ``+namespace`` is shorthand for
                :py:meth:`namespace.to_render_args() <to_render_args>`.
            """
            return RenderArgs(type(self)._RENDER_CLS, self)

        def __ror__(self, other: RenderArgs.Namespace | RenderArgs) -> RenderArgs:
            """Same as :py:meth:`__or__` but with reflected operands.

            NOTE:
                Unlike :py:meth:`__or__`, if *other* is a render argument namespace
                associated with the same :term:`render class` as *self*, *self* takes
                precedence.
            """
            # Not commutative
            if isinstance(other, __class__) and (
                type(self)._RENDER_CLS is type(other)._RENDER_CLS
            ):
                return RenderArgs(type(self)._RENDER_CLS, self)

            return self.__or__(other)  # All other cases are commutative

        def to_render_args(
            self, render_cls: type[Renderable] | None = None
        ) -> RenderArgs:
            """Creates a set of render arguments from the namespace.

            Args:
                render_cls: A :term:`render class`, with which the namespace is
                  compatible [#ran2]_.

            Returns:
                A set of render arguments associated with *render_cls* (or the
                associated [#ran1]_ render class of the namespace, if ``None``) and
                initialized with the namespace.

            Propagates exceptions raised by the
            :py:class:`~term_image.renderable.RenderArgs` constructor, as applicable.

            .. seealso:: :py:meth:`__pos__`.
            """
            return RenderArgs(render_cls or type(self)._RENDER_CLS, self)

        def update(self, **fields: Any) -> RenderArgs.Namespace:
            """Updates render argument fields.

            Args:
                fields: Render argument fields.

            Returns:
                A namespace with the given fields updated.

            Raises:
                term_image.exceptions.RenderArgsError: Unknown field name(s).
            """
            if not fields:
                return self

            unknown = fields.keys() - type(self)._FIELDS.keys()
            if unknown:
                raise RenderArgsError(
                    f"Unknown render argument field(s) {tuple(unknown)} for "
                    f"{type(self)._RENDER_CLS.__name__!r}"
                )

            new = type(self).__new__(type(self))
            new_fields = self.as_dict()
            new_fields.update(fields)
            super(__class__, new).__init__(new_fields)

            return new


class RenderData(RenderArgsData):
    """Render data.

    Args:
        render_cls: A :term:`render class`.

    An instance of this class is basically a container of render data namespaces
    (instances of :py:class:`RenderData.Namespace`); one for each :term:`render class`,
    which defines render data, in the Method Resolution Order of its associated
    [#rd1]_ render class.

    NOTE:
        * Instances are immutable but the constituent namespaces are mutable.
        * Instances and their contents shouldn't be copied by any means because
          finalizing an instance may invalidate all other copies.
        * Instances should always be explicitly finalized as soon as they're no longer
          needed.

    TIP:
        See the ``_Data_`` attribute (subclass of :py:class:`RenderData.Namespace`)
        of :term:`render classes`, if not ``None``, for their respective render
        data namespaces.
    """

    __slots__ = ("finalized",)

    # Instance Attributes

    finalized: bool
    """Finalization status"""

    render_cls: Type[Renderable]
    """The associated :term:`render class`"""

    # Special Methods

    def __init__(self, render_cls: type[Renderable]) -> None:
        super().__init__(
            render_cls,
            {cls: data_cls() for cls, data_cls in render_cls._RENDER_DATA_MRO.items()},
        )
        self.finalized = False

    def __del__(self):
        try:
            self.finalize()
        except AttributeError:  # Unsuccesful initialization
            pass

    def __getitem__(self, render_cls: Type[Renderable]) -> RenderData.Namespace:
        """Returns a constituent namespace.

        Args:
            render_cls: A :term:`render class` of which :py:attr:`render_cls` is a
              subclass (which may be :py:attr:`render_cls` itself) and which defines
              render data.

        Returns:
            The constituent namespace associated with *render_cls*.

        Raises:
            TypeError: An argument is of an inappropriate type.
            term_image.exceptions.RenderDataError: *render_cls* defines no render
              data.
            term_image.exceptions.RenderDataError: :py:attr:`render_cls` is not a
              subclass of *render_cls*.
        """
        try:
            return self._namespaces[render_cls]
        except (TypeError, KeyError):
            if not isinstance(render_cls, RenderableMeta):
                raise arg_type_error("render_cls", render_cls) from None

            if issubclass(self.render_cls, render_cls):
                raise RenderDataError(
                    f"{render_cls.__name__!r} defines no render data"
                ) from None

            raise RenderDataError(
                f"{self.render_cls.__name__!r} is not a subclass of "
                f"{render_cls.__name__!r}"
            ) from None

    def __iter__(self) -> Iterator[RenderData.Namespace]:
        """Returns an iterator that yields the constituent namespaces.

        Returns:
            An iterator that yields the constituent namespaces.

        WARNING:
            The number and order of namespaces is guaranteed to be the same across all
            instances associated [#rd1]_ with the same :term:`render class` but beyond
            this, should not be relied upon as the details (such as the specific
            number or order) may change without notice.

            The order is an implementation detail of the Renderable API and the number
            should be considered alike with respect to the associated render class.
        """
        return iter(self._namespaces.values())

    # Public Methods

    def finalize(self) -> None:
        """Finalizes the render data.

        Calls :py:meth:`~term_image.renderable.Renderable._finalize_render_data_`
        of :py:attr:`render_cls`.

        NOTE:
            This method is safe for multiple invokations on the same instance.
        """
        if not self.finalized:
            try:
                self.render_cls._finalize_render_data_(self)
            finally:
                self.finalized = True

    # Inner Classes

    class Namespace(RenderArgsData.Namespace, _base=True):
        """Namespace()

        :term:`Render class`\\ -specific render data namespace.

        Raises:
            TypeError: The [sub]class being instantiated is not associated [#rdn1]_
              with a render class.

        Subclassing, defining (and inheriting) fields is just as it is for
        :ref:`args-namespace`, except that values assigned to the class attributes
        are not used.

        Every field is initialized to ``None``. The fields are expected to be updated
        by the :py:meth:`~term_image.renderable.Renderable._get_render_data_` method
        of the render class associated [#rdn1]_ with the namespace, if neccessary.

        NOTE:
            * Fields are exposed as instance attributes.
            * Instances are mutable and fields can updated **in-place** either
              individually by assignment to an attribute reference or in batch via
              :py:meth:`update`.
            * An instance shouldn't be copied by any means because finalizing its
              containing :py:class:`RenderData` instance may invalidate all copies of
              the namespace.
            * Each subclass may be associated [#rdn1]_ with **only one** render class.

        .. Completed in /docs/source/api/renderable.rst
        """

        def __init__(self) -> None:
            super().__init__(type(self)._FIELDS)

        def __repr__(self) -> str:
            return "".join(
                (
                    f"{type(self)._RENDER_CLS.__name__}._Data_(",
                    ", ".join(
                        f"{name}={getattr(self, name)!r}" for name in type(self)._FIELDS
                    ),
                    ")",
                )
            )

        def __getattr__(self, attr):
            raise AttributeError(
                f"Unknown render data field {attr!r} for "
                f"{type(self)._RENDER_CLS.__name__!r}"
            )

        def __setattr__(self, attr, value):
            try:
                super().__setattr__(attr, value)
            except AttributeError:
                raise AttributeError(
                    f"Unknown render data field {attr!r} for "
                    f"{type(self)._RENDER_CLS.__name__!r}"
                ) from None

        def update(self, **fields: Any) -> None:
            """Updates render data fields.

            Args:
                fields: Render data fields.

            Raises:
                term_image.exceptions.RenderDataError: Unknown field name(s).
            """
            if fields:
                unknown = fields.keys() - type(self)._FIELDS.keys()
                if unknown:
                    raise RenderDataError(
                        f"Unknown render data field(s) {tuple(unknown)} for "
                        f"{type(self)._RENDER_CLS.__name__!r}"
                    )

                for field in fields.items():
                    super().__setattr__(*field)


# ==================== Exceptions ====================


class RenderArgsDataError(RenderableError):
    """Raised for errors common to both :py:class:`~term_image.renderable.RenderArgs`
    and :py:class:`~term_image.renderable.RenderData`.
    """


class RenderArgsError(RenderArgsDataError):
    """Raised for errors specific to :py:class:`~term_image.renderable.RenderArgs`."""


class RenderDataError(RenderArgsDataError):
    """Raised for errors specific to :py:class:`~term_image.renderable.RenderData`."""


# ==================== Variables ====================


BASE_RENDER_ARGS = RenderArgs.__new__(RenderArgs, None)

# Updated from `._renderable`
Renderable = "Renderable"
RenderableMeta = "RenderableMeta"
