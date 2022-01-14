Tutorial
========

This is a basic introduction to using the library. Please refer to :doc:`reference/index` for detailed description of the features and functionality provided by the library.

For this tutorial we'll be using the image below:

.. image:: /resources/tutorial/python.png

The image has a resolution of 288x288 pixels.

.. note:: All the samples in this tutorial occur in a terminal of **255 columns by 70 lines**.

Creating an instance
--------------------

If the file is stored on your local drive::

   from term_img.image import TermImage

   image = TermImage.from_file("python.png")

You can also use a URL if you don't have the file stored locally::

   from term_img.image import TermImage

   image = TermImage.from_url("https://raw.githubusercontent.com/AnonymouX47/term-img/docs/source/resources/python.png")

The library can also be used with PIL images::

   from PIL import Image
   from term_img.image import TermImage

   img = Image.open("python.png")
   image = TermImage(img)


Rendering an image
------------------

Rendering an image is simply the process of converting it (per-frame for animated images) into text (a string).

.. hint:: To display the rendered output in the following steps, just print the output string with ``print()``.

There are two ways to render an image:

1. Unformatted
^^^^^^^^^^^^^^
::

   str(image)

Renders the image without padding/alignment and with transparency enabled

The result should look like:

.. image:: /resources/tutorial/str.png

.. _formatted-render:

2. Formatted
^^^^^^^^^^^^
.. note::
   To see the the effect of *alignment* in the steps below, please scale the image down using::

     image.scale = .75

   This simply sets the x- and y-axis scales to 0.75. We'll see more about this later.

|

::

   format(image, "|200.^70#ffffff")

Renders the image with:

* **center** *horizontal alignment*
* a *padding width* of **200** columns
* **top** *vertical alignment*
* a *padding height* of **70** lines
* transparent background replaced with a **white** (#ffffff) *background*

.. note::
   If you get an error saying something like "padding width larger than...", either:
   
   * reduce the width (200) to something that'll fit into your terminal window, or
   * increase the size of the terminlal window

   You might use your own terminal height instead of **70**.

The result should look like:

.. image:: /resources/tutorial/white_bg.png

|

::

   f"{image:>._#.5}"

Renders the image with:

* **right** *horizontal alignment*
* **automatic** *padding width* (the current terminal width)
* **bottom** *vertical alignment*
* **automatic** *padding height* (the current terminal height with a 2-line allowance)
* transparent background with **0.5** *alpha threshold*

The result should look like:

.. image:: /resources/tutorial/alpha_0_5.png

|

::

   "{:1.1#}".format(image)

Renders the image with:

* **center** *horizontal alignment* (default)
* **no** *horizontal padding*, since **1** should be less than or equal to the image width
* **middle** *vertical alignment* (default)
* **no** *vertical padding*, since **1** is less than or equal to the *image height*
* transparency **disabled** (black background)

The result should look like:

.. image:: /resources/tutorial/no_alpha_no_align.png

You should also have a look at the complete :ref:`format-spec`\ .

Drawing/Displaying an image to/in the terminal
----------------------------------------------

There are two ways to draw an image to the terminal screen:

1. The ``draw_image()`` method
   ::

      image.draw_image()

   **NOTE:** ``draw_image()`` has various parameters for alignment/padding and transparency control.

2. Using ``print()`` with an image render output (i.e printing the rendered string)

   ::

      print(image)  # Uses str()

   OR

   ::

      print(f"{image:>200.^70#ffffff}")  # Uses format()

.. note:: For animated images, only the first method animates the output, the second only outputs the current frame.

.. Link class definition below

.. important:: All the examples above use automatic sizing and default scale.


Image render size
-----------------
| The *render size* of an image is the number of *pixels* with which the image is rendered.
| The *render size* can be retrieved via the ``size``, ``width`` and ``height`` properties.

The *render size* of an image can be in either of two states:

1. Set

   | The size is said the be *set* when the image has a fixed size.
   | In this state, the ``size`` property is a ``tuple`` of integers, the ``width`` and ``height`` properties are integers.

.. _unset-size:

2. Unset

   | The size is said to be *unset* when the image doesn't have a fixed size i.e the ``size`` property is ``None``.
   | In this case, the size with which the image is rendered is automatically calculated (based on the current terminal size) whenever the image is to be rendered.
   | In this state, the ``size``, ``width`` and ``height`` properties are ``None``.

| The render size of an image can be set when creating the instance by passing valid values to the *width* **or** *height* **keyword-only** parameter.
| For whichever axis is given, the other axis is proportionally calculated.

.. note::
   1. The argument can only be given by keyword.
   2. If neither is given, the size is *unset*.
   3. All methods of instantiation accept these arguments.

For example:

>>> image = Termimage.from_file("python.png")  # Unset
>>> image.size is None
True
>>> image = TermImage.from_file("python.png", width=60)  # width is given
>>> image.size
(60, 60)
>>> image.height
60
>>> image = TermImage.from_file("python.png", height=56)  # height is given
>>> image.size
(56, 56)
>>> image.width
56

The resulting size must fit into the terminal window

>>> image = TermImage.from_file("python.png", height=136)  # (terminal_height - 2) * 2; Still OK
>>> image.size
(136, 136)
>>> image = TermImage.from_file("python.png", height=137)  # Not OK
Traceback (most recent call last):
  .
  .
  .
term_img.exceptions.InvalidSize: The resulting rendered size will not fit into the available size

An exception is raised when both *width* and *height* are given.

>>> image = TermImage.from_file("python.png", width=100, height=100)
Traceback (most recent call last):
  .
  .
  .
ValueError: Cannot specify both width and height

The properties ``width`` and ``height`` are used to set the render size of an image after instantiation.

>>> image = Termimage.from_file("python.png")  # Unset
>>> image.size is None
True
>>> image.width = 56
>>> image.size
(56, 56)
>>> image.height
56
>>> image.height = 136
>>> image.size
(136, 136)
>>> image.width
136
>>> image.width = 200  # Even though the terminal can contain this width, it can't contain the resulting height
Traceback (most recent call last):
  .
  .
  .
term_img.exceptions.InvalidSize: The resulting rendered size will not fit into the available size

Setting ``width`` or ``height`` to ``None`` sets the size to that automatically calculated based on the current terminal size.

>>> image = Termimage.from_file("python.png")  # Unset
>>> image.size is None
True
>>> image.width = None
>>> image.size
(136, 136)
>>> image.width = 56
>>> image.size
(56, 56)
>>> image.height = None
>>> image.size
(136, 136)

The ``size`` property can only be set to one value, ``None`` and doing this :ref:`unsets <unset-size>` the *render size*.

>>> image = Termimage.from_file("python.png", width=100)
>>> image.size
(100, 100)
>>> image.size = None
>>> image.size is image.width is image.height is None
True

.. important::

   1. The currently set :ref:`font ratio <font-ratio>` is also taken into consideration when calculating or validating sizes.
   2. The resulting size must not exceed the terminal size i.e either for the given axis and the axis automatically calculated.
   3. The height is actually **twice the number of lines** that'll be used to render the image, assuming the *y-scale* is 1.0 (we'll get to that).
   4. There is a **default** 2-line allowance for the height, to allow for shell prompts or the likes.

   Therefore, **by default**, only ``terminal_height - 2`` lines are available i.e the maximum height is ``(terminal_height - 2) * 2``.

