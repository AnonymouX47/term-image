Tutorial
========

This is a basic introduction to using the library. Please refer to the :doc:`/reference/index` for detailed description of the features and functionality provided by the library.

For this tutorial we'll be using the image below:

.. image:: /resources/tutorial/python.png

The image has a resolution of **288x288 pixels**.

.. note:: All the samples in this tutorial occured in a terminal window of **255 columns by 70 lines**.


Creating an Instance
--------------------

Image instances can be created using the convinience functions :py:func:`~term_image.image.AutoImage`,
:py:func:`~term_image.image.from_file` and :py:func:`~term_image.image.from_url`,
which automatically detect the best style supported by the terminal emulator.

Instances can also be created using the :ref:`image-classes` directly via their respective
constructors or :py:meth:`~term_image.image.BaseImage.from_file` and
:py:meth:`~term_image.image.BaseImage.from_url` methods.

If the file is stored on your local filesystem::

   from term_image.image import from_file

   image = from_file("path/to/python.png")

You can also use a URL if you don't have the file stored locally::

   from term_image.image import from_url

   image = from_url("https://raw.githubusercontent.com/AnonymouX47/term-image/main/docs/source/resources/tutorial/python.png")

The library can also be used with :py:class:`PIL.Image.Image` instances::

   from PIL import Image
   from term_image.image import AutoImage

   img = Image.open("python.png")
   image = AutoImage(img)


Rendering an Image
------------------

Rendering an image is the process of converting it (per-frame for :term:`animated`
images) into text (a string) which reproduces a representation or approximation of
the image when written to the terminal.

.. hint:: To display the rendered image in the following steps, pass the string as an argument to :py:func:`print`.

There are two ways to render an image:

Unformatted Rendering
^^^^^^^^^^^^^^^^^^^^^
This is done using::

   str(image)

