.PHONY: pytest

pytest:
	pytest -v -s tests/

black:
	git ls-files | grep \.py$$ | xargs black --exclude="example_workflows"