from typing import Optional
#from app.services.git_service import create_commit_with_branch
from app.services.git_service import (
    push_branch,
    create_github_pr,
    run_git_command,
    create_commit_with_branch,   # 🔥 ADD THIS
)
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.git_service import push_branch, create_github_pr
from app.agents.debug_agent import debug_agent
from app.agents.graph import build_agent_graph
from app.services.change_service import apply_change
from app.services.chunking_service import chunk_code
from app.services.git_service import (
    get_git_diff,
    get_git_diff_stat,
    get_git_status,
    rollback_all,
    rollback_file,
)
from app.services.ingestion_service import load_repo_files
from app.services.llm_service import generate_answer
from app.services.patch_service import apply_generated_patch
from app.services.repo_service import clone_repo
from app.services.test_service import load_cached_failed_tests, run_repo_tests
from app.services.vector_service import index_chunks, search_chunks
from app.tools.file_tools import list_repo_files, read_file, write_file


router = APIRouter()


class RepoRequest(BaseModel):
    repo_url: str

class CommitRequest(BaseModel):
    message: str
    branch_name: Optional[str] = None


class ReadFileRequest(BaseModel):
    file_path: str


class WriteFileRequest(BaseModel):
    file_path: str
    content: str


class ApplyChangeRequest(BaseModel):
    file_path: str
    mode: str
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    new_content: Optional[str] = None
    backup: bool = True


class AskRepoRequest(BaseModel):
    question: str


class RollbackFileRequest(BaseModel):
    file_path: str


class RollbackAllRequest(BaseModel):
    delete_untracked: bool = False
class PRRequest(BaseModel):
    title: str
    body: str

@router.post("/clone")
def clone(request: RepoRequest):
    return clone_repo(request.repo_url)


@router.get("/{repo_id}/files")
def get_repo_files(repo_id: str):
    repo_path = f"repos/{repo_id}"
    files = load_repo_files(repo_path)

    return {
        "repo_id": repo_id,
        "total_files": len(files),
        "files": [file["path"] for file in files[:50]],
    }


@router.get("/{repo_id}/chunks")
def get_repo_chunks(repo_id: str):
    repo_path = f"repos/{repo_id}"
    files = load_repo_files(repo_path)
    chunks = chunk_code(files)

    return {
        "repo_id": repo_id,
        "total_chunks": len(chunks),
        "sample_chunks": chunks[:5],
    }


@router.post("/{repo_id}/index")
def index_repo(repo_id: str):
    repo_path = f"repos/{repo_id}"
    files = load_repo_files(repo_path)
    chunks = chunk_code(files)

    return index_chunks(repo_id, chunks)


@router.get("/{repo_id}/search")
def search_repo(repo_id: str, query: str):
    results = search_chunks(repo_id, query)

    return {
        "repo_id": repo_id,
        "query": query,
        "results": results,
    }


@router.get("/{repo_id}/ask")
def ask_repo(repo_id: str, question: str):
    results = search_chunks(repo_id, question, limit=5)

    context = "\n\n".join(
        [
            f"File: {item['path']}\nScore: {item['score']}\nCode:\n{item['content']}"
            for item in results
        ]
    )

    prompt = f"""
You are a senior software engineer.

Answer the user's question using ONLY the code context below.

User question:
{question}

Code context:
{context}

Important rules:
- Prefer actual source code files over HISTORY.md, README.md, docs, or tests.
- Mention exact file names.
- Explain clearly and practically.

Return in this format:

## Direct Answer

## Important Files

## Explanation

## Notes
"""

    answer = generate_answer(prompt)

    return {
        "repo_id": repo_id,
        "question": question,
        "retrieved_files": [item["path"] for item in results],
        "answer": answer,
    }


@router.get("/{repo_id}/list-files")
def list_files_api(repo_id: str):
    repo_path = f"repos/{repo_id}"
    files = list_repo_files(repo_path)

    return {
        "repo_id": repo_id,
        "total_files": len(files),
        "files": files[:100],
    }


