check: lint check-format check-imports test-no-url

check-format:
	black --check --diff --color .
	echo

check-imports:
	isort --check --diff --color --combine-as .
	echo

.PHONY: docs
docs:
	cd docs/; make html

format:
	black .

imports:
	isort --combine-as .

lint:
	flake8 --count --max-line-length 88 --extend-ignore E203 --extend-exclude build/ --show-source --statistics .
	echo

test:
	# Executing using `python -m` adds CWD to `sys.path`.
	python -m pytest -v tests/

test-no-url:
	# Executing using `python -m` adds CWD to `sys.path`.
	python -m pytest -v "--ignore-glob=*url*" tests/
