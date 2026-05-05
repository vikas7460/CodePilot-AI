from app.services.llm_service import generate_answer


def reviewer_agent(state: dict):
    user_task = state["user_task"]
    final_answer = state["final_answer"]
    research_results = state["research_results"]

    retrieved_files = [item["path"] for item in research_results]

    prompt = f"""
You are a senior code reviewer.

User task:
{user_task}

AI generated answer:
{final_answer["answer"]}

Retrieved files:
{retrieved_files}

Review the answer.

Check:
1. Is the answer grounded in retrieved files?
2. Are important source files mentioned?
3. Is there any noise or irrelevant file?
4. Is anything missing?
5. Give a reliability score from 1 to 10.

Return in this format:

## Review Summary

## Missing / Weak Points

## Reliability Score

## Suggested Improvement
"""

    review = generate_answer(prompt)

    state["review"] = {
        "retrieved_files": retrieved_files,
        "review": review
    }

    return state