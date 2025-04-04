.PHONY: build docs

_: check test


# Development Environment Setup

pip:  # Upgrade pip
	python -m pip install --upgrade pip

# # [Un]Install Package

install: pip  # Install package
	python -m pip install .

install-dev: pip  # Install package in develop/editable mode
	python -m pip install -e .

uninstall: pip  # Uninstall package
	python -m pip uninstall --yes term-image

# # Install Dev/Doc Dependencies

req: pip  # Install dev dependencies
	python -m pip install --upgrade -r requirements.txt

req-doc: pip  # Install doc dependencies
	python -m pip install --upgrade -r docs/requirements.txt

req-all: req req-doc

# # Install Dev/Doc Dependencies and Package

dev: req install-dev

dev-doc: req-doc install-dev

dev-all: req-all install-dev


# Pre-commit Checks and Corrections

check: check-code

py_files := src/ docs/source/conf.py tests/

## Code Checks

check-code: lint type check-format check-imports

lint:
	flake8 $(py_files) && echo

type:
	mypy && echo

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

## Filepath variables

test-top-level := tests/test_top_level.py
test-color := tests/test_color.py
test-geometry := tests/test_geometry.py
test-padding := tests/test_padding.py
test-renderable-renderable := tests/renderable/test_renderable.py
test-renderable-types := tests/renderable/test_types.py
test-render-iterator := tests/render/test_iterator.py
test-base := tests/test_image/test_base.py
test-block := tests/test_image/test_block.py
test-kitty := tests/test_image/test_kitty.py
test-iterm2 := tests/test_image/test_iterm2.py
test-url := tests/test_image/test_url.py
test-others := tests/test_image/test_others.py
test-iterator := tests/test_iterator.py
test-widget-urwid-main := tests/widget/urwid/test_main.py
test-widget-urwid-screen := tests/widget/urwid/test_screen.py

test-renderable := $(test-renderable-renderable) $(test-renderable-types)
test-render := $(test-render-iterator)
test-text := $(test-block)
test-graphics := $(test-kitty) $(test-iterm2)
test-image := $(test-base) $(test-text) $(test-graphics) $(test-others)
test-widget-urwid := $(test-widget-urwid-main) $(test-widget-urwid-screen)
test-widget := $(test-widget-urwid)
test := $(test-top-level) $(test-color) $(test-geometry) $(test-padding) $(test-renderable) $(test-render) $(test-image) $(test-iterator) $(test-widget)
test-all := $(test) $(test-url)

## Targets

test-top-level \
test-color \
test-geometry \
test-padding \
test-renderable test-renderable-renderable test-renderable-types \
test-render test-render-iterator \
test-image test-base test-text test-graphics test-block test-kitty test-iterm2 test-url test-others test-iterator \
test-widget test-widget-urwid test-widget-urwid-main test-widget-urwid-screen \
test test-all:
	pytest $($@)

test-cov:
	pytest --cov --cov-append --cov-report=term --cov-report=html $(test)

test-all-cov:
	pytest --cov --cov-report=term --cov-report=html $(test-all)

test-%-cov:
	pytest --cov --cov-append --cov-report=term --cov-report=html $(test-$*)


# Building the Docs

docs:
	cd docs/ && make html

clean-docs:
	cd docs/ && make clean


# Packaging

build: pip
	python -m pip install --upgrade build
	python -m build

clean:
	rm -rf build dist
