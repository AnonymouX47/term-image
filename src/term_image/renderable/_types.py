"""
.. Custom data types for the Renderable API
"""

from __future__ import annotations

__all__ = (
    "Frame",
    "RenderArgs",
    "ArgsNamespace",
    "RenderData",
    "DataNamespace",
    "RenderArgsDataError",
    "RenderArgsError",
    "RenderDataError",
    "IncompatibleArgsNamespaceError",
    "IncompatibleRenderArgsError",
    "NoArgsNamespaceError",
    "NoDataNamespaceError",
    "UnassociatedNamespaceError",
    "UninitializedDataFieldError",
    "UnknownArgsFieldError",
    "UnknownDataFieldError",
)

from inspect import Parameter, signature
from types import MappingProxyType
from typing import Any, ClassVar, Iterator, Mapping, NamedTuple, Sequence, Type

from typing_extensions import TYPE_CHECKING

from .. import geometry
from ..utils import arg_type_error, arg_type_error_msg
from ._exceptions import RenderableError

if TYPE_CHECKING:
    # `RenderableMeta` is set from `._renderable` later on, as a top-level import
    # will result in a circular import and localized imports are just unnecessarily
    # costly (no matter how minimal).
    from ._renderable import Renderable, RenderableMeta


# Exceptions ===================================================================


class RenderArgsDataError(RenderableError):
    """Base exception class for errors specific to :py:class:`RenderArgs` and
    :py:class:`RenderData`.

    Raised for errors that occur during the creation of render argument/data
    namespace classes.
    """


class RenderArgsError(RenderArgsDataError):
    """Base exception class for errors specific to :py:class:`RenderArgs`.

    Raised for errors that occur during the creation of render argument namespace
    classes.
    """


class RenderDataError(RenderArgsDataError):
    """Base exception class for errors specific to :py:class:`RenderData`."""


class IncompatibleArgsNamespaceError(RenderArgsError):
    """Raised when a given render argument namespace is incompatible [#ran2]_ with a
    certain :term:`render class`.
    """


class IncompatibleRenderArgsError(RenderArgsError):
    """Raised when a given set of render arguments is incompatible [#ra1]_ with a
    certain :term:`render class`.
    """


class NoArgsNamespaceError(RenderArgsError):
    """Raised when an attempt is made to get a render argument namespace for a
    :term:`render class` that has no render arguments.
    """


class NoDataNamespaceError(RenderDataError):
    """Raised when an attempt is made to get a render data namespace for a
    :term:`render class` that has no render data.
    """


class UnassociatedNamespaceError(RenderArgsDataError):
    """Raised when certain operations are attempted on a render argument/data namespace
    class that hasn't been associated [#ran1]_ [#rdn1]_ with a :term:`render class`.
    """


class UninitializedDataFieldError(RenderDataError, AttributeError):
    """Raised when an attempt is made to access a render data field that hasn't been
    initialized i.e for which a value hasn't been set.
    """


class UnknownArgsFieldError(RenderArgsError, AttributeError):
    """Raised when an attempt is made to access or modify an unknown render argument
    field.
    """


class UnknownDataFieldError(RenderDataError, AttributeError):
    """Raised when an attempt is made to access or modify an unknown render data
    field.
    """


# Classes ======================================================================


class ArgsDataNamespaceMeta(type):
    """Metaclass of render argument/data namespaces."""

    _associated: bool = False
    _FIELDS: MappingProxyType[str, Any] = MappingProxyType({})
    _RENDER_CLS: type[Renderable]

    def __new__(
        cls,
        name,
        bases,
        namespace,
        *,
        render_cls: type[Renderable] | None = None,
        _base: bool = False,
        **kwargs,
    ):
        if _base:
            namespace["__slots__"] = ()
        else:
            # Assumes the metaclass is never used directly without `_base=True`

            if len(bases) > 1:
                raise RenderArgsDataError("Multiple base classes")

            base = bases[0]
            fields: Sequence[str] = namespace.get("__annotations__", ())

            if base._FIELDS:
                if fields:
                    raise RenderArgsDataError("Cannot both inherit and define fields")
            elif fields:
                for field_name in fields:
                    namespace.pop(field_name, None)
                namespace["_FIELDS"] = MappingProxyType(dict.fromkeys(fields))

            namespace["__slots__"] = tuple(fields)

            if render_cls:
                if base._associated:
                    raise RenderArgsDataError(
                        "Cannot reassociate a namespace subclass; the base class "
                        f"is already associated with {base._RENDER_CLS.__name__!r}"
                    )
                if not fields:
                    raise RenderArgsDataError(
                        "Cannot associate a namespace class that has no fields"
                    )
                if not isinstance(render_cls, RenderableMeta):
                    raise arg_type_error("render_cls", render_cls)

                namespace["_associated"] = True
                namespace["_RENDER_CLS"] = render_cls

            elif fields:
                raise RenderArgsDataError("Unassociated namespace class with fields")

        new_cls = super().__new__(cls, name, bases, namespace, **kwargs)

        if new_cls._FIELDS:
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


