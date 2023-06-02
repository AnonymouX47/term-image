Top-Level Definitions
=====================

.. module:: term_image

Constants
---------

.. autodata:: DEFAULT_QUERY_TIMEOUT


Enumerations
------------

.. autoclass:: AutoCellRatio

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

   See :py:func:`set_cell_ratio`.


Functions
---------

.. automodulesumm:: term_image
   :autosummary-sections: Functions
   :autosummary-no-titles:

.. autofunction:: disable_queries

.. autofunction:: disable_win_size_swap

.. autofunction:: enable_queries

.. autofunction:: enable_win_size_swap

.. autofunction:: get_cell_ratio

.. autofunction:: set_cell_ratio

.. autofunction:: set_query_timeout
