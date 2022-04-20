Installation
============

Requirements
------------

* Operating System: Unix / Linux / MacOS X / Windows (partial support, see the :doc:`faqs`)
* `Python >= 3.7 <https://www.python.org/>`_
* A terminal emulator with full Unicode support and ANSI 24-bit color support

  * Plans are in place to support a wider variety of terminal emulators, whether not meeting or surpassing these requirements (see :ref:`library-planned`).


Steps
-----

The latest **stable** version can be installed from `PyPI <https://pypi.python.org/pypi/term-image>`_ using ``pip``:

.. code-block:: shell

   pip install term-image

The **development** version can be installed thus:
Clone the `repository <https://github.com/AnonymouX47/term-image>`_, then navigate into the project directory in a terminal and run:

.. code-block:: shell

   pip install .


Supported Terminal Emulators
----------------------------

Some terminals emulators that have been tested to meet all major requirements are:

- **libvte**-based terminal emulators such as:

  - Gnome Terminal
  - Terminator
  - Tilix

- Kitty
- Alacritty
- Windows Terminal
- Termux (on Android)

Other terminals that only support 256 colors but meet other requirements include:
- xterm, uxterm *(256 colors)*

.. note::
   If you've tested ``term-image`` on any other terminal emulator that meets all requirements, please mention the name in a new thread under `this discussion <https://github.com/AnonymouX47/term-image/discussions/4>`_.

   Also, if you're having an issue with terminal support, you may report or view information about it in the discussion linked above.


See `here <https://github.com/termstandard/colors>`_ for information about terminal colors and a list of potentially supported terminal emulators.

.. note:: Some terminal emulators support 24-bit color codes but have a 256-color pallete. This will limit color reproduction.
