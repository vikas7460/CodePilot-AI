import os

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv"
}

ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".html",
    ".css"
}

def should_include_file(file_path: str) -> bool:
    _, ext = os.path.splitext(file_path)
    return ext in ALLOWED_EXTENSIONS

def load_repo_files(repo_path: str):
    files = []

    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for filename in filenames:
            full_path = os.path.join(root, filename)

            if not should_include_file(full_path):
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                relative_path = os.path.relpath(full_path, repo_path)

                files.append({
                    "path": relative_path,
                    "content": content
                })

            except Exception:
                continue

    return files