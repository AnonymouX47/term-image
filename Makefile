py_files = *.py src/* docs/source/conf.py tests/

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

test-all: test test-url
test: test-base test-iterator test-others test-graphics test-text
test-graphics: test-kitty test-iterm2
test-text: test-block

# Executing using `python -m` adds CWD to `sys.path`.

test-base:
	python -m pytest -v tests/test_base.py

test-iterator:
	python -m pytest -v tests/test_image_iterator.py

test-others:
	python -m pytest -v tests/test_others.py

test-iterm2:
	python -m pytest -v tests/test_iterm2.py

test-kitty:
	python -m pytest -v tests/test_kitty.py

test-block:
	python -m pytest -v tests/test_block.py

test-url:
	python -m pytest -v tests/test_url.py
