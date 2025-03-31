#!/bin/bash

# Install dependencies using Poetry
poetry install

# Run tests with coverage using Poetry (pytest settings from pyproject.toml)
poetry run pytest

echo "HTML coverage report generated in htmlcov/ directory" 