check: lint check-format check-imports test-no-url

check-format:
	black --check --diff --color .
	echo

check-imports:
	isort --check --diff --color .
	echo

.PHONY: docs
docs:
	cd docs/; make html

format:
	black .

imports:
	isort .

lint:
	flake8 .
	echo

test:
	# Executing using `python -m` adds CWD to `sys.path`.
	python -m pytest -v tests/

test-no-url:
	# Executing using `python -m` adds CWD to `sys.path`.
	python -m pytest -v "--ignore-glob=*url*" tests/
