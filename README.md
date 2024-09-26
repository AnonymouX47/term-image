# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/AnonymouX47/term-image/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                  |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|-------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/term\_image/\_\_init\_\_.py       |       59 |        0 |       24 |        1 |     99% |  189->192 |
| src/term\_image/image/block.py        |       96 |        0 |       44 |        3 |     98% |30->37, 116->119, 126->exit |
| src/term\_image/\_ctlseqs.py          |      136 |        6 |        6 |        0 |     96% |245, 268-273 |
| src/term\_image/widget/\_urwid.py     |      303 |       12 |      148 |        7 |     95% |193, 274-277, 353->359, 374->380, 543, 583->586, 599, 622, 628-629, 656-657 |
| src/term\_image/image/common.py       |      683 |       49 |      400 |       17 |     93% |321->exit, 540, 622-623, 729->739, 734->739, 770, 783-785, 940, 997, 1225, 1229, 1290, 1306, 1323-1359, 1469->exit, 1477-1478, 1818->1825, 1890-1893, 1946, 2059-2063, 2163->2165, 2193->2177, 2197->exit, 2203 |
| src/term\_image/image/\_\_init\_\_.py |       21 |        0 |        4 |        2 |     92% |48->51, 49->48 |
| src/term\_image/image/iterm2.py       |      190 |       21 |       92 |        4 |     89% |106-107, 472, 474, 491-502, 530-547, 561, 715->718 |
| src/term\_image/image/kitty.py        |      227 |       34 |       92 |        4 |     82% |299-333, 367-370, 373-377, 396, 450->453, 518->exit, 524-527, 623 |
| src/term\_image/utils.py              |      309 |      165 |      161 |        7 |     45% |51-52, 93, 143, 148->152, 179-184, 187-188, 236->249, 271-293, 307, 310, 333, 366-370, 394, 413-476, 508-527, 542-561, 579-587, 620-631, 636->exit, 678-720, 734, 745-749, 762-794, 801-807, 820->exit, 828, 847-856 |
|                             **TOTAL** | **3064** |  **287** | **1334** |   **45** | **90%** |           |

12 files skipped due to complete coverage.


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/AnonymouX47/term-image/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/AnonymouX47/term-image/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/AnonymouX47/term-image/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/AnonymouX47/term-image/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2FAnonymouX47%2Fterm-image%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/AnonymouX47/term-image/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.