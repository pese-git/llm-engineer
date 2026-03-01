.DEFAULT_GOAL := all
DIRS = src/
uv = uv run
mypy = mypy


.PHONY: format
format:
	ruff format .
	ruff check . --fix

.PHONY: typecheck
typecheck:
	mypy $(DIRS)

.PHONY: all
all: format
