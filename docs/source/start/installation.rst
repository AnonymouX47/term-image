Installation
============

Requirements
------------

* Operating System: Unix / Linux / MacOS X / Windows (limited support, see the :doc:`/faqs`)
* `Python <https://www.python.org/>`_ >= 3.7
* A terminal emulator with **any** of the following:
  
  * support for the `Kitty graphics protocol <https://sw.kovidgoyal.net/kitty/graphics-protocol/>`_.
  * support for the `iTerm2 inline image protocol <https://iterm2.com/documentation-images.html>`_.
  * Unicode support and direct-color (truecolor) or indexed-color (256-color) support.

  **Plans to support a wider variety of terminal emulators are in motion** (see :doc:`/planned`).


Steps
-----

The latest **stable** version can be installed from `PyPI <https://pypi.org/project/term-image>`_ with:

.. code-block:: shell

   pip install term-image

The **development** version can be installed with:

.. code-block:: shell

   pip install git+https://github.com/AnonymouX47/term-image.git


Supported Terminal Emulators
----------------------------

Some terminals emulators that have been tested to meet the requirements for at least one render style include:

- Alacritty
- iTerm2
- Kitty
- Konsole
- MinTTY (on Windows)
- Terminal (on Mac OS)
- Terminology
- Termux (on Android)
- WezTerm
- Windows Terminal
- XTerm
- **libvte**-based terminal emulators such as:

  - Gnome Terminal
  - Terminator
  - Tilix

.. note::
   If you've tested ``term-image`` on any other terminal emulator that meets all
   requirements, please mention the name in a new thread under `this discussion
   <https://github.com/AnonymouX47/term-image/discussions/4>`_.

   Also, if you're having an issue with terminal support, you may report or check
   information about it in the discussion linked above.

.. note::
   Some terminal emulators support 24-bit color escape sequences but have a
   256-color pallete. This will limit color reproduction.
