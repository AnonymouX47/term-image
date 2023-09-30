``image`` Module
================

.. module:: term_image.image

Functions
---------

These functions automatically detect the best supported render style for the
current terminal.

Since all classes share a common interface (as defined by :py:class:`BaseImage`),
any operation supported by one image class can be performed on any other image class,
except style-specific operations.

.. automodulesumm:: term_image.image
   :autosummary-sections: Functions
   :autosummary-no-titles:


.. autofunction:: auto_image_class

.. autofunction:: AutoImage

.. autofunction:: from_file

.. autofunction:: from_url


Enumerations
------------

.. automodulesumm:: term_image.image
   :autosummary-sections: Enumerations
   :autosummary-no-titles:


.. autoclass:: ImageSource
   :autosummary-sections: None

|

.. autoclass:: Size
   :autosummary-sections: None


.. _image-classes:

Image Classes
-------------

Class Hierarchy
^^^^^^^^^^^^^^

* :py:class:`BaseImage`

  * :py:class:`TextImage`

    * :py:class:`BlockImage`

  * :py:class:`GraphicsImage`

    * :py:class:`ITerm2Image`
    * :py:class:`KittyImage`


The Classes
^^^^^^^^^^^

.. automodulesumm:: term_image.image
   :autosummary-sections: Classes
   :autosummary-no-titles:
   :autosummary-exclude-members: ImageIterator


.. autoclass:: BaseImage

|

.. autoclass:: TextImage

|

.. autoclass:: BlockImage

|

.. autoclass:: GraphicsImage

|

.. autoclass:: ITerm2Image

|

.. autoclass:: KittyImage

|

.. _context-manager:

Context Management Protocol Support
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:py:class:`BaseImage` instances are context managers i.e they can be used with the ``with`` statement as in::

   with from_url(url) as image:
       ...

Using an instance as a context manager guarantees **instant** object **finalization**
(i.e clean-up/release of resources), especially for instances with URL sources
(see :py:meth:`BaseImage.from_url`).

|

Iteration Support
^^^^^^^^^^^^^^^^^

:term:`Animated` images are iterable i.e they can be used with the ``for`` statement (and other means of iteration such as unpacking) as in::

   for frame in from_file("animated.gif"):
       ...

Subsequent frames of the image are yielded on subsequent iterations.

.. note::
   - ``iter(anim_image)`` returns an :py:class:`ImageIterator` instance with a repeat count of ``1``, hence caching is disabled.
   - The frames are unformatted and transparency is enabled i.e as returned by ``str(image)``.

   For extensive or custom iteration, use :py:class:`ImageIterator` directly.


Other Classes
-------------

.. autoclass:: ImageIterator
