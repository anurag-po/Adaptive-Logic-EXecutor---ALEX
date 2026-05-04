"""
ALEX — File Actions
create_folder, open_folder, search_file, delete_file, move_file, open_recent_files
"""

import os
import glob
import shutil
from utils.helpers import get_logger, sanitize_path

logger = get_logger()


def create_folder(path: str, name: str) -> str:
    """Create a new folder at the specified path."""
    path = sanitize_path(path)
    full_path = os.path.join(path, name)
    try:
        os.makedirs(full_path, exist_ok=True)
        logger.info(f"Created folder: {full_path}")
        return f"Folder '{name}' created at {path}."
    except OSError as e:
        logger.error(f"Failed to create folder: {e}")
        return f"Could not create folder: {e}"


def open_folder(path: str) -> str:
    """Open a folder in File Explorer."""
    path = sanitize_path(path)
    if not os.path.isdir(path):
        return f"Folder not found: {path}"
    try:
        os.startfile(path)
        logger.info(f"Opened folder: {path}")
        return f"Opened folder: {path}"
    except OSError as e:
        return f"Could not open folder: {e}"


def search_file(query: str) -> str:
    """
    Search for files matching the query in common user directories.
    Returns up to 10 matching file paths.
    """
    search_dirs = [
        os.path.expanduser("~\\Desktop"),
        os.path.expanduser("~\\Documents"),
        os.path.expanduser("~\\Downloads"),
    ]

    matches = []
    query_lower = query.lower()

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for root, dirs, files in os.walk(search_dir):
            # Skip hidden and system directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if query_lower in fname.lower():
                    matches.append(os.path.join(root, fname))
                    if len(matches) >= 10:
                        break
            if len(matches) >= 10:
                break
        if len(matches) >= 10:
            break

    if matches:
        result = f"Found {len(matches)} file(s):\n"
        result += "\n".join(f"  • {m}" for m in matches)
        logger.info(f"File search '{query}': {len(matches)} results")
        return result
    else:
        return f"No files found matching '{query}'."


def delete_file(path: str) -> str:
    """Delete a file at the given path. (Sensitive — requires confirmation)"""
    path = sanitize_path(path)
    if not os.path.exists(path):
        return f"File not found: {path}"
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
            logger.warning(f"Deleted directory: {path}")
            return f"Deleted directory: {path}"
        else:
            os.remove(path)
            logger.warning(f"Deleted file: {path}")
            return f"Deleted file: {path}"
    except OSError as e:
        return f"Could not delete: {e}"


def move_file(source: str, destination: str) -> str:
    """Move a file from source to destination."""
    source = sanitize_path(source)
    destination = sanitize_path(destination)
    if not os.path.exists(source):
        return f"Source not found: {source}"
    try:
        shutil.move(source, destination)
        logger.info(f"Moved {source} → {destination}")
        return f"Moved to {destination}."
    except Exception as e:
        return f"Could not move file: {e}"


def open_recent_files(limit: int = 5) -> str:
    """List recently accessed files from Windows Recent folder."""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 5

    recent_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Recent"
    )

    if not os.path.isdir(recent_dir):
        return "Could not access Recent files folder."

    files = []
    for fname in os.listdir(recent_dir):
        fpath = os.path.join(recent_dir, fname)
        if os.path.isfile(fpath):
            files.append((os.path.getmtime(fpath), fname))

    files.sort(reverse=True)
    recent = files[:limit]

    if recent:
        result = f"Last {len(recent)} recent files:\n"
        result += "\n".join(f"  • {name}" for _, name in recent)
        return result
    else:
        return "No recent files found."
