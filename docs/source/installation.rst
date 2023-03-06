Installation
============

Requirements
------------

* Operating System: Unix / Linux / MacOS X / Windows (limited support, see the :doc:`faqs`)
* `Python <https://www.python.org/>`_ >= 3.7
* A terminal emulator with **any** of the following:
  
  * support for the `Kitty graphics protocol <https://sw.kovidgoyal.net/kitty/graphics-protocol/>`_.
  * support for the `iTerm2 inline image protocol <https://iterm2.com/documentation-images.html>`_.
  * full Unicode support and ANSI 24-bit color support

  **Plans to support a wider variety of terminal emulators are in motion** (see :doc:`planned`).


Steps
-----

The latest **stable** version can be installed from `PyPI <https://pypi.python.org/pypi/term-image>`_ using ``pip``:

.. code-block:: shell

   pip install term-image

The **development** version can be installed thus:

**NOTE:** it's recommended to install in an isolated virtual environment, can be created by any means.

Clone the `repository <https://github.com/AnonymouX47/term-image>`_,

.. code-block:: shell

   git clone https://github.com/AnonymouX47/term-image.git

then navigate into the local repository

.. code-block:: shell

   cd term-image

and run

.. code-block:: shell

   pip install .


Supported Terminal Emulators
----------------------------

Some terminals emulators that have been tested to meet the requirements for at least one render style include:

- **libvte**-based terminal emulators such as:

  - Gnome Terminal
  - Terminator
  - Tilix

- Kitty
- Konsole
- iTerm2
- WezTerm
- Alacritty
- Windows Terminal
- MinTTY (on Windows)
- Termux (on Android)

For style-specific support, see the descriptions of the respective :ref:`image-classes`
or the **Render Styles** section towards the bottom of the command-line help text
(i.e the output of ``term-image --help``).

.. note::
   If you've tested ``term-image`` on any other terminal emulator that meets all
   requirements, please mention the name in a new thread under `this discussion
   <https://github.com/AnonymouX47/term-image/discussions/4>`_.

   Also, if you're having an issue with terminal support, you may report or check
   information about it in the discussion linked above.

.. note::
   Some terminal emulators support 24-bit color escape sequences but have a
   256-color pallete. This will limit color reproduction.
