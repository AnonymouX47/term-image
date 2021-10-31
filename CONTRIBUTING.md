## How to setup a development environment
### Requirements
- [Python >= 3.6](https://www.python.org/)
- [Pip](https://pip.pypa.io/en/stable/installation/)
- (Optional but recommended) A virtual environment

Run this to install all the required python packages
```sh
pip install -r requirements.txt
```

Now that you have created a development environment, you can contribute your code by creating a [pull request](https://github.com/AnonymouX47/term-img/pulls).

## Guidelines
**NAMES tell WHAT... CODE tell HOW... COMMENTS tell WHY, when necessary (and WHAT, when impossible to make it obvious with names)**

- For feature additions, please open a new Feature Request in the [issues section](https://github.com/AnonymouX47/term-img/issues) first to discuss how it would be implemented... you should propose your idea there.
- Try to make pull requests as specific as possible.
- Try to make sure the package is not in a broken state at any commit... can be incomplete but **not broken**.
- Always test that everything works as expected before opening a pull request.

## Style
- Maximum line length is 88 characters.
- Endeavour to run the `check` script for linting and formatting checks before commiting changes.
  - Note that this doesn't confer compatibility across multiple Python versions, final checks will be done automatically when you push the changes.
- Always format your code by running `black .` from the repository root.
- Please try as much as possible to follow formats already used in the project e.g for docstrings, etc...
- Any questions or suggestions about these can asked or given in the [discussions](https://github.com/AnonymouX47/term-img/discussions) tab.

* * *

Nothing is too small... some things can be too much though, like rewriting the entire package in one pull request. :smile:

Looking forward to your contributions...
