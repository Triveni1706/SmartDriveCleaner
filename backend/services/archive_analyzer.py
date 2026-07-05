"""
Archive analytics. ZIP is fully supported (stdlib zipfile — real, no
external deps). RAR and 7Z require external system tools (unrar/7z binaries)
that may not be installed; those are handled gracefully with a None result
rather than crashing the scan, and the API surface still reports them as
Archives with size/name info even without deep inspection.
"""
import zipfile
import os

try:
    import py7zr
    HAS_7Z = True
except ImportError:
    HAS_7Z = False

try:
    import rarfile
    HAS_RAR = True
except ImportError:
    HAS_RAR = False


def analyze_archive(filepath: str) -> dict:
    ext = os.path.splitext(filepath)[1].lower()
    info = {"file_count": None, "uncompressed_bytes": None}

    try:
        if ext == ".zip" and zipfile.is_zipfile(filepath):
            with zipfile.ZipFile(filepath) as zf:
                infos = zf.infolist()
                info["file_count"] = len(infos)
                info["uncompressed_bytes"] = sum(i.file_size for i in infos)

        elif ext == ".7z" and HAS_7Z:
            with py7zr.SevenZipFile(filepath, mode="r") as zf:
                names = zf.getnames()
                info["file_count"] = len(names)

        elif ext == ".rar" and HAS_RAR:
            with rarfile.RarFile(filepath) as rf:
                infos = rf.infolist()
                info["file_count"] = len(infos)
                info["uncompressed_bytes"] = sum(i.file_size for i in infos)

    except Exception:
        pass  # corrupt/encrypted/unsupported archive — leave as None, don't crash scan

    return info


def detect_zip_backups(archives: list) -> list[dict]:
    """Spec case: 'Project Folder' + 'Project.zip' both exist. For each
    archive row, check whether a same-named directory sits next to it on
    disk (base name match). If so it's very likely a redundant backup of
    that folder — flag it with the folder's total size as context.

    Pure filesystem check (directories are never indexed as ScannedFile
    rows, so this can't be answered from the DB alone).
    """
    pairs = []
    for archive in archives:
        try:
            folder = os.path.splitext(archive.path)[0]
            if os.path.isdir(folder):
                folder_bytes = _dir_size(folder)
                pairs.append({
                    "archive_id": archive.id,
                    "archive_name": archive.name,
                    "archive_path": archive.path,
                    "archive_bytes": archive.size_bytes or 0,
                    "folder_path": folder,
                    "folder_bytes": folder_bytes,
                })
        except OSError:
            continue
    return pairs


def _dir_size(folder: str, cap_files: int = 20000) -> int:
    total = 0
    count = 0
    for dirpath, _dirnames, filenames in os.walk(folder):
        for name in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
            count += 1
            if count >= cap_files:
                return total
    return total
