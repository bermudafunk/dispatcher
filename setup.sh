#!/usr/bin/env bash

if [ ! -d env ]; then
    virtualenv -p python3.5 env
fi

source env/bin/activate
pip install --upgrade pip
pip install --upgrade setuptools
pip install --upgrade -r requirements.txt

echo $(python -V)
