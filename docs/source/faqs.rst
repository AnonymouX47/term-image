FAQs
====

Why?
   - Why not?
   - To improve and extend the capabilities of CLI and TUI applications.
   - Terminals emulators have always been and always will be!

What about Windows support?
   - Only the new `Windows Terminal <https://github.com/microsoft/terminal>`_ seems to have proper ANSI support and mordern terminal emulator features.
   - Drawing images and animations doesn't work completely well in ``cmd`` and ``powershell``. See :ref:`issues`.
   - If stuck on Windows and want to use all features, you could use WSL + Windows Terminal.

Why are colours not properly reproduced?
   - Some terminals support 24-bit colors but have a **256-color pallete**. This limits color reproduction.

Why are images out of scale?
   - If :ref:`auto-cell-ratio` is supported and enabled,

     - call :py:func:`~term_image.enable_win_size_swap`.
       If this doesn't work, then open an issue `here
       <https://github.com/AnonymouX47/term-image/issues>`_ with adequate details.

   - Otherwise, adjust the :term:`cell ratio` using :py:func:`~term_image.set_cell_ratio`.
