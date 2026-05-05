from app.services.llm_service import generate_answer

def answer_agent(state: dict):
    user_task = state["user_task"]
    plan = state["plan"]
    research_results = state["research_results"]

    context = "\n\n".join([
        f"File: {item['path']}\nScore: {item['score']}\nCode:\n{item['content']}"
        for item in research_results
    ])

    prompt = f"""
You are a senior software engineer.

User task:
{user_task}

Plan:
{plan}

Relevant code context:
{context}

Rules:
- Prefer source code files over docs/tests.
- Mention exact file names.
- Explain clearly and practically.
- If information is missing, say what is missing.

Return answer in this format:

## Direct Answer

## Important Files

## Explanation

## Next Steps
"""

    answer = generate_answer(prompt)

    state["final_answer"] = {
        "task": user_task,
        "plan": plan,
        "retrieved_files": [item["path"] for item in research_results],
        "answer": answer
    }

    return state