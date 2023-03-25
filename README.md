<div align="center">
<h1><b>Term-Image</b></h1>
<img src="https://raw.githubusercontent.com/AnonymouX47/term-image/main/docs/source/resources/logo.png" height="200">

<br><br>
<b>Display Images in the terminal</b>
<br>

<p align="center">
   &#128214; <a href='https://term-image.readthedocs.io'>Docs</a>
    &#9553; 
   &#127979; <a href='https://term-image.readthedocs.io/en/stable/library/tutorial.html'>Tutorial</a>
</p>

<p align="center">
   <a href='https://pypi.org/project/term-image/'>
      <img src='https://img.shields.io/pypi/v/term-image.svg'>
   </a>
   <img src="https://static.pepy.tech/badge/term-image">
   <a href='https://pypi.org/project/term-image/'>
      <img src='https://img.shields.io/pypi/pyversions/term-image.svg'>
   </a>
   <a href='https://github.com/psf/black'>
      <img src='https://img.shields.io/badge/code%20style-black-000000.svg'>
   </a>
   <a href='https://github.com/AnonymouX47/term-image/actions/workflows/test.yml'>
      <img src='https://github.com/AnonymouX47/term-image/actions/workflows/test.yml/badge.svg'>
   </a>
   <a href='https://term-image.readthedocs.io'>
      <img src='https://readthedocs.org/projects/term-image/badge/?version=latest' alt='Documentation Status' />
   </a>
   <img src="https://img.shields.io/github/last-commit/AnonymouX47/term-image">
   <a href="https://twitter.com/intent/tweet?text=Display%20and%20browse%20images%20in%20the%20the%20terminal&url=https://github.com/AnonymouX47/term-image&hashtags=developers,images,terminal,python">
      <img src="https://img.shields.io/twitter/url/http/shields.io.svg?style=social">
   </a>
</p>

</div>


