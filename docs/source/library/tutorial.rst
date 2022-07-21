Tutorial
========

This is a basic introduction to using the library. Please refer to the :doc:`reference/index` for detailed description of the features and functionality provided by the library.

For this tutorial we'll be using the image below:

.. image:: /resources/tutorial/python.png

The image has a resolution of **288x288 pixels**.

.. note:: All the samples in this tutorial occured in a terminal window of **255 columns by 70 lines**.


Creating an instance
--------------------

Image instances can be created using the convinience functions :py:func:`~term_image.image.AutoImage`,
:py:func:`~term_image.image.from_file` and :py:func:`~term_image.image.from_url`.
These automatically detect the best style supported by the :term:`active terminal`.

Instances can also be created using the :ref:`image-classes` directly via their respective
constructors or :py:meth:`~term_image.image.BaseImage.from_file` and
:py:meth:`~term_image.image.BaseImage.from_url` methods.

If the file is stored on your local filesystem::

   from term_image.image import from_file

   image = from_file("path/to/python.png")

You can also use a URL if you don't have the file stored locally::

   from term_image.image import from_url

   image = from_url("https://raw.githubusercontent.com/AnonymouX47/term-image/main/docs/source/resources/tutorial/python.png")

The library can also be used with PIL image instances::

   from PIL import Image
   from term_image.image import AutoImage

   img = Image.open("python.png")
   image = AutoImage(img)


Rendering an image
------------------

Rendering an image is simply the process of converting it (per-frame for :term:`animated`
images) into text (a string).

.. hint:: To display the rendered image in the following steps, just pass the string as an argument to ``print()``.

There are two ways to render an image:

1. Unformatted
^^^^^^^^^^^^^^
::

   str(image)

Renders the image without *padding/alignment* and with transparency enabled

The result should look like:

.. image:: /resources/tutorial/str.png

.. _formatted-render:

2. Formatted
^^^^^^^^^^^^
.. note::
   To see the effect of *alignment* in the steps below, please scale the image down using::

     image.scale = 0.75

   This simply sets the x-axis and y-axis :term:`scales <scale>` of the image to ``0.75``.
   We'll see more about this :ref:`later <image-scale>`.

Below are examples of formatted rendering:

::

   format(image, "|200.^70#ffffff")

Renders the image with:

