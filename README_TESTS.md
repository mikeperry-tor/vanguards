# How to run the tests

This repository is configured to run unit tests on every commit in a pinned
virtual environment via [Travis CI](https://travis-ci.org/mikeperry-tor/vanguards/).

You can run the tests yourself with the python-tox and python-pytest packages,
simply by running 'tox' in the root directory of this source tree. This will
re-create the same test environment run on Travis CI, with the same pinned
dependency versions.

To use your distribution's packages instead, run:

```
 tox -c tox-systemonly.ini
```

or for each python version individually as:

```
 TOXENV=py27 tox -c tox-systemonly.ini
 TOXENV=py35 tox -c tox-systemonly.ini
 TOXENV=pypy tox -c tox-systemonly.ini
```


This will run python2.7, python3.5, and pypy tests, **as well as check your
system-installed packages for known vulnerabilities against
https://pyup.io/safety**.

To run just the tests in the bare source tree against the git checkout in
combination with system-wide packages, with no installation or known
vulnerability checks, run:

```
 PYTHONPATH=src python2 -m pytest tests/
 PYTHONPATH=src python3 -m pytest tests/
 PYTHONPATH=src pypy -m pytest tests/ 
```

After system-wide installation of the vanguards package, you can run the tests
without the PYTHONPATH specifier, to check the installed package:

```
 python2 -m pytest tests/
 python3 -m pytest tests/
 pypy -m pytest tests/ 
```
