# Contributing to Term-Image

First off, thanks for taking the time to contribute! :heart:

All types of contributions are encouraged and valued. See the [Table of Contents](#table-of-contents) for different ways to help and details about how this project handles them. Please make sure to read the relevant section before making your contribution. It will make it a lot easier for us maintainers and smooth out the experience for all involved. The community looks forward to your contributions. 

> And if you like the project, but just don't have time to contribute, that's fine. There are other easy ways to support the project and show your appreciation, which we would also be very happy about:
> - Star the project
> - Tweet about it or mention it in a potentially interested community
> - Refer this project in your project's readme
> - Mention the project at local meetups and tell your friends/colleagues

Any questions or suggestions about the contents of this document can be asked or given in [this discussion](https://github.com/AnonymouX47/term-image/discussions/9).


## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [I Have a Question](#i-have-a-question)
- [I Want to Contribute](#i-want-to-contribute)
  - [Legal Notice](#legal-notice)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
  - [Improving the Documentation](#improving-the-documentation)
  - [Contributing Code](#contributing-code)
- [Style Guides](#style-guides)
  - [Commit Style](#commit-style)
  - [Code Style](#code-style)
  - [Documentation Style](#documentation-style)
- [Setting up a Development Environment](#setting-up-a-development-environment)
- [Pre-commit Checks and Corrections](#pre-commit-checks-and-corrections)
  - [Code Checks](#code-checks)
  - [Code Corrections](#code-corrections)
  - [Documentation Checks](#documentation-checks)
  - [Documentation Corrections](#documentation-corrections)
- [Running the Tests](#running-the-tests)
- [Building the Documentation](#building-the-documentation)
- [Attribution](#attribution)


## Code of Conduct

This project and everyone participating in it is governed by the [term-image Code of Conduct](/CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code. Please report unacceptable behavior to <anonymoux47@gmail.com>.


## I Have a Question

> If you want to ask a question, we assume that you have read the available [documentation](https://term-image.readthedocs.io/en/latest).

Before you ask a question, it is best to search for existing [discussions](https://github.com/AnonymouX47/term-image/discussions) and [issues](https://github.com/AnonymouX47/term-image/issues) that might help you. In case you have found a suitable discussion or issue and still need clarification, you can write your question in this discussion or issue. It is also advisable to search the internet for answers first.

If you then still feel the need to ask a question and need clarification, we recommend the following:

- Open a [discussion](https://github.com/AnonymouX47/term-image/discussions/new).
- Provide as much context as you can about your question.
- Provide project and platform versions, depending on what seems relevant.

We will then answer the question as soon as possible.


## I Want to Contribute

### Legal Notice

When contributing to this project, you must agree that you have authored 100% of the content, that you have the necessary rights to the content and that the content you contribute may be provided under the [term-image license](/LICENSE).

If by any means, any content which you didn't author is included, this should be clearly and duely noted along with any neccesary attribution and license/copyright notices.
**NOTE:** We can not guarantee that such contributions will be accepted.


### Reporting Bugs

#### Before Submitting a Bug Report

A good bug report shouldn't leave others needing to chase you up for more information. Therefore, we ask you to investigate carefully, collect information and describe the issue in detail in your report. Please complete the following steps in advance to help us fix any potential bug as fast as possible.

- Make sure that you are using the latest version.
- Determine if your bug is really a bug and not an error on your side e.g. using incompatible environment components/versions.
  - Make sure that you have read the [documentation](https://term-image.readthedocs.io/en/latest).
  - If you are looking for support, you might want to check [this section](#i-have-a-question).
- To see if other users have experienced (and potentially already solved) the same issue you are having, check if there is not already a report existing for your bug or error in the [bug tracker](https://github.com/AnonymouX47/term-image/issues?q=label%3Abug).
- Also make sure to search the internet to see if users outside of the GitHub community have discussed the issue.
- Collect information about the bug:
    - Stack trace (Traceback), if applicable.
    - OS, Platform and Version (Windows, Linux, macOS, x86, ARM)
    - Version of the interpreter, compiler, SDK, runtime environment, package manager, depending on what seems relevant.
    - Possibly your input and the output
    - Can you reliably reproduce the issue? And can you also reproduce it with older versions?

#### How Do I Submit a Good Bug Report?

> You must never report security related issues, vulnerabilities or bugs including sensitive information to the issue tracker, or elsewhere in public. Instead sensitive bugs must be sent by email to <anonymoux47@gmail.com>.

We use [GitHub issues](https://github.com/AnonymouX47/term-image/issues) to track bugs and errors. If you run into an issue with the project:

- Open an [issue](https://github.com/AnonymouX47/term-image/issues/new/choose) (before you label it as a bug, please be sure it is).
- Explain the behavior you would expect and the actual behavior.
- Please provide as much context as possible and describe the *reproduction steps* that someone else can follow to recreate the issue on their own. This usually includes your code. For good bug reports you should isolate the problem and create a reduced test case.
- Provide the information you collected in the previous section.

Once it's filed:

- The project team will label the issue accordingly.
- A team member will try to reproduce the issue with your provided steps. If there are no reproduction steps or no obvious way to reproduce the issue, the team will ask you for those steps.
- If the team is able to reproduce the issue, it will be labeled appropriately, and the issue will be left to be [fixed by someone](#contributing-code).


### Suggesting Enhancements

This section guides you through submitting an enhancement suggestion, **including completely new features and minor improvements to existing functionality**. Following these guidelines will help maintainers and the community to understand your suggestion and find related suggestions.

#### Before Submitting an Enhancement

- Make sure that you are using the latest version.
- Read the [documentation](https://term-image.readthedocs.io/en/latest) carefully and find out if the functionality is already covered, maybe by an individual configuration.
- Perform a [search](https://github.com/AnonymouX47/term-image/issues) to see if the enhancement has already been suggested. If it has, add a comment to the existing issue instead of opening a new one.
- Find out whether your idea fits with the scope and aims of the project. It's up to you to make a strong case to convince the project's developers of the merits of this feature. Keep in mind that we want features that will be useful to the majority of our users and not just a small subset.

#### How Do I Submit a Good Enhancement Suggestion?

Enhancement suggestions are tracked as [GitHub issues](https://github.com/AnonymouX47/term-image/issues).

- Use a **clear and descriptive (not long) title** for the issue to identify the suggestion.
- Provide a **step-by-step description of the suggested enhancement** in as many details as possible.
- **Describe the current behavior** and **explain which behavior you expected to see instead** and why. At this point you can also tell which alternatives do not work for you.
- You may want to **include screenshots and/or brief screencasts** which help you demonstrate the steps or point out the part which the suggestion is related to.
- **Explain why this enhancement would be useful** to most **term-image** users. You may also want to point out the other projects that solved it better and which could serve as inspiration.


### Improving the Documentation

- Set up a [development environment](#setting-up-a-development-environment) (you may skip **step 1** if you wish).
- Go through and follow the [style guides](#style-guides).
- Before commiting changes, run the neccesary [checks](#documentation-checks), make any neccesary [correction](#documentation-corrections) and ensure they pass.
- Before opening a pull request, ensure the documentation [builds](#building-the-documentation) successfully.
- Open a [pull request](https://github.com/AnonymouX47/term-image/compare) from **a branch (of your fork) other than the default (`main`)** into the **upstream `main` branch** (except stated otherwise). Any pull request **from** the **default branch** will not be merged.
- If the pull request is **incomplete**, convert the pull request into a **draft**.


### Contributing Code

- Set up a [development environment](#setting-up-a-development-environment).
- Ensure the bug fix or enhancement has been discussed and the approach for implementation decided. If not, [suggest the enhancement](#suggesting-enhancements) before going ahead to implementation.
- Go through and follow the [style guides](#style-guides).
- Before commiting changes, run all [checks](#code-checks), make any neccesary [correction](#code-corrections) and ensure they pass.
- Before opening a pull request:
  - Add or update tests for the feature being added, improved or fixed.
  - Run all [tests](#running-the-tests), make any neccesary correction and ensure they pass.
  - Ensure everything you've implemented up to the latest commit works as expected.
  - Note that the sub-steps above might not confer compatibility across multiple Python versions or platforms, final checks will be done automatically when you push the changes or open a pull request.
- Open a [pull request](https://github.com/AnonymouX47/term-image/compare) from **a branch (of your fork) other than the default (`main`)** into the **upstream `main` branch** (except stated otherwise). Any pull request **from** the **default branch** will not be merged.
- If implementation is **incomplete**, convert the pull request into a **draft**.


## Style Guides

### Commit Style

Please put some effort into breaking your contribution up into a series of well formed commits. There is a good guide available at https://cbea.ms/git-commit/.

- Always run the [checks and corrections](#pre-commit-checks-and-corrections) before commiting changes.
- Each commit should ideally contain only one change
- Don't bundle multiple **unrelated** changes into a single commit
- Write descriptive and well formatted commit messages

#### Commit Messages

- Separate subject from body with a blank line
- Limit the subject line to 50 characters
- Capitalize the subject line
- Do not end the subject line with a period
- Use the imperative mood in the subject line
- Wrap the body at 72 characters
- Use the body to explain what and why vs. how

For a more detailed explanation with examples see the guide at https://cbea.ms/git-commit/.


### Code Style

- **NAMES tell WHAT... CODE tells HOW... COMMENTS tell WHY, when necessary (and WHAT, when impossible/unreasonable to make it obvious with names)**.
- Maximum line length is 88 characters.
- All functions (including methods) should be adequately annotated.
  - **Note:** Currently, annotations are only for documentation purposes and better/quicker comprehension of the defined interfaces by the users and developers.
- Try to keep things (definitions, names, dictionary keys, etc...) **sorted** wherever reasonably possible.
  - Makes finding things quicker and easier :smiley:.
- For any matter of style not directly/indirectly addressed here, please try as much as possible to follow formats or styles already established in the project.
- Any questions or suggestions about the above can be asked or given in [this discussion](https://github.com/AnonymouX47/term-image/discussions/7).
- See also: [Documentation Style](#documentation-style).


### Documentation Style

- The documentation source is being written in the [reStructuredText](https://docutils.sourceforge.io/rst.html) (reST) markup syntax.
- All modules, classes and functions (including methods) should have docstrings (as specified below).
- All docstrings should be written according to the [Google style](https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings) for the following reasons:
  - Uniformity.
  - The reference section of the documentation is auto-generated from the modules using the `autodoc` and `napoleon` extensions of [Sphinx](https://www.sphinx-doc.org/en/master/).
  - Google-style docstrings + `napoleon` is used instead of pure reStructuredText docstrings for the sake of readability and to reduce the requirements for contribution.
- Any questions or suggestions about the above can be asked or given in [this discussion](https://github.com/AnonymouX47/term-image/discussions/3).


## Setting up a Development Environment

### Requirements

- [Python](https://www.python.org/) >= 3.7
- [Pip](https://pip.pypa.io/en/stable/installation/)
- A new virtual environment
  - This is to ensure all contributors can always be on the same page as far as dependency versions are concerned.

### Steps

**0.** Fork [this repository](https://github.com/AnonymouX47/term-image) and clone your fork.

**1.** Install/upgrade the required dependencies for core development:

```shell
make install-req
```
OR
```shell
pip install --upgrade -r requirements.txt
```

**2.** Install the package in *develop*/*editable* mode:

```shell
make install
```
OR
```shell
pip install -e .
```
This way, the package is always available within the virtual environment.

**NOTE:** This is required to build the docs and to run tests.

**3.** Install the required dependencies for building the documentation:

```shell
make install-req-docs
```
OR
```shell
pip install --upgrade -r docs/requirements.txt
```


## Pre-commit Checks and Corrections

See the [Makefile](/Makefile) for the complete (and always up-to-date) list of check and correction targets.

### All Code and Documentation Checks

```shell
make check
```


### Code Checks

The following steps perform checks and report any errors without modifying source files. See [Code Corrections](#code-corrections) for how to correct any errors reported.

#### All Code Linting and Formatting Checks

```shell
make check-code
```

If you don't have the `make` utility, see the separate steps below.

#### Code Linting Check

```shell
make lint
```
OR

```shell
flake8 .
```

#### Code Formatting Check

```shell
make check-format
```
OR

```shell
black --check --diff --color .
```

#### Imports Formatting Check

```shell
make check-imports
```
OR

```shell
isort --check --diff --color .
```


### Code Corrections

The following steps correct errors reported by [Code Checks](#code-checks) and modify source files.

#### Code Linting Correction

At times, the other correction steps might take care of linting errors. Otherwise, they have to be corrected **manually**.

#### Code Formatting Correction

```shell
make format
```
OR

```shell
black .
```

#### Imports Formatting Correction

```shell
make imports
```
OR

```shell
isort .
```


### Documentation Checks

The following steps perform checks and report any errors without modifying source files. See [Documentation Corrections](#documentation-corrections) for how to correct any errors reported.

*Comming soon...*


### Documentation Corrections

The following steps correct errors reported by [Documentation Checks](#documentation-checks) and modify source files.

*Comming soon...*


## Running the Tests

See the [Makefile](/Makefile) for the complete (and always up-to-date) list of test targets.

### Run all tests

```shell
make test-all
```
OR

```shell
pytest -v tests
```

### Run non-URL-related tests

*This excludes tests involving **URL-sourced** images to help speed up the process and to eliminate the need for internet connection.*

```shell
make test
```

### Run URL-related tests

```shell
make test-url
```
OR

```shell
pytest -v tests/test_image/test_url.py
```

### Run render-style-specific tests

```shell
make test-<style>
```
OR

```shell
pytest -v tests/test_image/test_<style>.py
```
Where *<style>* is the name of the render style, in **lowercase** e.g *iterm2*, *kitty*.

### Run tests for all text-based render styles

```shell
make test-text
```

### Run tests for all graphics-based render styles

```shell
make test-graphics
```


## Building the Documentation

```shell
make docs
```
OR

```shell
cd docs; make html; cd ..
```


## Attribution

This guide is based on the **CONTRIBUTING.md**. [Make your own](https://contributing.md/)!

Some parts of this guide were adapted from https://cbea.ms/git-commit/ and [@ihabunek's toot/CONTRIBUTING.md](https://github.com/ihabunek/toot/blob/master/CONTRIBUTING.md).
