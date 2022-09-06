Glossary
========

Below are definitions of terms used across the library's public interface, exception messages, CLI help text and the documentation.

.. note::

   For contributors, these terms are also used in the source code, as variable names, in comments, docstrings, etc.

.. glossary::
   :sorted:

   active terminal
      The first terminal device discovered upon loading the package. See :ref:`here <active-terminal>`.

   alignment
      The position to place a rendered image within its padding.

   horizontal alignment
      The position to place a rendered image within its :term:`padding width`.

   vertical alignment
      The position to place a rendered image within its :term:`padding height`.

   allowance
      The amount of space to be left un-used in a given maximum size.

   horizontal allowance
      The amount of **columns** to be left un-used in a given maximum amount of columns.

   vertical allowance
      The amount of **lines** to be left un-used in a given maximum amount of lines.

   alpha threshold
      Alpha ratio/value above which a pixel is taken as **opaque** (applies only to text-based render styles).

   animated
      Having multiple frames.
      
      The frames of an animated image are generally meant to be displayed in rapid succession, to give the effect of animation.

   available size
      The remainder after :term:`allowances <allowance>` are subtracted from the maximum size.

   available width
      The remainder after horizontal allowance is subtracted from the maximum amount of columns.

   available height
      The remainder after vertical allowance is subtracted from the maximum amount of lines.

   cell ratio
      The **aspect ratio** (i.e the ratio of **width to height**) of a **character cell** in the terminal emulator.

      See also: :py:func:`get_cell_ratio() <term_image.get_cell_ratio>` and :py:func:`set_cell_ratio() <term_image.set_cell_ratio>`.

   render
   rendered
   rendering
      To convert image pixel data into a **string** (optionally including escape sequences to produce colour and transparency).

   rendered size
      The amount of space (columns and lines) that'll be occupied by a rendered image **when drawn onto a terminal screen**.

      This is determined by the size and :term:`scale` of an image.

   rendered width
      The amount of **columns** that'll be occupied by a rendered image **when drawn onto a terminal screen**.

   rendered height
      The amount of **lines** that'll be occupied by a rendered image **when drawn onto a terminal screen**.

   padding
   padding width
      Amount of columns within which to fit an image. Excess columns on either or both sides of the image (depending on the :term:`horizontal alignment`) will be filled with spaces.

   padding height
      Amount of columns within which to fit an image. Excess columns on either or both sides of the image (depending on the :term:`vertical alignment`) will be filled with spaces.

   pixel ratio
      
      It is equvalent to the :term:`cell ratio` multiplied by 2, since there are two pixels (arranged vertically) in one character cell.

   scale
      The fraction of an image's size that'll actually be used to :term:`render` it.
      
      See also: :ref:`image-scale`.

   automatic size
   automatic sizing
      The form of sizing wherein the image size is computed based on the :term:`available size` or the image's original size.

      See also: :py:class:`~term_image.image.Size`.

   dynamic size
   dynamic sizing
      The form of sizing wherein the image size is automatically computed at render-time.

      See also: :py:attr:`~term_image.image.BaseImage.size`.

   fixed size
   fixed sizing
      The form of sizing wherein the image size is set to a specific value which won't change until it is re-set.

      See also: :py:meth:`~term_image.image.BaseImage.set_size`,
      :py:attr:`~term_image.image.BaseImage.width` and
      :py:attr:`~term_image.image.BaseImage.height`.

   source
      The resource from which an image is derived.

   terminal size
      The amount of columns and lines on a terminal screen at a time i.e without scrolling.

   terminal width
      The amount of columns on a terminal screen at a time.

   terminal height
      The amount of lines on a terminal screen at a time i.e without scrolling.
