FAQs
====

Why?
   - Why not?
   - To improve and extend the capabilities of CLI and TUI applications.
   - Terminals emulators have been an always will be!

What about Windows support?
   - Firstly, only the new `Windows Terminal <https://github.com/microsoft/terminal>`_ seems to have proper ANSI support and mordern terminal emulator features.
   - The library and the viewer's CLI mode currently work (with a few quirks) on Windows (i.e using ``cmd`` or ``powershell``) if the other requirements are satisfied but can't guarantee it'll always be so.

     - Drawing images and animations doesn't work completely well in ``cmd`` and ``powershell``. See :ref:`library-issues`.

   - The TUI doesn't work due to the lack of `fcntl <https://docs.python.org/3/library/fcntl.html>`_ on Windows, which is used by `urwid <https://urwid.org>`_.
   - If stuck on Windows and want to use all features, you could use WSL + Windows Terminal.

Why are colours not properly reproduced?
   - Some terminals support 24-bit colors but have a **256-color pallete**. This limits color reproduction.

Why do images look out-of-scale in my terminal?
   - For the library, adjust the :term:`font ratio` using :py:func:`get_font_ratio() <term_image.get_font_ratio>`.
   - For the CLI or TUI, adjust your :ref:`font ratio <font-ratio-config>` setting.

Why is the TUI unresponsive or slow in drawing images?
   - Drawing (not rendering) speed is **enteirly** dependent on the terminal emulator itself.
   - Some terminal emulators block upon input, so rapidly repeated input could cause the terminal to be unresponsive.
