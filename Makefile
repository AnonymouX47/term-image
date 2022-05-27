py_files = *.py docs/source/conf.py term_img/ term_image/ tests/

_: check test

check: lint check-format check-imports

check-format:
	black --check --diff --color $(py_files) && echo

check-imports:
	isort --check --diff --color $(py_files) && echo

clean-docs:
	cd docs/ && make clean

.PHONY: docs
docs:
	cd docs/ && make html

format:
	black $(py_files)

imports:
	isort $(py_files)

lint:
	flake8 $(py_files) && echo


# Executing using `python -m` adds CWD to `sys.path`.

test: test-base test-iterator test-others test-text test-graphics
test-text: test-term
test-graphics: test-kitty

test-base:
	python -m pytest -v tests/test_base.py

test-iterator:
	python -m pytest -v tests/test_image_iterator.py

test-others:
	python -m pytest -v tests/test_others.py

test-kitty:
	python -m pytest -v tests/test_kitty.py

test-term:
	python -m pytest -v tests/test_term.py

test-url:
	python -m pytest -v tests/test_url.py
