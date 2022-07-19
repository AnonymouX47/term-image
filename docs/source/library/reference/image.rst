Core Library Definitions
========================

.. automodule:: term_image.image

   The ``term_image.image`` subpackage defines the following:


   Convenience Functions
   ---------------------

   These functions automatically detect the best supported render style for the
   current terminal.

   Since all classes define a common interface, any operation supported by one image
   class can be performed on any other image class, except stated otherwise.

   .. autofunction:: AutoImage

   .. autofunction:: from_file

   .. autofunction:: from_url


   .. _image-classes:

   Image Classes
   -------------

   **Class Hierachy:**

   * :py:class:`ImageSource`
   * :py:class:`Size`
   * :py:class:`BaseImage`

     * :py:class:`GraphicsImage`

       * :py:class:`ITerm2Image`
       * :py:class:`KittyImage`

     * :py:class:`TextImage`

       * :py:class:`BlockImage`

   .. autoclass:: ImageSource
      :members:
      :show-inheritance:

   .. autoclass:: Size
      :members:
      :show-inheritance:

   |

   .. note:: It's allowed to set properties for :term:`animated` images on non-animated ones, the values are simply ignored.

   .. autoclass:: BaseImage
      :members:
      :show-inheritance:

   |

   .. autoclass:: GraphicsImage
      :members:
      :show-inheritance:

   |

   .. autoclass:: TextImage
      :members:
      :show-inheritance:

   |

   .. autoclass:: BlockImage
      :members:
      :show-inheritance:

   |

   .. autoclass:: ITerm2Image
      :members:
      :show-inheritance:

   |

   .. autoclass:: KittyImage
      :members:
      :show-inheritance:

   |

   .. autoclass:: ImageIterator
      :members:
      :show-inheritance:

|

.. _context-manager:

Context Management Protocol Support
-----------------------------------

``BaseImage`` instances are context managers i.e they can be used with the ``with`` statement as in::

   with from_url(url) as image:
       ...

Using an instance as a context manager more surely guarantees **object finalization** (i.e clean-up/release of resources), especially for instances with URL sources (see :py:meth:`BaseImage.from_url`).


Iteration Support
-----------------

:term:`Animated` ``BaseImage`` instances are iterable i.e they can be used with the ``for`` statement (and other means of iteration such as unpacking) as in::

   for frame in from_file("animated.gif"):
       ...

Subsequent frames of the image are yielded on subsequent iterations.

.. note::
   - ``iter(anim_image)`` returns an :py:class:`ImageIterator` instance with a repeat count of `1`, hence caching is disabled.
   - The frames are unformatted and transparency is enabled i.e as returned by ``str(image)``.

   For more extensive or custom iteration, use :py:class:`ImageIterator` directly.
