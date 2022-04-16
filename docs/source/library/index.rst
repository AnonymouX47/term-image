Library Documentation
=====================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorial
   reference/index


.. _library-issues:

Known Issues
------------
1. Drawing of images and animations doesn't work completely well with ``cmd`` and ``powershell`` (tested in Windows Terminal).

   * **Description**: Some lines of the image seem to extend beyond the number of columns that it should normally occupy by about one or two columns. This behaviour causes animations to go bizzare.

   * **Comment**: First of all, the issue is inherent to these shells and neither a fault of this library nor the Windows Terminal, as drawing images and animations works properly with WSL within Windows Terminal.

   * **Solution**: A workaround is to leave some **horizontal allowance** of **at least two columns** to ensure the image never reaches the right edge of the terminal. This can be achieved in the library by using the *h_allow* parameter of :py:meth:`TermImage.set_size() <term_img.image.TermImage.set_size>`.


.. _library-planned:

Planned Features
----------------
* Performance improvements
* Support for terminal graphics protocols (See `#23 <https://github.com/AnonymouX47/term-img/issues/23>`_)
* More text-based render styles

  * Greyscale rendering (Good for 256-color terminals)
  * ASCII-based rendering (Support for terminals without unicode or 24-bit color support)
  * Black and white rendering

* Support for open file objects and ``Pathlike`` objects
* Determination of frame duration per frame during animations and image iteration
* Image source type property
* Framing formatting option
* Jumping to a specified frame during image iteration
* Image zoom and pan functionalities
* Addition of urwid widgets for displaying images
* etc...
