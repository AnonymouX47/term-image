Installation
============

Requirements
------------

* Operating System: Unix / Linux / MacOS X / Windows (partial, see the :doc:`faqs`)
* `Python >= 3.6 <https://www.python.org/>`_
* A Terminal with full Unicode support and ANSI 24-bit color support
  * Plans are in place to [partially] support terminals not meeting this requirement.

Steps
-----

The package can be installed using `pip`

.. code-block:: shell

   pip install term-img

OR

Clone this repository using any method, then navigate into the project directory in a terminal and run

.. code-block:: shell

   pip install .


Supported Terminal Emulators
----------------------------

Some terminals emulators that have been tested to meet all major requirements are:

- **lib-VTE**-based terminals such as:

  - Gnome Terminal
  - Terminator

- Tilix
- Alacritty
- Kitty
- Windows Terminal
- Termux (on Android)

.. warning::
   With some of these terminals, there's an issue where the TUI isn't cleared off the terminal screen after exiting.

   Mannually running ``clear`` should clear the terminal screen.

.. note::
   If you've tested ``term-img`` on any other terminal emulator that meets all requirements, please mention the name in a new thread under `this discussion <https://github.com/AnonymouX47/term-img/discussions/4>`_.

   Also, if you're having an issue with terminal support, also report or view information about it in the discussion linked above.

