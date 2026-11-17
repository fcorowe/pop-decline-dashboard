"""Tests that rebuild with the research inputs kept outside the repository."""
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not (ROOT.parent / "Map.gpkg").is_file(), reason="Raw study inputs are unavailable")
def test_build_is_byte_identical_on_repeat(tmp_path):
    output = tmp_path / "data"
    command = [sys.executable, str(ROOT / "scripts" / "build_data.py"), "--out", str(output)]

    def build_and_hash():
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()}

    assert build_and_hash() == build_and_hash()
