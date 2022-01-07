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
- Every pull request should be from a branch other than the default (`main` for development and `docs` for documentation).
- Try to make sure the package is not [obviously] broken at any commit... can be incomplete but **not broken**, at the same time :point_down:
- Avoid making too many unique/substantial changes in a single commit.
  - Closely-related or mutually-dependent changes should not be separated into different commits if doing so will cause the package to be broken at any of the commits.
- Try to make pull requests as specific as possible, though a single one could fix multiple **related** issues.
- Always test that everything works as expected before opening a pull request.

## Style
- Maximum line length is 88 characters.
- Endeavour to run the `check` script for linting and formatting checks before commiting changes.
  - Note that this doesn't confer compatibility across multiple Python versions, final checks will be done automatically when you push the changes.
- Always format your code by running `black .` from the repository root.
- All modules, classes and functions should have docstrings (as specified below) and proper annotations, most especially public ones.
- All docstrings should be written according to the [Google style](https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings) for the following reasons:
  - Uniformity.
  - The reference sections of the documentation are auto-generated from the modules using the `autodoc` and `napoleon` extensions of [Sphinx](https://www.sphinx-doc.org/en/master/).
  - Google-style docstrings + `napoleon` is used instead of pure reStructuredText docstrings for the sake of readability and to reduce the requirements for contribution.
- Please try as much as possible to follow formats or styles already established in the project.
- Any questions or suggestions about these can be asked or given in the [discussions](https://github.com/AnonymouX47/term-img/discussions) section.

* * *

Nothing is too small... some things can be too much though, like rewriting the entire package in one pull request. :smile:

Looking forward to your contributions... Thanks!
