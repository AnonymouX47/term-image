Concepts
========

.. _render-styles:

Render Styles
-------------

A render style is a specific implementation of representing or drawing images in a
terminal emulator and each is implemented as a class.

All render styles are designed to share a common interface (with some styles having
extensions), making the usage of one class directly compatibile with another, except
when using style-specific features.

Hence, the covenience functions :py:class:`~term_image.image.AutoImage`,
:py:class:`~term_image.image.from_file` and :py:class:`~term_image.image.from_url`
provide a means of render-style-agnostic usage of the library.
These functions automatically detect the best render style supported by the :term:`active terminal`.

There are two main categories of render styles:

.. _text-based:

Text-based Render Styles
^^^^^^^^^^^^^^^^^^^^^^^^

Represent images using ASCII or Unicode symbols, and in some cases, with escape sequences to reproduce color.

Classes for render styles in this category are subclasses of
:py:class:`~term_image.image.TextImage`. These include:

* :py:class:`~term_image.image.BlockImage`

.. _graphics-based:

Graphics-based Render Styles
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Represent images with actual pixels, using terminal graphics protocols.

Classes for render styles in this category are subclasses of
:py:class:`~term_image.image.GraphicsImage`. These include:

* :py:class:`~term_image.image.KittyImage`
* :py:class:`~term_image.image.ITerm2Image`


.. _auto-cell-ratio:

Auto Cell Ratio
---------------

.. note:: This concerns :ref:`text-based` only.

The is a feature which when supported, can be used to determine the :term:`cell ratio`
directly from the terminal emulator itself. With this feature, it is possible to always
produce images of text-based render styles with correct **aspect ratio**.

When using either mode of :py:class:`~term_image.AutoCellRatio`, it's important to
note that some terminal emulators (most non-graphics-capable ones) might have queried.
See :ref:`terminal-queries`.

If the program will never expect any useful input, particularly **while an image's
size is being set/calculated**, then using :py:attr:`~term_image.AutoCellRatio.DYNAMIC`
mode is OK. For an image with :term:`dynamic size`, this includes when it's being
rendered and when its :py:attr:`~term_image.image.BaseImage.rendered_size`,
:py:attr:`~term_image.image.BaseImage.rendered_width` or
:py:attr:`~term_image.image.BaseImage.rendered_height` property is invoked.

Otherwise i.e if the program will be expecting input, use
:py:attr:`~term_image.AutoCellRatio.FIXED` mode and use
:py:func:`~term_image.utils.read_tty_all` to read all currently unread input just
before calling :py:func:`~term_image.set_cell_ratio`.


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

  * *Default*: transparency is enabled with the default :term:`alpha threshold`.
  * ``threshold``: :term:`alpha threshold` e.g ``.0``, ``.325043``, ``.99999``.

    * The value must be in the range **0.0 <= threshold < 1.0**.
    * **Applies to only text-based render styles** e.g. :py:class:`~term_image.image.BlockImage`.

  * ``bgcolor``: Color to replace transparent background with. Can be:

    * ``#`` -> The terminal's default background color (or black, if undetermined) is used.
    * A hex color e.g ``ffffff``, ``7faa52``.

  * If neither ``threshold`` nor ``bgcolor`` is present, but ``#`` is present,
    transparency is disabled (alpha channel is removed).

* ``style``: Style-specific format specifier.

  See each render style in :ref:`image-classes` for its own specification, if it defines.

  ``style`` can be broken down into ``[parent] [current]``, where ``current`` is the
  spec defined by a class and ``parent`` is the spec defined by a parent of that class.
  ``parent`` can in turn be **recursively** broken down as such.

.. seealso:: :ref:`Formatted rendering <formatted-render>` tutorial.


.. _active-terminal:

The Active Terminal
-------------------

This refers to the first terminal device discovered upon loading the ``term_image`` package.

The following streams/files are checked in the following order (along with the
rationale behind the ordering):

* ``STDOUT``: Since it's where images will most likely be drawn.
* ``STDIN``: If output is redirected to a file or pipe and the input is a terminal,
  then using it as the :term:`active terminal` should give the expected result i.e the
  same as when output is not redirected.
* ``STDERR``: If both output and input are redirected, it's usually unlikely for
  errors to be.
* ``/dev/tty``: Finally, if all else fail, fall back to the process' controlling
  terminal, if any.

The first one that is ascertained to be a terminal device is used for all
:ref:`terminal-queries` and to retrieve the terminal (and window) size on some terminal
emulators.

.. note::
   If none of the streams/files is a terminal device, then a warning is issued
   and dependent functionality is disabled.


.. _terminal-queries:

Terminal Queries
----------------

Some features of this library require the aquisition of certain information from
the :term:`active terminal`. A single iteration of this aquisition procedure is called a
**query**.

A query involves three major steps:

1. Clear all unread input from the terminal
2. Write to the terminal
3. Read from the terminal

For this procedure to be successful, it must not be interrupted.

About #1
   If the program is expecting input, use :py:func:`~term_image.utils.read_tty_all`
   to read all currently unread input (**without blocking**) just before any operation
   involving a query.

About #2 and #3
   After sending a request to the terminal, its response is awaited. The default wait
   time is :py:data:`~term_image.DEFAULT_QUERY_TIMEOUT` but can be changed
   using :py:func:`~term_image.set_query_timeout`. If the terminal emulator
   responds after the set timeout, this can result in the application program recieving
   what would seem to be garbage or ghost input (see this :ref:`FAQ <query-timeout-faq>`).

   If the program includes any other function that could write to the terminal OR
   especially, read from the terminal or modify it's attributes, while a query is in
   progress (as a result of asynchronous execution e.g multithreading or multiprocessing),
   decorate it with :py:func:`~term_image.utils.lock_tty` to ensure it doesn't interfere.

   For example, an `image viewer <https://github.com/AnonymouX47/term-image-viewer>`_
   based on this project uses `urwid <https://urwid.org>`_ which reads from the
   terminal using ``urwid.raw_display.Screen.get_available_raw_input()``.
   To prevent this method from interfering with terminal queries, it is wrapped thus::

       urwid.raw_display.Screen.get_available_raw_input = lock_tty(
           urwid.raw_display.Screen.get_available_raw_input
       )

   Also, if the :term:`active terminal` is not the controlling terminal of the process
   using this library (e.g output is redirected to another terminal), ensure no
   process that can interfere with a query (e.g a shell) is currently running in the
   active terminal. For instance, such a process can be temporarily put to sleep.


.. _queried-features:

Features that require terminal queries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In parentheses are the outcomes when the terminal doesn't support queries or when queries
are disabled.

- :ref:`auto-cell-ratio` (determined to be unsupported)
- Support checks for :ref:`graphics-based` (determined to be unsupported)
- Auto background color (black is used)
- Alpha blend for pixels above the alpha threshold in transparent renders with
  :ref:`text-based` (black is used)
- Workaround for ANSI background colors in text-based renders on the Kitty terminal
  (the workaround is disabled)

.. note::
   This list might not always be complete. In case you notice

   - any difference with any unlisted feature when terminal queries are enabled versus
     when disabled, or
   - a behaviour different from the one specified for the listed features, when terminal
     queries are disabled,

   please open an issue `here <https://github.com/AnonymouX47/term-image/issues>`_.
