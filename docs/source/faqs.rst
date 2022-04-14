FAQs
====

Why?
   - Why not?
   - To improve and extend the capabilities of CLI and TUI applications.
   - Terminals emulators have been an always will be!

What about Windows support?
   - Firstly, only the new `Windows Terminal <https://github.com/microsoft/terminal>`_ seems to have proper ANSI support and mordern terminal emulator features.
   - The library and the viewer's CLI mode currently work (with a few quirks) on Windows (i.e using ``cmd`` or ``powershell``) if the other requirements are satisfied but can't guarantee it'll always be so.

     - Tranparent images and animations don't work well with ``cmd`` and ``powershell`` i.e in Windows Terminal.

   - The TUI doesn't work due to the lack of `fcntl <https://docs.python.org/3/library/fcntl.html>`_ on Windows, which is used by `urwid <https://urwid.org>`_.
   - If stuck on Windows and want to use all features, you could use WSL + Windows Terminal.

Why are colours not properly reproduced?
   - Some terminals support 24-bit colors but have a **256-color pallete**. This limits color reproduction.

Why do images look out-of-scale in my terminal?
   - Simply adjust your :ref:`font ratio <font-ratio-config>` setting appropriately.

Why is the TUI unresponsive or slow in drawing images?
   - Drawing (not rendering) speed is **enteirly** dependent on the terminal emulator itself.
   - Some terminal emulators block upon input, so rapidly repeated input could cause the terminal to be unresponsive.
