from app.services.vector_service import search_chunks

def researcher_agent(state: dict):
    repo_id = state["repo_id"]
    user_task = state["user_task"]

    results = search_chunks(
        repo_id=repo_id,
        query=user_task,
        limit=3
    )

    state["research_results"] = results

    return state