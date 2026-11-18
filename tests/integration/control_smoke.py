"""Check the real launcher and Tor control protocol before bootstrap."""

from functools import partial
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

import stem.connection
from stem.control import Controller


def wait_for_control(connect, tor):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and tor.poll() is None:
        try:
            return connect()
        except (stem.SocketError, FileNotFoundError):
            time.sleep(0.1)
    raise RuntimeError("Tor control listener did not become ready")


def check_endpoint(connect, options, tor, work):
    with wait_for_control(connect, tor) as controller:
        assert controller.msg("AUTHENTICATE " + "00" * 32).content()[0][0] == "515"

    with wait_for_control(connect, tor) as controller:
        controller.authenticate()
        assert str(controller.get_version()) == "0.4.9.17"
        assert controller.get_conf("DataDirectory") == str(work / "tor")
        assert controller.get_conf("DisableNetwork") == "1"
        for setting in ("HSLayer2Nodes", "HSLayer3Nodes", "VanguardsLiteEnabled",
                        "NumEntryGuards", "NumDirectoryGuards", "ProtocolWarnings"):
            controller.get_conf(setting)
        controller.add_event_listener(
            lambda event: None, "CIRC", "CIRC_MINOR", "CIRC_BW", "ORCONN",
            "BW", "NETWORK_LIVENESS", "NEWCONSENSUS", "SIGNAL", "NOTICE", "WARN", "ERR",
        )

    state_path = work / "vanguards.state"
    result = subprocess.run(
        [sys.executable, "/checkout/src/vanguards.py", *options,
         "--state", str(state_path), "--retry_limit", "1"],
        cwd=work, capture_output=True, text=True, timeout=15,
    )
    missing = f"Cannot read {work / 'tor' / 'cached-microdesc-consensus'}:"
    assert result.returncode == 1 and missing in result.stdout, result
    assert not state_path.exists()


def main():
    with tempfile.TemporaryDirectory(prefix="vanguards-") as directory:
        work = Path(directory)
        torrc = work / "torrc"
        socket_path = work / "control.sock"
        port_file = work / "control-port"
        torrc.write_text(
            f"DataDirectory {work / 'tor'}\n"
            "DisableNetwork 1\nSocksPort 0\nCookieAuthentication 1\n"
            f"ControlSocket {socket_path}\nControlPort auto\n"
            f"ControlPortWriteToFile {port_file}\n"
        )
        with (work / "tor.log").open("w+") as log:
            with subprocess.Popen(["tor", "-f", str(torrc)], stdout=log, stderr=log) as tor:
                try:
                    check_endpoint(
                        partial(Controller.from_socket_file, str(socket_path)),
                        ["--control_socket", str(socket_path)], tor, work,
                    )
                    listeners = dict(line.split("=", 1) for line in port_file.read_text().splitlines())
                    address, port = listeners["PORT"].split(":")
                    check_endpoint(
                        partial(Controller.from_port, address, int(port)),
                        ["--control_ip", address, "--control_port", port], tor, work,
                    )
                except Exception:
                    log.seek(0)
                    print(log.read(), file=sys.stderr)
                    raise
                finally:
                    tor.terminate()
                    try:
                        tor.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        tor.kill()
    print("Tor 0.4.9.17 accepted Unix and TCP control and rejected invalid auth. "
          "Both launchers took the missing-consensus retry path without writing state.")


if __name__ == "__main__":
    signal.alarm(60)
    main()
