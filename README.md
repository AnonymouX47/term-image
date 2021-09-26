<div align="center">
<h1><b><code>Img</code></b></h1>
Display Images in your terminal with python

<br>
 
<img src="https://i.imgur.com/O1zIgca.png" height="250">
<br>

 <!-- <img src="https://cdn.discordapp.com/attachments/875983412639436850/891594483626573844/unknown.png" height="250"> -->

<p align="center">
    <img src="https://static.pepy.tech/badge/terminal-img">
    <img src="https://badges.frapsoft.com/os/v1/open-source.svg?v=103">
    <img src="https://img.shields.io/github/last-commit/pranavbaburaj/img">
    <a href="https://twitter.com/intent/tweet?text=Display%20images%20in%20the%20the%20terminal%20using%20python&url=https://github.com/pranavbaburaj/img&via=_pranavbaburaj&hashtags=developers,images,terminal"><img src="https://img.shields.io/twitter/url/http/shields.io.svg?style=social"></a>
  </p>

</div>

## Installation

The package can be installed via `pip`

```py
pip install terminal-img
```

## Quick Start

The library is really simple to get started with. Here's is an example of how you display an image

```py
from image import DrawImage

image = DrawImage("image.png")
```

> You can also use a url if you dont have the file locally stored

```py
image = DrawImage.from_url("url")
```

## Methods

#### `image.DrawImage`

- `filename`: The name of the file containing the image
- `size`(_`Optional[Tuple]`_) : The size of the image to be displayed. Default: 24, 24
- `draw`: Whether to draw on creating an instance or wait for the user to call the function

#### `image.DrawImage.from_url`

- `url` : The url of the image
- `size`(_`Optional[Tuple]`_) : The size of the image to be displayed. Default: 24, 24
- `draw`: Whether to draw on creating an instance or wait for the user to call the function