class ArgsDataNamespace(metaclass=ArgsDataNamespaceMeta, _base=True):
    """:term:`Render class`\\ -specific argument/data namespace."""

    def __new__(cls, *args, **kwargs):
        if not cls._associated:
            raise UnassociatedNamespaceError(
                "Cannot instantiate a render argument/data namespace class "
                "that hasn't been associated with a render class"
            )

        return super().__new__(cls)

    def __init__(self, fields: Mapping[str, Any]) -> None:
        setattr_ = __class__.__setattr__  # Subclass(es) redefine `__setattr__()`
        for name in type(self)._FIELDS:
            setattr_(self, name, fields[name])

    def __delattr__(self, _):
        raise AttributeError("Cannot delete field")

    @classmethod
    def get_render_cls(cls) -> Type[Renderable]:
        """Returns the associated :term:`render class`.

        Returns:
            The associated render class, if the namespace class has been
            associated.

        Raises:
            UnassociatedNamespaceError: The namespace class hasn't been associated
              with a render class.
        """
        if not cls._associated:
            raise UnassociatedNamespaceError(
                "This namespace class hasn't been associated with a render class"
            )

        return cls._RENDER_CLS


class ArgsNamespaceMeta(ArgsDataNamespaceMeta):
    """Metaclass of render argument namespaces."""

    def __new__(cls, name, bases, namespace, *, _base=False, **kwargs):
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

        args_cls = super().__new__(cls, name, bases, namespace, _base=_base, **kwargs)

        if not _base:
            if "_FIELDS" in args_cls.__dict__:
                args_cls._FIELDS = MappingProxyType(defaults)

            if render_cls := args_cls.__dict__.get("_RENDER_CLS"):
                if render_cls.Args:
                    raise RenderArgsError(
                        f"{render_cls.__name__!r} already has an associated render "
                        f"argument namespace class {render_cls.Args.__name__!r}"
                    )
                render_cls.Args = args_cls
                render_cls._ALL_DEFAULT_ARGS = MappingProxyType(
                    {render_cls: args_cls(), **render_cls._ALL_DEFAULT_ARGS}
                )

        return args_cls


