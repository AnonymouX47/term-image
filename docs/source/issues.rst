Known Issues
============

1. Drawing of images and animations doesn't work completely well with Python **for
   Windows** (tested in Windows Terminal and MinTTY).

   * **Description:** Some lines of the image seem to extend beyond the number of
     columns that they should normally occupy by one or two columns.
     
     This behaviour causes animations to go bizarre when lines extend beyond the width
     of the terminal emulator.

   * **Comment:** First of all, the issue seems to be caused by the layer(s) between
     Python and the terminal emulators i.e the Windows Console APIs.

     It is neither a fault of this library nor of the terminal emulators, as drawing
     of images and animations works properly with WSL within Windows Terminal.

   * **Solution:** A workaround is to leave some columns between the right edge of the
     image and the right edge of the terminal.

2. Animations with the **kitty** render style on the **Kitty terminal emulator** might
   be glitchy for some images with **high resolution and size** and/or **sparse color
   distribution**.

   * **Description:** When the **LINES** render method is used, lines of the image
     might intermittently disappear. When the **WHOLE** render method is used,
     the entire image might intermitently disappear.

   * **Comment:** This is due to the fact that drawing each frame requires clearing the
     previous frame off the screen, since the terminal would otherwise blend subsequent
     frames. Not clearing previous frames would break transparent animations and result
     in a performance lag that gets worse over time.

   * **Solution:** Plans are in motion to implement support for native animations i.e
     utilizing the animation features provided by the protocol
     (See :github:issue:`40`).
