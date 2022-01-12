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
