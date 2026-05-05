import os
import uuid
from git import Repo

REPOS_DIR = "repos"

def clone_repo(repo_url: str):
    # ensure repos folder exists
    os.makedirs(REPOS_DIR, exist_ok=True)

    repo_id = str(uuid.uuid4())
    repo_path = os.path.join(REPOS_DIR, repo_id)

    Repo.clone_from(repo_url, repo_path)

    return {
        "repo_id": repo_id,
        "repo_path": repo_path
    }