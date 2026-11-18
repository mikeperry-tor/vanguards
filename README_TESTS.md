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

## Tor control smoke test

From a checkout with Docker available, build the test image and run the control
fixture. The image build fetches dependencies. The fixture runs with container
networking disabled and starts Tor with disposable configuration and state.

```sh
docker build -f tests/integration/Dockerfile -t vanguards-integration-local .
docker run --rm --network none \
  --mount "type=bind,source=$PWD/src,target=/checkout/src,readonly" \
  --mount "type=bind,source=$PWD/tests/integration,target=/checkout/tests/integration,readonly" \
  vanguards-integration-local tests/integration/control_smoke.py
```

This checks Unix and TCP control authentication, option and event availability,
and the launcher's retry when no consensus is available. The fixture runs
before bootstrap.
