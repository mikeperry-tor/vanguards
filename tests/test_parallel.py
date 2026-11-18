import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize("checkout", [True, False])
def test_parallel_launcher_selects_one_cli_for_all_workers(tmp_path, checkout):
  launcher = tmp_path / "checkout with spaces" / "vanguards_parallel.sh"
  launcher.parent.mkdir()
  shutil.copy(Path(__file__).resolve().parents[1] / launcher.name, launcher)
  bin_dir = tmp_path / "bin"
  bin_dir.mkdir()
  worker = tmp_path / "worker.py"
  worker.write_text('import json, sys\nprint("worker:", json.dumps(sys.argv), flush=True)\n')
  for name, command in (("python3", '"$TEST_PYTHON" "$@"'),
                        ("vanguards", '"$TEST_PYTHON" "$TEST_WORKER" "$@"')):
    executable = bin_dir / name
    executable.write_text(f"#!/bin/sh\nexec {command}\n")
    executable.chmod(0o755)

  expected_worker = worker
  if checkout:
    expected_worker = launcher.parent / "src" / "vanguards.py"
    expected_worker.parent.mkdir()
    shutil.copy(worker, expected_worker)

  state = str(tmp_path / "state with spaces")
  env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
             TEST_PYTHON=sys.executable, TEST_WORKER=str(worker))
  result = subprocess.run(["sh", "-e", str(launcher), "--state", state],
                          cwd=tmp_path, env=env, capture_output=True, text=True,
                          check=True, timeout=10)
  workers = [json.loads(line.removeprefix("worker: "))
             for line in result.stdout.splitlines() if line.startswith("worker: ")]
  common_args = ["--logfile", ":syslog:", "--state", state]
  assert sorted(workers) == sorted([
    [str(expected_worker), "--disable_bandguards", "--disable_rendguard", *common_args],
    [str(expected_worker), "--disable_vanguards", "--disable_rendguard", *common_args],
    [str(expected_worker), "--disable_vanguards", "--disable_bandguards",
     "--parallel_rendguard_state", *common_args],
  ])
