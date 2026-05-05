from app.services.test_service import run_repo_tests


def test_runner_agent(state: dict):
    repo_path = state.get("repo_path", "")

    if not repo_path:
        state["test_result"] = {
            "passed": False,
            "error": "repo_path missing in agent state",
        }
        return state

    result = run_repo_tests(repo_path)

    state["test_result"] = result

    return state