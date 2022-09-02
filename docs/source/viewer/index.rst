Image viewer
============

.. attention::
   🚧 Under Construction - There might be incompatible changes (particularly in the CLI
   options and configuration) between minor versions of
   `version zero <https://semver.org/spec/v2.0.0.html#spec-item-4>`_!

   If you want to use the viewer in a project while it's still on version zero,
   ensure you pin the dependency to a specific minor version e.g ``>=0.4,<0.5``.

   On this note, you probably also want to switch to the specific documentation for the
   version you're using (somewhere at the lower left corner of this page).

.. toctree::
   :maxdepth: 2
   :caption: Sub-sections:

   tui
   config

The package comes with a standalone in-terminal image viewer based on the library.

| The image viewer is started from the command line using either the ``term-image`` command (only works if the Python scripts directory is on ``PATH``) or ``python -m term_image``.
| **\*Take note of the differences**.


Image sources
-------------

The viewer accepts the following kinds of sources:

* An image file on a local filesystem.
* A directory on a local filesystem.
* An Image URL.

Any other thing given as a :term:`source` is simply reported as invalid.


Modes
-----

The viewer can be used in two modes:

1. **CLI mode**

   In this mode, images are directly printed to standard output. It is used when:
   
   * output is not a terminal
   * there is only a single image source
   * the ``--cli`` option is specified

2. **TUI mode**

   In this mode, a Terminal/Text-based User Interface is launched, within which images
   and directories can be browsed and viewed in different ways. It is used when:

   * there is at least one non-empty directory source
   * there are multiple image sources
   * the ``--tui`` option is specified


Usage
-----

| Run ``term-image`` with the ``--help`` option to see the usage info and help text.
| All arguments and options are described there.

Note that some options are only applicable to a specific mode. If used with the other mode, they're simply ignored.

| Some options have a ``[N]`` (where *N* is a number) behind their description, it indicates that the option has a footnote attached.
| All footnotes are at the bottom of the help text.


.. _render-styles-viewer:

Render Styles
-------------

See :ref:`render-styles`.

By default, the best style supported by the :term:`active terminal` is automatically detected.
A particular render style can be specified using the ``style`` :ref:`config option <style-config>`
or the ``-S | --style`` command-line option.

| If the specified render style is graphics-based and not supported, an error notification is emitted and the process exits with code ``1`` (FAILURE, see the description below).
| If the specified render style is text-based and not [fully] supported, a warning notification is emitted but execution still proceeds with the style.

The ``--force-style`` command-line option can be used to bypass style support checks and force the usage of any style whether it's supported or not.


.. _font-ratio-viewer:

Font Ratio
----------

The :term:`font ratio` is taken into consideration when setting image sizes for **text-based** render styles, in order to preserve the aspect ratio of images drawn to the terminal.

| This value is determined by the :ref:`config option <font-ratio-config>` ``font ratio`` OR either of the command-line options ``-F | --font-ratio`` and ``--auto-font-ratio``.
| The command-line options are mutually exclusive and override the config option.

| By default (i.e without changing the config option value or specifying the command-line option), ``term-image`` tries to determine the value from the :term:`active terminal` which works on most mordern terminal emulators (currently supported on UNIX-like platforms only).
| This is probably the best choice, except the terminal emulator or platform doesn't support this feature.

| If ``term-image`` is unable to determine this value automatically, it falls back to ``0.5``, which is a reasonable value in most cases.
| In case *auto* font ratio is not supported and the fallback value does not give expected results, a different value can be specified using the config or command-line option.

.. attention::
   If using *auto* font ratio and the :term:`active terminal` is not the controlling terminal of the ``term-image`` process (e.g output is redirected to another terminal), ensure no process that might read input (e.g a shell) is currently running in the active terminal, as such a process might interfere with determining the font ratio on some terminal emulators (e.g VTE-based ones).

   For instance, the ``sleep`` command can be executed if a shell is currently running in the active terminal.


Notifications
-------------

| Notifications are event reports meant to be brought to the immediate knowledge of the user.
| Notifications have two possible destinations:

* Standard output/error stream: This is used while the TUI is **not** launched.
* TUI :ref:`notification bar <notif-bar>`: This is used while the TUI is launched.

Notifications sent to the TUI's :ref:`notification bar <notif-bar>` automatically disappear after 5 seconds.

.. _logging:

Logging
-------

Logs are more detailed event reports meant for troubleshooting and debugging purporses.

Logs are written to a file on a local filesystem. The default log file is ``~/.term_image/term_image.log`` but a different file can be specified:

* for all sessions, using the :ref:`log file <log-file>` config option
* per session, using the ``--log`` command-line option

A log entry has the following format:

.. code-block:: none

   (<pid>) (<date> <time>) <process>: <thread>: [<level>] <module>: <function>: <message>

* *pid*: The process ID of the term-image session.
* *date* and *time*: Current system date and time in the format ``%Y-%m-%d %H:%M:%S,<ms>``, where ``<ms>`` is in milliseconds.
* *process* and *thread*: The names of the python process and thread that produced the log record.

  * Only present when the *logging level* is set to ``DEBUG`` (either by ``--debug`` or ``--log-level=DEBUG``).

* *level*: The level of the log entry, this indicates it's importance.
* *module*: The package sub-module from which it originated.
* *function*: The function from which it originated.

  * Only present when running on **Python 3.8+** and *logging level* is set to ``DEBUG`` (either by ``--debug`` or ``--log-level=DEBUG``).

* *message*: The actual report describing the event that occured.


.. note::

   * Certain logs and some extra info are only provided when *logging level* is set to ``DEBUG``.
   * Log files are **appended to**, so it's safe use the same file for multiple sessions.
   * Log files are rotated upon reaching a size of **1MiB**.

     * Only the current and immediate previous log file are kept.

   * The Process ID of the ``term-image`` instance preceeds every log entry, so this can be used to distinguish and track logs from different sessions running simultaneously while using the same log file.


Exit Codes
----------
``term-image`` returns the following exit codes with the specified meanings:

* ``0`` (SUCESS): Exited normally and successfully.
* ``1`` (FAILURE): Exited due to an unhandled exception or a non-specific error.
* ``2`` (INVALID_ARG): Exited due to an invalid command-line argument value or option combination.
* ``3`` (INTERRUPTED): The program recieved an interrupt signal i.e ``SIGINT``.
* ``4`` (NO_VALID_SOURCE): Exited due to lack of any valid source.


Known Issues
------------
1. The TUI is not supported on Windows
2. Drawing of images and animations doesn't work completely well with Python for windows
   (tested in Windows Terminal and MinTTY). See :ref:`here <library-issues>` for details.

   In the viewer's CLI mode, use the ``--h-allow`` option to specify a horizontal allowance.

3. Some animations with the **kitty** render style within the **Kitty terminal emulator**
   might be glitchy at the moment. See :ref:`here <library-issues>` for details.


Planned Features
----------------
In no particular order:

* Performance improvements
* STDIN source
* Open image in external viewer
* Pattern-based file and directory exclusion
* Minimum and maximum file size
* Optionally following/skipping symlinks
* Distinguished color for symlinked entries in the list view
* Full grid view [TUI]
* Grid cells for directory entries [TUI]
* CLI grid view
* Interactive CLI mode
* Slideshow
* Zoom/Pan
* Sorting options
* Search in iist view
* Filter in list and grid views
* Alpha backaground adjustment per image
* Frame duration adjustment per animated image
* Copy:

   * Image data
   * File/Directory name
   * Full path
   * Parent directory path

* Theme customization
* Config menu
* Also check the library's :ref:`library-planned` since the viewer is based on it.
* etc...
