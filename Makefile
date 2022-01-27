check: lint format-check test

.PHONY: docs
docs:
	cd docs/; make html

lint:
	flake8 --max-line-length 88 --extend-ignore E203 --extend-exclude build/ --show-source --statistics .
	echo

format:
	black .

format-check:
	black --check --diff --color .
	echo

test:
	python -m pytest -v "--ignore-glob=*url*" tests/
