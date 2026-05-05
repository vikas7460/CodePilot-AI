import os
import subprocess
import datetime

def run_git_command(repo_path: str, command: str):
    result = subprocess.run(
        command,
        cwd=repo_path,
        shell=True,
        capture_output=True,
        text=True,
    )

    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.returncode == 0,
    }


def is_git_repo(repo_path: str) -> bool:
    return os.path.exists(os.path.join(repo_path, ".git"))


def init_git_if_needed(repo_path: str):
    if is_git_repo(repo_path):
        return {
            "status": "already_initialized",
            "message": "Git repo already exists.",
        }

    init_result = run_git_command(repo_path, "git init")
    add_result = run_git_command(repo_path, "git add .")
    commit_result = run_git_command(
        repo_path,
        'git commit -m "Initial snapshot before AI changes"',
    )

    return {
        "status": "initialized",
        "init": init_result,
        "add": add_result,
        "commit": commit_result,
    }


def get_git_status(repo_path: str):
    init_git_if_needed(repo_path)
    return run_git_command(repo_path, "git status --short")


def get_git_diff(repo_path: str):
    init_git_if_needed(repo_path)
    return run_git_command(repo_path, "git diff")


def get_git_diff_stat(repo_path: str):
    init_git_if_needed(repo_path)
    return run_git_command(repo_path, "git diff --stat")


def rollback_file(repo_path: str, file_path: str):
    init_git_if_needed(repo_path)

    return run_git_command(
        repo_path,
        f'git checkout -- "{file_path}"',
    )


def rollback_all(repo_path: str, delete_untracked: bool = False):
    """
    Concept: Safe rollback = revert tracked file changes first.
    Untracked files are deleted only if explicitly requested.
    """
    init_git_if_needed(repo_path)

    checkout_result = run_git_command(repo_path, "git checkout -- .")

    clean_result = None

    if delete_untracked:
        clean_result = run_git_command(repo_path, "git clean -fd")

    return {
        "tracked_files_rollback": checkout_result,
        "untracked_files_deleted": delete_untracked,
        "untracked_cleanup": clean_result,
        "safety_note": (
            "Tracked file changes were reverted. "
            "Untracked files are deleted only when delete_untracked=true."
        ),
    }



def create_branch(repo_path: str, branch_name: str = None):
    init_git_if_needed(repo_path)

    if not branch_name:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"ai-fix-{timestamp}"

    checkout = run_git_command(
        repo_path,
        f'git checkout -b "{branch_name}"'
    )

    return {
        "branch_name": branch_name,
        "checkout": checkout
    }


def stage_all_changes(repo_path: str):
    return run_git_command(repo_path, "git add .")


def commit_changes(repo_path: str, message: str):
    return run_git_command(
        repo_path,
        f'git commit -m "{message}"'
    )


def create_commit_with_branch(repo_path: str, message: str):
    branch = create_branch(repo_path)
    stage = stage_all_changes(repo_path)
    commit = commit_changes(repo_path, message)

    return {
        "branch": branch,
        "stage": stage,
        "commit": commit
    }
import requests
import os


def get_remote_repo_info(repo_path: str):
    """
    Extract owner and repo name from git remote origin
    """
    result = run_git_command(repo_path, "git config --get remote.origin.url")

    url = result["stdout"].strip()

    if "github.com" not in url:
        return None

    # Handle both HTTPS and SSH
    if url.startswith("git@"):
        # git@github.com:user/repo.git
        parts = url.split(":")[1].replace(".git", "")
    else:
        # https://github.com/user/repo.git
        parts = url.split("github.com/")[1].replace(".git", "")

    owner, repo = parts.split("/")

    return owner, repo


def push_branch(repo_path: str, branch_name: str):
    return run_git_command(
        repo_path,
        f'git push -u origin "{branch_name}"'
    )


def create_github_pr(repo_path: str, branch_name: str, title: str, body: str):
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        return {
            "success": False,
            "error": "GITHUB_TOKEN not set"
        }

    repo_info = get_remote_repo_info(repo_path)

    if not repo_info:
        return {
            "success": False,
            "error": "Could not detect GitHub repo"
        }

    owner, repo = repo_info

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"

    payload = {
        "title": title,
        "body": body,
        "head": branch_name,
        "base": "main"
    }

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.post(url, json=payload, headers=headers)

    return {
        "status_code": response.status_code,
        "response": response.json(),
        "success": response.status_code in [200, 201]
    }