## Contents
- [Installation](#installation)
- [Features](#features)
- [Demo](#demo)
- [Quick Start](#library-quick-start)
- [Usage](#usage)
- [Contribution](#contribution)
- [Planned Features](#planned-features)
- [Known Issues](#known-issues)
- [FAQs](#faqs)
- [Credits](#credits)
- [Donate](#donate)


> ### :warning: NOTICE!!! :warning:
> The image viewer (CLI and TUI) has been moved to [term-image-viewer](https://github.com/AnonymouX47/term-image-viewer).


## Installation

### Requirements
- Operating System: Unix / Linux / Mac OS X / Windows (limited support, see the [FAQs](https://term-image.readthedocs.io/en/stable/faqs.html))
- [Python](https://www.python.org/) >= 3.7
- A terminal emulator with **any** of the following:
  
  - support for the [Kitty graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/).
  - support for the [iTerm2 inline image protocol](https://iterm2.com/documentation-images.html).
  - full Unicode support and ANSI 24-bit color support

  **Plans to support a wider variety of terminal emulators are in motion** (see [Planned Features](#planned-features)).

### Steps
The latest **stable** version can be installed from [PyPI](https://pypi.python.org/pypi/term-image) using `pip` (**recommended**):

```shell
pip install term-image
```

The **development** version can be installed thus:

**NOTE:** it's recommended to install in an isolated virtual environment which can be created by any means.

Clone this repository from within a terminal
```shell
git clone https://github.com/AnonymouX47/term-image.git
```

Navigate into the local repository
```shell
cd term-image
```

Install
```shell
pip install .
```

### Supported Terminal Emulators
See [here](https://term-image.readthedocs.io/en/stable/installation.html#supported-terminal-emulators) for a list of tested terminal emulators.

If you've tested this library on any other terminal emulator that meets the requirements for any of the render styles,
please mention the name (and version) in a new thread under [this discussion](https://github.com/AnonymouX47/term-image/discussions/4).

Also, if you have any issue with terminal support, you may report or check information about it in the discussion linked above.


## Features
- Multiple image formats (basically all formats supported by [`PIL.Image.open()`](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html))
- Multiple image source types: PIL image instance, local file, URL
- Multiple image render styles (with automatic support detection)
- Support for multiple terminal graphics protocols: [Kitty](https://sw.kovidgoyal.net/kitty/graphics-protocol/), [iTerm2](https://iterm2.com/documentation-images.html)
  - Exposes various features of the protocols
- Transparency support (with multiple options)
- Animated image support (including transparent ones)
  - Multiple formats: GIF, WEBP, APNG (and possibly more)
  - Fully controllable iteration over rendered frames of animated images
  - Image animation with multiple parameters
- Terminal size awareness
- Automatic and manual image sizing
- Horizontal and vertical alignment
- Automatic and manual font ratio adjustment (to preserve image aspect ratio)
- Well-documented
- and more... :grin:


## Demo

Check out this [image viewer](https://github.com/AnonymouX47/term-image-viewer) based on this library.


## Quick Start

### Creating an instance

<details>
<summary>Click to expand</summary>

```python
from term_image.image import from_file

image = from_file("path/to/image.png")
```

You can also use a URL if you don't have the file stored locally
```python
from term_image.image import from_url

image = from_url("https://www.example.com/image.png")
```

The library can also be used with PIL images
```python
from PIL import Image
from term_image.image import AutoImage

img = Image.open("path/to/image.png")
image = AutoImage(img)
```

</details>

### Drawing/Displaying an image to/in the terminal

<details>
<summary>Click to expand</summary>

There are two ways to draw an image to the terminal.

#### 1. The `draw()` method
```python
image.draw()
```

#### 2. Using `print()` with a rendered image
```python
print(image)  # without formatting
```
OR
```python
print(f"{image:>200.^100#ffffff}")  # with formatting
```

For animated images, only the first method can animate the output, the second only outputs the current frame.

</details>


## Usage

<p align="center"><b>
   :construction: Under Construction - There will most likely be incompatible changes between minor versions of
   <a href='https://semver.org/spec/v2.0.0.html#spec-item-4'>version zero</a>!
</b></p>

**If you want to use this library in a project while it's still on version zero, ensure you pin the dependency version to a specific minor version e.g `>=0.4,<0.5`.**

See the [tutorial](https://term-image.readthedocs.io/en/stable/library/tutorial.html) for a more detailed introduction and the [reference](https://term-image.readthedocs.io/en/stable/library/reference/index.html) for full descriptions and details of the available features.


## Contribution

Please read through the [guidelines](https://github.com/AnonymouX47/term-image/blob/main/CONTRIBUTING.md).

For code contributions, you should also check out the [Planned Features](#planned-features).
If you wish to work on any of the listed features/improvements, please click on the linked issue or go through the [issues](https://github.com/AnonymouX47/term-image/issues) section and join in on an ongoing discussion about the task or create a new issue if one hasn't been created yet, so that the implementation can be discussed.

Hint: You can filter issues by *label* or simply *search* using the features's description.

Thanks! :heart:


## Planned Features

See [here](https://term-image.readthedocs.io/en/stable/library/index.html#planned-features).

## Known Issues

See [here](https://term-image.readthedocs.io/en/stable/library/index.html#known-issues).

## FAQs

See the [FAQs](https://term-image.readthedocs.io/en/stable/faqs.html) section of the docs.

## Credits

The following projects have been (and are still) crucial to the development of this project:

- [Pillow](https://python-pillow.org)

## Donate

Your donation will go a long way in aiding the progress and development of this project.

```
USDT Address: TKP6d3hLcs7i5R18WRFxLe3zsPQcCBS1Ro
Network: TRC20
```
I'm sincerly sorry for any inconviences that may result from the means of donation.

Please bare with me, as usual means of accepting donations are not available in the region of the world where I reside.

Thank you! :heart:
