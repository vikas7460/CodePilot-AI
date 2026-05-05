import os
import re
from typing import Optional

from app.services.change_service import apply_change
from app.services.patch_service import apply_generated_patch
from app.services.vector_service import search_chunks


def normalize_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return path.replace("/", "\\")


def extract_failure_summary(test_result: dict) -> dict:
    stdout = test_result.get("logs", {}).get("stdout", "")
    stderr = test_result.get("logs", {}).get("stderr", "")
    logs = stdout + "\n" + stderr

    failed_tests = re.findall(r"FAILED\s+([^\s]+)", logs)

    source_file_matches = re.findall(r"(src[\\/][\w\\/.-]+\.py):\d+", logs)
    source_file = normalize_path(source_file_matches[-1]) if source_file_matches else None

    error_lines = re.findall(r"E\s+(.+)", logs)
    error_message = error_lines[-1].strip() if error_lines else None

    exception_match = re.search(
        r"(AssertionError|NameError|ModuleNotFoundError|ImportError|FileNotFoundError|OSError|TypeError|AttributeError|ValueError|SyntaxError)",
        logs,
    )
    exception_type = exception_match.group(1) if exception_match else None

    missing_module_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", logs)
    missing_module = missing_module_match.group(1) if missing_module_match else None

    name_error_match = re.search(r"NameError:\s+name ['\"]([^'\"]+)['\"] is not defined", logs)
    missing_name = name_error_match.group(1) if name_error_match else None

    return {
        "failed_tests": failed_tests,
        "failed_test": failed_tests[0] if failed_tests else None,
        "source_file": source_file,
        "exception_type": exception_type,
        "error_message": error_message,
        "missing_module": missing_module,
        "missing_name": missing_name,
        "raw_logs": logs[-12000:],
    }


def read_file(repo_path: str, file_path: str) -> str:
    full_path = os.path.abspath(os.path.join(repo_path, file_path))

    with open(full_path, "r", encoding="utf-8") as file:
        return file.read()


def file_exists(repo_path: str, file_path: Optional[str]) -> bool:
    if not file_path:
        return False

    full_path = os.path.abspath(os.path.join(repo_path, file_path))
    return os.path.exists(full_path)


def apply_regex_patch(
    repo_path: str,
    file_path: str,
    pattern: re.Pattern,
    replacement_builder,
    rule_name: str,
):
    original = read_file(repo_path, file_path)
    match = pattern.search(original)

    if not match:
        return None

    old_text = match.group(0)
    new_text = replacement_builder(match)

    if old_text == new_text:
        return None

    result = apply_change(
        repo_path=repo_path,
        file_path=file_path,
        mode="replace_text",
        old_text=old_text,
        new_text=new_text,
        backup=True,
    )

    return {
        "rule_name": rule_name,
        "matched": True,
        "source_file": file_path,
        "apply_result": result,
    }


# RULE 1: generic path resolution fix
def rule_preserve_original_path_in_error(repo_path: str, failure_summary: dict):
    logs = failure_summary.get("raw_logs", "")
    source_file = failure_summary.get("source_file")

    if not file_exists(repo_path, source_file):
        return None

    path_error_signals = [
        "invalid path:",
        "No such file or directory",
        "Could not find",
        "FileNotFoundError",
        "OSError",
    ]

    if not any(signal in logs for signal in path_error_signals):
        return None

    pattern = re.compile(
        r"""(?P<indent>[ \t]+)if (?P<var>[a-zA-Z_][a-zA-Z0-9_]*) and not os\.path\.isabs\((?P=var)\):\n"""
        r"""(?:[ \t]*#.*\n)?"""
        r"""(?P=indent)[ \t]+(?P=var) = os\.path\.abspath\((?P=var)\)\n"""
        r"""(?P=indent)if not (?P=var) or not os\.path\.exists\((?P=var)\):\n"""
        r"""(?P=indent)[ \t]+raise (?P<error_type>[a-zA-Z_][a-zA-Z0-9_]*Error)\(\n"""
        r"""(?P<body>[\s\S]*?)"""
        r"""(?P=indent)[ \t]+\)""",
        re.MULTILINE,
    )

    def build_replacement(match):
        indent = match.group("indent")
        var = match.group("var")
        error_type = match.group("error_type")
        body = match.group("body")

        original_var = f"original_{var}"
        resolved_var = f"resolved_{var}"

        body = body.replace("{" + var + "}", "{" + original_var + "}")

        return (
            f"{indent}{original_var} = {var}\n\n"
            f"{indent}if {var} and not os.path.isabs({var}):\n"
            f"{indent}    {resolved_var} = os.path.abspath({var})\n"
            f"{indent}else:\n"
            f"{indent}    {resolved_var} = {var}\n\n"
            f"{indent}if not {resolved_var} or not os.path.exists({resolved_var}):\n"
            f"{indent}    raise {error_type}(\n"
            f"{body}"
            f"{indent}    )\n\n"
            f"{indent}{var} = {resolved_var}"
        )

    return apply_regex_patch(
        repo_path=repo_path,
        file_path=source_file,
        pattern=pattern,
        replacement_builder=build_replacement,
        rule_name="preserve_original_path_in_error",
    )


