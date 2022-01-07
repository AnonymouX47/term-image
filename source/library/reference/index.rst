Reference
=========

.. toctree::
   :maxdepth: 2
   :caption: The library consists of the following:

   image
   exceptions

The package defines the following top-level functions:

.. _font-ratio:

.. autofunction:: term_img.get_font_ratio

.. autofunction:: term_img.set_font_ratio

|

.. _format-spec:

Image Format Specification
--------------------------

.. code-block:: none

   [h_align] [width] [ . [v_align] [height] ] [ # [threshold | bgcolor] ]

*The spaces are only for clarity and not included in the syntax.*

* ``h_align``: This can be one of:

  * ``<`` → left
  * ``|`` → center
  * ``>`` → right
  * *absent* → center

* ``width``: Integer padding width (default: terminal width)

  * Must not be greater than the terminal width.

* ``v_align``: This can be one of:

  * ``^`` → top
  * ``-`` → middle
  * ``_`` → bottom
  * *absent* → middle

* ``height``: Integer padding height (default: terminal height, with a 2-line allowance)

  * Must not be greater than the terminal height **for animated images**.

* ``#``: Transparency setting:

   * If absent, transparency is enabled.
   * ``threshold``: Alpha ratio above which pixels are taken as opaque e.g ``.0``, ``.325043``, ``.99999``. The value must be in the range **0.0 <= threshold < 1.0**.
   * ``bgcolor``: Hex color with which transparent background should be replaced e.g ``ffffff``, ``7faa52``.
   * If neither ``threshold`` nor ``bgcolor`` is present, but ``#`` is present, transparency is disabled i.e the image has a **black background**.

.. note::

   * Fields within ``[]`` are optional.
   * ``|`` implies mutual exclusivity.
   * ``width`` and ``height`` are in units of columns and lines repectively.
   * If the padding width or height is less than or equal to the image's rendered width or height (i.e number of columns or lines occupied by the render result) respectively, the padding has **no effect**.

See :ref:`Formatted rendering <formatted-render>` for examples.
