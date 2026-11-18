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
docker build --target control -f tests/integration/Dockerfile -t vanguards-integration-local .
docker run --rm --network none \
  --mount "type=bind,source=$PWD/src,target=/checkout/src,readonly" \
  --mount "type=bind,source=$PWD/tests/integration,target=/checkout/tests/integration,readonly" \
  vanguards-integration-local tests/integration/control_smoke.py
```

This checks Unix and TCP control authentication, option and event availability,
and the launcher's retry when no consensus is available. The fixture runs
before bootstrap.

## Private onion-service qualification

Use a disposable checkout of the pinned Chutney revision. Run these commands
from the Vanguards checkout. The test starts its own directory authorities and
relays, and uses separate v3 onion services for the two guard modes. A Tor
client exercises both services inside the Docker container.

```sh
chutney_dir=$(mktemp -d /tmp/vanguards-chutney.XXXXXX)
git clone https://github.com/torproject/chutney.git "$chutney_dir"
git -C "$chutney_dir" checkout --detach 62b54a55215c94eb14adc22c5acd17b2ada04b76
docker build --target onion -f tests/integration/Dockerfile -t vanguards-onion-local .
docker run --rm --network none -e PYTHONPATH=/checkout/src \
  --mount "type=bind,source=$PWD/src,target=/checkout/src,readonly" \
  --mount "type=bind,source=$PWD/tests/integration,target=/checkout/tests/integration,readonly" \
  --mount "type=bind,source=$chutney_dir,target=/chutney,readonly" \
  vanguards-onion-local tests/integration/onion_service.py
```

The fixture uses Tor 0.4.9.17 and synthetic authority votes. It exercises
`VanguardsLiteEnabled=1` with Tor-selected guards and with explicit addon guard
layers, including four throttled transfers per mode. The Tor-selected service
uses the microdescriptor consensus and the addon-managed service uses the NS
consensus (`UseMicrodescriptors 0`). The fixture verifies circuit
bandwidth events, reload, reconnect, persisted state, and one-shot configuration.
The container discards its test identities and run data. Remove the temporary
Chutney checkout after the run.
