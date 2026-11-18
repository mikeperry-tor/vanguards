# Run the tests

The unit suite uses local fixtures. It does not require Docker or a connection
to the Tor network. Use a virtual environment with Python 3.11 or later.

To test the source tree, run these commands from the repository root.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.txt -r test-requirements.txt
PYTHONPATH=src python -m pytest tests/
```

To test the installed package, also install the checkout in the environment
and run the suite with the default import path.

```sh
python -m pip install --no-deps .
python -m pytest tests/
```

With tox installed, run `tox` to test the wheel on CPython 3.11 through 3.15.
Use `tox -e py313` to select one interpreter.
