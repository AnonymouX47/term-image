<div align="center">
<h1><b>Term-Img</b></h1>
<b>Display Images in your terminal with python</b>
<br>
<img src="https://i.imgur.com/8Tk6A15.png" height="450">

<p align="center">
    <img src="https://static.pepy.tech/badge/term-img">
    <img src="https://badges.frapsoft.com/os/v1/open-source.svg?v=103">
    <img src="https://img.shields.io/github/last-commit/AnonymouX47/term-img">
    <a href="https://twitter.com/intent/tweet?text=Display%20images%20in%20the%20the%20terminal%20using%20python&url=https://github.com/AnonymouX47/term-img&hashtags=developers,images,terminal">
        <img src="https://img.shields.io/twitter/url/http/shields.io.svg?style=social">
    </a>
</p>

</div>

## NOTE: This project is a _work in progress_ and not everything on here has actually been implemented.

## Contents
- [Installation](#installation)
- [Features](#features)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Contribution](#contribution)

## Installation

### Requirements
- Operating System: Unix / Linux / MacOS X
  -	Should work on **Windows** if the other requirements are satisfied (except the TUI, due to lack of the **curses** library).
- Python >= 3.7
- A Terminal (with Unicode and ANSI 24-bit color support)

### Steps
The package can be installed via `pip` **(NOT YET UPLOADED!!!)**

```shell
pip install term-img
```
OR

Clone this repository using any method, then navigate into the project directory in a terminal and run

```shell
pip install .
```

## Features
- Multiple format support
- Animated image support
- Variable image size and scale
- Horizontal alignment control
- Terminal size awareness

## Quick Start

The library is really simple to get started with. Here are examples of how you display an image

### From a shell (CLI)
From a local image file
```bash
term-img image.png
```

From a URL
```bash
term-img https://www.example.com/image.png
```
**If multiple sources or at least one directory is given, a TUI is launched to navigate through the images.**

**NOTE:** `python -m term_img` can be used as an alternative to the `term-img` command _(take note of the underscore VS hyphen)_.

### From a Python script
```python
from term_img import DrawImage

image = DrawImage.from_file("image.png")
image.draw_image()
```

You can also use a URL if you don't have the file locally stored
```python
from term_img import DrawImage

image = DrawImage.from_url("https://www.example.com/image.png")
image.draw_image()
```

The library can also be used with PIL images
```python
from PIL import Image
from term_img import DrawImage

image = DrawImage(Image.open("image.png"))
image.draw_image()
```

## Usage

### CLI
Run `term-img --help` to see full usage info.

### TUI
The controls are context based and displayed at the bottom of the terminal window.

### Library
See the [examples]() for usage samples and the [documentation]() for full description and details of the available features.

## Contribution

If you find any bugs or want to suggest a new feature, please open a new issue with proper description (after browsing through the existing issues and making sure you won't create a duplicate).

For code contributions, please make sure you read the [guidelines](CONTRIBUTING.md).

Thanks! :heart:

* * *

**Acknowledging [@pranavbaburaj](https://github.com/pranavbaburaj) for starting the project.**