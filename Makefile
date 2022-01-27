check: lint format-check test

.PHONY: docs
docs:
	cd docs/; make html

lint:
	# Much slower when run on `.`, probably processing more files than it should
	flake8 --max-line-length 88 --extend-ignore E203 --extend-exclude build/ --show-source --statistics setup.py term_img/ tests/ docs/source/conf.py
	echo

format:
	black .

format-check:
	black --check --diff --color .
	echo

test:
	python -m pytest -v "--ignore-glob=*url*" tests/
