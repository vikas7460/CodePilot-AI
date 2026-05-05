import os
from app.services.llm_service import generate_answer
from app.services.change_service import apply_change


def choose_primary_source_file(search_results: list) -> str:
    for item in search_results:
        path = item.get("path", "")
        lower_path = path.lower()

        if lower_path.startswith(("src\\", "src/", "app\\", "app/", "lib\\", "lib/")):
            return path

    return search_results[0].get("path", "") if search_results else ""


def clean_ai_output(text: str) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```python"):
        cleaned = cleaned.replace("```python", "", 1).strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```", "", 1).strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    return cleaned


def validate_append_content(text: str):
    if not text.strip():
        raise ValueError("AI returned empty content")

    if len(text.strip()) < 10:
        raise ValueError("AI returned too little content")

    return True


def auto_edit_file(repo_path: str, user_task: str, search_results: list):
    primary_file = choose_primary_source_file(search_results)

    if not primary_file:
        raise ValueError("No source file found to edit")

    prompt = f"""
You are editing a Python source file.

Task:
{user_task}

Target file:
{primary_file}

Return ONLY a short Python comment block to append at the end of the file.
Do not return markdown.
Do not return explanation.
Do not use code fences.

Example format:
# AI CHANGE NOTE:
# custom authentication support experiment
"""

    ai_output = generate_answer(prompt)
    append_text = clean_ai_output(ai_output)

    validate_append_content(append_text)

    result = apply_change(
        repo_path=repo_path,
        file_path=primary_file,
        mode="append",
        new_text=append_text,
        backup=True,
    )

    return {
        "edited_file": primary_file,
        "result": result,
    }