# RULE 2: generic missing import helper
def rule_name_error_missing_import(repo_path: str, failure_summary: dict):
    source_file = failure_summary.get("source_file")
    missing_name = failure_summary.get("missing_name")

    if not source_file or not missing_name:
        return None

    if not file_exists(repo_path, source_file):
        return None

    task = f"""
Fix NameError in {source_file}.

Missing name:
{missing_name}

Rules:
- Add the smallest safe import or definition.
- Do not rewrite the whole file.
- Preserve behavior.
"""

    search_results = [{"path": source_file, "content": read_file(repo_path, source_file), "score": 1.0}]

    patch_result = apply_generated_patch(
        repo_path=repo_path,
        user_task=task,
        search_results=search_results,
    )

    return {
        "rule_name": "name_error_missing_import",
        "matched": True,
        "source_file": source_file,
        "apply_result": patch_result,
    }


# RULE 3: generic missing dependency rule
def rule_missing_dependency(repo_path: str, failure_summary: dict):
    missing_module = failure_summary.get("missing_module")

    if not missing_module:
        return None

    return {
        "rule_name": "missing_dependency",
        "matched": True,
        "action": "no_code_change",
        "reason": f"Missing Python module: {missing_module}",
        "suggested_fix": f"Install dependency or add it to requirements/dev requirements: {missing_module}",
    }


# RULE 4: generic syntax error fallback
def rule_syntax_error(repo_path: str, failure_summary: dict):
    if failure_summary.get("exception_type") != "SyntaxError":
        return None

    source_file = failure_summary.get("source_file")

    if not file_exists(repo_path, source_file):
        return None

    task = f"""
Fix SyntaxError in {source_file}.

Logs:
{failure_summary.get("raw_logs")}

Rules:
- Make the smallest syntax-only fix.
- Do not change behavior.
"""

    search_results = [{"path": source_file, "content": read_file(repo_path, source_file), "score": 1.0}]

    patch_result = apply_generated_patch(
        repo_path=repo_path,
        user_task=task,
        search_results=search_results,
    )

    return {
        "rule_name": "syntax_error_fix",
        "matched": True,
        "source_file": source_file,
        "apply_result": patch_result,
    }


# RULE 5: generic assertion failure fallback
def rule_assertion_failure(repo_path: str, failure_summary: dict):
    if failure_summary.get("exception_type") != "AssertionError":
        return None

    source_file = failure_summary.get("source_file")

    if not file_exists(repo_path, source_file):
        return None

    task = f"""
Fix AssertionError without changing tests.

Failing tests:
{failure_summary.get("failed_tests")}

Likely source file:
{source_file}

Logs:
{failure_summary.get("raw_logs")}

Rules:
- Do not modify tests.
- Preserve public API behavior.
- Make smallest safe source-code change.
"""

    search_results = [{"path": source_file, "content": read_file(repo_path, source_file), "score": 1.0}]

    patch_result = apply_generated_patch(
        repo_path=repo_path,
        user_task=task,
        search_results=search_results,
    )

    return {
        "rule_name": "assertion_failure_ai_assist",
        "matched": True,
        "source_file": source_file,
        "apply_result": patch_result,
    }


def try_rule_based_fix(repo_path: str, failure_summary: dict):
    rules = [
        rule_preserve_original_path_in_error,
        rule_missing_dependency,
        rule_name_error_missing_import,
        rule_syntax_error,
        rule_assertion_failure,
    ]

    for rule in rules:
        try:
            result = rule(repo_path, failure_summary)
            if result:
                return result
        except Exception as error:
            continue

    return None


def build_debug_task(failure_summary: dict) -> str:
    return f"""
Fix the failing test.

Failed tests:
{failure_summary.get("failed_tests")}

Likely source file:
{failure_summary.get("source_file")}

Exception:
{failure_summary.get("exception_type")}

Error:
{failure_summary.get("error_message")}

Relevant logs:
{failure_summary.get("raw_logs")}

Goal:
- Fix the root cause.
- Make the smallest safe code change.
- Preserve existing behavior.
- Do not modify tests unless absolutely necessary.
"""


def run_debug_fix(repo_id: str, repo_path: str, test_result: dict) -> dict:
    failure_summary = extract_failure_summary(test_result)

    rule_fix = try_rule_based_fix(repo_path, failure_summary)

    if rule_fix:
        return {
            "strategy": "hybrid_rule_engine",
            "failure_summary": failure_summary,
            "rule_fix": rule_fix,
        }

    debug_task = build_debug_task(failure_summary)

    search_query = (
        failure_summary.get("error_message")
        or failure_summary.get("failed_test")
        or "test failure"
    )

    search_results = search_chunks(
        repo_id=repo_id,
        query=search_query,
        limit=5,
    )

    patch_result = apply_generated_patch(
        repo_path=repo_path,
        user_task=debug_task,
        search_results=search_results,
    )

    return {
        "strategy": "ai_patch",
        "failure_summary": failure_summary,
        "debug_task": debug_task,
        "patch_result": patch_result,
    }