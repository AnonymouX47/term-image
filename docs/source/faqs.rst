FAQs
====

Why?
   - Why not?
   - To improve and extend the capabilities of CLI and TUI applications.
   - Terminals emulators have always been and always will be!

What about Windows support?
   - Firstly, only the new `Windows Terminal <https://github.com/microsoft/terminal>`_ seems to have proper ANSI support and mordern terminal emulator features.
   - The library and the viewer's CLI mode currently work (with a few quirks) on Windows (i.e using ``cmd`` or ``powershell``) if the other requirements are satisfied but can't guarantee it'll always be so.

     - Drawing images and animations doesn't work completely well in ``cmd`` and ``powershell``. See :ref:`library-issues`.

   - The TUI doesn't work due to the lack of `fcntl <https://docs.python.org/3/library/fcntl.html>`_ on Windows, which is used by `urwid <https://urwid.org>`_.
   - If stuck on Windows and want to use all features, you could use WSL + Windows Terminal.

Why are colours not properly reproduced?
   - Some terminals support 24-bit colors but have a **256-color pallete**. This limits color reproduction.

Why are images out of scale?
   - If :ref:`auto-cell-ratio` is supported and enabled,

     - For the library, set :py:data:`~term_image.utils.SWAP_WIN_SIZE` to ``True``.
     - For the CLI or TUI, use the `swap win size` :ref:`config option <swap-win-size-config>`
       or the ``--swap-win-size`` command-line option.
     - If any of the above doesn't work, then open a new issue `here
       <https://github.com/AnonymouX47/term-image/issues>`_ with adequate details.

   - Otherwise,

     - For the library, adjust the :term:`cell ratio` using :py:func:`~term_image.set_cell_ratio`.
     - For the CLI or TUI, adjust the :term:`cell ratio` using the :ref:`config option <cell-ratio-config>`
       or the ``-C | --cell-ratio`` command-line option.

Why is the TUI unresponsive or slow in drawing images?
   - Drawing (not rendering) speed is **entirely** dependent on the terminal emulator itself.
   - Some terminal emulators block upon input, so rapidly repeated input could cause the terminal to be unresponsive.
