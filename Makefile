.PHONY: docs-install docs-serve docs-build docs-deploy docs-clean

docs-install:
	pip install -r docs-requirements.txt

docs-serve:
	mkdocs serve

docs-build:
	mkdocs build --strict

docs-deploy:
	mkdocs gh-deploy --force --clean

docs-clean:
	rm -rf site/
