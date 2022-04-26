Image viewer
============

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

   | In this mode, images are directly printed to standard output.
   | This mode is used whenever there is only a single image source or when the ``--cli`` option is specified.

2. **TUI mode**

   | In this mode, a Terminal/Text-based User Interface is launched, within which images and directories can be browsed and viewed in different ways.
   | This mode is used whenever there are multiple image sources or at least one directory source, or when the ``--tui`` option is specified.


Usage
-----

| Run ``term-image`` with the ``--help`` option to see the usage info and help text.
| All arguments and options are described there.

Note that some options are only applicable to a specific mode. If used with the other mode, they're simply ignored.

| Some options have a ``[N]`` (where *N* is a number) behind their description, it indicates that the option has a footnote attached.
| All footnotes are at the bottom of the help text.


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
* *date* and *time*: Current system date and time in the format ``%d-%m-%Y %H:%M:%S``.
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
* ``3`` (INTERRUPTED): The program recieved an interrupt signal i.e ``SIGINT``.
* ``4`` (CONFIG_ERROR): Exited due to an irremediable error while loading the user config.
* ``5`` (NO_VALID_SOURCE): Exited due to lack of any valid source.
* ``6`` (INVALID_ARG): Exited due to an invalid command-line argument value.


Known Issues
------------
1. The TUI is not supported on Windows
2. Drawing of images and animations doesn't work completely well with ``cmd`` and ``powershell`` (tested in Windows Terminal). See :ref:`library-issues` for details.

   * In the viewer's CLI mode, use the ``--h-allow`` option to specify a horizontal allowance.


Planned Features
----------------
* Performance improvements
* STDIN source
* Open in external viewer
* Pattern-based file and directory exclusion
* Minimum and maximum file size
* Optionally skipping symlinks
* Distinguished color for symlinked entries in the list view
* Full grid view
* Grid cells for directory entries
* Interactive CLI mode
* Slideshow
* Zoom/Pan
* Sorting options
* Find in iist view
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
* Overlay support for ``Image`` widgets
* etc...
