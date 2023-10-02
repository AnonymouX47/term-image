``renderable`` Module
=====================

.. module:: term_image.renderable

Classes
-------

.. automodulesumm:: term_image.renderable
   :autosummary-no-titles:
   :autosummary-members: Renderable, RenderArgs, Frame


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
      An set of render arguments (an instance of this class) is compatible with its
      associated [#ra2]_ :term:`render class` and its subclasses.
   .. [#ra2]
      The associated :term:`render class` of a set of render arguments (an instance of
      this class) is *render_cls*, accessible via :py:attr:`render_cls`.

|

.. autoclass:: term_image.renderable.RenderArgs.Namespace
   :special-members: __eq__, __hash__, __or__, __pos__, __ror__
   :inherited-members: get_render_cls

   .. seealso:: :ref:`args-namespace`.

   .. rubric:: Footnotes

   .. [#ran1]
      A render argument namespace class, its subclasses and their instances are
      associated with the :term:`render class` that defines (not inherits) the namespace
      class as its :ref:`Args <renderable-args>` attribute **at its creation**.
      The associated render class is accessible via
      :py:meth:`~term_image.renderable.RenderArgs.Namespace.get_render_cls`.
   .. [#ran2]
      A render argument namespace is compatible with its associated [#ran1]_
      :term:`render class` and the subclasses thereof.

|

.. autoclass:: Frame
   :special-members: __str__

|

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

.. autoclass:: Seek
   :autosummary-sections: None
   :undoc-members:

|

Exceptions
----------

.. automodulesumm:: term_image.renderable
   :autosummary-sections: Exceptions
   :autosummary-no-titles:


.. autoexception:: RenderableError
.. autoexception:: IndefiniteSeekError
.. autoexception:: RenderError
.. autoexception:: RenderSizeOutofRangeError
.. autoexception:: RenderArgsDataError
.. autoexception:: RenderArgsError
.. autoexception:: RenderDataError
.. autoexception:: IncompatibleArgsNamespaceError
.. autoexception:: IncompatibleRenderArgsError
.. autoexception:: NoArgsNamespaceError
.. autoexception:: NoDataNamespaceError
.. autoexception:: NonAnimatedFrameDurationError
.. autoexception:: UninitializedDataFieldError
.. autoexception:: UnknownArgsFieldError
.. autoexception:: UnknownDataFieldError

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

.. _renderable-ext-api:

Renderable
^^^^^^^^^^

.. py:class:: Renderable
   :noindex:

   See :py:class:`Renderable` for the public API.

   .. autoclasssumm:: Renderable
      :autosummary-members:
        _EXPORTED_ATTRS_,
        _EXPORTED_DESCENDANT_ATTRS_,
        _animate_,
        _clear_frame_,
        _finalize_render_data_,
        _get_frame_count_,
        _get_render_data_,
        _handle_interrupted_draw_,
        _init_render_,
        _render_,
        _Data_,

   .. autoattribute:: _EXPORTED_ATTRS_
   .. autoattribute:: _EXPORTED_DESCENDANT_ATTRS_
   .. automethod:: _animate_
   .. automethod:: _clear_frame_
   .. automethod:: _finalize_render_data_
   .. automethod:: _get_frame_count_
   .. automethod:: _get_render_data_
   .. automethod:: _get_render_size_
   .. automethod:: _handle_interrupted_draw_
   .. automethod:: _init_render_
   .. automethod:: _render_

.. autoclass:: term_image.renderable.Renderable._Data_

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
   instance associated [#ra2]_ with the render class defining this attribute or any
   of its subclasses.

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
      NoArgsNamespaceError: 'Bar' defines no render arguments

   .. note::

      * If this attribute is not defined at creation of a render class, it's set to
        ``None``.
      * If this attribute is intended to be a class, it must be defined before the
        creation of the render class.
      * Modifying this attribute after creation of the render class neither associates
        nor disassociates a render argument namespace class.

|

.. _renderable-data:

Renderable._Data_
"""""""""""""""""
.. py:attribute:: Renderable._Data_
   :noindex:
   :type: typing.ClassVar[type[RenderData.Namespace] | None]

   :term:`Render class`\ -specific render data.

   If this is a class, it defines the render data of the render class defining
   this attribute.

   An instance of this class (``_Data_``), is contained in any :py:class:`RenderData`
   instance associated [#rd1]_ with the render class defining this attribute or any
   of its subclasses.

   Also, an instance of this class (``_Data_``) is returned by
   :py:meth:`render_data[render_cls] <RenderData.__getitem__>`, where *render_data* is
   an instance of :py:class:`~term_image.renderable.RenderData` as previously described
   and *render_cls* is the render class defining this attribute.

   .. collapse:: Example

      >>> class Foo(Renderable):
      ...     class _Data_(RenderData.Namespace):
      ...         foo: str | None
      ...
      >>> foo_data = Foo._Data_()
      >>> foo_data
      <Foo._Data_: foo=<uninitialized>>
      >>> foo_data.foo
      Traceback (most recent call last):
        ...
      UninitializedDataFieldError: The render data field 'foo' of 'Foo' has not been initialized
      >>>
      >>> foo_data.foo = "FOO"
      >>> foo_data
      <Foo._Data_: foo='FOO'>
      >>> assert foo_data.foo == "FOO"
      >>>
      >>> render_data = RenderData(Foo)
      >>> render_data[Foo]
      <Foo._Data_: foo=<uninitialized>>
      >>>
      >>> render_data[Foo].foo = "bar"
      >>> render_data[Foo]
      <Foo._Data_: foo='bar'>

   On the other hand, if this is ``None``, it implies the render class defines no
   render data.

   .. collapse:: Example

      >>> class Bar(Renderable):
      ...     pass
      ...
      >>> assert Bar._Data_ is None
      >>>
      >>> render_data = RenderData(Bar)
      >>> render_data[Bar]
      Traceback (most recent call last):
        ...
      NoDataNamespaceError: 'Bar' defines no render data

   .. note::

      * If this attribute is not defined at creation of a render class, it's set to
        ``None``.
      * If this attribute is intended to be a class, it must be defined before the
        creation of the render class.
      * Modifying this attribute after creation of the render class neither associates
        nor disassociates a render data namespace class.

   .. seealso:: :py:class:`Renderable._Data_ <term_image.renderable.Renderable._Data_>`.

|

.. _args-namespace:

RenderArgs.Namespace
^^^^^^^^^^^^^^^^^^^^

.. py:class:: RenderArgs.Namespace
   :noindex:

   See :py:class:`RenderArgs.Namespace <term_image.renderable.RenderArgs.Namespace>`
   for the public API.

   .. rubric:: Subclassing

   * A Subclass cannot have multiple base classes.
   * Every **direct** subclass of this class must define fields.
   * Every **indirect** subclass (i.e subclass of a **strict** subclass) of this class
     must not define fields.
   * A **direct** subclass that has not been associated with a :term:`render class`
     cannot be further subclassed.
   * A subclass' constructor must not have required parameters.

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
   Every **indirect** subclass of this class inherits the fields and associated
   [#ran1]_ render class of its parent.

   .. collapse:: Example

      >>> class Args1(RenderArgs.Namespace):
      ...     foo: str = "FOO"
      ...
      >>> assert Args1.get_render_cls() is None
      >>> Args1.get_fields()
      mappingproxy({'foo': 'FOO'})
      >>>
      >>> class Foo(Renderable):
      ...     Args = Args1
      ...
      >>> assert Args1.get_render_cls() is Foo
      >>>
      >>> class Args2(Args1):
      ...     pass
      ...
      >>> assert Args2.get_render_cls() is Foo
      >>> Args2.get_fields()
      mappingproxy({'foo': 'FOO'})

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

RenderData
^^^^^^^^^^

.. autoclass:: RenderData
   :autosummary-exclude-members:
   :special-members: __getitem__, __iter__
   :inherited-members: render_cls
   :exclude-members: Namespace

   .. rubric:: Footnotes

   .. [#rd1]
      The associated :term:`render class` of a set of render data (an instance of this
      class) is *render_cls*, accessible via :py:attr:`render_cls`.

|

.. autoclass:: term_image.renderable.RenderData.Namespace
   :inherited-members: get_render_cls

   .. rubric:: Footnotes

   .. [#rdn1]
      A render data namespace class, its subclasses and their instances are associated
      with the :term:`render class` that defines (not inherits) the namespace class as
      its :ref:`_Data_ <renderable-data>` attribute **at its creation**.
      The associated render class is accessible via
      :py:meth:`~term_image.renderable.RenderData.Namespace.get_render_cls`.
