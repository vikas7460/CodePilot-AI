import os
import re
from typing import Optional

from app.tools.terminal_tools import run_command


TEST_VENV_DIR = ".ai_test_venv"
DEPS_READY_FILE = ".ai_deps_ready"
FAILED_TESTS_CACHE_FILE = ".ai_failed_tests"


def get_abs_repo_path(repo_path: str) -> str:
    return os.path.abspath(repo_path)


def get_test_python(repo_path: str) -> str:
    abs_repo_path = get_abs_repo_path(repo_path)

    if os.name == "nt":
        return os.path.join(abs_repo_path, TEST_VENV_DIR, "Scripts", "python.exe")

    return os.path.join(abs_repo_path, TEST_VENV_DIR, "bin", "python")


def get_deps_ready_path(repo_path: str) -> str:
    return os.path.join(
        get_abs_repo_path(repo_path),
        TEST_VENV_DIR,
        DEPS_READY_FILE,
    )


def get_failed_tests_cache_path(repo_path: str) -> str:
    return os.path.join(
        get_abs_repo_path(repo_path),
        FAILED_TESTS_CACHE_FILE,
    )


def extract_failed_tests(logs: str):
    return re.findall(r"FAILED\s+([^\s]+)", logs)


def save_failed_tests(repo_path: str, failed_tests: list):
    cache_path = get_failed_tests_cache_path(repo_path)

    with open(cache_path, "w", encoding="utf-8") as file:
        for test in failed_tests:
            file.write(test + "\n")


def load_cached_failed_tests(repo_path: str):
    cache_path = get_failed_tests_cache_path(repo_path)

    if not os.path.exists(cache_path):
        return []

    with open(cache_path, "r", encoding="utf-8") as file:
        return [line.strip() for line in file.readlines() if line.strip()]


def clear_failed_tests_cache(repo_path: str):
    cache_path = get_failed_tests_cache_path(repo_path)

    if os.path.exists(cache_path):
        os.remove(cache_path)


def ensure_test_venv(repo_path: str):
    abs_repo_path = get_abs_repo_path(repo_path)
    test_python = get_test_python(abs_repo_path)

    if os.path.exists(test_python):
        return {
            "command": "create test venv",
            "returncode": 0,
            "stdout": "Test virtual environment already exists.",
            "stderr": "",
            "success": True,
            "timed_out": False,
        }

    return run_command(
        command=f'python -m venv "{TEST_VENV_DIR}"',
        cwd=abs_repo_path,
        timeout=300,
    )


def run_in_test_venv(repo_path: str, command: str, timeout: int = 600):
    abs_repo_path = get_abs_repo_path(repo_path)
    test_python = get_test_python(abs_repo_path)

    final_command = command.replace("PYTHON", f'"{test_python}"')

    return run_command(
        command=final_command,
        cwd=abs_repo_path,
        timeout=timeout,
    )


def target_is_safe(target: str) -> bool:
    blocked = ["&", "|", ">", "<", ";", "`"]
    return not any(char in target for char in blocked)


def install_python_dependencies(repo_path: str, force: bool = False):
    abs_repo_path = get_abs_repo_path(repo_path)
    results = []

    venv_result = ensure_test_venv(abs_repo_path)
    results.append(venv_result)

    if not venv_result["success"]:
        return results

    deps_ready_path = get_deps_ready_path(abs_repo_path)

    if os.path.exists(deps_ready_path) and not force:
        results.append(
            {
                "command": "install dependencies",
                "returncode": 0,
                "stdout": "Dependencies already installed. Skipping install.",
                "stderr": "",
                "success": True,
                "timed_out": False,
            }
        )
        return results

    files = set(os.listdir(abs_repo_path))

    results.append(
        run_in_test_venv(
            abs_repo_path,
            "PYTHON -m pip install --upgrade pip setuptools wheel --disable-pip-version-check",
            timeout=600,
        )
    )

    if "requirements.txt" in files:
        results.append(
            run_in_test_venv(
                abs_repo_path,
                "PYTHON -m pip install -r requirements.txt --disable-pip-version-check",
                timeout=600,
            )
        )

    for req_file in [
        "requirements-dev.txt",
        "dev-requirements.txt",
        "test-requirements.txt",
    ]:
        if req_file in files:
            results.append(
                run_in_test_venv(
                    abs_repo_path,
                    f"PYTHON -m pip install -r {req_file} --disable-pip-version-check",
                    timeout=900,
                )
            )

    if "pyproject.toml" in files or "setup.py" in files:
        results.append(
            run_in_test_venv(
                abs_repo_path,
                "PYTHON -m pip install -e . --disable-pip-version-check",
                timeout=900,
            )
        )

    pytest_check = run_in_test_venv(
        abs_repo_path,
        "PYTHON -m pytest --version",
        timeout=60,
    )

    if not pytest_check["success"]:
        results.append(
            run_in_test_venv(
                abs_repo_path,
                "PYTHON -m pip install pytest --disable-pip-version-check",
                timeout=600,
            )
        )

    if all(result.get("success") for result in results):
        os.makedirs(os.path.dirname(deps_ready_path), exist_ok=True)

        with open(deps_ready_path, "w", encoding="utf-8") as file:
            file.write("ready")

    return results


def build_test_command(target: Optional[str] = None) -> str:
    if target:
        if not target_is_safe(target):
            raise ValueError("Unsafe test target")

        return f'PYTHON -m pytest --rootdir=. "{target}"'

    return "PYTHON -m pytest --rootdir=."


def has_install_failure(install_results: list) -> bool:
    return any(not result.get("success") for result in install_results)


def run_repo_tests(
    repo_path: str,
    target: Optional[str] = None,
    force_install: bool = False,
):
    abs_repo_path = get_abs_repo_path(repo_path)

    install_results = install_python_dependencies(
        abs_repo_path,
        force=force_install,
    )

    if has_install_failure(install_results):
        return {
            "setup_success": False,
            "passed": False,
            "reason": "Dependency installation failed. Tests were not run.",
            "install": install_results,
            "test_command": None,
            "target": target,
            "logs": {
                "stdout": "",
                "stderr": "Install dependencies failed. Check install logs.",
            },
            "returncode": 1,
        }

    test_command = build_test_command(target)

    test_result = run_in_test_venv(
        abs_repo_path,
        test_command,
        timeout=300,
    )

    combined_logs = test_result["stdout"] + "\n" + test_result["stderr"]
    failed_tests = extract_failed_tests(combined_logs)

    if failed_tests:
        save_failed_tests(abs_repo_path, failed_tests)
    elif target is None and test_result["success"]:
        clear_failed_tests_cache(abs_repo_path)

    return {
        "setup_success": True,
        "install": install_results,
        "test_command": test_result["command"],
        "target": target,
        "passed": test_result["success"],
        "failed_tests": failed_tests,
        "logs": {
            "stdout": test_result["stdout"],
            "stderr": test_result["stderr"],
        },
        "returncode": test_result["returncode"],
    }