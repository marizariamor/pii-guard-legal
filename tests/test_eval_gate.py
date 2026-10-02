"""Eval-гейт тоже проверяется тестом, чтобы pytest падал при регрессии качества."""

import subprocess
import sys
from pathlib import Path


def test_eval_gate_passes():
    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run([sys.executable, str(root / "evals" / "run_eval.py")], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stdout + proc.stderr
