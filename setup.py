#!/usr/bin/env python
"""
fedflare
==========
.. code:: shell
  $ fedflare domain.com
"""

from setuptools import find_packages, setup
from io import open
import os
import re

_version_re = re.compile(r"__version__\s=\s'(.*)'")

install_requires = [
    "cloudflare"
]
tests_requires = []

docs_requires = [
    "mkdocs==1.2.1",
    "mkdocs-material",
    "mkdocstrings",
    "markdown-include"
]

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

base_dir = os.path.dirname(__file__)

with open(os.path.join(base_dir, "fedflare", "__about__.py"), 'r') as f:
    version = _version_re.search(f.read()).group(1)

setup(
    name="fedflare",
    version=version,
    author="Danila Vershinin",
    author_email="info@getpagespeed.com",
    url="https://github.com/dvershinin/fedflare",
    description="A CLI tool for smart-clearing Cloudflare-cached RPM repositories by Fedora",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=["tests", "docs"]),
    zip_safe=False,
    license="BSD",
    install_requires=install_requires,
    extras_require={
        "tests": install_requires + tests_requires,
        "docs": docs_requires,
        "build": install_requires + tests_requires + docs_requires,
    },
    tests_require=tests_requires,
    include_package_data=True,
    entry_points={"console_scripts": ["fedflare = fedflare:main"]},
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Operating System :: OS Independent",
        "Topic :: Software Development",
        "Topic :: Utilities"
    ],
)
