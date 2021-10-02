#! /bin/bash -xe

python3 setup.py bdist_wheel

# build wheels for projects that don't do it
pip wheel -w dist paho-mqtt pybars4 PyMeta3

# download appropriate native-including wheel
pip download --no-deps --platform win_amd64 --dest dist ruamel.yaml.clib

python3 -m venv --clear build/venv
source build/venv/bin/activate

pip install homebrew-pypi-poet wheel pynsist
pip install ruamel.yaml.clib openapi-spec-validator
pip install -e .[cloud]
python3 msi.py

deactivate


