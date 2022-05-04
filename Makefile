py_files = *.py docs/source/conf.py term_img/ term_image/ tests/

check: lint check-format check-imports test test-text

check-format:
	black --check --diff --color $(py_files)
	echo

check-imports:
	isort --check --diff --color $(py_files)
	echo

clean-docs:
	cd docs/; make clean

.PHONY: docs
docs:
	cd docs/; make html

format:
	black $(py_files)

imports:
	isort $(py_files)

lint:
	flake8 $(py_files)
	echo


# Executing using `python -m` adds CWD to `sys.path`.

test: test-base test-iterator

test-text: test-term

test-base:
	python -m pytest -v tests/test_base.py

test-iterator:
	python -m pytest -v tests/test_image_iterator.py

test-term:
	python -m pytest -v tests/test_term.py

test-url:
	python -m pytest -v tests/test_url.py