.. hint::

   See ``TermImage.set_size()`` in :doc:`reference/image` for advanced sizing control.


Image render scale
------------------

| The *render scale* of an image is the **fraction** of the *render size* that'll actually be used to render the image.
| A valid scale value is a ``float`` in the range ``0 < x <= 1`` i.e greater than zero but less than or equal to one.
| The *render scale* can be retrieved via the properties ``scale``, ``scale_x`` and ``scale_y``.

The scale can be set at instantiation by passing a value to the *scale* **keyword-only** paramter.

>>> image = Termimage.from_file("python.png", scale=(0.75, 0.6))
>>> image.scale
>>> (0.75, 0.6)

The rendered result (using ``image.draw_image()``) should look like:

.. image:: /resources/tutorial/scale_set.png

If the argument is ommited, the default scale ``(1.0, 1.0)`` is used.

>>> image = Termimage.from_file("python.png")
>>> image.scale
>>> (1.0, 1.0)

The rendered result (using ``image.draw_image()``) should look like:

.. image:: /resources/tutorial/scale_unset.png

| The properties ``scale``, ``scale_x`` and ``scale_y`` are used to set the *render scale* of an image after instantiation.
| ``scale`` accepts a ``tuple`` of two scale values or a single scale value.
| ``scale_x`` and ``scale_y`` accept a single scale value.

>>> image = Termimage.from_file("python.png")
>>> image.scale = (.3, .56756)
>>> image.scale
(0.3, 0.56756)
>>> image.scale = .5
>>> image.scale
(0.5, 0.5)
>>> image.scale_x = .75
>>> image.scale
(0.75, 0.5)
>>> image.scale_y = 1.
>>> image.scale
(0.75, 1.0)

Finally, to explore more of the library's features and functionality, check out the :doc:`reference/index` section.
