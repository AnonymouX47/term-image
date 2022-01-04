Tutorial
========

This is a basic introduction to using the library. Please refer to :doc:`features` for detailed description of the features provided by the library or the :doc:`reference` for the complete library reference.

For this tutorial we'll be using the image below:

.. image:: /resources/tutorial/python.png

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

The class constructor and helper methods above accept more arguments, please check their docstrings (just for the mean time, the library documentation is coming up soon).

.. Link the constructor and helper methods

Rendering an image
------------------

Rendering an image is simply the process of converting it (per-frame for animated images) into text (a string).
There are two ways to render an image:

1. **Unformatted**
   ::

      str(image)

   Renders the image without padding/alignment and with transparency enabled

   The result should look like:

   .. image:: /resources/tutorial/str.png

   |

2. **Formatted**

   .. note::
      To see the the effect of *alignment* in the steps below, please scale the image down using::

        image.scale = .75

      This simply sets the x- and y-axis scales to 0.75.

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

   You should also have a look at the complete :ref:`format-spec`.

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

.. important:: All the above examples use automatic sizing and default scale, see ``help(TermImage)`` for the descriptions of the *width*, *height* and *scale* constructor parameters and object properties to set custom image size and scale.
