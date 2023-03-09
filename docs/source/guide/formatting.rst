Image Formatting
=================

.. _format-spec:

Image Format Specification
--------------------------

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
