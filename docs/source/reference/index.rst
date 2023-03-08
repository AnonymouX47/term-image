Reference
=========

.. attention::
   🚧 Under Construction - There might be incompatible interface changes between minor
   versions of `version zero <https://semver.org/spec/v2.0.0.html#spec-item-4>`_!

   If you want to use the library in a project while it's still on version zero,
   ensure you pin the dependency to a specific minor version e.g ``>=0.4,<0.5``.

   On this note, you probably also want to switch to the specific documentation for the
   version you're using (somewhere at the lower left corner of this page).

.. toctree::
   :maxdepth: 2
   :caption: Sub-sections:

   image
   widget
   exceptions
   utils


Top-Level Definitions
---------------------

.. autodata:: term_image.DEFAULT_QUERY_TIMEOUT

.. autoclass:: term_image.AutoCellRatio
   :show-inheritance:

   .. autoattribute:: is_supported

      Auto cell ratio support status. Can be
      
      - ``None`` -> support status not yet determined
      - ``True`` -> supported
      - ``False`` -> not supported
      
      Can be explicitly set when using auto cell ratio but want to avoid the support
      check in a situation where the support status is foreknown. Can help to avoid
      being wrongly detected as unsupported on a :ref:`queried <terminal-queries>`
      terminal that doesn't respond on time.
      
      For instance, when using multiprocessing, if the support status has been
      determined in the main process, this value can simply be passed on to and set
      within the child processes.

   .. autoattribute:: FIXED
      :annotation:

   .. autoattribute:: DYNAMIC
      :annotation:

   See :py:func:`~term_image.set_cell_ratio`.

.. autofunction:: term_image.disable_queries

.. autofunction:: term_image.disable_win_size_swap

.. autofunction:: term_image.enable_queries

.. autofunction:: term_image.enable_win_size_swap

.. autofunction:: term_image.get_cell_ratio

.. autofunction:: term_image.set_cell_ratio

.. autofunction:: term_image.set_query_timeout
