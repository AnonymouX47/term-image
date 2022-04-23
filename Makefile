py_files = *.py docs/source/conf.py term_img/ term_image/ tests/

check: lint check-format check-imports test-no-url

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

test:
	# Executing using `python -m` adds CWD to `sys.path`.
	python -m pytest -v tests/

test-no-url:
	# Executing using `python -m` adds CWD to `sys.path`.
	python -m pytest -v "--ignore-glob=*url*" tests/
