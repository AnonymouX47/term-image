``render`` Module
=================

.. module:: term_image.render

Classes
-------

.. automodulesumm:: term_image.render
   :autosummary-sections: Classes
   :autosummary-no-titles:


.. autoclass:: RenderIterator

|


Exceptions
----------

.. automodulesumm:: term_image.render
   :autosummary-sections: Exceptions
   :autosummary-no-titles:


.. autoexception:: RenderIteratorError
.. autoexception:: FinalizedIteratorError

|


Extension API
-------------

.. note::
   The following definitions are provided and required only for extended use of the
   interfaces defined above.

   Everything required for normal usage should typically be exposed in the public API.

.. _render-iterator-ext-api:

RenderIterator
^^^^^^^^^^^^^^
.. class:: RenderIterator
   :noindex:

   See :py:class:`RenderIterator` for the public API.

   .. autoclasssumm:: RenderIterator
      :autosummary-members: _from_render_data_

   .. automethod:: _from_render_data_

|

.. rubric:: Footnotes

.. [#ri-nf]
   The frame to be rendered **next** is:

   * the first frame, if no seek operation or render has occurred;
   * otherwise, the frame after that which was rendered **last**, if no seek operation
     has occurred since the last render;
   * otherwise, the frame set by the **latest** seek operation since the last render.
