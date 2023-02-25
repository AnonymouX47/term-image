py_files := *.py src/* docs/source/conf.py tests/

_: check test

.PHONY: build
build:
	python -m pip install --upgrade pip
	python -m pip install --upgrade build
	python -m build

# Docs

clean-docs:
	cd docs/ && make clean

.PHONY: docs
docs:
	cd docs/ && make html

# Pre-commit checks

check: lint check-format check-imports

check-format:
	black --check --diff --color $(py_files) && echo

check-imports:
	isort --check --diff --color $(py_files) && echo

format:
	black $(py_files)

imports:
	isort $(py_files)

lint:
	flake8 $(py_files) && echo

# Installation

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

# Tests

pytest := pytest -v

## Filepath variables

test-top := tests/test_top_level.py
test-base := tests/test_image/test_base.py
test-block := tests/test_image/test_block.py
test-kitty := tests/test_image/test_kitty.py
test-iterm2 := tests/test_image/test_iterm2.py
test-url := tests/test_image/test_url.py
test-others := tests/test_image/test_others.py
test-iterator := tests/test_iterator.py
test-urwid := tests/test_widget/test_urwid.py

test-text := $(test-block)
test-graphics := $(test-kitty) $(test-iterm2)
test-image := $(test-base) $(test-text) $(test-graphics) $(test-others)
test-widget := $(test-urwid)
test := $(test-top) $(test-image) $(test-iterator) $(test-widget)
test-all := $(test) $(test-url)

## Targets

test-all test test-image test-text test-graphics test-widget \
test-top test-base test-block test-kitty test-iterm2 test-url test-others test-iterator test-urwid:
	$(pytest) $($@)
