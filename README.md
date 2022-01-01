<div align="center">
<h1><b>Term-Img</b></h1>
<b>Display Images in your terminal with python</b>
<br>
<img src="https://raw.githubusercontent.com/AnonymouX47/term-img/docs/demo/shot.png">

<p align="center">
    <img src="https://static.pepy.tech/badge/term-img">
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
- Operating System: Unix / Linux / MacOS X
- [Python >= 3.6](https://www.python.org/)
- A Terminal with full Unicode support and ANSI 24-bit color support
  - Plans are in place to [partially] support terminals not meeting this requirement.

### Steps
The package can be installed using `pip`

```shell
pip install term-img
```
OR

Clone this repository using any method, then navigate into the project directory in a terminal and run

```shell
pip install .
```

## Features

### Library features
- Multiple image format support
  - Basically supports all formats supported by `PIL.Image.open()`
- Multiple image sources (PIL image, local file, URL)
- Transparency support (with multiple options)
- Animated image support (even transparent ones)
- Terminal size awareness
- Variable image size
- Automatic image sizing, best fit within the terminal window or a given size
- Variable image scale
- Horizontal and vertical alignment/padding
- Font-ratio adjustment
- Frame duration (animation speed) control
- ... more coming soon :grin:

### CLI/TUI features
- Basically everything the library supports
- Individual image display
- Multiple images / Directory / Recursive browsing
- Context-based controls
- Dynamic controls (context actions are disabled and enabled dynamically)
- Customizable controls and configuration options
- Automatic adjustment upon terminal resize (TUI)
- Detailed logging
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

**If multiple sources or at least one directory is given, the TUI (Text-based/Terminal User Interface) is launched to navigate through the images.**

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

img = Image.open("image.png")
image = TermImage(img)
```
The class constructor and helper methods above accept more arguments, please check their docstrings (just for the mean time, the library documentation is coming up soon).

### Rendering an image
Rendering an image is simply the process of converting it (per-frame for animated images) into text (a string).
There are two ways to render an image:

#### 1. Unformatted
```python
str(image)
```
Renders the image without padding/alignment and with transparency enabled

#### 2. Formatted
```python
format(image, "|200.^100#ffffff")
```
Renders the image with:
- center horizontal alignment
- a padding width of 200 columns
- top vertical alignment
- a padding height of 100 lines
- transparent background replaced with a white (#ffffff) background

```
f"{image:>._#.5}"
````
Renders the image with:
- right horizontal alignment
- automatic padding width (the current terminal width)
- bottom vertical alignment
- automatic padding height (the current terminal height with a 2-line allowance)
- transparent background with 0.5 alpha threshold

```
"{:1.1#}".format(image)
```
Renders the image with:
- center horizontal alignment (default)
- no horizontal padding, since `1` is less than the image width
- middle vertical alignment (default)
- no vertical padding, since `1` is less than the image height
- transparency disabled (black background)

For the complete format specification, see the description of `TermImage.__format__()` (just for the mean-time, a proper documentation is being worked upon).

### Drawing/Displaying an image to/in the terminal
There are two ways to draw an image to the terminal screen.

#### 1. `draw_image()` method
```python
image.draw_image()
```
**NOTE:** `draw_image()` has various parameters for alignment/padding and transparency control.

#### 2. Using `print()` with an image render output (i.e printing the rendered string)
```python
print(image)  # Uses str(image)
```
OR
```python
print(f"{image:>200.^100#ffffff}")  # Uses format(image)
```

For animated images, only the first method animates the output, the second only outputs the current frame.

**NOTE:** All the above examples use automatic sizing and default scale, see `help(TermImage)` for the descriptions of the _width_, _height_ and _scale_ constructor parameters and object properties to set custom image size and scale.


## Usage

### CLI
Run `term-img --help` to see full usage info.

### TUI (Text-based/Terminal User Interface)
The controls are context-based and displayed at the bottom of the terminal window.
Pressing the `F1` key (in most contexts) brings up a help menu describing the various controls (called _actions_) in that context.

The TUI controls can be configured by modifying the config file `~/.term_img/config.json` (more on that coming up in the documentation).

### Library
See the [examples]() for usage samples and the [documentation]() for full description and details of the available features.

**NOTE:**
1. **The examples and documentation are in progress**. Please bear with the help messages (for the CLI/TUI) and docstrings (for the library) for now. **Thanks**
2. The project is currently at a stage where the public API can change without notice.

## Contribution

If you find any bugs or want to suggest a new feature, please open a new issue with proper description (after browsing through the existing issues and making sure you won't create a duplicate).

For code contributions, please make sure you read the [guidelines](CONTRIBUTING.md).

Also, check out the [WIP](#wip) and [TODO](#todo) sections below. If you wish to work on any of these, please open an issue appropriately (if one hasn't been opened yet), so the implementation can be discussed.

Thanks! :heart:

## WIP
- Documentation (Using `Sphinx`)
- Unit-testing (using `pytest`)

## TODO

In no particular order (Will probably create a roadmap soon):

- Performance improvements
- Urwid widgets for displaying images
- Theme customization
- Slideshow
- Zoom
- Add modified keys (e.g "ctrl shift a") to valid keys
- Grid cell animations
- Animated image iterators
- Config menu
- Pattern-based file and directory exclusion
- Minimum and maximum file size
- Optionally skipping symlinks
- ... and more :grin:.

## FAQs
1. Why?
   - Why not?
   - Some of us literally spend our lives in terminals :cry: .
2. What about Windows support?
   - Firstly, only the new [Windows Terminal](https://github.com/microsoft/terminal) seems to have proper ANSI support and mordern terminal emulator features.
   - The CLI-only mode currently works on Windows (i.e using CMD or Powershell) if the other requirements are satisfied but can't guarantee it'll always be so.
   - The TUI doesn't work due to lack of [**urwid**](https://urwid.org) support.
   - If stuck on Windows, you could use WSL + Windows Terminal.

* * *

## Acknowledgment

This project started as a fork of [img](https://github.com/pranavbaburaj/img) by [@pranavbaburaj](https://github.com/pranavbaburaj) but has since grown into something almost entirely different.
