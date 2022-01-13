Configuration
=============

The configuration is divided into the following categories:

* Options
* Keys

The configuration is stored in the JSON format in a file located at ``~/.term_img/config.json``.


Config Options
--------------

These are fields whose values control various behaviours of the viewer. They are as follows:

* **cell width**: The initial width of (no of columns for) grid cells, in the TUI.

  * Type: integer
  * Valid values: x > 0

* **font ratio**: The :ref:`font ratio <font-ratio>` used, when ``--font-ratio`` CLI option is not specified.

  * Type: float
  * Valid values: x > 0.0

* **frame duration**: The the time (in seconds) between frames of an animated image, when ``--frame-duration`` CLI option is not specified.

  * Type: float
  * Valid values: x > 0.0

* **max pixels**: The maximum amount of pixels in images to be displayed in the TUI, when ``--max-pixels`` CLI option is not specified.

  * Type: integer
  * Valid values: x > 0
  * Any image having more pixels than the specified maximum will be replaced with a placeholder when displayed but can still be forced to display or viewed externally.
  * Note that increasing this will have adverse effects on performance.


Key Config
----------


