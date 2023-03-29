Concepts
========

.. _render-styles:

Render Styles
-------------

See :term:`render style`.

All render style classes are designed to share a common interface (with some having
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

Render style classes in this category are subclasses of
:py:class:`~term_image.image.TextImage`. These include:

* :py:class:`~term_image.image.BlockImage`

.. _graphics-based:

Graphics-based Render Styles
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Represent images with actual pixels, using terminal graphics protocols.

Render style classes in this category are subclasses of
:py:class:`~term_image.image.GraphicsImage`. These include:

* :py:class:`~term_image.image.KittyImage`
* :py:class:`~term_image.image.ITerm2Image`

.. _render-methods:

Render Methods
^^^^^^^^^^^^^^

A :term:`render style` may implement multiple :term:`render methods`. See the **Render
Methods** section in the description of a render style class (that implements multiple
render methods), for the description of its render methods.


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


.. _active-terminal:

The Active Terminal
-------------------

See :term:`active terminal`.

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
   If none of the streams/files is a TTY device, then a
   :py:class:`~term_image.exceptions.TermImageWarning`
   is issued and dependent functionality is disabled.


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

   For example, an :github:repo:`image viewer <AnonymouX47/termvisage>`
   based on this project uses `urwid <https://urwid.org>`_ which reads from the
   terminal using :py:meth:`urwid.raw_display.Screen.get_available_raw_input`.
   To prevent this method from interfering with terminal queries, it uses
   :py:class:`~term_image.widget.UrwidImageScreen` which overrides and wraps the
   method like::

      class UrwidImageScreen(Screen):
          @lock_tty
          def get_available_raw_input(self):
             return super().get_available_raw_input()

   Also, if the :term:`active terminal` is not the controlling terminal of the process
   using this library (e.g output is redirected to another TTY device), ensure no
   process that can interfere with a query (e.g a shell or REPL) is currently running
   in the active terminal. For instance, such a process can be temporarily put to sleep.


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
