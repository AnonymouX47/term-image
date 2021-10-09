<div align="center">
<h1><b><code>Img</code></b></h1>
Display Images in your terminal with python
 
 <br>
<img src="https://i.imgur.com/O1zIgca.png" height="150">


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

image = DrawImage.from_file("image.png")
image.draw_image()
```

> You can also use a url if you dont have the file locally stored

```py
image = DrawImage.from_url("url")
image.draw_image()
```

> The library can also be used with PIL images
```py
from PIL import Image
from image import DrawImage

img = DrawImage(Image.open("img.png"))
img.draw_image()
```

## Methods


#### `image.DrawImage`

- `image`: The PIL image
- `size`(_`Optional[Tuple]`_) : The size of the image to be displayed. Default: 24, 24


#### `image.DrawImage.from_file`

- `filename`: The name of the file containing the image
- `size`(_`Optional[Tuple]`_) : The size of the image to be displayed. Default: 24, 24

#### `image.DrawImage.from_url`

- `url` : The url of the image
- `size`(_`Optional[Tuple]`_) : The size of the image to be displayed. Default: 24, 24



Special thanks to [@AnonymouX47](https://github.com/AnonymouX47) ❤
