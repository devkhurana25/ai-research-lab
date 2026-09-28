"""
Controlled Python execution tool (spec section 8).

Guarantees provided here:
  - runs in a dedicated temp workspace, not the main process cwd
  - hard wall-clock timeout via subprocess
  - no network access is granted by this tool itself (caller's OS/network
    policy must still enforce this — documented in docs/SECURITY.md)
  - stdout/stderr/runtime/status/artifacts always captured, never swallowed
"""
from __future__ import annotations
import subprocess
import sys
import tempfile
import time
import os
import shutil
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    code: str
    stdout: str
    stderr: str
    runtime_s: float
    status: str          # "ok" | "error" | "timeout"
    artifacts: list[str]
    workspace: str


def run_python(code: str, timeout_s: int = 30, input_files: dict[str, str] | None = None) -> ExecutionResult:
    """
    Execute `code` in an isolated temp directory.
    input_files: {dest_filename: source_path} copied into the workspace before execution
                 so analysis code can refer to them by simple relative names.
    """
    workspace = tempfile.mkdtemp(prefix="ai_lab_exec_")
    input_files = input_files or {}
    for dest, src in input_files.items():
        shutil.copy(src, os.path.join(workspace, dest))

    script_path = os.path.join(workspace, "_script.py")
    with open(script_path, "w") as f:
        f.write(code)

    before = set(os.listdir(workspace))
    start = time.time()
    status = "ok"
    stdout, stderr = "", ""
    try:
        proc = subprocess.run(
            [sys.executable, "_script.py"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        stdout, stderr = proc.stdout, proc.stderr
        if proc.returncode != 0:
            status = "error"
    except subprocess.TimeoutExpired as e:
        status = "timeout"
        stdout = e.stdout or ""
        stderr = (e.stderr or "") + "\n[execution exceeded timeout]"
    runtime = time.time() - start

    after = set(os.listdir(workspace))
    new_files = sorted(after - before - {"_script.py"})
    artifacts = [os.path.join(workspace, f) for f in new_files]

    return ExecutionResult(
        code=code, stdout=stdout, stderr=stderr, runtime_s=runtime,
        status=status, artifacts=artifacts, workspace=workspace,
    )
