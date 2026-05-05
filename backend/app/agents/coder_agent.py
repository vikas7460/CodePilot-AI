from app.services.llm_service import generate_answer


def choose_primary_source_file(research_results: list) -> str:
    """
    Concept: Primary source file = the main implementation file the Coder Agent should modify.
    """
    for item in research_results:
        path = item.get("path", "")

        lower_path = path.lower()

        if lower_path.startswith("src\\") or lower_path.startswith("src/"):
            return path

        if lower_path.startswith("app\\") or lower_path.startswith("app/"):
            return path

        if lower_path.startswith("lib\\") or lower_path.startswith("lib/"):
            return path

    return research_results[0].get("path", "") if research_results else ""


def coder_agent(state: dict):
    """
    Concept: Coder Agent = proposes safe file-level implementation changes before real editing.
    """
    user_task = state.get("user_task", "")
    research_results = state.get("research_results", [])

    primary_file = choose_primary_source_file(research_results)

    primary_content = ""

    for item in research_results:
        if item.get("path") == primary_file:
            primary_content = item.get("content", "")
            break

    prompt = f"""
You are a senior Python engineer.

User task:
{user_task}

You are allowed to modify ONLY this file:
{primary_file}

Relevant code from this file:
{primary_content[:1600]}

Instructions:
- Suggest changes for ONLY the allowed file.
- Use the exact same file path in FILES and CHANGES.
- Do NOT mention tests/test_utils.py as a file to modify.
- Do NOT invent new files.
- Do NOT use markdown code blocks.
- Do NOT generate full code.
- Keep output short, practical, and consistent.

Return in this exact format:

FILES:
- path: {primary_file}
  reason: short reason

CHANGES:
- file: {primary_file}
  change: short implementation step

TESTS:
- short test idea

RISK:
Low / Medium / High

NOTES:
short notes
"""

    suggestion = generate_answer(prompt)

    state["code_suggestion"] = {
        "task": user_task,
        "primary_file": primary_file,
        "suggestion": suggestion
    }

    return state