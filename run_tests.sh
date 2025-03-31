#!/bin/bash

# Install test dependencies
pip install -r requirements-dev.txt

# Run tests with coverage
pytest test_signalwire_adapter.py -v --cov=signalwire_adapter --cov-report=term --cov-report=html

echo "HTML coverage report generated in htmlcov/ directory" 