## Seting up a development environment

### Requirements
- [Python >= 3.6](https://www.python.org/)
- [Pip](https://pip.pypa.io/en/stable/installation/)
- A new virtual environment
  - This is to ensure all contributors are always on the same page as far as dependency versions are concerned.

### Steps
To install/upgrade all the required python packages for core development, run:

```shell
pip install --upgrade -r requirements.txt
```

To install the required packages for building the documentation, run:

```shell
pip install --upgrade -r docs/requirements.txt
```

You probably also want to install the package in `develop` mode:

```shell
pip install -e .
```
This way, the package and the CLI command are always available in the virtual environment.

Now that you have created a development environment, you can create a new branch and start making changes (after reading the guidelines below :smile:) and when done, contribute your changes by opening a [pull request](https://github.com/AnonymouX47/term-img/pulls).

* * *

Nothing is too small... but some things can be too much though, like rewriting the entire package in one pull request. :smile:

Looking forward to your contributions... Thanks!


## Guidelines
**NAMES tell WHAT... CODE tell HOW... COMMENTS tell WHY, when necessary (and WHAT, when impossible to make it obvious with names)**

- For feature additions, please open a new Feature Request in the [issues section](https://github.com/AnonymouX47/term-img/issues) first to discuss how it would be implemented... you should propose your idea there.
- Every **pull request** should be **from a branch other than the default** (`main`).
- Try to make sure the package is not [obviously] broken at any commit... can be incomplete but **not broken**, at the same time :point_down:
- Avoid making too many unique and substantial changes in a single commit.
  - Closely-related or mutually-dependent changes should not be separated into different commits if doing so will cause the package to be broken at any of the commits.
- Commit messages should be detailed enough, such that a search through the logs with one to three keywords could identify a commit with the changes it made.
- Try to make pull requests as specific as possible, though a single one could fix multiple **related** issues.
- Always test that everything works as expected before opening a pull request.


## Style
- Maximum line length is 88 characters.
- Endeavour to run the checks and tests (as described in the sections below) before commiting changes.
  - Note that this might not confer compatibility across multiple Python versions, final checks will be done automatically when you push the changes.
- Always format your code by running `make format` or `black .` from the repository root.
- All modules, classes and functions should have docstrings (as specified below) and proper annotations, most especially public ones.
- All docstrings should be written according to the [Google style](https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings) for the following reasons:
  - Uniformity.
  - The reference sections of the documentation are auto-generated from the modules using the `autodoc` and `napoleon` extensions of [Sphinx](https://www.sphinx-doc.org/en/master/).
  - Google-style docstrings + `napoleon` is used instead of pure reStructuredText docstrings for the sake of readability and to reduce the requirements for contribution.
- Please try as much as possible to follow formats or styles already established in the project.
- Any questions or suggestions about these can be asked or given in [this discussion](https://github.com/AnonymouX47/term-img/discussions/6).


### Pre-commit Checks
Run:

```shell
make
```
to run linting and formatting checks and tests locally before commiting changes.

If you don't have the `make` utility, see the separate steps below.

### Code linting
Run:

```shell
make lint
```
OR

```shell
	flake8 --max-line-length 88 --extend-ignore E203 --extend-exclude build/ --show-source --statistics .
```
if you don't have the `make` utility.

### Check code formatting
To simply check the formatting without modifying the files, run:

```shell
make format-check
```
OR

```shell
	black --check --diff --color .
```
if you don't have the `make` utility.

### Code formatting
To re-format wrong formated modules (and write to file), run:

```shell
make format
```
OR

```shell
	black .
```
if you don't have the `make` utility.

### Run tests
Run:

```shell
make test
```
OR

```shell
	python -m pytest -v "--ignore-glob=*url*" tests
```
if you don't have the `make` utility.

Tests involving **URL-sourced** images are ignored to help speed up the process and to eliminate the need for internet connection.

### Build the documentation
Run:

```shell
make docs
```
OR

```shell
	cd docs; make html; cd ..
```
if you don't have the `make` utility.
