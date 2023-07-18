.PHONY: build docs

_: check test


# Development Environment Setup

pip:
	python -m pip install --upgrade pip

install: install-req
	python -m pip install -e .

install-all: pip
	python -m pip install --upgrade -e . -r requirements.txt -r docs/requirements.txt

install-req: pip
	python -m pip install --upgrade -r requirements.txt

install-req-all: pip
	python -m pip install --upgrade -r requirements.txt -r docs/requirements.txt

install-req-docs: pip
	python -m pip install --upgrade -r docs/requirements.txt

uninstall:
	pip uninstall -y term-image


# Pre-commit Checks and Corrections

check: check-code

py_files := *.py src/ docs/source/conf.py tests/

## Code Checks

check-code: lint check-format check-imports

lint:
	flake8 $(py_files) && echo

check-format:
	black --check --diff --color $(py_files) && echo

check-imports:
	isort --check --diff --color $(py_files) && echo

## Code Corrections

format:
	black $(py_files)

imports:
	isort $(py_files)


# Tests

pytest := pytest -v

## Filepath variables

test-top := tests/test_top_level.py
test-geometry := tests/test_geometry.py
test-renderable-renderable := tests/renderable/test_renderable.py
test-base := tests/test_image/test_base.py
test-block := tests/test_image/test_block.py
test-kitty := tests/test_image/test_kitty.py
test-iterm2 := tests/test_image/test_iterm2.py
test-url := tests/test_image/test_url.py
test-others := tests/test_image/test_others.py
test-iterator := tests/test_iterator.py
test-urwid := tests/test_widget/test_urwid.py

test-renderable := $(test-renderable-renderable)
test-text := $(test-block)
test-graphics := $(test-kitty) $(test-iterm2)
test-image := $(test-base) $(test-text) $(test-graphics) $(test-others)
test-widget := $(test-urwid)
test := $(test-top) $(test-geometry) $(test-renderable) $(test-image) $(test-iterator) $(test-widget)
test-all := $(test) $(test-url)

## Targets

test-all test test-renderable test-text test-graphics test-image test-widget \
test-top test-geometry test-base test-block test-kitty test-iterm2 test-url test-others test-iterator test-urwid:
	$(pytest) $($@)


# Building the Docs

docs:
	cd docs/ && make html

clean-docs:
	cd docs/ && make clean


# Packaging

build:
	python -m pip install --upgrade pip
	python -m pip install --upgrade build
	python -m build

clean:
	rm -rf build dist
