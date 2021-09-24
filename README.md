<div align="center">
<h1><b>Img</b></h1>
Display Images in your terminal with python

<hr>
<img src="https://i.imgur.com/O1zIgca.png">
<hr>
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

