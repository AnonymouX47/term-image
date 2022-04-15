Core Library Definitions
========================

.. automodule:: term_img.image
   :members:
   :show-inheritance:

   The ``term_img.image`` module defines the following:

   .. note:: It's allowed to set properties for :term:`animated` images on non-animated ones, the values are simply ignored.

|

.. _context-manager:

Context Management Protocol Support
-----------------------------------

``TermImage`` instances are context managers i.e they can be used with the ``with`` statement as in::

   with TermImage.from_url(url) as image:
       ...

Using an instance as a context manager more surely guarantees **object finalization** (i.e clean-up/release of resources), especially for instances with URL sources (see :py:meth:`TermImage.from_url`).


Iteration Support
-----------------

:term:`Animated` ``TermImage`` instances are iterable i.e they can be used with the ``for`` statement (and other means of iteration such as unpacking) as in::

   for frame in TermImage.from_file("animated.gif"):
       ...

Subsequent frames of the image are yielded on subsequent iterations.

.. note::
   - ``iter(anim_image)`` returns an :py:class:`ImageIterator` instance with a repeat count of `1`, hence caching is disabled.
   - The frames are unformatted and transparency is enabled i.e as returned by ``str(image)``.

   For more extensive or custom iteration, use :py:class:`ImageIterator` directly.
