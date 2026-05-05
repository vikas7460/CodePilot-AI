import json
import os
import re
from typing import Optional

from app.services.change_service import apply_change
from app.services.llm_service import generate_answer


def extract_json(text: str) -> Optional[dict]:
    """
    Concept: JSON extraction = tries to recover a JSON object from messy LLM output.
    """
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)

    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def choose_primary_source_file(search_results: list) -> str:
    """
    Concept: Primary source file = the safest implementation file to modify first.
    """
    for item in search_results:
        path = item.get("path", "")
        lower_path = path.lower()

        if lower_path.startswith(("src\\", "src/", "app\\", "app/", "lib\\", "lib/")):
            return path

    return search_results[0].get("path", "") if search_results else ""


def read_file_content(repo_path: str, file_path: str) -> str:
    full_path = os.path.abspath(os.path.join(repo_path, file_path))

    with open(full_path, "r", encoding="utf-8") as file:
        return file.read()


def validate_patch(patch: dict, file_path: str, original_content: str) -> bool:
    """
    Concept: Patch validation = blocks unsafe or fake AI-generated edits.
    """
    required_keys = ["file_path", "old_text", "new_text", "reason"]

    for key in required_keys:
        if key not in patch:
            raise ValueError(f"Patch missing required key: {key}")

    if patch["file_path"] != file_path:
        raise ValueError("Patch file_path does not match selected file")

    old_text = patch["old_text"]
    new_text = patch["new_text"]

    if not isinstance(old_text, str) or not old_text.strip():
        raise ValueError("old_text cannot be empty")

    if not isinstance(new_text, str) or not new_text.strip():
        raise ValueError("new_text cannot be empty")

    if old_text not in original_content:
        raise ValueError("old_text not found in original file")

    if old_text == new_text:
        raise ValueError("Patch does not change anything")

    if len(new_text) > len(original_content) * 0.8:
        raise ValueError("new_text too large. Refusing risky patch.")

    dangerous_patterns = [
        "os.system(",
        "subprocess.",
        "eval(",
        "exec(",
        "pickle.loads",
        "__import__(",
    ]

    for pattern in dangerous_patterns:
        if pattern in new_text:
            raise ValueError(f"Dangerous code pattern detected: {pattern}")

    return True


def build_custom_auth_patch(file_path: str, original_content: str, user_task: str) -> Optional[dict]:
    """
    Concept: Task-specific fallback = real code modification for known safe tasks.
    """

    task = user_task.lower()

    if "auth" not in task and "authentication" not in task:
        return None

    if "class CustomHeaderAuth" in original_content:
        raise ValueError("CustomHeaderAuth already exists in this file")

    auth_base_pattern = re.compile(
        r'class AuthBase:\n'
        r'    """Base class that all auth implementations derive from"""\n\n'
        r'    def __call__\(self, r\):\n'
        r'        raise NotImplementedError\("Auth hooks must be callable\."\)'
    )

    match = auth_base_pattern.search(original_content)

    if not match:
        return None

    old_text = match.group(0)

    new_text = old_text + '''

class CustomHeaderAuth(AuthBase):
    """Attaches a custom authentication header to the given Request object."""

    def __init__(self, header_name, header_value):
        if not header_name:
            raise ValueError("header_name is required")

        self.header_name = header_name
        self.header_value = header_value

    def __eq__(self, other):
        return all(
            [
                self.header_name == getattr(other, "header_name", None),
                self.header_value == getattr(other, "header_value", None),
            ]
        )

    def __ne__(self, other):
        return not self == other

    def __call__(self, r):
        r.headers[self.header_name] = self.header_value
        return r
'''

    return {
        "file_path": file_path,
        "old_text": old_text,
        "new_text": new_text,
        "reason": "Added CustomHeaderAuth so callers can attach custom authentication headers while preserving the existing AuthBase pattern.",
        "fallback_used": "custom_auth_template",
    }


def build_known_safe_patch(file_path: str, original_content: str, user_task: str) -> dict:
    """
    Concept: Known safe patch = deterministic real code patch when the local LLM fails.
    """
    custom_auth_patch = build_custom_auth_patch(file_path, original_content, user_task)

    if custom_auth_patch:
        return custom_auth_patch

    raise ValueError(
        "Could not create a safe real-code fallback patch for this task. "
        "Try a more specific task or use manual apply-change."
    )


def generate_ai_patch(file_path: str, original_content: str, user_task: str) -> Optional[dict]:
    """
    Concept: AI patch = model proposes old_text/new_text, but backend still validates it.
    """
    prompt = f"""
Return ONLY valid JSON.

Task:
{user_task}

You can modify ONLY this file:
{file_path}

Original file content:
{original_content[:6000]}

Return a small real code patch in this exact JSON format:
{{
  "file_path": "{file_path}",
  "old_text": "exact existing code block copied from the file",
  "new_text": "updated replacement code block",
  "reason": "short reason"
}}

Rules:
- old_text must exist exactly in the original file.
- new_text must be valid code.
- Do not return markdown.
- Do not explain.
- Do not use placeholders.
- Do not rewrite the full file.
- Make the smallest useful code change.
"""

    raw_response = generate_answer(prompt)
    return extract_json(raw_response)


def generate_patch(repo_path: str, user_task: str, search_results: list) -> dict:
    """
    Concept: Patch generation = AI first, deterministic safe fallback second.
    """
    file_path = choose_primary_source_file(search_results)

    if not file_path:
        raise ValueError("No source file found for patching")

    original_content = read_file_content(repo_path, file_path)

    ai_patch = generate_ai_patch(
        file_path=file_path,
        original_content=original_content,
        user_task=user_task,
    )

    if ai_patch:
        try:
            validate_patch(ai_patch, file_path, original_content)
            ai_patch["fallback_used"] = False
            return ai_patch
        except Exception:
            pass

    fallback_patch = build_known_safe_patch(
        file_path=file_path,
        original_content=original_content,
        user_task=user_task,
    )

    validate_patch(fallback_patch, file_path, original_content)
    return fallback_patch


def apply_generated_patch(repo_path: str, user_task: str, search_results: list) -> dict:
    """
    Concept: Apply generated patch = validated patch gets written using replace_text mode.
    """
    patch = generate_patch(
        repo_path=repo_path,
        user_task=user_task,
        search_results=search_results,
    )

    result = apply_change(
        repo_path=repo_path,
        file_path=patch["file_path"],
        mode="replace_text",
        old_text=patch["old_text"],
        new_text=patch["new_text"],
        backup=True,
    )

    return {
        "patch": patch,
        "apply_result": result,
    }