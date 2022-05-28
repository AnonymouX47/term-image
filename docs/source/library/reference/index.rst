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

.. autoclass:: term_image.FontRatio
   :show-inheritance:

   .. autoattribute:: AUTO
      :annotation:

   .. autoattribute:: FULL_AUTO
      :annotation:

.. autofunction:: term_image.set_font_ratio

.. autofunction:: term_image.get_font_ratio

|


.. _render-styles:

Render Styles
-------------

A render style is a specific implementation of representing or drawing images in a terminal emulator and each is implemented as a class.

All render styles are designed to share a common interface (with some having extensions), making the usage of one class directly compatibile with another.

| Hence, the covenience functions :py:class:`AutoImage <term_image.image.AutoImage>`, :py:class:`from_file() <term_image.image.from_file>` and :py:class:`from_url() <term_image.image.from_url>` provide a means of render-style-independent usage of the library.
| These functions automatically detect the best render style supported by the :term:`active terminal`.

There a two categories of render styles:

Text-based Render Styles
^^^^^^^^^^^^^^^^^^^^^^^^

Represent images using ASCII or Unicode symbols, and in some cases, in conjunction with ANSI colour escape codes.

Classes for render styles in this category are subclasses of :py:class:`TextImage <term_image.image.TextImage>`. These include:

- :py:class:`TermImage <term_image.image.TermImage>`.

Graphics-based Render Styles
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Represent images with actual pixels, using terminal graphics protocols.

Classes for render styles in this category are subclasses of :py:class:`GraphicsImage <term_image.image.GraphicsImage>`. These include:

- :py:class:`KittyImage <term_image.image.KittyImage>`.


.. _auto-font-ratio:

Auto Font Ratio
---------------

When using **auto font ratio** (in either mode), it's important to note that some (not all) terminal emulators (e.g VTE-based ones) might have to be queried, which involves:

  1. Clearing all unread input from the active terminal
  2. Writing to the active terminal
  3. Reading from the active terminal

For this communication to be successful, it must not be interrupted.

About #1
   If this isn't a concern i.e the program will never expect any useful input, **particularly while an image's size is being set or when an image with** :ref:`unset size <unset-size>` **is being rendered**, then using ``FULL_AUTO`` mode is OK.

   Otherwise i.e if the program will be expecting input:

     * Use ``AUTO`` mode.
     * Use :py:func:`utils.read_tty() <term_image.utils.read_tty>` (simply calling it without any argument is enough) to read all unread input (**without blocking**) before calling :py:func:`set_font_ratio() <term_image.set_font_ratio>`.

About #2 and #3
   If the program includes any other function that could write to the terminal OR especially, read from the terminal or modify it's attributes, while a query is in progress, decorate it with :py:func:`utils.lock_input <term_image.utils.lock_input>` to ensure it doesn't interfere.

   For example, the TUI included in this package (i.e ``term_image``) uses `urwid <https://urwid.org>`_ which reads from the terminal using ``urwid.raw_display.Screen.get_available_raw_input()``. To prevent this method from interfering with terminal queries, it is wrapped thus::

       urwid.raw_display.Screen.get_available_raw_input = lock_input(
           urwid.raw_display.Screen.get_available_raw_input
       )

   Also, if the :term:`active terminal` is not the controlling terminal of the process using this library (e.g output is redirected to another terminal), ensure no process that can interfere with a query (e.g a shell) is currently running in the active terminal.

   For instance, such a process can be temporarily put to sleep.


.. _format-spec:

Image Format Specification
--------------------------

.. code-block:: none

   [h_align] [width] [ . [v_align] [height] ] [ # [threshold | bgcolor] ]

.. note::

   * The spaces are only for clarity and not included in the syntax.
   * Fields within ``[ ]`` are optional.
   * ``|`` implies mutual exclusivity.
   * If the ``.`` is present, then at least one of ``v_align`` and ``height`` must be present.
   * ``width`` and ``height`` are in units of columns and lines repectively.
   * If the :term:`padding width` or :term:`padding height` is less than or equal to the image's :term:`rendered width` or :term:`rendered height` respectively, the padding has **no effect**.

* ``h_align``: This can be one of:

  * ``<`` → left
  * ``|`` → center
  * ``>`` → right
  * *absent* → center

* ``width``: Integer padding width (default: :term:`terminal width` minus :term:`horizontal allowance`)

* ``v_align``: This can be one of:

  * ``^`` → top
  * ``-`` → middle
  * ``_`` → bottom
  * *absent* → middle

* ``height``: Integer padding height (default: :term:`terminal height` minus :term:`vertical allowance`)

* ``#``: Transparency setting:

  * If absent, transparency is enabled.
  * ``threshold``: Alpha ratio above which pixels are taken as opaque e.g ``.0``, ``.325043``, ``.99999``.

    * The value must be in the range **0.0 <= threshold < 1.0**.
    * **Applies to only text-based render styles**, (i.e those not based on terminal
      graphics protocols) e.g. :py:class:`TermImage <term_image.image.TermImage>`.

  * ``bgcolor``: Hex color with which transparent background should be replaced e.g ``ffffff``, ``7faa52``.
  * If neither ``threshold`` nor ``bgcolor`` is present, but ``#`` is present, transparency is disabled (uses the image's default background color, or black if none).

See :ref:`Formatted rendering <formatted-render>` for examples.
