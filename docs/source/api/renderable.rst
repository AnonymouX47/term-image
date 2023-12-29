``renderable`` Module
=====================

.. module:: term_image.renderable

Classes
-------

.. automodulesumm:: term_image.renderable
   :autosummary-no-titles:
   :autosummary-members: Renderable, RenderArgs, ArgsNamespace, Frame


.. autoclass:: Renderable
   :no-autosummary:
   :special-members: __iter__, __str__
   :exclude-members: Args

   .. autoclasssumm:: Renderable
      :autosummary-special-members: __iter__, __str__

   .. autoattribute:: Args()
      :no-value:

|

.. autoclass:: RenderArgs
   :special-members: __contains__, __eq__, __getitem__, __hash__, __iter__
   :inherited-members: render_cls

   .. rubric:: Footnotes

   .. [#ra-ass]
      The associated :term:`render class` of a set of render arguments (an instance of
      this class) is *render_cls*, accessible via :py:attr:`render_cls`.
   .. [#ra-com]
      An set of render arguments (an instance of this class) is compatible with its
      associated [#ra-ass]_ :term:`render class` and its subclasses.

|

.. autoclass:: ArgsNamespace
   :special-members: __eq__, __hash__, __or__, __pos__, __ror__
   :inherited-members: get_render_cls

   .. seealso:: :ref:`args-namespace`.

   .. rubric:: Footnotes

   .. [#an-ass]
      A render argument namespace class (**that has fields**), along with its
      subclasses and their instances, is associated with the :term:`render class`
      that was :ref:`specified <associating-namespace>` **at its creation**.
      The associated render class is accessible via :py:meth:`get_render_cls`.
   .. [#an-com]
      A render argument namespace is compatible with its associated [#an-ass]_
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


.. autoclass:: FrameCount()
   :autosummary-sections: None

|

.. autoclass:: FrameDuration()
   :autosummary-sections: None

|

.. autoclass:: Seek()
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
.. autoexception:: UnassociatedNamespaceError
.. autoexception:: UninitializedDataFieldError
.. autoexception:: UnknownArgsFieldError
.. autoexception:: UnknownDataFieldError

|

Type Variables and Aliases
--------------------------

.. autotypevar:: OptionalPaddingT
   :no-type:

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
        _Data_,
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

   .. autoattribute:: _Data_()
      :no-value:
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

|

.. _args-namespace:

ArgsNamespace
^^^^^^^^^^^^^^^^^^^^

.. py:class:: ArgsNamespace
   :noindex:

   See :py:class:`~term_image.renderable.ArgsNamespace` for the public API.


   Defining Fields
   """""""""""""""

   Fields are defined as **annotated** class attributes. All annotated attributes of a
   subclass are taken to be fields. Every such attribute must be assigned a value which
   is taken to be the default value of the field.

   .. collapse:: Example

      >>> class Foo(Renderable):
      ...     pass
      ...
      >>> class FooArgs(ArgsNamespace, render_cls=Foo):
      ...     foo: str = "FOO"
      ...     bar: str = "BAR"
      ...
      >>> FooArgs.get_fields()
      mappingproxy({'foo': 'FOO', 'bar': 'BAR'})

   The attribute annotations are only used to identify the fields, they're never
   evaluated or used otherwise by any part of the Renderable API.
   The field names will be unbound from their assigned values (the default field
   values) during the creation of the class.

   .. note::

      A subclass that :ref:`inherits <inheriting-fields>` fields must not define fields.


   .. _associating-namespace:

   Associating With a Render Class
   """""""""""""""""""""""""""""""

   To associate a namespace class with a render class, the render class should be
   specified via the *render_cls* keyword argument in the class definition header.

   .. collapse:: Example

      >>> class Foo(Renderable):
      ...     pass
      ...
      >>> class FooArgs(ArgsNamespace, render_cls=Foo):
      ...     foo: str = "FOO"
      ...
      >>> FooArgs.get_render_cls() is Foo
      True

   .. note::

      * A subclass that **has fields** must be associated [#an-ass]_ with a render class.
      * A subclass that **has NO fields** cannot be associated with a render class.
      * A subclass that :ref:`inherits <inheriting-fields>` fields cannot be
        reassociated with another render class.

   .. attention::

      Due to the design of the Renderable API, if a render class is intended to have
      a namespace class asssociated, the namespace class should be associated with it
      before it is subclassed or any :py:class:`~term_image.renderable.RenderArgs`
      instance associated with it is created.


   .. _inheriting-fields:

   Inheriting Fields
   """""""""""""""""

   Fields are inherited from any associated [#an-ass]_ render argument namespace class
   (i.e anyone that **has fields**) by subclassing it. The new subclass inherits both
   the fields and associated render class of its parent.

   .. collapse:: Example

      >>> class Foo(Renderable):
      ...     pass
      ...
      >>> class FooArgs(ArgsNamespace, render_cls=Foo):
      ...     foo: str = "FOO"
      ...
      >>> FooArgs.get_render_cls() is Foo
      True
      >>> FooArgs.get_fields()
      mappingproxy({'foo': 'FOO'})
      >>>
      >>> class SubFooArgs(FooArgs):
      ...     pass
      ...
      >>> SubFooArgs.get_render_cls() is Foo
      True
      >>> SubFooArgs.get_fields()
      mappingproxy({'foo': 'FOO'})

   .. note::

      A subclass that inherits fields:

      * must not define fields.
      * cannot be reassociated with another render class.


   Other Notes
   """""""""""

   .. note::

      * A subclass cannot have multiple base classes.
      * The constructor of any subclass that **has fields** must not have required
        parameters.

   .. tip::

      A subclass may neither define nor inherit fields. Such can be used as a base
      class for other namespace classes.

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
        * different namespaces may contain the same object as field values.

      * be **hashable**.

        Otherwise, the namespace and any containing set of render arguments will also
        not be hashable.

|

Other Classes
^^^^^^^^^^^^^

.. automodulesumm:: term_image.renderable
   :autosummary-no-titles:
   :autosummary-members: RenderData, DataNamespace, RenderableData


.. autoclass:: RenderData
   :special-members: __getitem__, __iter__
   :inherited-members: render_cls

   .. rubric:: Footnotes

   .. [#rd-ass]
      The associated :term:`render class` of a set of render data (an instance of this
      class) is *render_cls*, accessible via :py:attr:`render_cls`.

|

.. autoclass:: DataNamespace
   :inherited-members: get_render_cls

   .. rubric:: Footnotes

   .. [#dn-ass]
      A render data namespace class (**that has fields**), along with its
      subclasses and their instances, is associated with the :term:`render class`
      that was :ref:`specified <associating-namespace>` **at its creation**.
      The associated render class is accessible via :py:meth:`get_render_cls`.

|

.. autoclass:: RenderableData
