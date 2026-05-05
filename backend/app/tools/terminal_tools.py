import subprocess


def run_command(command: str, cwd: str, timeout: int = 300):
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout[-8000:],
            "stderr": result.stderr[-8000:],
            "success": result.returncode == 0,
            "timed_out": False,
        }

    except subprocess.TimeoutExpired as e:
        return {
            "command": command,
            "returncode": -1,
            "stdout": (e.stdout or "")[-8000:] if isinstance(e.stdout, str) else "",
            "stderr": (e.stderr or "")[-8000:] if isinstance(e.stderr, str) else "",
            "success": False,
            "timed_out": True,
            "error": f"Command timed out after {timeout} seconds",
        }