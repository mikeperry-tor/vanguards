"""setup.py: setuptools control."""

import io
import os
import sys

from setuptools import find_packages
from setuptools import setup

DESCRIPTION = """
For the full README and other project information, please see the
`Vanguard project page on github <https://github.com/mikeperry-tor/vanguards>`_.
"""

# Read version and other info from package's __init.py file
module_info = {}
init_path = os.path.join(os.path.dirname(__file__), "src", 'vanguards',
                         '__init__.py')
with open(init_path) as init_file:
    exec(init_file.read(), module_info)


import sys

from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    user_options = [("pytest-args=", "a", "Arguments to pass to pytest")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = "tests"

    def run_tests(self):
        import shlex

        # import here, cause outside the eggs aren't loaded
        import pytest

        errno = pytest.main(shlex.split(self.pytest_args))
        sys.exit(errno)

def read(*names, **kwargs):
    return io.open(
        os.path.join(os.path.dirname(__file__), *names),
        encoding=kwargs.get("encoding", "utf8")
    ).read()

setup(
    name="vanguards",
    packages=find_packages('src'),
    package_dir={'': 'src'},
    entry_points={
        "console_scripts": [
            'vanguards = vanguards.main:main',
        ]},
    description="Vanguards help guard you from getting vanned...",
    long_description=DESCRIPTION,
    include_package_data=True,
    version=module_info.get('__version__'),
    author=module_info.get('__author__'),
    author_email=module_info.get('__contact__'),
    url=module_info.get('__url__'),
    license=module_info.get('__license__'),
    tests_require=['pytest'],
    cmdclass={"test": PyTest},
    keywords='tor',
    install_requires=[
        'setuptools',
        'ipaddress>=1.0.17 ; python_version<"3"',
        'stem==1.5.4',
        ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ]
)
