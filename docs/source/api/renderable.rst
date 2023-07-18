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
   :special-members: __eq__, __hash__

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
.. class:: Renderable
   :noindex:

   See :py:class:`Renderable` for the public API.

   .. autoclasssumm:: Renderable
      :autosummary-members:
        _EXPORTED_ATTRS_,
        _EXPORTED_DESCENDANT_ATTRS_,
        _RENDER_PARAMS_,
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
   .. autoattribute:: _RENDER_PARAMS_
   .. automethod:: _animate_
   .. automethod:: _finalize_render_data_
   .. automethod:: _format_render_
   .. automethod:: _get_frame_count_
   .. automethod:: _get_render_data_
   .. automethod:: _handle_interrupted_draw_
   .. automethod:: _init_render_
   .. automethod:: _render_

|

Other Classes
^^^^^^^^^^^^^

.. automodulesumm:: term_image.renderable
   :autosummary-no-titles:
   :autosummary-members: RenderParam, RenderData

.. autoclass:: RenderData

|

.. autoclass:: RenderParam