class ArgsNamespace(ArgsDataNamespace, metaclass=ArgsNamespaceMeta, _base=True):
    """ArgsNamespace(*values, **fields)

    :term:`Render class`\\ -specific render argument namespace.

    Args:
        values: Render argument field values.

          The values are mapped to fields in the order in which the fields were
          defined.

        fields: Render argument fields.

          The keywords must be names of render argument fields for the associated
          [#ran1]_ render class.

    Raises:
        UnassociatedNamespaceError: The namespace class hasn't been associated
          [#ran1]_ with a render class.
        TypeError: More values (positional arguments) than there are fields.
        UnknownArgsFieldError: Unknown field name(s).
        TypeError: Multiple values given for a field.

    If no value is given for a field, its default value is used.

    NOTE:
        * Fields are exposed as instance attributes.
        * Instances are immutable but updated copies can be created via
          :py:meth:`update`.

    .. Completed in /docs/source/api/renderable.rst
    """

    def __init__(self, *values: Any, **fields: Any) -> None:
        default_fields = type(self)._FIELDS

        if len(values) > len(default_fields):
            raise TypeError(
                f"{type(self).__name__!r} defines {len(default_fields)} render "
                f"argument field(s) but {len(values)} values were given"
            )
        value_fields = dict(zip(default_fields, values))

        unknown = fields.keys() - default_fields.keys()
        if unknown:
            raise UnknownArgsFieldError(
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
                f"{type(self).__name__}(",
                ", ".join(
                    f"{name}={getattr(self, name)!r}" for name in type(self)._FIELDS
                ),
                ")",
            )
        )

    def __getattr__(self, attr):
        raise UnknownArgsFieldError(
            f"Unknown render argument field {attr!r} for "
            f"{type(self)._RENDER_CLS.__name__!r}"
        )

    def __setattr__(self, *_):
        raise AttributeError(
            "Cannot modify render argument fields, use the `update()` method "
            "of the namespace or the containing `RenderArgs` instance, as "
            "applicable, instead"
        )

    def __eq__(self, other: ArgsNamespace) -> bool:
        """Compares the namespace with another.

        Args:
            other: Another render argument namespace.

        Returns:
            ``True`` if both operands are associated with the same
            :term:`render class` and have equal field values.
            Otherwise, ``False``.
        """
        if isinstance(other, ArgsNamespace):
            return self is other or (
                type(self)._RENDER_CLS is type(other)._RENDER_CLS
                and all(
                    getattr(self, name) == getattr(other, name)
                    for name in type(self)._FIELDS
                )
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

    def __or__(self, other: ArgsNamespace | RenderArgs) -> RenderArgs:
        """Derives a set of render arguments from the combination of both operands.

        Args:
            other: Another render argument namespace or a set of render arguments.

        Returns:
            A set of render arguments associated with the **most derived** one
            of the associated :term:`render classes` of both operands.

        Raises:
            IncompatibleArgsNamespaceError: *other* is a render argument namespace
              and neither operand is compatible [#ra1]_ [#ran2]_ with the
              associated :term:`render class` of the other.
            IncompatibleRenderArgsError: *other* is a set of render arguments
              and neither operand is compatible [#ra1]_ [#ran2]_ with the
              associated :term:`render class` of the other.

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
            raise IncompatibleArgsNamespaceError(
                f"A render argument namespace for {other_render_cls.__name__!r} "
                "cannot be combined with a render argument namespace for "
                f"{self_render_cls.__name__!r}."
            )

        if isinstance(other, RenderArgs):
            other_render_cls = other.render_cls
            if issubclass(self_render_cls, other_render_cls):
                return RenderArgs(self_render_cls, other, self)
            if issubclass(other_render_cls, self_render_cls):
                return RenderArgs(other_render_cls, other, self)
            raise IncompatibleRenderArgsError(
                f"A set of render arguments for {other_render_cls.__name__!r} "
                "cannot be combined with a render argument namespace for "
                f"{self_render_cls.__name__!r}."
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

    def __ror__(self, other: ArgsNamespace | RenderArgs) -> RenderArgs:
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

        return type(self).__or__(self, other)  # All other cases are commutative

    def as_dict(self) -> dict[str, Any]:
        """Copies the namespace as a dictionary.

        Returns:
            A dictionary mapping field names to their values.

        WARNING:
            The number and order of fields are guaranteed to be the same for a
            namespace class that defines fields, its subclasses, and all their
            instances; but beyond this, should not be relied upon as the details
            (such as the specific number or order) may change without notice.

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
            The number and order of fields are guaranteed to be the same for a
            namespace class that defines fields, its subclasses, and all their
            instances; but beyond this, should not be relied upon as the details
            (such as the specific number or order) may change without notice.

            The order is an implementation detail of the Render Arguments/Data API
            and the number should be considered an implementation detail of the
            specific namespace subclass.
        """
        return cls._FIELDS

    def to_render_args(self, render_cls: type[Renderable] | None = None) -> RenderArgs:
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

    def update(self, **fields: Any) -> ArgsNamespace:
        """Updates render argument fields.

        Args:
            fields: Render argument fields.

        Returns:
            A namespace with the given fields updated.

        Raises:
            UnknownArgsFieldError: Unknown field name(s).
        """
        if not fields:
            return self

        unknown = fields.keys() - type(self)._FIELDS.keys()
        if unknown:
            raise UnknownArgsFieldError(
                f"Unknown render argument field(s) {tuple(unknown)} for "
                f"{type(self)._RENDER_CLS.__name__!r}"
            )

        new = type(self).__new__(type(self))
        new_fields = self.as_dict()
        new_fields.update(fields)
        super(__class__, new).__init__(new_fields)

        return new


class DataNamespaceMeta(ArgsDataNamespaceMeta):
    """Metaclass of render data namespaces."""

    def __new__(cls, name, bases, namespace, *, _base=False, **kwargs):
        data_cls = super().__new__(cls, name, bases, namespace, _base=_base, **kwargs)

        if not _base and (render_cls := data_cls.__dict__.get("_RENDER_CLS")):
            if render_cls._Data_:
                raise RenderDataError(
                    f"{render_cls.__name__!r} already has an associated render "
                    f"data namespace class {render_cls._Data_.__name__!r}"
                )
            render_cls._Data_ = data_cls
            render_cls._RENDER_DATA_MRO = MappingProxyType(
                {render_cls: data_cls, **render_cls._RENDER_DATA_MRO}
            )

        return data_cls


class DataNamespace(ArgsDataNamespace, metaclass=DataNamespaceMeta, _base=True):
    """DataNamespace()

    :term:`Render class`\\ -specific render data namespace.

    Raises:
        UnassociatedNamespaceError: The namespace class hasn't been associated
          [#rdn1]_ with a render class.

    Subclassing, defining (and inheriting) fields and associating with a render
    class are just as they are for :ref:`args-namespace`, except that values
    assigned to class attributes are neither required nor used.

    Every field of a namespace is **uninitialized** immediately after instantiation.
    The fields are expected to be initialized within the
    :py:meth:`~term_image.renderable.Renderable._get_render_data_` method of the
    render class with which the namespace is associated [#rdn1]_ or at some other
    point during a render operation, if necessary.

    NOTE:
        * Fields are exposed as instance attributes.
        * Instances are mutable and fields can be updated **in-place**, either
          individually by assignment to an attribute reference or in batch via
          :py:meth:`update`.
        * An instance shouldn't be copied by any means because finalizing its
          containing :py:class:`RenderData` instance may invalidate all copies of
          the namespace.

    .. Completed in /docs/source/api/renderable.rst
    """

    def __init__(self) -> None:
        pass

    def __repr__(self) -> str:
        fields_repr = {}
        for name in type(self)._FIELDS:
            try:
                fields_repr[name] = repr(getattr(self, name))
            except UninitializedDataFieldError:
                fields_repr[name] = "<uninitialized>"

        return "".join(
            (
                f"<{type(self).__name__}: ",
                ", ".join(
                    f"{name}={value_repr}" for name, value_repr in fields_repr.items()
                ),
                ">",
            )
        )

    def __getattr__(self, attr):
        if attr in type(self)._FIELDS:
            raise UninitializedDataFieldError(
                f"The render data field {attr!r} of "
                f"{type(self)._RENDER_CLS.__name__!r} has not been initialized"
            )

        raise UnknownDataFieldError(
            f"Unknown render data field {attr!r} for "
            f"{type(self)._RENDER_CLS.__name__!r}"
        )

    def __setattr__(self, attr, value):
        try:
            super().__setattr__(attr, value)
        except AttributeError:
            raise UnknownDataFieldError(
                f"Unknown render data field {attr!r} for "
                f"{type(self)._RENDER_CLS.__name__!r}"
            ) from None

    def as_dict(self) -> dict[str, Any]:
        """Copies the namespace as a dictionary.

        Returns:
            A dictionary mapping field names to their current values.

        Raises:
          UninitializedDataFieldError: A field has not been initialized.

        WARNING:
            The number and order of fields are guaranteed to be the same for a
            namespace class that defines fields, its subclasses, and all their
            instances; but beyond this, should not be relied upon as the details
            (such as the specific number or order) may change without notice.

            The order is an implementation detail of the Render Arguments/Data API
            and the number should be considered an implementation detail of the
            specific namespace subclass.
        """
        return {name: getattr(self, name) for name in type(self)._FIELDS}

    @classmethod
    def get_fields(cls) -> tuple[str]:
        """Returns the field names.

        Returns:
            A tuple of field names.

        WARNING:
            The number and order of fields are guaranteed to be the same for a
            namespace class that defines fields, its subclasses, and all their
            instances; but beyond this, should not be relied upon as the details
            (such as the specific number or order) may change without notice.

            The order is an implementation detail of the Render Arguments/Data API
            and the number should be considered an implementation detail of the
            specific namespace subclass.
        """
        return tuple(cls._FIELDS)

    def update(self, **fields: Any) -> None:
        """Updates render data fields.

        Args:
            fields: Render data fields.

        Raises:
            UnknownDataFieldError: Unknown field name(s).
        """
        if fields:
            unknown = fields.keys() - type(self)._FIELDS.keys()
            if unknown:
                raise UnknownDataFieldError(
                    f"Unknown render data field(s) {tuple(unknown)} for "
                    f"{type(self)._RENDER_CLS.__name__!r}"
                )

            setattr_ = super().__setattr__
            for field in fields.items():
                setattr_(*field)


class Frame(NamedTuple):
    """A rendered frame.

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

    The number of the rendered frame (a non-negative integer), if the frame was
    rendered by a renderable with *definite* frame count. Otherwise, the value range
    and meaning of this field is unspecified.
    """

    duration: int
    """Frame duration (in **milliseconds**)

    The duration of the rendered frame (a non-negative integer), if the frame was
    rendered by an **animated** renderable. Otherwise, the value range and meaning
    of this field is unspecified.

    HINT:
        For animated renderables, a zero value indicates that the next frame should
        be displayed immediately after (without any delay), except stated otherwise.
    """

    render_size: geometry.Size
    """Frame :term:`render size`"""

    render_output: str
    """Frame :term:`render output`"""

    def __str__(self) -> str:
        """Returns the frame :term:`render output`.

        Returns:
            The frame render output, :py:attr:`render_output`.
        """
        return self.render_output


class RenderArgsData:
    """Render arguments/data baseclass."""

    __slots__ = ("render_cls", "_namespaces")

    def __init__(
        self,
        render_cls: type[Renderable],
        namespaces: dict[type[Renderable], ArgsDataNamespace],
    ) -> None:
        self.render_cls = render_cls
        self._namespaces = MappingProxyType(namespaces)


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
        IncompatibleRenderArgsError: *init_render_args* is incompatible [#ra1]_ with
          *render_cls*.
        IncompatibleArgsNamespaceError: Incompatible [#ran2]_ render argument namespace.

    A set of render arguments (an instance of this class) is basically a container of
    render argument namespaces (instances of
    :py:class:`~term_image.renderable.ArgsNamespace`); one for
    each :term:`render class`, which has render arguments, in the Method Resolution
    Order of its associated [#ra2]_ render class.

    The namespace for each render class is derived from the following sources, in
    [descending] order of precedence:

    * *namespaces*
    * *init_render_args*
    * default render argument namespaces

    NOTE:
        Instances are immutable but updated copies can be created via :py:meth:`update`.

    .. seealso::

       :py:attr:`~term_image.renderable.Renderable.Args`
          Render class-specific render arguments.

    .. Completed in /docs/source/api/renderable.rst
    """

    # Class Attributes =========================================================

    __slots__ = ()

    __interned: ClassVar[dict[type[Renderable], RenderArgs]] = {}

    # Instance Attributes ======================================================

    render_cls: Type[Renderable]
    """The associated :term:`render class`"""

    # Special Methods ==========================================================

    def __new__(
        cls,
        render_cls: type[Renderable],
        init_or_namespace: RenderArgs | ArgsNamespace | None = None,
        *namespaces: ArgsNamespace,
    ) -> RenderArgs:
        if init_or_namespace is None:
            init_render_args = None
        elif isinstance(init_or_namespace, __class__):
            init_render_args = init_or_namespace
        elif isinstance(init_or_namespace, ArgsNamespace):
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
                raise IncompatibleRenderArgsError(
                    f"'init_render_args' (associated with "
                    f"{init_render_args.render_cls.__name__!r}) is incompatible with "
                    f"{render_cls.__name__!r} "
                )

        if not namespaces:
            # has default namespaces only
            if (
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
                and type(init_render_args) is cls
                and init_render_args.render_cls is render_cls
            ):
                return init_render_args

        return super().__new__(cls)

    def __init__(
        self,
        render_cls: type[Renderable],
        init_or_namespace: RenderArgs | ArgsNamespace | None = None,
        *namespaces: ArgsNamespace,
    ) -> None:
        # `init_or_namespace` is validated in `__new__()`.
        # `render_cls` is validated in `__new__()`, if and only if `init_or_namespace`
        # is a `RenderArgs` instance.

        if init_or_namespace is None:
            init_render_args = None
        elif isinstance(init_or_namespace, __class__):
            init_render_args = init_or_namespace
        else:
            init_render_args = None
            namespaces = (init_or_namespace, *namespaces)

        # has default namespaces only
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
            if init_render_args is self:
                return
        # Otherwise, `render_cls` wasn't validated in `__new__()`
        elif not isinstance(render_cls, RenderableMeta):
            raise arg_type_error("render_cls", render_cls)

        namespaces_dict = render_cls._ALL_DEFAULT_ARGS.copy()

        # if `init_render_args` is non-default
        if init_render_args and BASE_RENDER_ARGS is not init_render_args is not (
            type(self).__interned.get(init_render_args.render_cls)
        ):
            namespaces_dict.update(init_render_args._namespaces)

        for index, namespace in enumerate(namespaces):
            if not isinstance(namespace, ArgsNamespace):
                raise arg_type_error(f"namespaces[{index}]", namespace)
            if namespace._RENDER_CLS not in render_cls._ALL_DEFAULT_ARGS:
                raise IncompatibleArgsNamespaceError(
                    f"'namespaces[{index}]' (associated with "
                    f"{namespace._RENDER_CLS.__name__!r}) is incompatible with "
                    f"{render_cls.__name__!r} "
                )
            namespaces_dict[namespace._RENDER_CLS] = namespace

        super().__init__(render_cls, namespaces_dict)

        if intern:
            type(self).__interned[render_cls] = self

    def __init_subclass__(cls, **kwargs) -> None:
        cls.__interned = {}
        super().__init_subclass__(**kwargs)

    def __contains__(self, namespace: ArgsNamespace) -> bool:
        """Checks if a render argument namespace is contained in this set of render
        arguments.

        Args:
            namespace: A render argument namespace.

        Returns:
            ``True`` if the given namespace is equal to any of the namespaces
            contained in this set of render arguments. Otherwise, ``False``.
        """
        return None is not self._namespaces.get(namespace._RENDER_CLS) == namespace

    def __eq__(self, other: RenderArgs) -> bool:
        """Compares this set of render arguments with another.

        Args:
            other: Another set of render arguments.

        Returns:
            ``True`` if both are associated with the same :term:`render class`
            and have equal argument values. Otherwise, ``False``.
        """
        if isinstance(other, RenderArgs):
            return (
                self is other
                or self.render_cls is other.render_cls
                and self._namespaces == other._namespaces
            )

        return NotImplemented

    def __getitem__(self, render_cls: Type[Renderable]) -> ArgsNamespace:
        """Returns a constituent namespace.

        Args:
            render_cls: A :term:`render class` of which :py:attr:`render_cls` is a
              subclass (which may be :py:attr:`render_cls` itself) and which has
              render arguments.

        Returns:
            The constituent namespace associated with *render_cls*.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: :py:attr:`render_cls` is not a subclass of *render_cls*.
            NoArgsNamespaceError: *render_cls* has no render arguments.
        """
        try:
            return self._namespaces[render_cls]
        except (TypeError, KeyError):
            if not isinstance(render_cls, RenderableMeta):
                raise arg_type_error("render_cls", render_cls) from None

            if issubclass(self.render_cls, render_cls):
                raise NoArgsNamespaceError(
                    f"{render_cls.__name__!r} has no render arguments"
                ) from None

            raise ValueError(
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

    def __iter__(self) -> Iterator[ArgsNamespace]:
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

    def __repr__(self) -> str:
        return "".join(
            (
                f"{type(self).__name__}({self.render_cls.__name__}",
                ", " if self._namespaces else "",
                ", ".join(map(repr, self._namespaces.values())),
                ")",
            )
        )

    # Public Methods ===========================================================

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
            ValueError: *render_cls* is not a parent or child of :py:attr:`render_cls`.
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

        raise ValueError(
            f"{render_cls.__name__!r} is not a parent or child of "
            f"{self.render_cls.__name__!r}"
        )

    def update(
        self,
        render_cls_or_namespace: Type[Renderable] | ArgsNamespace,
        *namespaces: ArgsNamespace,
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
              itself) and which has render arguments.
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
        * :py:meth:`__getitem__` and :py:meth:`ArgsNamespace.update()
          <term_image.renderable.ArgsNamespace.update>`, for the **second** form.
        """
        if isinstance(render_cls_or_namespace, RenderableMeta):
            if namespaces:
                raise TypeError(
                    "No other positional argument is expected when the first argument "
                    "is a render class"
                )
            render_cls = render_cls_or_namespace
        elif isinstance(render_cls_or_namespace, ArgsNamespace):
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


class RenderData(RenderArgsData):
    """Render data.

    Args:
        render_cls: A :term:`render class`.

    An instance of this class is basically a container of render data namespaces
    (instances of :py:class:`~term_image.renderable.DataNamespace`); one for each
    :term:`render class`, which has render data, in the Method Resolution Order
    of its associated [#rd1]_ render class.

    NOTE:
        * Instances are immutable but the constituent namespaces are mutable.
        * Instances and their contents shouldn't be copied by any means because
          finalizing an instance may invalidate all other copies.
        * Instances should always be explicitly finalized as soon as they're no longer
          needed.

    .. seealso::

       :py:attr:`~term_image.renderable.Renderable._Data_`
          Render class-specific render data.
    """

    # Class Attributes =========================================================

    __slots__ = ("finalized",)

    # Instance Attributes ======================================================

    finalized: bool
    """Finalization status"""

    render_cls: Type[Renderable]
    """The associated :term:`render class`"""

    # Special Methods ==========================================================

    def __init__(self, render_cls: type[Renderable]) -> None:
        super().__init__(
            render_cls,
            {cls: data_cls() for cls, data_cls in render_cls._RENDER_DATA_MRO.items()},
        )
        self.finalized = False

    def __del__(self):
        try:
            self.finalize()
        except AttributeError:  # Unsuccessful initialization
            pass

    def __getitem__(self, render_cls: Type[Renderable]) -> DataNamespace:
        """Returns a constituent namespace.

        Args:
            render_cls: A :term:`render class` of which :py:attr:`render_cls` is a
              subclass (which may be :py:attr:`render_cls` itself) and which has
              render data.

        Returns:
            The constituent namespace associated with *render_cls*.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: :py:attr:`render_cls` is not a subclass of *render_cls*.
            NoDataNamespaceError: *render_cls* has no render data.
        """
        try:
            return self._namespaces[render_cls]
        except (TypeError, KeyError):
            if not isinstance(render_cls, RenderableMeta):
                raise arg_type_error("render_cls", render_cls) from None

            if issubclass(self.render_cls, render_cls):
                raise NoDataNamespaceError(
                    f"{render_cls.__name__!r} has no render data"
                ) from None

            raise ValueError(
                f"{self.render_cls.__name__!r} is not a subclass of "
                f"{render_cls.__name__!r}"
            ) from None

    def __iter__(self) -> Iterator[DataNamespace]:
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

    def __repr__(self) -> str:
        return "".join(
            (
                f"<{type(self).__name__}({self.render_cls.__name__})",
                ": " if self._namespaces else "",
                ", ".join(map(repr, self._namespaces.values())),
                ">",
            )
        )

    # Public Methods ===========================================================

    def finalize(self) -> None:
        """Finalizes the render data.

        Calls :py:meth:`~term_image.renderable.Renderable._finalize_render_data_`
        of :py:attr:`render_cls`.

        NOTE:
            This method is safe for multiple invocations on the same instance.
        """
        if not self.finalized:
            try:
                self.render_cls._finalize_render_data_(self)
            finally:
                self.finalized = True


# Variables ====================================================================

BASE_RENDER_ARGS = RenderArgs.__new__(RenderArgs, None)
