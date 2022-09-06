.. automodule:: term_image.utils
   :members: DISABLE_QUERIES, SWAP_WIN_SIZE, lock_tty, read_tty, set_query_timeout
   :show-inheritance:


   .. _active-terminal:

   Every mention of *active terminal* in this module refers to the first terminal
   device discovered.

   The following streams/files are checked in the following order of priority
   (along with the rationale behind the ordering):

   * ``STDOUT``: Since it's where images will most likely be drawn.
   * ``STDIN``: If output is redirected to a file or pipe and the input is a terminal,
     then using it as the :term:`active terminal` should give the expected result i.e the
     same as when output is not redirected.
   * ``STDERR``: If both output and input are redirected, it's usually unlikely for
     errors to be.
   * ``/dev/tty``: Finally, if all else fail, fall back to the process' controlling
     terminal, if any.

   The first one that is ascertained to be a terminal device is used for
   all terminal queries and terminal size computations.

   .. note::
      If none of the streams/files is a terminal device, then a warning is issued
      and affected functionality disabled.


   .. _terminal-queries:

   Terminal Queries
   ----------------

   Some functionalities of this library require the aquisition of certain information from
   the :term:`active terminal`. A single iteration of this aquisition procedure is called a
   **query**.

   A query involves three major steps:

   1. Clear all unread input from the terminal
   2. Write to the terminal
   3. Read from the terminal

   For this procedure to be successful, it must not be interrupted.

   About #1
      If the program is expecting input, use :py:func:`read_tty` (simply calling it
      without any argument is enough) to read all currently unread input
      (**without blocking**) just before any operation involving a query.

   About #2 and #3
      After sending a request to the terminal, its response is awaited. The default wait
      time is **0.1 seconds** but can be changed using :py:func:`~term_image.utils.set_query_timeout`.

      If the program includes any other function that could write to the terminal OR
      especially, read from the terminal or modify it's attributes, while a query is in
      progress, decorate it with :py:func:`lock_tty` to ensure it doesn't interfere.

      For example, the TUI included in this package (i.e ``term_image``) uses
      `urwid <https://urwid.org>`_ which reads from the terminal using
      ``urwid.raw_display.Screen.get_available_raw_input()``.
      To prevent this method from interfering with terminal queries, it is wrapped thus::

          urwid.raw_display.Screen.get_available_raw_input = lock_tty(
              urwid.raw_display.Screen.get_available_raw_input
          )

      | Also, if the :term:`active terminal` is not the controlling terminal of the process
        using this library (e.g output is redirected to another terminal), ensure no
        process that can interfere with a query (e.g a shell) is currently running in the
        active terminal.
      | For instance, such a process can be temporarily put to sleep.

   .. _queried-features:

   List of features that use terminal queries
   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

   |

   The ``term_image.utils`` module provides the following public definitions.

   .. attention::
      Any other definition in this module should be considered part of the private
      interface and can change without notice.
