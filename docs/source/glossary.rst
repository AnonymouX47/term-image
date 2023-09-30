Glossary
========

Below are definitions of terms used across the API, exception messages and the documentation.

.. note::

   For contributors, some of these terms are also used in the source code, as variable names, in comments, docstrings, etc.

.. glossary::
   :sorted:

   active terminal
      The terminal emulator connected to the first TTY device discovered upon loading
      the ``term_image`` package.

      At times, this may also be used to refer to the TTY device itself.

      .. seealso:: :ref:`active-terminal`

   alignment
      The position of a primary :term:`render` output within its :term:`padding`.

      .. seealso:: :ref:`alignment`

   horizontal alignment
      The horizontal position of a primary :term:`render` output within its :term:`padding width`.

      .. seealso:: :ref:`alignment`

   vertical alignment
      The vertical position of a primary :term:`render` output within its :term:`padding height`.

      .. seealso:: :ref:`alignment`

   alpha threshold
      Alpha ratio/value above which a pixel is taken as **opaque** (applies only to :ref:`text-based`).

      .. seealso:: :ref:`transparency`

   animated
      Having multiple frames.
      
      The frames of an animated image are generally meant to be displayed in rapid succession, to give the effect of animation.

   cell ratio
      The **aspect ratio** (i.e the ratio of **width to height**) of a **character cell** on a terminal screen.

      .. seealso::
         :py:func:`~term_image.get_cell_ratio` and :py:func:`~term_image.set_cell_ratio`

   frame size
      The dimensions of the area used in :term:`automatic sizing`.

   frame width
      The width of the area used in :term:`automatic sizing`.

   frame height
      The height of the area used in :term:`automatic sizing`.

   render
   rendered
   rendering
      The process of encoding pixel data into a byte/character **string** (possibly including escape sequences to reproduce colour and transparency).

      This string is also called the **primary** render output and **excludes** :term:`padding`.

   rendered size
      The amount of space (columns and lines) that'll be occupied by a primary :term:`render` output **when drawn (written) onto a terminal screen**.

   .. seealso:: :py:attr:`~term_image.image.BaseImage.rendered_size`

   rendered width
      The amount of **columns** that'll be occupied by a primary :term:`render` output **when drawn (written) onto a terminal screen**.

   .. seealso:: :py:attr:`~term_image.image.BaseImage.rendered_width`

   rendered height
      The amount of **lines** that'll be occupied by a primary :term:`render` output **when drawn (written) onto a terminal screen**.

   .. seealso:: :py:attr:`~term_image.image.BaseImage.rendered_height`

   padding
      Amount of lines and columns within which to fit a primary :term:`render` output.

      .. seealso:: :ref:`padding`

   padding width
      Amount of **columns** within which to fit a primary :term:`render` output.

      Excess columns on either or both sides of the render output (depending on the :term:`horizontal alignment`) will be filled with spaces.

      .. seealso:: :ref:`padding`

   padding height
      Amount of **lines** within which to fit a primary :term:`render` output.

      Excess lines on either or both sides of the render output (depending on the :term:`vertical alignment`) will be filled with spaces.

      .. seealso:: :ref:`padding`

   pixel ratio
      The aspect ratio with which one rendered pixel is drawn/displayed on the terminal screen.

      For :ref:`graphics-based`, this is ideally ``1.0``.

      For :ref:`text-based`, this is equivalent to the :term:`cell ratio` multiplied by 2,
      since there are technically two times more pixels along the vertical axis than
      along the horizontal axis in one character cell.

   render method
   render methods
      A unique implementation of a :term:`render style`.

      .. seealso:: :ref:`render-methods`

   render style
   render styles
   style
   styles
      A specific technique for rendering or displaying pixel data (including images)
      in a terminal emulator. 

      A render style (or simply *style*) is implemented by a class, often referred to
      as a *render style class* (or simply *style class*).

      .. seealso:: :ref:`render-styles`

   manual size
   manual sizing
      A form of sizing wherein **both** the width and the height are specified to set the image size.

      This form of sizing does not preserve image aspect ratio and can only be used with :term:`fixed sizing`.

      .. seealso::
         :term:`automatic sizing`,
         :py:attr:`~term_image.image.BaseImage.size` and
         :py:meth:`~term_image.image.BaseImage.set_size`

   automatic size
   automatic sizing
      A form of sizing wherein an image's size is computed based on a combination of a
      :term:`frame size`, the image's original size and a given width **or** height.

      This form of sizing tries to preserve image aspect ratio and can be used with both
      :term:`fixed sizing` and :term:`dynamic sizing`.

      .. seealso::
         :term:`manual sizing`,
         :py:class:`~term_image.image.Size`,
         :py:attr:`~term_image.image.BaseImage.size` and
         :py:meth:`~term_image.image.BaseImage.set_size`

   dynamic size
   dynamic sizing
      A form of sizing wherein the image size is automatically computed at render-time.

      This only works with :term:`automatic sizing`.

      .. seealso::
         :term:`fixed sizing` and
         :py:attr:`~term_image.image.BaseImage.size`

   fixed size
   fixed sizing
      A form of sizing wherein the image size is set to a specific value which won't change until it is re-set.

      This works with both :term:`manual sizing` and :term:`automatic sizing`.

      .. seealso::
         :term:`dynamic sizing`,
         :py:meth:`~term_image.image.BaseImage.set_size`,
         :py:attr:`~term_image.image.BaseImage.width` and
         :py:attr:`~term_image.image.BaseImage.height`

   source
      The resource from which an image instance is initialized.

      .. seealso::
         :py:attr:`~term_image.image.BaseImage.source` and
         :py:attr:`~term_image.image.BaseImage.source_type` 

   terminal size
      The amount of columns and lines on a terminal screen at a time i.e without scrolling.

   terminal width
      The amount of columns on a terminal screen at a time.

   terminal height
      The amount of lines on a terminal screen at a time i.e without scrolling.

   descendant
      Refers to an attribute, property or setting set on a class which applies to that
      class and all its subclasses on which the attribute, property or setting is unset.
