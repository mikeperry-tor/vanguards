"""Qualify Vanguards with a private Chutney v3 onion service and client."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from threading import Event, Thread
import time

import stem
from stem.control import Controller
from stem.descriptor import DocumentHandler, parse_file

from vanguards.vanguards import VanguardState

FIXTURE = Path(__file__).resolve().parent
LAUNCHER = "/checkout/src/vanguards.py"
LOG_STEM_ERRORS = (
    "import logging, runpy, sys; "
    "handler = logging.StreamHandler(); handler.setLevel(logging.WARNING); "
    "logging.getLogger('stem').addHandler(handler); "
    "sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')"
)
BODY = b"Vanguards integration\n" * 12288
GUARD_OPTIONS = ("HSLayer2Nodes", "HSLayer3Nodes", "NumEntryGuards", "NumDirectoryGuards")
BW_FIELDS = {"DELIVERED_READ", "DELIVERED_WRITTEN", "OVERHEAD_READ", "OVERHEAD_WRITTEN"}


class PayloadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        self.wfile.write(BODY)

    def log_message(self, format, *args):
        pass


def wait_for(description, check, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.2)
    raise RuntimeError("Timed out waiting for " + description)


def redact(line):
    line = re.sub(r"\$[0-9A-Fa-f]{40}[^ \r\n]*", "[circuit path]", line)
    line = re.sub(r"(?i)[0-9a-f]{40}|[a-z2-7]{56}", "[identifier]", line)
    return re.sub(r"REND_QUERY=\S+", "REND_QUERY=[service]", line)


def connect(node):
    controller = Controller.from_socket_file(str(node / "control"))
    controller.authenticate()
    controller.set_caching(False)
    return controller


def ready(node):
    try:
        with connect(node) as control:
            if "PROGRESS=100" not in control.get_info("status/bootstrap-phase"):
                return False
            assert str(control.get_version()) == "0.4.9.17"
            routers = list(control.get_network_statuses())
        doc = next(parse_file(str(node / "cached-microdesc-consensus"),
                              document_handler=DocumentHandler.BARE_DOCUMENT))
    except (FileNotFoundError, stem.SocketError, stem.DescriptorUnavailable, StopIteration):
        return False
    weights = doc.bandwidth_weights
    groups = {("Guard" in router.flags, "Exit" in router.flags) for router in routers}
    middle = sum(
        {"Fast", "Stable", "Valid"} <= set(router.flags)
        and "Authority" not in router.flags and "Exit" not in router.flags
        and weights.get("Wmg" if "Guard" in router.flags else "Wmm", 0) > 0
        for router in routers
    )
    return len(groups) == 4 and middle >= 8 and {"Wmm", "Wmg", "Wme", "Wmd", "Wee", "Wed"} <= weights.keys()


def chutney(command, work, check=True, timeout=160):
    with (work / "chutney.log").open("a") as log:
        subprocess.run(
            ["/chutney/chutney", command, str(FIXTURE / "network")],
            stdout=log, stderr=log, cwd=work, check=check, timeout=timeout,
        )


@contextmanager
def addon(work, options, logfile):
    with logfile.open("w") as log:
        with subprocess.Popen(
            [sys.executable, "-c", LOG_STEM_ERRORS, LAUNCHER, *options, "--loglevel", "DEBUG"],
            stdout=log, stderr=log, cwd=work,
        ) as process:
            try:
                yield process
                assert process.poll() is None, "Addon stopped before completing the scenario"
            finally:
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()


def tor_settings(controller):
    return tuple(controller.get_conf(key) for key in GUARD_OPTIONS)


def wait_for_refresh(state):
    stamp = state.stat().st_mtime_ns
    wait_for("addon consensus refresh and state update", lambda: state.stat().st_mtime_ns != stamp, timeout=35)


def restart_tor(work, service, control, log, state):
    stamp = state.stat().st_mtime_ns
    service_log = service / "info.log"
    log_start = service_log.stat().st_size
    shutdown_tor(service, control)
    wait_for("addon disconnect detection", lambda: "connection closed" in log.read_text())
    start_tor(work, service)
    wait_for("addon reconnect and state update", lambda: state.stat().st_mtime_ns != stamp
             and log.read_text().count("connected to Tor 0.4.9.17") >= 2)

    def descriptor_uploaded():
        with service_log.open("rb") as tor_log:
            tor_log.seek(log_start)
            return b"Uploaded hidden service descriptor (status 200 " in tor_log.read()

    wait_for("restarted service to publish an onion descriptor", descriptor_uploaded, timeout=75)


def start_tor(work, service):
    result = subprocess.run(["tor", "-f", str(service / "torrc")], cwd=work,
                            capture_output=True, text=True, timeout=15)
    if result.returncode:
        detail = " ".join((result.stdout + result.stderr).splitlines()[-3:])
        raise RuntimeError("Private Tor restart failed: " + redact(detail))


def shutdown_tor(service, control):
    pid = (service / "pid").read_text().strip()
    control.signal("SHUTDOWN")
    wait_for("Tor process exit", lambda: not (Path("/proc") / pid).exists())


def save_guards(work, options):
    result = subprocess.run(
        [sys.executable, LAUNCHER, *options, "--one_shot_vanguards"],
        cwd=work, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0 and "Updated vanguards in torrc" in result.stdout, "One-shot SAVECONF failed"


def transfer(client, service, control, log, explicit_layers, *, after_reconnect=False):
    path = service / "hidden_service" / "hostname"
    wait_for("onion service identity", path.is_file)
    wait_for("an established service introduction circuit", lambda: any(
        circuit.purpose == "HS_SERVICE_INTRO" and circuit.hs_state == "HSSI_ESTABLISHED"
        for circuit in control.get_circuits()
    ))
    onion = path.read_text().strip()
    rendezvous = {}
    bandwidth = set()
    states = set()
    log_start = len(log.read_text())

    def circuit(event):
        if event.purpose == "HS_SERVICE_REND":
            states.add((event.status, event.hs_state))
        if event.status == "BUILT" and event.purpose == "HS_SERVICE_REND":
            rendezvous[event.id] = tuple(fingerprint for fingerprint, _ in event.path)

    def circuit_bandwidth(event):
        if (event.id in rendezvous and BW_FIELDS <= event.keyword_args.keys()
                and int(event.keyword_args["DELIVERED_WRITTEN"]) > 0):
            bandwidth.add(event.id)

    def accounted_rendezvous():
        diagnostics = log.read_text()[log_start:]
        accounted = set(re.findall(
            r"(?m)^DEBUG\[[^\n]+\]: (?:650 )?CIRC_BW ID=(\d+) [^\n]*\bDELIVERED_WRITTEN=[1-9]\d*\b",
            diagnostics,
        ))
        return bool(accounted & bandwidth)

    control.add_event_listener(circuit, "CIRC")
    control.add_event_listener(circuit_bandwidth, "CIRC_BW")
    try:
        with connect(client) as client_control:
            newnym = Event()
            client_control.add_event_listener(
                lambda event: newnym.set() if event.signal == "NEWNYM" else None, "SIGNAL",
            )
            client_control.signal("NEWNYM")
            assert newnym.wait(12), "Tor client did not clear its old circuit and descriptor state"
            socks = client_control.get_info("net/listeners/socks").strip('"')
        deadline = time.monotonic() + 55
        count = 2 if after_reconnect else 4
        phase = "reconnect" if after_reconnect else "initial"
        for index in range(count):
            while True:
                try:
                    result = subprocess.run(
                        ["curl", "--silent", "--fail", "--max-time", "18", "--limit-rate", "48k",
                         "--socks5-hostname", socks, "--proxy-user", f"{phase}{index}:test",
                         f"http://{onion}:5858/"],
                        capture_output=True, timeout=20,
                    )
                except subprocess.TimeoutExpired:
                    raise RuntimeError(f"Private onion transfer {index + 1} timed out") from None
                if result.returncode == 0 and result.stdout == BODY:
                    break
                if index or time.monotonic() >= deadline:
                    diagnostics = log.read_text()[log_start:]
                    raise RuntimeError(
                        f"Private onion transfer {index + 1} failed with curl status {result.returncode}; "
                        f"received {len(result.stdout)} bytes; built {len(rendezvous)} rendezvous circuits; "
                        f"addon closures: {diagnostics.count('We force-closed circuit')}; "
                        f"callback errors: {diagnostics.count('Event listener raised an uncaught exception')}"
                    )
                time.sleep(1)
        wait_for("service rendezvous bandwidth data", lambda: bool(bandwidth))
        wait_for("Bandguards accounting for a service rendezvous circuit", accounted_rendezvous)
    finally:
        control.remove_event_listener(circuit)
        control.remove_event_listener(circuit_bandwidth)

    assert len(rendezvous) >= 2, "Too few fresh service rendezvous circuits"
    selected = list(rendezvous.values())
    if explicit_layers:
        layer2, layer3 = explicit_layers
        assert all(len(path) > 3 and path[1] in layer2 and path[2] in layer3 for path in selected)
    else:
        tor_layer2 = set(re.findall(r"Adding Layer2 guard ([A-Fa-f0-9]{40})", (service / "info.log").read_text()))
        assert tor_layer2 and all(len(path) > 2 and path[1] in tor_layer2 for path in selected)

    diagnostics = log.read_text()[log_start:]
    assert "consensus weight of " in diagnostics, f"Rendguard did not observe a rendezvous circuit; states: {states}"
    assert not re.search(r"Application (read|written) data exceeds cell data", diagnostics)
    assert "Event listener raised an uncaught exception" not in diagnostics
    assert "We force-closed circuit" not in diagnostics, "Addon closed a circuit during valid traffic"
    print(f"Transferred {len(BODY) * count} bytes on {len(rendezvous)} rendezvous circuits "
          f"with {'explicit' if explicit_layers else 'Tor-selected'} guard layers "
          f"({phase}), with CIRC_BW accounting.", flush=True)


def built_in_mode(work, service, client):
    log = work / "built-in.log"
    state = work / "built-in.state"
    with connect(service) as control:
        expected = tor_settings(control)
        assert expected[:2] == (None, None)
        assert control.get_conf("VanguardsLiteEnabled") == "1"
        options = ["--control_socket", str(service / "control"),
                   "--disable_vanguards", "--state", str(state)]
        with addon(work, options, log):
            wait_for("Rendguard startup", state.is_file)
            assert tor_settings(control) == expected
            reloaded = []
            control.add_event_listener(lambda event: reloaded.append(event.signal), "SIGNAL")
            control.signal("RELOAD")
            wait_for("Tor reload", lambda: "RELOAD" in reloaded)
            transfer(client, service, control, log, None)
            wait_for_refresh(state)
            assert tor_settings(control) == expected, "Monitoring-only addon modified Tor guard settings"
            restart_tor(work, service, control, log, state)
            with connect(service) as reconnected:
                assert tor_settings(reconnected) == expected
                transfer(client, service, reconnected, log, None, after_reconnect=True)
                wait_for_refresh(state)
                assert tor_settings(reconnected) == expected
            assert "Reapplying vanguards" not in log.read_text()
            assert "Event listener raised an uncaught exception" not in log.read_text()
    assert VanguardState.read_from_file(str(state)).rendguard.total_use_counts > 0


def addon_mode(work, service, client):
    log = work / "managed.log"
    state = work / "managed.state"
    with connect(service) as control:
        listen = control.get_info("net/listeners/control").split()[0].strip('"')
        host, port = listen.split(":")
        options = ["--control_ip", host, "--control_port", port, "--state", str(state)]
        save_guards(work, options)
        shutdown_tor(service, control)
    start_tor(work, service)
    wait_for("addon-managed service bootstrap", lambda: ready(service))
    with connect(service) as control:
        with addon(work, options, log):
            expected = tor_settings(control)
            assert expected[2:] == ("2", "2")
            assert [len(layer.split(",")) for layer in expected[:2]] == [4, 8]
            wait_for_refresh(state)
            torrc = service / "torrc"
            updated, count = re.subn(r"(?m)^NumDirectoryGuards 2$", "NumDirectoryGuards 1", torrc.read_text())
            assert count == 1, "One-shot did not persist the directory guard count"
            torrc.write_text(updated)
            control.signal("RELOAD")
            try:
                wait_for("addon guard reapplication", lambda: "Reapplying vanguards" in log.read_text()
                         and tor_settings(control) == expected)
            except RuntimeError as exc:
                actual = tor_settings(control)
                mismatches = [key for key, before, after in zip(GUARD_OPTIONS, expected, actual)
                              if before != after]
                reapplied = "Reapplying vanguards" in log.read_text()
                raise RuntimeError(f"{exc}; reload callback ran: {reapplied}; "
                                   f"settings differed: {mismatches}") from None
            layers = [set(layer.split(",")) for layer in expected[:2]]
            transfer(client, service, control, log, layers)
            wait_for_refresh(state)
            assert tor_settings(control) == expected
            restart_tor(work, service, control, log, state)
            with connect(service) as reconnected:
                wait_for("guard state after reconnect", lambda: tor_settings(reconnected) == expected)
                assert reconnected.get_conf("VanguardsLiteEnabled") == "1"
                transfer(client, service, reconnected, log, layers, after_reconnect=True)
                wait_for_refresh(state)
                assert tor_settings(reconnected) == expected
    persisted = VanguardState.read_from_file(str(state))
    assert "Event listener raised an uncaught exception" not in log.read_text()
    assert (persisted.layer2_guardset(), persisted.layer3_guardset()) == expected[:2]
    assert persisted.rendguard.total_use_counts > 0
    save_guards(work, options)
    assert VanguardState.read_from_file(str(state)).rendguard.total_use_counts == persisted.rendguard.total_use_counts
    saved = (service / "torrc").read_text().splitlines()
    assert all(any(line.startswith(key + " ") and expected[index] in line for line in saved)
               for index, key in enumerate(GUARD_OPTIONS[:2]))


def main():
    with tempfile.TemporaryDirectory(prefix="vanguards-") as directory:
        work = Path(directory)
        templates = work / "torrc_templates"
        shutil.copytree("/chutney/torrc_templates", templates)
        common = templates / "common.i"
        # Tor combines repeated router sets. Drop Chutney's wildcard votes so
        # the authority template can assign each Guard/Exit weight category.
        common.write_text("\n".join(line for line in common.read_text().splitlines()
                                    if line not in ("TestingDirAuthVoteGuard *", "TestingDirAuthVoteExit *")) + "\n")
        shutil.copy(FIXTURE / "vanguards-authority.tmpl", templates)
        (work / "resolv.conf").write_text("nameserver 127.0.0.1\n")
        os.environ.update(CHUTNEY_PATH=str(work), CHUTNEY_DATA_DIR=str(work / "net"),
                          CHUTNEY_DNS_CONF=str(work / "resolv.conf"),
                          CHUTNEY_TOR_SANDBOX="0")
        nodes = work / "net" / "nodes"
        service = nodes / "025h"
        managed_service = nodes / "026h"
        client = nodes / "024c"

        with ThreadingHTTPServer(("127.0.0.1", 4747), PayloadHandler) as server:
            Thread(target=server.serve_forever, daemon=True).start()
            try:
                chutney("configure", work)
                for node in (service, managed_service):
                    with (node / "torrc").open("a") as config:
                        config.write("\nVanguardsLiteEnabled 1\n")
                chutney("start", work)
                print("Private Tor network started", flush=True)
                wait_for("client and service bootstrap with usable consensuses",
                         lambda: ready(client) and ready(service) and ready(managed_service), timeout=145)
                print("Private service and client bootstrapped with usable consensuses", flush=True)
                built_in_mode(work, service, client)
                addon_mode(work, managed_service, client)
                print("Verified bootstrap, consensus refresh, reload, reconnect, state, and SAVECONF.", flush=True)
            except Exception:
                for mode in ("built-in", "managed"):
                    path = work / (mode + ".log")
                    if not path.exists():
                        continue
                    lines = path.read_text().splitlines()
                    for line in lines:
                        if not any(marker in line for marker in
                                   ("dropped cell", "data exceeds cell data", "uncaught exception")):
                            continue
                        print(f"{mode}: {redact(line)}", file=sys.stderr)
                raise
            finally:
                server.shutdown()
                try:
                    chutney("stop", work, check=False, timeout=25)
                except subprocess.TimeoutExpired:
                    print("Chutney stop timed out; the container will terminate its remaining processes.", file=sys.stderr)


if __name__ == "__main__":
    signal.alarm(420)
    main()
