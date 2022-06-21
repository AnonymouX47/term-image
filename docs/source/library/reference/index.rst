Reference
=========

.. toctree::
   :maxdepth: 2
   :caption: Sub-sections:

   image
   exceptions
   utils

Top-Level Definitions
---------------------

.. autofunction:: term_image.set_query_timeout

.. autofunction:: term_image.set_font_ratio

.. autofunction:: term_image.get_font_ratio

.. autoclass:: term_image.FontRatio
   :show-inheritance:

   .. autoattribute:: AUTO
      :annotation:

   .. autoattribute:: FULL_AUTO
      :annotation:

.. autoclass:: term_image.TermImageWarning
   :show-inheritance:

|


.. _render-styles:

Render Styles
-------------

A render style is a specific implementation of representing or drawing images in a terminal emulator and each is implemented as a class.

All render styles are designed to share a common interface (with some styles having extensions), making the usage of one class directly compatibile with another, except when using style-specific features.

| Hence, the covenience functions :py:class:`AutoImage <term_image.image.AutoImage>`, :py:class:`from_file() <term_image.image.from_file>` and :py:class:`from_url() <term_image.image.from_url>` provide a means of render-style-independent usage of the library.
| These functions automatically detect the best render style supported by the :term:`active terminal`.

There a two categories of render styles:

Text-based Render Styles
^^^^^^^^^^^^^^^^^^^^^^^^

Represent images using ASCII or Unicode symbols, and in some cases, in conjunction with ANSI colour escape codes.

Classes for render styles in this category are subclasses of :py:class:`TextImage <term_image.image.TextImage>`. These include:

* :py:class:`BlockImage <term_image.image.BlockImage>`

Graphics-based Render Styles
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Represent images with actual pixels, using terminal graphics protocols.

Classes for render styles in this category are subclasses of :py:class:`GraphicsImage <term_image.image.GraphicsImage>`. These include:

* :py:class:`KittyImage <term_image.image.KittyImage>`
* :py:class:`ITerm2Image <term_image.image.ITerm2Image>`


.. _auto-font-ratio:

Auto Font Ratio
---------------

When using **auto font ratio** (in either mode), it's important to note that some
(not all) terminal emulators (e.g VTE-based ones) might have to be queried.
**See** :ref:`terminal-queries`.

If the program will never expect any useful input, **particularly while an image's
size is being set or when an image with** :ref:`unset size <unset-size>` **is being
rendered**, then using ``FULL_AUTO`` mode is OK.

Otherwise i.e if the program will be expecting input, use ``AUTO`` mode and use
:py:func:`utils.read_tty() <term_image.utils.read_tty>` to read all currently unread
input just before calling :py:func:`set_font_ratio() <term_image.set_font_ratio>`.


.. _format-spec:

Image Format Specification
--------------------------

.. code-block:: none

   [h_align] [width] [ . [v_align] [height] ] [ # [threshold | bgcolor] ] [ + {style} ]

.. note::

   * The spaces are only for clarity and not included in the syntax.
   * Fields within ``[ ]`` are optional.
   * Fields within ``{ }`` are required, though subject to any enclosing ``[ ]``.
   * ``|`` implies mutual exclusivity.
   * If the ``.`` is present, then at least one of ``v_align`` and ``height`` must be present.
   * ``width`` and ``height`` are in units of columns and lines repectively.
   * If the :term:`padding width` or :term:`padding height` is less than or equal to the image's :term:`rendered width` or :term:`rendered height` respectively, the padding has **no effect**.

* ``h_align``: This can be one of:

  * ``<`` → left
  * ``|`` → center
  * ``>`` → right
  * *Default* → center

* ``width``: padding width

  * Positive integer
  * *Default*: :term:`terminal width` minus :term:`horizontal allowance`

* ``v_align``: This can be one of:

  * ``^`` → top
  * ``-`` → middle
  * ``_`` → bottom
  * *Default* → middle

* ``height``: padding height

  * Positive integer
  * *Default*: :term:`terminal height` minus :term:`vertical allowance`

* ``#``: Transparency setting:

  * *Default*: transparency is enabled with default :term:`alpha threshold`.
  * ``threshold``: :term:`alpha threshold` e.g ``.0``, ``.325043``, ``.99999``.

    * The value must be in the range **0.0 <= threshold < 1.0**.
    * **Applies to only text-based render styles**, (i.e those not based on terminal
      graphics protocols) e.g. :py:class:`BlockImage <term_image.image.BlockImage>`.

  * ``bgcolor``: Hex color with which transparent background should be replaced e.g ``ffffff``, ``7faa52``.
  * If neither ``threshold`` nor ``bgcolor`` is present, but ``#`` is present, transparency is disabled (uses the image's default background color, or black if none).

* ``style``: Style-specific format specification.

  See each render style in :ref:`image-classes` for its own specification, if it defines.

  ``style`` can be broken down into ``[parent] [current]``, where ``current`` is the
  spec defined by a class and ``parent`` is the spec defined by a parent of that class.
  ``parent`` can in turn be **recursively** broken down as such.

See :ref:`Formatted rendering <formatted-render>` for examples.