The image is rendered without *padding*/*alignment* and with transparency enabled.

The output (using :py:func:`print`) should look like:

.. image:: /resources/tutorial/str.png

|

.. _formatted-render:

Formatted Rendering
^^^^^^^^^^^^^^^^^^^
.. note::
   To see the effect of :term:`alignment` in the steps below, please scale the image down using::

     image.scale = 0.75

   This simply sets the x-axis and y-axis :term:`scale` of the image to ``0.75``.
   We'll see more about this :ref:`later <image-scale>`.

Below are examples of formatted rendering:

::

   format(image, "|200.^70#ffffff")

Renders the image with:

* **center** :term:`horizontal alignment`
* a :term:`padding width` of **200** columns
* **top** :term:`vertical alignment`
* a :term:`padding height` of **70** lines
* **white** (``#ffffff``) background underlay

.. note::
   You might have to reduce the padding width (200) and/or height (70) to something that'll
   fit into your terminal window, or increase the size of the terminlal window

The output (using :py:func:`print`) should look like:

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

The output (using :py:func:`print`) should look like:

.. image:: /resources/tutorial/alpha_0_5.png

|

::

   "{:1.1#}".format(image)

Renders the image with:

* **center** :term:`horizontal alignment` (default)
* **no** horizontal :term:`padding`, since ``1`` is less than or equal to the image width
* **middle** :term:`vertical alignment` (default)
* **no** vertical :term:`padding`, since ``1`` is less than or equal to the image height
* transparency is **disabled** (alpha channel is ignored)

The output (using :py:func:`print`) should look like:

.. image:: /resources/tutorial/no_alpha_no_align.png

.. seealso:: :doc:`/guide/formatting` and :ref:`format-spec`


Drawing/Displaying an Image
---------------------------

There are two ways to draw an image to the terminal screen:

1. Using the :py:meth:`~term_image.image.BaseImage.draw` method::

      image.draw()

   **NOTE:** :py:meth:`~term_image.image.BaseImage.draw` has various parameters for
   :term:`alignment`/:term:`padding`, transparency, animation control, etc.

2. Using :py:func:`print` with an image render output (i.e printing the rendered string):

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


.. important:: All the examples above use :term:`dynamic <dynamic size>`,
   :term:`automatic <automatic size>` sizing and default :term:`scale`.


Image Size
----------

| The size of an image is the **unscaled** dimension with which an image is rendered.
| The image size can be retrieved via the :py:attr:`~term_image.image.BaseImage.size`,
  :py:attr:`~term_image.image.BaseImage.width` and :py:attr:`~term_image.image.BaseImage.height` properties.

The size of an image can be in either of two states:

1. Fixed

   In this state,
   
   * the ``size`` property evaluates to a 2-tuple of integers, while the ``width`` and
     ``height`` properties evaluate to integers,
   * the image is rendered with the set size.

2. Dynamic

   In this state,

   * the ``size``, ``width`` and ``height`` properties evaluate to a
     :py:class:`~term_image.image.Size` enum member,
   * the size with which the image is rendered is automatically calculated
     (based on the current :term:`terminal size` or the image's original size) whenever the
     image is to be rendered.

The size of an image can be set at instantiation by passing an integer or a
:py:class:`~term_image.image.Size` enum member to **either** the *width* **or** the
*height* **keyword-only** parameter.
For whichever axis a dimension is given, the dimension on the other axis is calculated
**proportionally**.

.. note::
   1. The arguments can only be given **by keyword**.
   2. If neither is given, the :py:attr:`~term_image.image.Size.FIT` :term:`dynamic size`
      applies.
   3. All methods of instantiation accept these arguments.

For example:

>>> from term_image.image import Size, from_file
>>> image = from_file("python.png")  # Dynamic FIT
>>> image.size is Size.FIT
True
>>> image = from_file("python.png", width=60)  # Fixed
>>> image.size
(60, 30)
>>> image.height
30
>>> image = from_file("python.png", height=56)  # Fixed
>>> image.size
(112, 56)
>>> image.width
112
>>> image = from_file("python.png", height=Size.FIT)  # Fixed FIT
>>> image.size
(136, 68)
>>> image = from_file("python.png", width=Size.FIT_TO_WIDTH)  # Fixed FIT_TO_WIDTH
>>> image.size
(255, 128)
>>> image = from_file("python.png", height=Size.ORIGINAL)  # Fixed ORIGINAL
>>> image.size
(288, 144)

No size validation is performed i.e the resulting size might not fit into the terminal window

>>> image = from_file("python.png", height=68)  # Will fit in, OK
>>> image.size
(136, 68)
>>> image = from_file("python.png", height=500)  # Will not fit in, also OK
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
properties can be used to set the size of an image after instantiation, resulting in :term:`fixed size`.

>>> image = from_file("python.png")
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
>>> # Even though the terminal can't contain the resulting height, the size is still set
>>> image.width = 200
>>> image.size
(200, 100)
>>> image.width = Size.FIT
>>> image.size
(136, 69)
>>> image.height = Size.FIT_TO_WIDTH
>>> image.size
(255, 128)
>>> image.height = Size.ORIGINAL
>>> image.size
(288, 144)

The :py:attr:`~term_image.image.BaseImage.size` property can only be set to a
:py:class:`~term_image.image.Size` enum member, resulting in :term:`dynamic size`.

>>> image = from_file("python.png")
>>> image.size = Size.FIT
>>> image.size is image.width is image.height is Size.FIT
True
>>> image.size = Size.FIT_TO_WIDTH
>>> image.size is image.width is image.height is Size.FIT_TO_WIDTH
True
>>> image.size = Size.ORIGINAL
>>> image.size is image.width is image.height is Size.ORIGINAL
True

.. important::

   1. The currently set :term:`cell ratio` is also taken into consideration when calculating sizes for images of :ref:`text-based`.
   2. There is a **default** 2-line :term:`vertical allowance`, to allow for shell prompts or the likes.

.. tip::

   See :py:meth:`~term_image.image.BaseImage.set_size` for extended sizing control.


.. _image-scale:

Image scale
-----------

| The scale of an image is the **ratio** of its size with which it will actually be rendered.
| A valid scale value is a :py:class:`float` in the range ``0.0`` < ``x`` <= ``1.0``
  i.e greater than zero and less than or equal to one.

The image scale can be retrieved via the properties :py:attr:`~term_image.image.BaseImage.scale`,
:py:attr:`~term_image.image.BaseImage.scale_x` and :py:attr:`~term_image.image.BaseImage.scale_y`.

The scale can be set at instantiation by passing a value to the *scale* **keyword-only** paramter.

>>> image = from_file("python.png", scale=(0.75, 0.6))
>>> image.scale
>>> (0.75, 0.6)

The drawn image (using ``image.draw()``) should look like:

.. image:: /resources/tutorial/scale_set.png

If the *scale* argument is ommited, the default scale ``(1.0, 1.0)`` is used.

>>> image = from_file("python.png")
>>> image.scale
>>> (1.0, 1.0)

The drawn image (using ``image.draw()``) should look like:

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

|

Finally, to explore more of the library's features and functionality, check out the :doc:`/guide/index` and the :doc:`/reference/index`.
