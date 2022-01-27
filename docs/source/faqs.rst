FAQs
====

Why?
   - Why not?
   - To improve and extend the capabilities of CLI and TUI applications.
   - Terminals are here to stay!

What about Windows support?
   - Firstly, only the new `Windows Terminal <https://github.com/microsoft/terminal>`_ seems to have proper ANSI support and mordern terminal emulator features.
   - The CLI-only mode currently works on Windows (i.e using CMD or Powershell) if the other requirements are satisfied but can't guarantee it'll always be so.
   - The TUI doesn't work due to lack of `urwid <https://urwid.org>`_ support.
   - If stuck on Windows, you could use WSL + Windows Terminal.

Why do images look out-of-scale in my terminal?
   - Simply adjust your :ref:`font ratio <font-ratio-config>` setting appropriately.

Why is the TUI unresponsive or slow in drawing images?
   - Drawing (not rendering) speed is **enteirly** dependent on the terminal emulator itself.
   - Some terminal emulators block upon input, so rapidly repeated input could cause the terminal to be unresponsive. An example of such is `Tilix <https://gnunn1.github.io/tilix-web/>`_.
