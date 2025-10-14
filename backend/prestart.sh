#! /usr/bin/env bash

set -e
set -x

PYTHON_CMD=python3

# Check if python3 exists, else fallback to python
if ! command -v $PYTHON_CMD &> /dev/null; then
    PYTHON_CMD=python
fi

# Let the DB start
$PYTHON_CMD app/prestart.py
$PYTHON_CMD app/initialize.py
$PYTHON_CMD app/scripts.py