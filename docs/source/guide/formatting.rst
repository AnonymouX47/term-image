Render Formatting
=================

Render formatting is simply the modification of a primary :term:`render` output.
This is provided via:

* Python's string formatting protocol by using :py:func:`format`, :py:meth:`str.format` or
  `formatted string literals
  <https://docs.python.org/3/reference/lexical_analysis.html#formatted-string-literals>`_
  with the :ref:`format-spec`
* Parameters of :py:meth:`~term_image.image.BaseImage.draw`

The following constitute render formatting:


.. _padding:

Padding
-------

This adds whitespace around a primary :term:`render` output.
The amount of whitespace added is determined by two values (with respect to the rendered size):

* :term:`padding width`, determines horizontal padding

  * uses the ``width`` field of the :ref:`format-spec`
  * uses the *pad_width* parameter of :py:meth:`~term_image.image.BaseImage.draw`

* :term:`padding height`, determines vertical padding

  * uses the ``height`` field of the :ref:`format-spec`
  * uses the *pad_height* parameter of :py:meth:`~term_image.image.BaseImage.draw`

If the padding width or height is less than or equal to the width or height of the primary
render output, then the padding has no effect on the corresponding axis.


.. _alignment:

Alignment
---------

This determines the position of a primary :term:`render` output within it's :ref:`padding`.
The position is determined by two values:

* :term:`horizontal alignment`, determines the horizontal position

  * uses the ``h_align`` field of the :ref:`format-spec`
  * uses the *h_align* parameter of :py:meth:`~term_image.image.BaseImage.draw`

* :term:`vertical alignment`, determines the vertical position

  * uses the ``v_align`` field of the :ref:`format-spec`
  * uses the *v_align* parameter of :py:meth:`~term_image.image.BaseImage.draw`


.. _transparency:

Transparency
------------

This determines how transparent pixels are rendered.
Transparent pixels can be rendered in one of the following ways:

* Transparency disabled

  Alpha channel is ignored.

  * uses the ``#`` field of the :ref:`format-spec`, without ``threshold`` or ``bgcolor``
  * uses the *alpha* parameter of :py:meth:`~term_image.image.BaseImage.draw`, set to ``None``

* Transparency enabled with an :term:`alpha threshold`

  For :ref:`text-based`, any pixel with an alpha value above the given threshold is
  taken as **opaque**.
  For :ref:`graphics-based`, the alpha value of each pixel is used as-is.

  * uses the ``threshold`` field of the :ref:`format-spec`
  * uses the *alpha* parameter of :py:meth:`~term_image.image.BaseImage.draw`, set to a :py:class:`float` value

* Transparent pixels overlaid on a color

  May be specified to be a specific color or the default background color of the
  terminal emulator (if it can't be determined, black is used).

  * uses the ``bgcolor`` field of the :ref:`format-spec`
  * uses the *alpha* parameter of :py:meth:`~term_image.image.BaseImage.draw`, set to a string value


.. _format-spec:

Render Format Specification
---------------------------

.. code-block:: none

   [h_align] [width] [ . [v_align] [height] ] [ # [threshold | bgcolor] ] [ + {style} ]

.. note::

   * The spaces are only for clarity and not included in the syntax.
   * Fields within ``[ ]`` are optional.
   * Fields within ``{ }`` are required, though subject to any enclosing ``[ ]``.
   * ``|`` implies mutual exclusivity.
   * If the ``.`` is present, then at least one of ``v_align`` and ``height`` must be present.
   * ``width`` and ``height`` are in units of columns and lines repectively.
   * If the :term:`padding width` or :term:`padding height` is less than or equal to the image's :term:`rendered width` or :term:`rendered height` respectively, the padding has **no effect**.

* ``h_align``: This can be one of:

  * ``<`` → left
  * ``|`` → center
  * ``>`` → right
  * *Default* → center

* ``width``: padding width

  * Positive integer
  * *Default*: :term:`terminal width` minus :term:`horizontal allowance`

* ``v_align``: This can be one of:

  * ``^`` → top
  * ``-`` → middle
  * ``_`` → bottom
  * *Default* → middle

* ``height``: padding height

  * Positive integer
  * *Default*: :term:`terminal height` minus :term:`vertical allowance`

* ``#``: Transparency setting:

  * *Default*: transparency is enabled with the default :term:`alpha threshold`.
  * ``threshold``: :term:`alpha threshold` e.g ``.0``, ``.325043``, ``.99999``.

    * The value must be in the range **0.0 <= threshold < 1.0**.
    * **Applies to only text-based render styles** e.g. :py:class:`~term_image.image.BlockImage`.

  * ``bgcolor``: Color to replace transparent background with. Can be:

    * ``#`` -> The terminal's default background color (or black, if undetermined) is used.
    * A hex color e.g ``ffffff``, ``7faa52``.

  * If neither ``threshold`` nor ``bgcolor`` is present, but ``#`` is present,
    transparency is disabled (alpha channel is removed).

* ``style``: Style-specific format specifier.

  See each render style in :ref:`image-classes` for its own specification, if it defines.

  ``style`` can be broken down into ``[parent] [current]``, where ``current`` is the
  spec defined by a class and ``parent`` is the spec defined by a parent of that class.
  ``parent`` can in turn be **recursively** broken down as such.

.. seealso:: :ref:`Formatted rendering <formatted-render>` tutorial.
