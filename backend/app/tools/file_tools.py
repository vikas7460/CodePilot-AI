import os


def safe_path(repo_path: str, file_path: str) -> str:
    full_path = os.path.abspath(os.path.join(repo_path, file_path))
    repo_root = os.path.abspath(repo_path)

    if not full_path.startswith(repo_root):
        raise ValueError("Unsafe file path detected")

    return full_path


def read_file(repo_path: str, file_path: str) -> str:
    full_path = safe_path(repo_path, file_path)

    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(repo_path: str, file_path: str, content: str):
    full_path = safe_path(repo_path, file_path)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status": "success",
        "message": "File written successfully",
        "file_path": file_path
    }


def list_repo_files(repo_path: str):
    files = []

    ignore_dirs = {".git", "node_modules", "venv", "__pycache__", "qdrant_db"}

    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for filename in filenames:
            full_path = os.path.join(root, filename)
            relative_path = os.path.relpath(full_path, repo_path)
            files.append(relative_path)

    return files