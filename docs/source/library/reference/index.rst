Reference
=========

.. toctree::
   :maxdepth: 2
   :caption: Sub-sections:

   image
   exceptions

Top-Level Functions
-------------------

.. autofunction:: term_image.get_font_ratio

.. autofunction:: term_image.set_font_ratio

|

.. _format-spec:

Image Format Specification
--------------------------

.. code-block:: none

   [h_align] [width] [ . [v_align] [height] ] [ # [threshold | bgcolor] ]

.. note::

   * The spaces are only for clarity and not included in the syntax.
   * Fields within ``[ ]`` are optional.
   * ``|`` implies mutual exclusivity.
   * If the ``.`` is present, then at least one of ``v_align`` and ``height`` must be present.
   * ``width`` and ``height`` are in units of columns and lines repectively.
   * If the :term:`padding width` or :term:`padding height` is less than or equal to the image's :term:`rendered width` or :term:`rendered height` respectively, the padding has **no effect**.

* ``h_align``: This can be one of:

  * ``<`` → left
  * ``|`` → center
  * ``>`` → right
  * *absent* → center

* ``width``: Integer padding width (default: :term:`terminal width` minus :term:`horizontal allowance`)

* ``v_align``: This can be one of:

  * ``^`` → top
  * ``-`` → middle
  * ``_`` → bottom
  * *absent* → middle

* ``height``: Integer padding height (default: :term:`terminal height` minus :term:`vertical allowance`)

* ``#``: Transparency setting:

  * If absent, transparency is enabled.
  * ``threshold``: Alpha ratio above which pixels are taken as opaque e.g ``.0``, ``.325043``, ``.99999``.

    * The value must be in the range **0.0 <= threshold < 1.0**.
    * **Applies to only text-based render styles**, (i.e those not based on terminal
      graphics protocols) e.g. :py:class:`TermImage <term_image.image.TermImage>`.

  * ``bgcolor``: Hex color with which transparent background should be replaced e.g ``ffffff``, ``7faa52``.
  * If neither ``threshold`` nor ``bgcolor`` is present, but ``#`` is present, transparency is disabled (uses the image's default background color, or black if none).

See :ref:`Formatted rendering <formatted-render>` for examples.
