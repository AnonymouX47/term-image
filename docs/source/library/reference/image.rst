.. automodule:: term_img.image
   :members:
   :show-inheritance:

   The ``term_img.image`` module defines the following:

   .. note:: It's allowed to set properties for :term:`animated` images on non-animated ones, the values are simply ignored.

|

.. _context-manager:

Context Management Support
==========================

``TermImage`` supports the context management protocol i.e they can be used with the ``with`` statement such as in::

   with TermImage.from_url(url) as image:
       ...

Using an instance as a context manager more surely guarantees **object finalization** (i.e clean-up/release of resources), especially for instances with URL sources (see :py:meth:`TermImage.from_url`).
