#! /bin/bash -xe

python3 setup.py bdist_wheel
pip download --no-deps --platform win_amd64 --dest dist ruamel.yaml.clib

python3 -m venv --clear build/venv
source build/venv/bin/activate

pip install homebrew-pypi-poet wheel pynsist
pip install ruamel.yaml.clib six~=1.15
pip install -e .[cloud]
python3 msi.py

deactivate


