Image viewer
============

.. toctree::
   :maxdepth: 2
   :caption: Sub-sections:

   tui
   config

The package comes with a standalone in-terminal image viewer based on the library.

The image viewer is started from the command line using either the ``term-img`` command (only works if the Python scripts directory is on ``PATH``) or ``python -m term_img``.

.. image:: /resources/tui.png


Image sources
-------------

The viewer accepts the following kinds of sources:

* An image file on a local filesystem.
* A directory on a local filesystem.
* An Image URL.

Any other thing given as a *source* is simply reported as invalid.


Modes
-----

The viewer can be used in two modes:

1. **CLI mode**

   | In this mode, images are directly printed to standard output.
   | This mode is used whenever there is only a single image source or when the ``--cli`` option is specified.

2. **TUI**

   | In this mode, a Terminal/Text-based User Interface is launched, within which images and directories can be browsed and viewd in different ways.
   | This mode is used whenever there are multiple image sources or at least one directory source, or when the ``--tui`` option is specified.


Usage
-----

| Run ``term-img`` with the ``--help`` option to see the usage info and help text.
| All arguments and options are described there.

Note that some options are only applicable to a specific mode. If used with the other mode, they're simply ignored.

| Some options have a ``[N]`` (where *N* is a number) behind their description, it indicates that the option has a footnote attached.
| All footnotes are at the bottom of the help text.


Notifications
-------------

| Notifications are event reports meant to be brought to the immediate knowledge of the user.
| Notifications have two possible destinations:

* Standard output: This is used while the TUI is **not** launched.
* TUI :ref:`notification bar <notif-bar>`: This is used while the TUI is launched.

Notifications sent to the TUI's :ref:`notification bar <notif-bar>` automatically disappear after 5 seconds.


Logging
-------

| Logs are more detailed event reports meant for troubleshooting and debugging purporses.

| Logs are written to a file on a local filesystem. The default log file is ``~/.term_img/term_img.log`` but a different file can be specified (for a single session) using the ``--log`` CLI option.

A log entry has the following format:

.. code-block:: none

   (<pid>) (<date> <time>) [<level>] <module>: <function>: <message>

* *pid*: The process ID of the term-img session.
* *date* and *time*: Current system date and time in the format ``%d-%m-%Y %H:%M:%S``.

  * Only present when *logging level* is set to ``DEBUG`` (either by ``--debug`` or ``--log-level=DEBUG``).

* *level*: The level of the log entry, this indicates it's importance.
* *module*: The package sub-module from which it originated.
* *function*: The function from which it originated.

  * Only present when running on **Python 3.8+** and *logging level* is set to ``DEBUG`` (either by ``--debug`` or ``--log-level=DEBUG``).

* *message*: The actual report describing the event that occured.


.. note::

   * Certain logs and some extra info are only provided when *logging level* is set to ``DEBUG``.
   * Log files are **appended to**, so it's safe use the same file for multiple sessions.
   * Logs are rotated upon reaching a size of **1MiB**.

     * Only the current and immediate previous log file are kept.

   * The Process ID of the ``term-img`` instance preceeds every log entry, so this can be used to distinguish and track logs from different sessions running simultaneously while using the same log file.


Known Issues
------------


Planned Features
----------------