@router.post("/{repo_id}/read-file")
def read_file_api(repo_id: str, request: ReadFileRequest):
    repo_path = f"repos/{repo_id}"
    content = read_file(repo_path, request.file_path)

    return {
        "repo_id": repo_id,
        "file_path": request.file_path,
        "content": content,
    }


@router.post("/{repo_id}/write-file")
def write_file_api(repo_id: str, request: WriteFileRequest):
    repo_path = f"repos/{repo_id}"

    return write_file(
        repo_path=repo_path,
        file_path=request.file_path,
        content=request.content,
    )


@router.post("/{repo_id}/apply-change")
def apply_change_api(repo_id: str, request: ApplyChangeRequest):
    repo_path = f"repos/{repo_id}"

    return apply_change(
        repo_path=repo_path,
        file_path=request.file_path,
        mode=request.mode,
        old_text=request.old_text,
        new_text=request.new_text,
        new_content=request.new_content,
        backup=request.backup,
    )


@router.post("/{repo_id}/auto-patch")
def auto_patch_api(repo_id: str, request: AskRepoRequest):
    repo_path = f"repos/{repo_id}"

    search_results = search_chunks(
        repo_id=repo_id,
        query=request.question,
        limit=3,
    )

    result = apply_generated_patch(
        repo_path=repo_path,
        user_task=request.question,
        search_results=search_results,
    )

    return {
        "repo_id": repo_id,
        "task": request.question,
        "result": result,
    }


@router.post("/{repo_id}/run-tests")
def run_tests_api(
    repo_id: str,
    target: Optional[str] = None,
    force_install: bool = False,
):
    repo_path = f"repos/{repo_id}"

    result = run_repo_tests(
        repo_path=repo_path,
        target=target,
        force_install=force_install,
    )

    return {
        "repo_id": repo_id,
        "target": target,
        "result": result,
    }


@router.post("/{repo_id}/auto-debug")
def auto_debug_api(repo_id: str):
    repo_path = f"repos/{repo_id}"

    cached_failed_tests = load_cached_failed_tests(repo_path)

    if cached_failed_tests:
        targeted_before = [
            run_repo_tests(
                repo_path=repo_path,
                target=test,
                force_install=False,
            )
            for test in cached_failed_tests[:3]
        ]

        all_targeted_before_passed = all(
            result.get("passed") for result in targeted_before
        )

        if all_targeted_before_passed:
            full_result = run_repo_tests(
                repo_path=repo_path,
                force_install=False,
            )

            return {
                "repo_id": repo_id,
                "mode": "fast_path_cached_failures_now_pass",
                "cached_failed_tests": cached_failed_tests,
                "targeted_before": targeted_before,
                "debug": {
                    "status": "no_action",
                    "message": "Cached failing tests now pass. Full suite was executed.",
                },
                "after_debug_test": full_result,
            }

        first_failed_result = next(
            result for result in targeted_before if not result.get("passed")
        )

        state = {
            "repo_id": repo_id,
            "repo_path": repo_path,
            "test_result": first_failed_result,
        }

        state = debug_agent(state)
        debug_result = state.get("debug", {})

        targeted_after = [
            run_repo_tests(
                repo_path=repo_path,
                target=test,
                force_install=False,
            )
            for test in cached_failed_tests[:3]
        ]

        all_targeted_after_passed = all(
            result.get("passed") for result in targeted_after
        )

        full_result = None

        if all_targeted_after_passed:
            full_result = run_repo_tests(
                repo_path=repo_path,
                force_install=False,
            )

        return {
            "repo_id": repo_id,
            "mode": "fast_path_debug_cached_failures",
            "cached_failed_tests": cached_failed_tests,
            "targeted_before": targeted_before,
            "debug": debug_result,
            "targeted_after": targeted_after,
            "after_debug_test": full_result,
            "note": "Full suite runs only if targeted tests pass.",
        }

    full_before = run_repo_tests(
        repo_path=repo_path,
        force_install=False,
    )

    if full_before.get("passed"):
        return {
            "repo_id": repo_id,
            "mode": "cold_start_all_passed",
            "before_test": full_before,
            "debug": {
                "status": "no_action",
                "message": "Full test suite already passes.",
            },
            "after_debug_test": full_before,
        }

    state = {
        "repo_id": repo_id,
        "repo_path": repo_path,
        "test_result": full_before,
    }

    state = debug_agent(state)
    debug_result = state.get("debug", {})

    failed_tests = full_before.get("failed_tests", [])

    targeted_after = [
        run_repo_tests(
            repo_path=repo_path,
            target=test,
            force_install=False,
        )
        for test in failed_tests[:3]
    ]

    all_targeted_after_passed = (
        bool(targeted_after)
        and all(result.get("passed") for result in targeted_after)
    )

    full_after = None

    if all_targeted_after_passed:
        full_after = run_repo_tests(
            repo_path=repo_path,
            force_install=False,
        )

    return {
        "repo_id": repo_id,
        "mode": "cold_start_debug",
        "before_test": full_before,
        "debug": debug_result,
        "targeted_after": targeted_after,
        "after_debug_test": full_after,
        "note": "Future auto-debug calls will use cached failed tests first.",
    }


