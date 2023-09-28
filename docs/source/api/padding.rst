``padding`` Module
==================

.. module:: term_image.padding

Classes
-------

.. automodulesumm:: term_image.padding
   :autosummary-sections: Classes
   :autosummary-no-titles:


.. autoclass:: Padding

|

.. autoclass:: AlignedPadding

|

.. autoclass:: ExactPadding

|


Enumerations
------------

.. automodulesumm:: term_image.padding
   :autosummary-sections: Enumerations
   :autosummary-no-titles:


.. autoclass:: HAlign
   :autosummary-sections: None

|

.. autoclass:: VAlign
   :autosummary-sections: None

|


Exceptions
----------

.. automodulesumm:: term_image.padding
   :autosummary-sections: Exceptions
   :autosummary-no-titles:


.. autoexception:: PaddingError
.. autoexception:: RelativePaddingDimensionError

|


Extension API
-------------

.. note::
   The following definitions are provided and required only for extended use of the
   interfaces defined above.

   Everything required for normal usage should typically be exposed in the public API.

.. _padding-ext-api:

Padding
^^^^^^^
.. class:: Padding
   :noindex:

   See :py:class:`Padding` for the public API.

   .. note::
      Instances of subclasses should be immutable to avoid inconsistent results in
      asynchronous render operations that perform padding.

   .. autoclasssumm:: Padding
      :autosummary-members: _get_exact_dimensions_

   .. automethod:: _get_exact_dimensions_
