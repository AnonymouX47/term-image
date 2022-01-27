.. automodule:: term_img.image
   :members:
   :show-inheritance:

   The ``term_img.image`` module defines the following:

|

.. note:: It's allowed to set properties for :term:`animated` images on non-animated ones, the values are simply ignored.

|

.. _context-manager:

Context Manager Support
=======================

``TermImage`` instances are context managers i.e they can be used with the ``with`` statement such as in::

   with TermImage.from_url(url) as image:
       ...

Using an instance as a context manager ensures **100% guarantee** to of **object finalization** (i.e clean-up/release of resources), especially for instances with URL sources (see :py:meth:`TermImage.from_url`).
