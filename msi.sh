#! /bin/bash -xe

python3 setup.py bdist_wheel

# build wheels for projects that don't do it
pip wheel -w dist paho-mqtt pybars4 PyMeta3

# download appropriate native-including wheel
pip download --no-deps --platform win_amd64 --dest dist ruamel.yaml.clib

python3 -m venv --clear build/venv
source build/venv/bin/activate

pip install homebrew-pypi-poet wheel pynsist
pip install -U ruamel.yaml.clib setuptools # to get it installed with certain version
pip install -e .[cloud]

mv dist dist-msi
python3 msi.py
echo $?
ls -la build/nsis/Mockintosh_*_x64.exe

deactivate