@router.get("/{repo_id}/git-status")
def git_status_api(repo_id: str):
    repo_path = f"repos/{repo_id}"

    return {
        "repo_id": repo_id,
        "status": get_git_status(repo_path),
    }


@router.get("/{repo_id}/git-diff")
def git_diff_api(repo_id: str):
    repo_path = f"repos/{repo_id}"

    return {
        "repo_id": repo_id,
        "diff": get_git_diff(repo_path),
    }


@router.get("/{repo_id}/git-diff-stat")
def git_diff_stat_api(repo_id: str):
    repo_path = f"repos/{repo_id}"

    return {
        "repo_id": repo_id,
        "diff_stat": get_git_diff_stat(repo_path),
    }


@router.post("/{repo_id}/rollback-file")
def rollback_file_api(repo_id: str, request: RollbackFileRequest):
    repo_path = f"repos/{repo_id}"

    result = rollback_file(
        repo_path=repo_path,
        file_path=request.file_path,
    )

    return {
        "repo_id": repo_id,
        "file_path": request.file_path,
        "result": result,
    }


@router.post("/{repo_id}/rollback-all")
def rollback_all_api(repo_id: str, request: RollbackAllRequest):
    repo_path = f"repos/{repo_id}"

    result = rollback_all(
        repo_path=repo_path,
        delete_untracked=request.delete_untracked,
    )

    return {
        "repo_id": repo_id,
        "delete_untracked": request.delete_untracked,
        "result": result,
    }

@router.post("/{repo_id}/commit")
def commit_api(repo_id: str, request: CommitRequest):
    repo_path = f"repos/{repo_id}"

    result = create_commit_with_branch(
        repo_path=repo_path,
        message=request.message,
    )

    return {
        "repo_id": repo_id,
        "result": result
    }
@router.post("/{repo_id}/create-pr")
def create_pr_api(repo_id: str, request: PRRequest):
    repo_path = f"repos/{repo_id}"

    # Get current branch
    branch_result = run_git_command(repo_path, "git branch --show-current")
    branch_name = branch_result["stdout"].strip()

    # Push branch
    push_result = push_branch(repo_path, branch_name)

    # Create PR
    pr_result = create_github_pr(
        repo_path=repo_path,
        branch_name=branch_name,
        title=request.title,
        body=request.body,
    )

    return {
        "repo_id": repo_id,
        "branch": branch_name,
        "push": push_result,
        "pr": pr_result,
    }
@router.get("/{repo_id}/agent-ask")
def agent_ask(repo_id: str, task: str, review: bool = True):
    graph = build_agent_graph()

    result = graph.invoke(
        {
            "repo_id": repo_id,
            "user_task": task,
            "review_enabled": review,
            "plan": [],
            "research_results": [],
            "code_suggestion": {},
            "final_answer": {},
            "review": {},
        }
    )

    return result