.PHONY: help test

help:
	@echo "Available targets:"
	@echo "  make test    Run the test suite"

test:
	poetry run pytest
