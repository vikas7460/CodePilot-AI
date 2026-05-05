from app.services.debug_service import run_debug_fix


def debug_agent(state: dict):
    """
    Concept: Debug Agent = fixes code based on failing test output.
    """
    repo_id = state.get("repo_id")
    repo_path = state.get("repo_path")
    test_result = state.get("test_result", {})

    if not repo_id or not repo_path:
        state["debug"] = {
            "status": "failed",
            "error": "repo_id or repo_path missing",
        }
        return state

    if not test_result:
        state["debug"] = {
            "status": "no_action",
            "message": "No test result available",
        }
        return state

    if test_result.get("passed"):
        state["debug"] = {
            "status": "no_action",
            "message": "Tests already passed",
        }
        return state

    try:
        debug_result = run_debug_fix(
            repo_id=repo_id,
            repo_path=repo_path,
            test_result=test_result,
        )

        state["debug"] = {
            "status": "fix_applied",
            **debug_result,
        }

    except Exception as error:
        state["debug"] = {
            "status": "failed",
            "error": str(error),
        }

    return state