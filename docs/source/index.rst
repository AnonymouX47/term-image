.. term-image documentation master file
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to term-image's documentation!
======================================

.. attention::
   🚧 Under Construction - There might be incompatible changes between minor
   versions of `version zero <https://semver.org/spec/v2.0.0.html#spec-item-4>`_!

   If you want to use this library in a project while it's still on version zero,
   ensure you pin the dependency to a specific minor version e.g ``>=0.4,<0.5``.

   On this note, you probably also want to switch to the specific documentation for the
   version you're using (somewhere at the lower left corner of this page).

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   gallery
   tutorial
   reference/index
   faqs
   glossary


Known Issues
------------
1. Drawing of images and animations doesn't work completely well with Python for windows
   (tested in Windows Terminal and MinTTY).

   * **Description:** Some lines of the image seem to extend beyond the number of columns
     that they should normally occupy by one or two columns.
     
     This behaviour causes animations to go bizzare when lines extend beyond the width of the terminal emulator.

   * **Comment:** First of all, the issue seems to caused by the layer between Python
     and the terminal emulators (i.e the PTY implementation in use) which "consumes" the
     escape sequences used to display images.
     
     It is neither a fault of this library nor of the terminal emulators, as drawing
     of images and animations works properly with WSL within Windows Terminal.

   * **Solution:** A workaround is to leave some **horizontal allowance** of **at least
     two columns** to ensure the image never reaches the right edge of the terminal.

     This can be achieved in the library using the *h_allow* parameter of
     :py:meth:`~term_image.image.BaseImage.set_size`.

2. Some animations with the **kitty** render style within the **Kitty terminal emulator**
   might be glitchy at the moment.

   * **Description:** When the **LINES** render method is used, lines of the image
     might intermittently disappear. When the **WHOLE** render method is used,
     the entire image might intermitently dissapear.

   * **Comment:** This is due to the fact that drawn each frame requires clearing the
     previous frame off the screen, since the terminal would otherwise blend subsequent
     frames. Not clearing previous frames would break transparent animations and result
     in a performance lag that gets worse over time.

   * **Solution:** Plans are in motion to implement support for native animations i.e
     utilizing the animation features provided by the protocol
     (See `#40 <https://github.com/AnonymouX47/term-image/issues/40>`_).


Planned Features
----------------
In no particular order:

* Performance improvements
* Support for more terminal graphics protocols
  (See `#23 <https://github.com/AnonymouX47/term-image/issues/23>`_)
* More text-based render styles
  (See `#57 <https://github.com/AnonymouX47/term-image/issues/57>`_)
* Support for terminal emulators with 256 colors, 8 colors and no color
  (See `#61 <https://github.com/AnonymouX47/term-image/issues/61>`_)
* Support for terminal emulators without Unicode support
  (See `#58 <https://github.com/AnonymouX47/term-image/issues/58>`_,
  `#60 <https://github.com/AnonymouX47/term-image/issues/60>`_)
* Support for `fbTerm <https://code.google.com/archive/p/fbterm/>`_
* Support for open file objects and the ``Pathlike`` interface
* Determination of frame duration per frame during animations and image iteration
* Multithreaded animation
* Kitty image ID (See `#40 <https://github.com/AnonymouX47/term-image/issues/40>`_)
* Kitty native animation (See `#40 <https://github.com/AnonymouX47/term-image/issues/40>`_)
* Framing formatting option
* Image zoom and pan functionalities
* Setting images to their original size
* Key-value pair format specification
* Specifiy key to end animation
* Drawing images to an alternate output
* Use ``termpile`` for URL-sourced images
* Source images from raw pixel data
* IPython Extension
* Addition of urwid widgets for displaying images
* etc...


Indices and tables
==================

* :doc:`glossary`
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
