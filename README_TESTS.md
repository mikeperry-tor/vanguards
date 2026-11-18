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

This checks Unix and TCP control authentication and option and event availability
before bootstrap. On both endpoints, one-shot operation fails without writing
state. The long-running addon retries while no usable consensus is available,
and Bandguards reports the disconnected network on its bandwidth heartbeat.
The smoke fixture also checks that the operator's Conflux setting survives
addon attachment and Tor reload.

## Private onion-service qualification

Use a disposable checkout of the pinned Chutney revision. Run these commands
from the Vanguards checkout. The test starts its own directory authorities and
relays, and uses a separate v3 onion service for each scenario. A Tor client
exercises all three services inside the Docker container.

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
`VanguardsLiteEnabled=1` with Tor-selected guards and the default microdescriptor
consensus, and with explicit addon guard layers on both the microdescriptor and
NS consensus (`UseMicrodescriptors 0`). Each scenario exercises four throttled
transfers before restarting Tor and two after the addon reconnects. The fixture
waits for the client to receive a fresh descriptor after restart. It checks
rendezvous paths, Bandguards accounting, and Rendguard observations during
those transfers, as well as reload, persisted state, and one-shot configuration
for managed guards.
The container discards its test identities and run data. Remove the temporary
Chutney checkout after the run.

## GitHub Actions

CI runs the tox wheel tests on Linux with CPython 3.11 through 3.15. It also
runs both Docker fixtures on Linux ARM64 with container networking disabled.

The coverage job measures source-tree unit line coverage on CPython 3.13.
Find the Octocov summary in the workflow run and download the
`unit-line-coverage` artifact for the HTML report, LCOV data, and SVG badge.
Pull request comparisons use a retained default-branch baseline. Octocov
updates the coverage comment for pull requests from the same repository.
