Library Documentation
=====================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorial
   reference/index


Known Issues
------------
* Transparent and animated images don't work well with ``cmd`` and ``powershell`` on Windows i.e within Windows Terminal.


.. _library-planned:

Planned Features
----------------
* Performance improvements
* Support for terminal graphics protocols (See `#22 <https://github.com/AnonymouX47/term-img/issues/22>`_)
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
