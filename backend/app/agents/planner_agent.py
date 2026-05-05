def planner_agent(state: dict):
    user_task = state["user_task"]

    state["plan"] = [
        f"Understand the task: {user_task}",
        "Search relevant code chunks from vector database",
        "Analyze retrieved files",
        "Generate a clear engineering answer"
    ]

    return state