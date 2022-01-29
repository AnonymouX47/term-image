<div align="center">
<h1><b>Term-Img</b></h1>
<b>Display Images in the terminal</b>
<br>
<img src="https://raw.githubusercontent.com/AnonymouX47/term-img/main/docs/source/resources/tui.png">

<p align="center">
    <img src="https://static.pepy.tech/badge/term-image">
    <img src="https://badges.frapsoft.com/os/v1/open-source.svg?v=103">
    <img src="https://img.shields.io/github/last-commit/AnonymouX47/term-img">
    <a href="https://twitter.com/intent/tweet?text=Display%20images%20in%20the%20the%20terminal%20using%20python&url=https://github.com/AnonymouX47/term-img&hashtags=developers,images,terminal">
        <img src="https://img.shields.io/twitter/url/http/shields.io.svg?style=social">
    </a>
</p>

</div>


## Contents
- [Installation](#installation)
- [Features](#features)
- [CLI/TUI Quick Start](#clitui-quick-start)
- [Library Quick Start](#library-quick-start)
- [Usage](#usage)
- [Contribution](#contribution)
- [WIP](#wip)
- [TODO](#todo)
- [FAQs](#faqs)


## Installation

### Requirements
- Operating System: Unix / Linux / MacOS X / Windows (partial, more info in the [FAQs](https://term-img.readthedocs.io/en/latest/faqs.html))
- [Python >= 3.6](https://www.python.org/)
- A Terminal emulator with full Unicode support and ANSI 24-bit color support
  - Plans are in place to [partially] support terminals not meeting this requirement (see [here](https://term-img.readthedocs.io/en/latest/library/index.html#planned-features)).

### Steps
The package can be installed from PyPI using `pip`:

```shell
pip install term-image
```
OR

Clone this repository using any method, then navigate into the project directory in a terminal and run:

```shell
pip install .
```

### Supported Terminal Emulators
See [here](https://term-img.readthedocs.io/en/latest/installation.html#supported-terminal-emulators) for a list of tested terminal emulators.

If you've tested `term-img` on any other terminal emulator that meets all requirements, please mention the name in a new thread under [this discussion](https://github.com/AnonymouX47/term-img/discussions/4).
Also, if you're having an issue with terminal support, also report or view information about it in the discussion linked above.


## Features

### Library features
- Multiple image format support
  - Basically supports all formats supported by `PIL.Image.open()`
- Multiple image sources (PIL image, local file, URL)
- Transparency support (with multiple options)
- Animated image support (including transparent ones)
- Terminal size awareness
- Variable image size
- Automatic image sizing; best fit within the terminal window or a given size
- Variable image scale
- Horizontal and vertical alignment/padding
- Font-ratio adjustment
- Frame duration (animation speed) control
- ... more coming soon :grin:

### CLI/TUI features
- Basically everything the library supports
- Individual image display
- Multiple images / Directory / Recursive browsing
- Image grid [TUI]
- Context-based controls [TUI]
- Dynamic controls (context actions are disabled and enabled dynamically) [TUI]
- Customizable controls and configuration options
- Automatic adjustment upon terminal resize [TUI]
- Image deletion [TUI]
- Notification system
- Detailed logging system
- ... more coming soon :grin:


## CLI/TUI Quick Start

From a local image file
```bash
term-img path/to/image.png
```

From a URL
```bash
term-img https://www.example.com/image.png
```

If the image is animated (GIF, WEBP), the animation is infinitely looped but can be stopped with `Ctrl-C`.

**By default, if multiple sources or at least one directory is given, the TUI (Text-based/Terminal User Interface) is launched to navigate through the images.**

**NOTE:** `python -m term_img` can be used as an alternative to the `term-img` command **(take note of the _underscore_ VS _hyphen_)**.


## Library Quick Start

### Creating an instance

```python
from term_img.image import TermImage

image = TermImage.from_file("path/to/image.png")
```

You can also use a URL if you don't have the file stored locally
```python
from term_img.image import TermImage

image = TermImage.from_url("https://www.example.com/image.png")
```

The library can also be used with PIL images
```python
from PIL import Image
from term_img.image import TermImage

img = Image.open("path/to/image.png")
image = TermImage(img)
```

### Rendering an image
Rendering an image, in this context, is simply the process of converting it into text (a string).
There are two ways to render an image:

#### 1. Unformatted
```python
str(image)
```
Renders the image without padding/alignment and with transparency enabled.

#### 2. Formatted
```python
format(image, "|200.^100#ffffff")
```
Renders the image with:

* **center** horizontal alignment
* a **padding width** of **200** columns
* **top** vertical alignment
* a **padding height** of **70** lines
* transparent background replaced with a **white** (``#ffffff``) background

```python
f"{image:>._#.5}"
````
Renders the image with:

* **right** horizontal alignment
* **automatic** padding width (the current terminal width minus horizontal allowance)
* **bottom** vertical alignment
* **automatic** padding height (the current terminal height minus vertical allowance)
* transparent background with **0.5** alpha threshold

```python
"{:1.1#}".format(image)
```
Renders the image with:

* **center** horizontal alignment (default)
* **no** horizontal padding, since ``1`` must be less than or equal to the image width
* **middle** vertical alignment (default)
* **no** vertical padding, since ``1`` is less than or equal to the image height
* transparency **disabled** (black background)

### Drawing/Displaying an image to/in the terminal
There are two ways to draw an image to the terminal screen.

#### 1. The `draw()` method
```python
image.draw()
```
**NOTE:** `TermImage.draw()` method has various parameters for **alignment/padding**, **transparency** and **animation** control.

#### 2. Using `print()` with an image render output (i.e printing the rendered string)
```python
print(image)  # Uses str()
```
OR
```python
print(f"{image:>200.^100#ffffff}")  # Uses format()
```

For animated images, only the first method can animate the output, the second only outputs the current frame.

**NOTE:** All the above examples use **automatic sizing** and default scale.


## Usage

### CLI (Command-Line Interface)
Run `term-img --help` to see full usage info.

### TUI (Text-based/Terminal User Interface)
The controls are **context-based** and displayed at the bottom of the terminal window.
Pressing the `F1` key (in most contexts) brings up a **help** menu describing the available controls (called *actions*) in that context.

The TUI controls can be configured by modifying the config file `~/.term_img/config.json`. See the [Configuration](https://term-img.readthedocs.io/en/latest/viewer/config.html) section.
[Here](https://github.com/AnonymouX47/term-img/blob/main/vim-style_config.json) is a config file with Vim-style key-bindings (majorly navigation).
*Remember to rename the file to `config.json`.*

### Library
See the [tutorial](https://term-img.readthedocs.io/en/latest/library/tutorial.html) for a more detailed introduction and the [reference](https://term-img.readthedocs.io/en/latest/library/reference/index.html) for full descriptions and details of the available features.

_**NOTE:** The project is currently at a stage where the public API might change without warning but significant changes will always be specified in the [changelog](https://github.com/AnonymouX47/term-img/blob/main/CHANGELOG.md)._


## Contribution

If you've found any bug or want to suggest a new feature, please open a new [issue](https://github.com/AnonymouX47/term-img/issues) with proper description, after browsing/searching through the existing issues and making sure you won't create a duplicate.

For code contributions, please make sure you read through the [guidelines](https://github.com/AnonymouX47/term-img/blob/main/CONTRIBUTING.md).

Also, check out the [WIP](#wip) and [TODO](#todo) sections below.
If you wish to work on any of the listed tasks, please go through the [discussions](https://github.com/AnonymouX47/term-img/discussions) tab and join in on an ongoing discussion about a task or create a new discussion if one hasn't been created yet, so that the implementation can be discussed.

Hint: You can filter discussions by *Category* or *label* or simply *search* using the task's name or description.

For anything other than the above (such as questions or anything that would fit under the term "discussion"), please open a new [discussion](https://github.com/AnonymouX47/term-img/discussions) instead.

Thanks! :heart:


## WIP
- Performance improvements


## TODO

Check [here](https://term-img.readthedocs.io/en/latest/library/index.html#planned-features) for the library and [here](https://term-img.readthedocs.io/en/latest/viewer/index.html#planned-features) for the image viewer.

## FAQs
See the [FAQs](https://term-img.readthedocs.io/en/latest/faqs.html) section of the docs.

* * *

## Acknowledgment

This project started as a fork of [img](https://github.com/pranavbaburaj/img) by [@pranavbaburaj](https://github.com/pranavbaburaj) but has since grown into something almost entirely different.