* **center** :term:`horizontal alignment`
* a :term:`padding width` of **200** columns
* **top** :term:`vertical alignment`
* a :term:`padding height` of **70** lines
* transparent background replaced with a **white** (``#ffffff``) background

.. note::
   You might have to reduce the padding width (200) and/or height (70) to something that'll
   fit into your terminal window, or increase the size of the terminlal window

The result should look like:

.. image:: /resources/tutorial/white_bg.png

|

::

   f"{image:>._#.5}"

Renders the image with:

* **right** :term:`horizontal alignment`
* **automatic** :term:`padding width` (the current :term:`terminal width` minus :term:`horizontal allowance`)
* **bottom** :term:`vertical alignment`
* **automatic** :term:`padding height` (the current :term:`terminal height` minus :term:`vertical allowance`)
* transparent background with **0.5** :term:`alpha threshold`

The result should look like:

.. image:: /resources/tutorial/alpha_0_5.png

|

::

   "{:1.1#}".format(image)

Renders the image with:

* **center** :term:`horizontal alignment` (default)
* **no** horizontal :term:`padding`, since ``1`` must be less than or equal to the image width
* **middle** :term:`vertical alignment` (default)
* **no** vertical :term:`padding`, since ``1`` is less than or equal to the image height
* transparency **disabled** (alpha channel is removed)

The result should look like:

.. image:: /resources/tutorial/no_alpha_no_align.png

You should also have a look at the complete :ref:`format-spec`.


Drawing/Displaying an image to/in the terminal
----------------------------------------------

There are two ways to draw an image to the terminal screen:

1. The :py:meth:`~term_image.image.BaseImage.draw` method
   ::

      image.draw()

   **NOTE:** :py:meth:`~term_image.image.BaseImage.draw` has various parameters for
   :term:`alignment`/:term:`padding`, transparency, animation control, etc.

2. Using ``print()`` with an image render output (i.e printing the rendered string)

   ::

      print(image)  # Uses str()

   OR

   ::

      print(f"{image:>200.^70#ffffff}")  # Uses format()

.. note::
   * For :term:`animated` images, only the former animates the output, the latter only
     draws the **current** frame (see :py:meth:`seek() <term_image.image.BaseImage.seek()>`
     and :py:meth:`tell() <term_image.image.BaseImage.tell()>`).
   * Also, the former performs size validation to see if the image will fit into the
     terminal, while the latter doesn't.


.. important:: All the examples above use automatic sizing and default :term:`scale`.


Image size
----------
| The size of an image is the **unscaled** dimension with which an image is rendered.
| The image size can be retrieved via the :py:attr:`~term_image.image.BaseImage.size`,
  :py:attr:`~term_image.image.BaseImage.width` and :py:attr:`~term_image.image.BaseImage.height` properties.

The size of an image can be in either of two states:

1. Set

   | The size is said the be *set* when the image has a fixed size.
   | In this state, the ``size`` property is a ``tuple`` of integers, the ``width`` and
     ``height`` properties are integers.

.. _unset-size:

2. Unset

   The size is said to be *unset* when the image doesn't have a fixed size. In this state,

   * the size with which the image is rendered is automatically calculated
     (based on the current :term:`terminal size`) whenever the image is to be rendered.
   * the ``size``, ``width`` and ``height`` properties are ``None``.

| The size of an image can be set when creating the instance by passing a valid value to
  **either** the *width* **or** the *height* **keyword-only** parameter.
| For whichever axis is given, the other axis is calculated **proportionally**.

.. note::
   1. The arguments can only be given **by keyword**.
   2. If neither is given, the size is *unset*.
   3. All methods of instantiation accept these arguments.

For example:

>>> image = from_file("python.png")  # Unset
>>> image.size is None
True
>>> image = from_file("python.png", width=60)  # width is given
>>> image.size
(60, 30)
>>> image.height
30
>>> image = from_file("python.png", height=56)  # height is given
>>> image.size
(112, 56)
>>> image.width
112

No size validation is performed i.e the resulting size might not fit into the terminal window

>>> image = from_file("python.png", height=68)  # Will fit, OK
>>> image.size
(136, 68)
>>> image = from_file("python.png", height=500)  # Will not fit, also OK
>>> image.size
(1000, 500)

An exception is raised when both *width* and *height* are given.

>>> image = from_file("python.png", width=100, height=100)
Traceback (most recent call last):
  .
  .
  .
ValueError: Cannot specify both width and height

The :py:attr:`~term_image.image.BaseImage.width` and :py:attr:`~term_image.image.BaseImage.height`
properties are used to set the size of an image after instantiation.

>>> image = from_file("python.png")  # Unset
>>> image.size is None
True
>>> image.width = 56
>>> image.size
(56, 28)
>>> image.height
28
>>> image.height = 68
>>> image.size
(136, 68)
>>> image.width
136
>>> image.width = 200  # Even though the terminal can't contain the resulting height, the size is still set
>>> image.size
(200, 100)

Setting ``width`` or ``height`` to ``None`` sets the size to that automatically calculated
based on the current :term:`terminal size`.

>>> image = from_file("python.png")  # Unset
>>> image.size is None
True
>>> image.width = None
>>> image.size
(136, 68)
>>> image.width = 56
>>> image.size
(56, 28)
>>> image.height = None
>>> image.size
(136, 68)

.. note:: An exception is raised if the terminal size is too small to calculate a size.

The :py:attr:`~term_image.image.BaseImage.size` property can only be set to one value,
``None`` and doing this :ref:`unsets <unset-size>` the image size.

>>> image = from_file("python.png", width=100)
>>> image.size
(100, 50)
>>> image.size = None
>>> image.size is image.width is image.height is None
True

.. important::

   1. The currently set :term:`font ratio` is also taken into consideration when setting sizes.
   2. There is a **default** 2-line :term:`vertical allowance`, to allow for shell prompts or the likes.

.. hint::

   See :py:meth:`~term_image.image.BaseImage.set_size` for extended sizing control.


.. _image-scale:

Image scale
-----------

| The scale of an image is the **fraction** of the size that'll actually be used to render the image.
| A valid scale value is a ``float`` in the range ``0 < x <= 1`` i.e greater than zero
  and less than or equal to one.

The image scale can be retrieved via the properties :py:attr:`~term_image.image.BaseImage.scale`,
:py:attr:`~term_image.image.BaseImage.scale_x` and :py:attr:`~term_image.image.BaseImage.scale_y`.

The scale can be set at instantiation by passing a value to the *scale* **keyword-only** paramter.

>>> image = from_file("python.png", scale=(0.75, 0.6))
>>> image.scale
>>> (0.75, 0.6)

The rendered result (using ``image.draw()``) should look like:

.. image:: /resources/tutorial/scale_set.png

If the *scale* argument is ommited, the default scale ``(1.0, 1.0)`` is used.

>>> image = from_file("python.png")
>>> image.scale
>>> (1.0, 1.0)

The rendered result (using ``image.draw()``) should look like:

.. image:: /resources/tutorial/scale_unset.png

| The properties :py:attr:`~term_image.image.BaseImage.scale`, :py:attr:`~term_image.image.BaseImage.scale_x` and :py:attr:`~term_image.image.BaseImage.scale_y` are used to set the scale of an image after instantiation.

| ``scale`` accepts a tuple of two scale values or a single scale value.
| ``scale_x`` and ``scale_y`` each accept a single scale value.

>>> image = from_file("python.png")
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
