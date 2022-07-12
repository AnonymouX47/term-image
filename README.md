<div align="center">
<h1><b>Term-Image</b></h1>
<b>Display Images in the terminal</b>
<br>
<img src="https://raw.githubusercontent.com/AnonymouX47/term-image/main/docs/source/resources/tui.png">

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
   <a href='https://term-image.readthedocs.io/en/latest/?badge=latest'>
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
- [CLI/TUI Quick Start](#clitui-quick-start)
- [Library Quick Start](#library-quick-start)
- [Usage](#usage)
- [Contribution](#contribution)
- [Planned Features](#planned-features)
- [Known Issues](#known-issues)
- [FAQs](#faqs)
- [Credits](#credits)
- [Donate](#donate)


## Installation

### Requirements
- Operating System: Unix / Linux / Mac OS X / Windows (limited support, see the [FAQs](https://term-image.readthedocs.io/en/latest/faqs.html))
- [Python](https://www.python.org/) >= 3.7
- A terminal emulator with **any** of the following:
  
  - support for the [Kitty graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/).
  - support for the [iTerm2 inline image protocol](https://iterm2.com/documentation-images.html).
  - full Unicode support and ANSI 24-bit color support

  **Plans to support a wider variety of terminal emulators are in motion** (see [here](https://term-image.readthedocs.io/en/latest/library/index.html#planned-features)).

### Steps
The latest **stable** version can be installed from [PyPI](https://pypi.python.org/pypi/term-image) using `pip`:

```shell
pip install term-image
```

The **development** version can be installed thus:

**NOTE:** it's recommended to install in an isolated virtual environment which can be created by any means.

Clone this repository from within a terminal
```shell
git clone https://github.com/AnonymouX47/term-image.git
```

then navigate into the local repository
```shell
cd term-image
```

and run
```shell
pip install .
```

### Supported Terminal Emulators
See [here](https://term-image.readthedocs.io/en/latest/installation.html#supported-terminal-emulators) for a list of tested terminal emulators.

If you've tested `term-image` on any other terminal emulator that meets the requirements for any of the render styles,
please mention the name (and version) in a new thread under [this discussion](https://github.com/AnonymouX47/term-image/discussions/4).

Also, if you have any issue with terminal support, you may report or check information about it in the discussion linked above.


## Features

### Library features
- Multiple image formats (basically all formats supported by [`PIL.Image.open()`](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html))
- Multiple image source types: PIL image instance, local file, URL
  - Exposes various features of the protocols
- Multiple image render styles (with automatic support detection)
- Support for multiple terminal graphics protocols: [Kitty](https://sw.kovidgoyal.net/kitty/graphics-protocol/), [iTerm2](https://iterm2.com/documentation-images.html)
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

### CLI/TUI features
- Almost everything the library supports
- Individual/Multiple image display [CLI]
- Browse multiple images and directories (recursively) [TUI]
- Adjustable image grids [TUI]
- Context-based controls [TUI]
- Customizable controls and configuration options
- Smooth and performant experience
- and more... :grin:

### How does this project compare with similar ones?
As far as I know, the only aspect of this project that any other currently existing project can be compared with is the CLI.

I prefer to leave comparisons to the users.


## Demo

Check out the [gallery](https://term-image.readthedocs.io/en/latest/gallery.html).

<details>
<summary>Click to expand</summary>

[TUI Demo Video](https://user-images.githubusercontent.com/61663146/163809903-e8fb254b-a0aa-4d0d-9fc9-dd676c10b735.mp4)

_\*The video was recorded at normal speed and not sped up._

</details>


## CLI/TUI Quick Start

<details>
<summary>Click to expand</summary>

With a local image file
```shell
term-image path/to/image.png
```

With an image URL
```shell
term-image https://www.example.com/image.png
```

With a directory, recursively (not currently supported on Windows)
```shell
term-image -r path/to/dir/
```

If the image is animated (GIF, WEBP), the animation is infinitely looped **by default** but can be stopped with `Ctrl-C`.

**By default, if multiple sources or at least one directory is given, the TUI (Text-based/Terminal User Interface) is launched to navigate through the images (and/or directories).**

**NOTE:** `python -m term_image` can be used as an alternative to the `term-image` command **(take note of the _underscore_ VS _hyphen_)**.

</details>


## Library Quick Start

<details>
<summary>Click to expand</summary>

### Creating an instance

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

### Drawing/Displaying an image to/in the terminal

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
   :construction: Under Construction - There might be incompatible changes between minor versions of
   <a href='https://semver.org/spec/v2.0.0.html#spec-item-4'>version zero</a>!
</b></p>

**If you want to use `term-image` in a project while it's still on version zero, ensure you pin the dependency version to a specific minor version e.g `>=0.4,<0.5`.**

### Library
See the [tutorial](https://term-image.readthedocs.io/en/latest/library/tutorial.html) for a more detailed introduction and the [reference](https://term-image.readthedocs.io/en/latest/library/reference/index.html) for full descriptions and details of the available features.

### CLI (Command-Line Interface)
Run `term-image --help` to see the full usage info and list of options.

### TUI (Text-based/Terminal User Interface)
The controls are **context-based** and displayed at the bottom of the terminal window.
Pressing the `F1` key (in most contexts) brings up a **help** menu describing the available controls (called *actions*) in that context.

The TUI can be configured by modifying the config file `~/.term_image/config.json`. See the [Configuration](https://term-image.readthedocs.io/en/latest/viewer/config.html) section of the docs.

[Here](https://github.com/AnonymouX47/term-image/blob/main/vim-style_config.json) is a config file with Vim-style key-bindings (majorly navigation). *Remember to rename the file to `config.json`.*


## Contribution

If you've found any bug or want to suggest a new feature, please open a new [issue](https://github.com/AnonymouX47/term-image/issues) with proper description, after browsing/searching through the existing issues and making sure you won't create a duplicate.

For code contributions, please read through the [guidelines](https://github.com/AnonymouX47/term-image/blob/main/CONTRIBUTING.md).

Also, check out the [Planned Features](#planned-features) section below.
If you wish to work on any of the listed tasks, please click on the linked issue or go through the [issues](https://github.com/AnonymouX47/term-image/issues) tab and join in on an ongoing discussion about the task or create a new issue if one hasn't been created yet, so that the implementation can be discussed.

Hint: You can filter issues by *label* or simply *search* using the task's name or description.

For anything other than the above (such as questions or anything that would fit under the term "discussion"), please open a new [discussion](https://github.com/AnonymouX47/term-image/discussions) instead.

Thanks! :heart:


## Planned Features

Check [here](https://term-image.readthedocs.io/en/latest/library/index.html#planned-features) for the library and [here](https://term-image.readthedocs.io/en/latest/viewer/index.html#planned-features) for the image viewer.

## Known Issues

Check [here](https://term-image.readthedocs.io/en/latest/library/index.html#known-issues) for the library and [here](https://term-image.readthedocs.io/en/latest/viewer/index.html#known-issues) for the image viewer.

## FAQs

See the [FAQs](https://term-image.readthedocs.io/en/latest/faqs.html) section of the docs.

## Credits

The following projects have been (and are still) crucial to the development of this project:

- [Pillow](https://python-pillow.org)
- [Urwid](https://urwid.org)

## Donate

Your donation will go a long way in aiding the progress and development of this project.

```
USDT Address: TKP6d3hLcs7i5R18WRFxLe3zsPQcCBS1Ro
Network: TRC20
```
I'm sincerly sorry for any inconviences that may result from the means of donation.

Please bare with me, as usual means of accepting donations are not available in the region of the world where I reside.

Thank you! :heart:
