import os
import shutil
import difflib


BLOCKED_FILES = {".env", "id_rsa", "id_rsa.pub"}
ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go",
    ".md", ".json", ".yml", ".yaml", ".html", ".css", ".txt"
}


def safe_path(repo_path: str, file_path: str) -> str:
    repo_root = os.path.abspath(repo_path)
    full_path = os.path.abspath(os.path.join(repo_root, file_path))

    if not full_path.startswith(repo_root):
        raise ValueError("Unsafe file path detected")

    filename = os.path.basename(full_path)

    if filename in BLOCKED_FILES:
        raise ValueError("Editing this file is not allowed")

    _, ext = os.path.splitext(full_path)

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File extension not allowed: {ext}")

    return full_path


def create_backup(full_path: str) -> str:
    backup_path = full_path + ".bak"
    shutil.copy2(full_path, backup_path)
    return backup_path


def generate_diff(original: str, updated: str, file_path: str) -> str:
    diff = difflib.unified_diff(
        original.splitlines(),
        updated.splitlines(),
        fromfile=f"{file_path} (before)",
        tofile=f"{file_path} (after)",
        lineterm=""
    )

    return "\n".join(diff)


def apply_change(
    repo_path: str,
    file_path: str,
    mode: str,
    old_text: str | None = None,
    new_text: str | None = None,
    new_content: str | None = None,
    backup: bool = True
):
    full_path = safe_path(repo_path, file_path)

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(full_path, "r", encoding="utf-8") as f:
        original = f.read()

    if mode == "replace_text":
        if not old_text or new_text is None:
            raise ValueError("old_text and new_text are required for replace_text mode")

        if old_text not in original:
            raise ValueError("old_text not found in file")

        updated = original.replace(old_text, new_text, 1)

    elif mode == "append":
        if not new_text:
            raise ValueError("new_text is required for append mode")

        updated = original.rstrip() + "\n\n" + new_text.strip() + "\n"

    elif mode == "overwrite":
        if new_content is None:
            raise ValueError("new_content is required for overwrite mode")

        updated = new_content

    else:
        raise ValueError("Invalid mode. Use replace_text, append, or overwrite")

    backup_path = None

    if backup:
        backup_path = create_backup(full_path)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(updated)

    return {
        "status": "success",
        "file_path": file_path,
        "mode": mode,
        "backup_path": backup_path,
        "diff": generate_diff(original, updated, file_path)
    }