``renderable`` Module
=====================

.. module:: term_image.renderable

Enumerations
------------

.. automodulesumm:: term_image.renderable
   :autosummary-sections: Enumerations
   :autosummary-no-titles:


.. autoclass:: FrameCount
   :autosummary-sections: None

|

.. autoclass:: FrameDuration
   :autosummary-sections: None

|

.. autoclass:: HAlign
   :autosummary-sections: None

|

.. autoclass:: VAlign
   :autosummary-sections: None

|


Classes
-------

.. automodulesumm:: term_image.renderable
   :autosummary-no-titles:
   :autosummary-members: Renderable, RenderArgs, RenderFormat, Frame


.. autoclass:: Renderable
   :special-members: __iter__, __str__

|

.. autoclass:: RenderArgs
   :autosummary-exclude-members:
   :special-members: __eq__, __getitem__, __hash__, __iter__
   :inherited-members: render_cls
   :exclude-members: Namespace

   .. rubric:: Footnotes

   .. [#ra1]
      An instance is compatible with its associated [#ra2]_ :term:`render class`
      and its subclasses.
   .. [#ra2]
      The associated :term:`render class` of an instance is *render_cls*,
      accessible via :py:attr:`render_cls`.

|

.. autoclass:: term_image.renderable.RenderArgs.Namespace
   :special-members: __eq__, __hash__, __or__, __pos__, __ror__
   :inherited-members: as_dict, as_tuple, get_fields, get_render_cls

   .. seealso:: :ref:`args-namespace`.

   .. rubric:: Footnotes

   .. [#ran1]
      A subclass, along with its subclasses (that inherit its fields and are not
      associated with another render class) and their instances, is associated
      with the :term:`render class` that defines (not inherits) that subclass as
      its :ref:`Args <renderable-args>` attribute **at its creation**.
      The render class is accessible via
      :py:meth:`~term_image.renderable.RenderArgs.Namespace.get_render_cls`.
   .. [#ran2]
      An instance is compatible with its associated [#ran1]_ :term:`render class`
      and its subclasses.

|

.. autoclass:: RenderFormat

|

.. autoclass:: Frame
   :special-members: __str__

|


Extension API
-------------

.. note::
   The following interfaces are provided and required only to extend the Renderable API
   i.e to create custom renderables or extend any of those provided by this library.

   Everything required for normal usage should typically be exposed in the public API.

   For performance reasons, all implementations of these interfaces within this library
   perform no form of argument validation, except stated otherwise. The same should apply
   to any extension or override of these interfaces. All arguments are and should be
   expected to be valid. Hence, arguments should be validated beforehand if necessary.

   In the same vein, return values of any of these interfaces will not be validated by
   the callers before use.

Renderable
^^^^^^^^^^

.. py:class:: Renderable
   :noindex:

   See :py:class:`Renderable` for the public API.

   .. autoclasssumm:: Renderable
      :autosummary-members:
        _EXPORTED_ATTRS_,
        _EXPORTED_DESCENDANT_ATTRS_,
        _RENDER_DATA_,
        _animate_,
        _finalize_render_data_,
        _format_render_,
        _get_frame_count_,
        _get_render_data_,
        _handle_interrupted_draw_,
        _init_render_,
        _render_,

   .. autoattribute:: _EXPORTED_ATTRS_
   .. autoattribute:: _EXPORTED_DESCENDANT_ATTRS_
   .. autoattribute:: _RENDER_DATA_
   .. automethod:: _animate_
   .. automethod:: _finalize_render_data_
   .. automethod:: _format_render_
   .. automethod:: _get_frame_count_
   .. automethod:: _get_render_data_
   .. automethod:: _handle_interrupted_draw_
   .. automethod:: _init_render_
   .. automethod:: _render_

|

.. _renderable-args:

Renderable.Args
"""""""""""""""
.. py:attribute:: Renderable.Args
   :noindex:
   :type: typing.ClassVar[type[RenderArgs.Namespace] | None]

   :term:`Render class`\ -specific render arguments.

   If this is a class, it defines the render arguments of the render class defining
   this attribute.

   An instance of this class (``Args``), is contained in any :py:class:`RenderArgs`
   instance compatible [#ra1]_ with the render class defining this attribute.

   Also, an instance of this class (``Args``) is returned by
   :py:meth:`render_args[render_cls] <RenderArgs.__getitem__>`, where *render_args* is
   an instance of :py:class:`~term_image.renderable.RenderArgs` as previously described
   and *render_cls* is the render class defining this attribute.

   .. collapse:: Example

      >>> class Foo(Renderable):
      ...     class Args(RenderArgs.Namespace):
      ...         foo: str | None = None
      ...
      >>> # default
      >>> Foo.Args()
      Foo.Args(foo=None)
      >>> render_args = RenderArgs(Foo)
      >>> render_args[Foo]
      Foo.Args(foo=None)
      >>>
      >>> # non-default
      >>> foo_args = Foo.Args("FOO")
      >>> foo_args
      Foo.Args(foo='FOO')
      >>> render_args = RenderArgs(Foo, foo_args.update(foo="bar"))
      >>> render_args[Foo]
      Foo.Args(foo='bar')

   On the other hand, if this is ``None``, it implies the render class defines no
   render arguments.

   .. collapse:: Example

      >>> class Bar(Renderable):
      ...     pass
      ...
      >>> assert Bar.Args is None
      >>> render_args = RenderArgs(Bar)
      >>> render_args[Bar]
      Traceback (most recent call last):
      ...
      term_image.exceptions.RenderArgsError: 'Bar' defines no render arguments

   .. note::

      * If this attribute is not defined at creation of a render class, it's set to
        ``None``.
      * If this attribute is intended to be a class, it must be defined before the
        creation of the render class.
      * Modifying this attribute after creation of the render class neither associates
        nor disassociates a render argument namespace class.

|

.. _args-namespace:

RenderArgs.Namespace
^^^^^^^^^^^^^^^^^^^^

.. py:class:: RenderArgs.Namespace
   :noindex:

   See :py:class:`RenderArgs.Namespace <term_image.renderable.RenderArgs.Namespace>`
   for the public API.

   .. rubric:: Subclassing

   * Every subclass must **either** define or inherit fields.
   * Every **direct** subclass of this class must define fields.
   * Directly subclassing multiple namespace classes is invalid.

   .. rubric:: Defining Fields

   Fields are defined as **annotated** class attributes.
   All annotated attributes of this class are taken to be fields.
   Every such attribute must be assigned a value which is taken to be the default
   value of the field.

   .. collapse:: Example

      >>> class Args(RenderArgs.Namespace):
      ...     foo: str = "FOO"
      ...     bar: str = "BAR"
      ...
      >>> Args.get_fields()
      mappingproxy({'foo': 'FOO', 'bar': 'BAR'})

   The attribute annotations are only used to identify render argument fields,
   they're never evaluated or used otherwise by any part of the Renderable API.
   The field names will be unbound from their assigned values (the default field
   values) during the creation of the subclass.

   .. rubric:: Inheriting Fields

   Fields may be inherited from any **concrete** render argument namespace
   class (i.e any **strict** subclass of this class) by subclassing it.
   By default, every **indirect** subclass (i.e subclass of a subclass) of this
   class inherits the fields and associated [#ran1]_ render class (if any), of its
   parent.

   .. collapse:: Example

      >>> class Args1(RenderArgs.Namespace):
      ...     foo: str = "FOO"
      ...
      >>> Args1.get_fields()
      mappingproxy({'foo': 'FOO'})
      >>> assert Args1.get_render_cls() is None
      >>>
      >>> class Args2(Args1):
      ...     pass
      ...
      >>> Args2.get_fields()
      mappingproxy({'foo': 'FOO'})
      >>> assert Args1.get_render_cls() is None
      >>> assert Args2.get_render_cls() is None
      >>>
      >>> class Foo(Renderable):
      ...     Args = Args2
      ...
      >>> assert Args1.get_render_cls() is None
      >>> assert Args2.get_render_cls() is Foo
      >>>
      >>> class Args3(Args2):
      ...     pass
      ...
      >>> Args3.get_fields()
      mappingproxy({'foo': 'FOO'})
      >>> assert Args1.get_render_cls() is None
      >>> assert Args2.get_render_cls() is Foo
      >>> assert Args3.get_render_cls() is Foo

   To disable inheritance of fields and associated [#ran1]_ render class, the
   ``inherit=False`` keyword argument should be passed in the class definition
   header, in which case the new subclass must define fields.

   .. collapse:: Example

      >>> class Args1(RenderArgs.Namespace):
      ...     foo: str = "FOO"
      ...
      >>> Args1.get_fields()
      mappingproxy({'foo': 'FOO'})
      >>> assert Args1.get_render_cls() is None
      >>>
      >>> class Args2(Args1, inherit=False):
      ...     pass
      ...
      Traceback (most recent call last):
        ...
      term_image.exceptions.RenderArgsDataError: No field defined or to inherit
      >>>
      >>> class Args2(Args1, inherit=False):
      ...     bar: str = "BAR"
      ...
      >>> Args2.get_fields()
      mappingproxy({'bar': 'BAR'})
      >>> assert Args1.get_render_cls() is None
      >>> assert Args2.get_render_cls() is None
      >>>
      >>> class Foo(Renderable):
      ...     Args = Args1
      ...
      >>> assert Args1.get_render_cls() is Foo
      >>> assert Args2.get_render_cls() is None
      >>>
      >>> class Args3(Args1, inherit=False):
      ...     baz: str = "BAZ"
      ...
      >>> Args3.get_fields()
      mappingproxy({'baz': 'BAZ'})
      >>> assert Args1.get_render_cls() is Foo
      >>> assert Args2.get_render_cls() is None
      >>> assert Args3.get_render_cls() is None

   When a subclass is associated [#ran1]_ with a render class, all existing
   subclasses **that inherited its fields** and haven't been associated with
   another render class automatically inherit its associated render class.

   .. collapse:: Example

      >>> class Args1(RenderArgs.Namespace):
      ...     foo: str = "FOO"
      ...
      >>> class Args2(Args1):
      ...     pass
      ...
      >>> class Args3(Args2):
      ...     pass
      ...
      >>> assert Args1.get_render_cls() is None
      >>> assert Args2.get_render_cls() is None
      >>> assert Args3.get_render_cls() is None
      >>>
      >>> class Bar(Renderable):
      ...     Args = Args3
      ...
      >>> assert Args1.get_render_cls() is None
      >>> assert Args2.get_render_cls() is None
      >>> assert Args3.get_render_cls() is Bar
      >>>
      >>> class Foo(Renderable):
      ...     Args = Args1
      ...
      >>> assert Args1.get_render_cls() is Foo
      >>> assert Args2.get_render_cls() is Foo
      >>> assert Args3.get_render_cls() is Bar

   .. important::

      Due to the design and implementation of the API, field values (including defaults)
      should:

      * (and are **expected** to) be **immutable**.

        Otherwise, such may yield unexpected behaviour during render operations or
        unexpected render outputs, **if an object used as a field value is modified**,
        as:

        * a namespace containing a mutable field value (or a set of render arguments
          containing such a namespace) may be in use in an asynchronous render
          operation,
        * different sets of render arguments may contain the same namespace, and
        * different namespaces may contain the same object as the field values.

      * be **hashable**.

        Otherwise, the namespace and any containing set of render arguments will also
        not be hashable.

   .. seealso:: :ref:`renderable-args`.

|

Other Classes
^^^^^^^^^^^^^

.. automodulesumm:: term_image.renderable
   :autosummary-no-titles:
   :autosummary-members: RenderData

.. autoclass:: RenderData
