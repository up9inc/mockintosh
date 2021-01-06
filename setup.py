#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
# To use a consistent encoding
from codecs import open
from os import path

from setuptools import setup, find_packages

__location__ = path.abspath(path.dirname(__file__))


def read_requirements():
    """parses requirements from requirements.txt"""
    reqs_path = path.join(__location__, 'requirements.txt')
    with open(reqs_path, encoding='utf8') as f:
        reqs = [line.strip() for line in f if not line.strip().startswith('#')]

    names = []
    for req in reqs:
        names.append(req)
    return {'install_requires': names}


# Get the long description from the README file
with open(path.join(__location__, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='mockintosh',
    description='The API mocking server for microservice environments',
    long_description=long_description,
    long_description_content_type='text/markdown',

    # The project's main homepage.
    url='https://github.com/up9inc/mockintosh',

    # Choose your license
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Natural Language :: English',
        'Programming Language :: Python :: 3 :: Only',
    ],

    # What does your project relate to?
    keywords='mock api json restful automatic web server generator configuration',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(),

    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    **read_requirements(),

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'dev': [
            'flake8',
            'psutil',
            'pytest',
            'coverage',
            'codecov',
            'requests'
        ]
    },

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={
        # If any package contains data files, include them:
        'mockintosh': ['schema.json', 'res/*', 'ssl/*']
    },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    data_files=[],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'mockintosh=mockintosh:initiate',
        ],
    },
    ext_modules=[]
)
