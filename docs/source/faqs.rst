FAQs
====

Why?
   - Why not?
   - To improve and extend the capabilities of CLI and TUI applications.
   - Terminals emulators have always been and always will be!

What about Windows support?
   - `Windows Terminal <https://github.com/microsoft/terminal>`_ and
     `Mintty <https://mintty.github.io/>`_ (at least) have modern terminal emulator
     features including full Unicode and Truecolor support.
   - Drawing images and animations doesn't work completely well with Python **for
     Windows**.  See :doc:`issues`.
   - Note that the graphics protocols supported by Mintty would only work for Cygwin,
     MSYS and Msys2 programs, or via WSL; not for native Windows programs.

Why are colours not properly reproduced?
   - Some terminal emulators support direct-color (truecolor) sequences but use a
     **256-color** palette. This limits color reproduction.

Why are images out of scale?
   - If :ref:`auto-cell-ratio` is supported and enabled, call
     :py:func:`~term_image.enable_win_size_swap`. If this doesn't work,
     then open an issue `here <https://github.com/AnonymouX47/term-image/issues/new>`_
     with adequate details.
   - Otherwise, adjust the :term:`cell ratio` using :py:func:`~term_image.set_cell_ratio`.

.. _query-timeout-faq:

Why does my program get garbage input (possibly also written to the screen) or phantom keystrokes?
   - This is most definitely due to slow response of the terminal emulator to :ref:`terminal-queries`.
   - To resolve this, set a higher timeout using :py:func:`~term_image.set_query_timeout`. The default is :py:data:`~term_image.DEFAULT_QUERY_TIMEOUT` seconds.
   - You can also disable terminal queries using :py:func:`~term_image.disable_queries` but note that this disables certain :ref:`features <queried-features>`.
