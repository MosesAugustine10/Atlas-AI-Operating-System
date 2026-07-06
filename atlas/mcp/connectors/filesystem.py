"""Filesystem MCP connector — real implementation.

Exposes comprehensive filesystem capabilities via :mod:`pathlib`,
:mod:`shutil`, and :mod:`zipfile`. Every operation works against the
real local filesystem.

Capabilities:

* ``file.read`` — read a file's contents.
* ``file.write`` — write content to a file (overwrites).
* ``file.append`` — append content to a file.
* ``file.copy`` — copy a file or directory.
* ``file.move`` — move a file or directory.
* ``file.rename`` — rename a file or directory.
* ``file.delete`` — delete a file or directory.
* ``file.exists`` — check whether a path exists.
* ``file.search`` — glob-search for files matching a pattern.
* ``file.list`` — list directory contents.
* ``file.mkdir`` — create a directory (with parents).
* ``file.watch`` — placeholder (returns a marker; real watch needs a
  background thread).
* ``file.zip`` — zip a file or directory.
* ``file.extract`` — extract a zip archive.
* ``file.path`` — path utilities (resolve, absolute, parent, name, stem,
  suffix, parts).
"""

from __future__ import annotations

import fnmatch
import os
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas.mcp.base import BaseConnector
from atlas.mcp.connector_config import get_connector_config
from atlas.mcp.models import (
    HealthLevel,
    MCPCapability,
    MCPHealth,
    MCPRequest,
    MCPStatus,
    MCPTransport,
    TransportKind,
)
from atlas.mcp.permissions import PermissionLevel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class FilesystemConnector(BaseConnector):
    """Real filesystem MCP connector.

    Parameters:
        root: Root directory for relative paths. Defaults to the value
            in ``connectors.yaml`` (``filesystem.root``), or ``"."`` if
            not configured. Can be overridden via the
            ``ATLAS_FILESYSTEM_ROOT`` environment variable.
        encoding: Text encoding for read/write operations.
        max_file_size_mb: Maximum file size for read operations (safety
            guard against reading huge files into memory).
    """

    def __init__(
        self,
        root: str | Path | None = None,
        encoding: str | None = None,
        max_file_size_mb: int | None = None,
    ) -> None:
        cfg = get_connector_config("filesystem")
        self.root = Path(root or cfg.get("root", "."))
        self.encoding = encoding or cfg.get("encoding", "utf-8")
        self.max_file_size_mb = (
            max_file_size_mb
            if max_file_size_mb is not None
            else cfg.get("max_file_size_mb", 100)
        )
        # Undo stack for write/delete operations (stores backup content)
        self._undo_stack: list[dict[str, Any]] = []
        self._max_undo: int = 50
        super().__init__(
            name="filesystem",
            description=(
                "Filesystem access (read, write, append, copy, move, "
                "rename, delete, exists, search, list, mkdir, zip, "
                "extract, path utilities)"
            ),
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.STDIO),
            default_transport=TransportKind.IN_PROCESS,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="file.read", description="Read a file", permissions=("read",)
                ),
                MCPCapability(
                    name="file.write",
                    description="Write a file",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="file.append",
                    description="Append to a file",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="file.copy",
                    description="Copy a file or directory",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="file.move",
                    description="Move a file or directory",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="file.rename",
                    description="Rename a file or directory",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="file.delete",
                    description="Delete a file or directory",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="file.exists",
                    description="Check if a path exists",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="file.search",
                    description="Search for files matching a pattern",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="file.list",
                    description="List directory contents",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="file.mkdir",
                    description="Create a directory",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="file.watch",
                    description="Watch a directory (placeholder)",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="file.zip",
                    description="Zip a file or directory",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="file.extract",
                    description="Extract a zip archive",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="file.path",
                    description="Path utilities",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="file.index",
                    description="Recursively index a project directory",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="file.undo",
                    description="Undo the last write/delete operation",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="file.git_info",
                    description="Git-aware file info (ignored, tracked, modified)",
                    permissions=("read",),
                ),
            ),
            metadata={
                "root": str(self.root),
                "encoding": self.encoding,
                "max_file_size_mb": self.max_file_size_mb,
            },
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _do_connect(self, transport: MCPTransport) -> None:
        """Ensure the root directory exists."""
        self.root.mkdir(parents=True, exist_ok=True)

    def _do_disconnect(self) -> None:
        return None

    def _do_health(self) -> MCPHealth:
        try:
            exists = self.root.exists()
            status = MCPStatus.CONNECTED if exists else MCPStatus.DEGRADED
            level = HealthLevel.HEALTHY if exists else HealthLevel.WARNING
            return MCPHealth(
                connector=self.name,
                status=status,
                level=level,
                latency_ms=0.1,
                last_check_at=_utcnow(),
                uptime_seconds=self.uptime_seconds,
                metadata={"root": str(self.root), "exists": exists},
            )
        except Exception as exc:  # noqa: BLE001
            return MCPHealth(
                connector=self.name,
                status=MCPStatus.FAILED,
                level=HealthLevel.CRITICAL,
                last_error=str(exc),
                last_check_at=_utcnow(),
            )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _do_execute(self, request: MCPRequest) -> Any:
        cap = request.capability
        params = request.params
        if cap == "file.read":
            return self._read_file(params)
        if cap == "file.write":
            return self._write_file(params)
        if cap == "file.append":
            return self._append_file(params)
        if cap == "file.copy":
            return self._copy(params)
        if cap == "file.move":
            return self._move(params)
        if cap == "file.rename":
            return self._rename(params)
        if cap == "file.delete":
            return self._delete(params)
        if cap == "file.exists":
            return self._exists(params)
        if cap == "file.search":
            return self._search(params)
        if cap == "file.list":
            return self._list_directory(params)
        if cap == "file.mkdir":
            return self._create_directory(params)
        if cap == "file.watch":
            return self._watch(params)
        if cap == "file.zip":
            return self._zip(params)
        if cap == "file.extract":
            return self._extract(params)
        if cap == "file.path":
            return self._path_utilities(params)
        if cap == "file.index":
            return self._index_project(params)
        if cap == "file.undo":
            return self._undo(params)
        if cap == "file.git_info":
            return self._git_aware_info(params)
        raise ValueError(f"Unknown capability: {cap!r}")

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    def _resolve(self, path: str) -> Path:
        """Resolve a user-supplied path against ``self.root``."""
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.root / p).resolve()

    def _check_size(self, path: Path) -> None:
        """Raise if ``path`` exceeds the max file size."""
        if path.is_file():
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                raise ValueError(
                    f"file {path} is {size_mb:.1f} MB which exceeds the "
                    f"max of {self.max_file_size_mb} MB"
                )

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def _read_file(self, params: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(params.get("path", ""))
        binary = params.get("binary", False)
        self._check_size(path)
        if binary:
            data = path.read_bytes()
            return {"path": str(path), "bytes": len(data), "binary": True}
        content = path.read_text(encoding=self.encoding)
        return {
            "path": str(path),
            "content": content,
            "bytes": len(content.encode(self.encoding)),
            "encoding": self.encoding,
        }

    def _write_file(self, params: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(params.get("path", ""))
        content = params.get("content", "")
        binary = params.get("binary", False)
        # Push undo entry: backup existing content
        old_content = ""
        if path.exists() and path.is_file():
            try:
                old_content = path.read_text(encoding=self.encoding)
            except Exception:  # noqa: BLE001
                old_content = ""
        self._push_undo({"op": "write", "path": str(path), "old_content": old_content})
        path.parent.mkdir(parents=True, exist_ok=True)
        if binary:
            data = params.get("data", b"")
            if isinstance(data, str):
                data = data.encode(self.encoding)
            path.write_bytes(data)
            return {"path": str(path), "bytes_written": len(data)}
        path.write_text(content, encoding=self.encoding)
        return {
            "path": str(path),
            "bytes_written": len(content.encode(self.encoding)),
        }

    def _append_file(self, params: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(params.get("path", ""))
        content = params.get("content", "")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=self.encoding) as f:
            f.write(content)
        return {
            "path": str(path),
            "bytes_appended": len(content.encode(self.encoding)),
        }

    def _copy(self, params: dict[str, Any]) -> dict[str, Any]:
        src = self._resolve(params.get("src", ""))
        dst = self._resolve(params.get("dst", ""))
        if not src.exists():
            raise FileNotFoundError(f"source not found: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return {"src": str(src), "dst": str(dst), "copied": True}

    def _move(self, params: dict[str, Any]) -> dict[str, Any]:
        src = self._resolve(params.get("src", ""))
        dst = self._resolve(params.get("dst", ""))
        if not src.exists():
            raise FileNotFoundError(f"source not found: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return {"src": str(src), "dst": str(dst), "moved": True}

    def _rename(self, params: dict[str, Any]) -> dict[str, Any]:
        src = self._resolve(params.get("src", ""))
        name = params.get("name", "")
        if not src.exists():
            raise FileNotFoundError(f"source not found: {src}")
        dst = src.parent / name
        src.rename(dst)
        return {"src": str(src), "dst": str(dst), "renamed": True}

    def _delete(self, params: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(params.get("path", ""))
        recursive = params.get("recursive", True)
        if not path.exists():
            return {"path": str(path), "deleted": False, "reason": "not found"}
        # Push undo entry: backup file content (for files only)
        if path.is_file():
            try:
                content = path.read_text(encoding=self.encoding)
                self._push_undo({"op": "delete", "path": str(path), "content": content})
            except Exception:  # noqa: BLE001
                pass
        if path.is_dir():
            if recursive:
                shutil.rmtree(path)
            else:
                path.rmdir()  # only works if empty
        else:
            path.unlink()
        return {"path": str(path), "deleted": True}

    def _exists(self, params: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(params.get("path", ""))
        return {
            "path": str(path),
            "exists": path.exists(),
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
        }

    def _search(self, params: dict[str, Any]) -> dict[str, Any]:
        pattern = params.get("pattern", "*")
        directory = self._resolve(params.get("directory", "."))
        recursive = params.get("recursive", True)
        if not directory.exists():
            raise FileNotFoundError(f"directory not found: {directory}")
        matches: list[str] = []
        if recursive:
            for root, _dirs, files in os.walk(directory):
                for fname in files:
                    if fnmatch.fnmatch(fname, pattern):
                        matches.append(str(Path(root) / fname))
        else:
            for entry in directory.iterdir():
                if fnmatch.fnmatch(entry.name, pattern):
                    matches.append(str(entry))
        return {
            "directory": str(directory),
            "pattern": pattern,
            "matches": matches,
            "count": len(matches),
        }

    def _list_directory(self, params: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(params.get("path", "."))
        if not path.exists():
            raise FileNotFoundError(f"path not found: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"not a directory: {path}")
        entries: list[dict[str, Any]] = []
        for entry in sorted(path.iterdir()):
            stat = entry.stat()
            entries.append(
                {
                    "name": entry.name,
                    "is_file": entry.is_file(),
                    "is_dir": entry.is_dir(),
                    "size": stat.st_size if entry.is_file() else 0,
                    "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                }
            )
        return {"path": str(path), "entries": entries, "count": len(entries)}

    def _create_directory(self, params: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(params.get("path", ""))
        parents = params.get("parents", True)
        exist_ok = params.get("exist_ok", True)
        if parents:
            path.mkdir(parents=parents, exist_ok=exist_ok)
        else:
            path.mkdir(exist_ok=exist_ok)
        return {"path": str(path), "created": True}

    def _watch(self, params: dict[str, Any]) -> dict[str, Any]:
        """Placeholder — real watch needs a background thread / inotify."""
        path = self._resolve(params.get("path", "."))
        return {
            "path": str(path),
            "watching": True,
            "note": "placeholder — real watch needs a background thread",
        }

    def _zip(self, params: dict[str, Any]) -> dict[str, Any]:
        src = self._resolve(params.get("src", ""))
        dst = self._resolve(params.get("dst", ""))
        if not src.exists():
            raise FileNotFoundError(f"source not found: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
            if src.is_file():
                zf.write(src, src.name)
            else:
                for root, _dirs, files in os.walk(src):
                    for fname in files:
                        fpath = Path(root) / fname
                        arcname = fpath.relative_to(src.parent)
                        zf.write(fpath, arcname)
        return {
            "src": str(src),
            "dst": str(dst),
            "zipped": True,
            "size": dst.stat().st_size,
        }

    def _extract(self, params: dict[str, Any]) -> dict[str, Any]:
        src = self._resolve(params.get("src", ""))
        dst = self._resolve(params.get("dst", "."))
        if not src.exists():
            raise FileNotFoundError(f"archive not found: {src}")
        dst.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(src, "r") as zf:
            members = zf.namelist()
            zf.extractall(dst)
        return {
            "src": str(src),
            "dst": str(dst),
            "extracted": True,
            "members": len(members),
        }

    def _path_utilities(self, params: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(params.get("path", ""))
        op = params.get("op", "info")
        if op == "info":
            return {
                "path": str(path),
                "absolute": str(path.absolute()),
                "resolved": str(path.resolve()),
                "parent": str(path.parent),
                "name": path.name,
                "stem": path.stem,
                "suffix": path.suffix,
                "parts": list(path.parts),
            }
        if op == "resolve":
            return {"path": str(path), "resolved": str(path.resolve())}
        if op == "absolute":
            return {"path": str(path), "absolute": str(path.absolute())}
        if op == "parent":
            return {"path": str(path), "parent": str(path.parent)}
        if op == "name":
            return {"path": str(path), "name": path.name}
        if op == "stem":
            return {"path": str(path), "stem": path.stem}
        if op == "suffix":
            return {"path": str(path), "suffix": path.suffix}
        if op == "parts":
            return {"path": str(path), "parts": list(path.parts)}
        raise ValueError(f"unknown path op: {op!r}")

    # ------------------------------------------------------------------
    # Recursive project indexing
    # ------------------------------------------------------------------

    def _index_project(self, params: dict[str, Any]) -> dict[str, Any]:
        """Recursively index a project directory.

        Returns a tree of files and directories with metadata.
        Respects .gitignore when available.
        """
        path = self._resolve(params.get("path", "."))
        max_depth = params.get("max_depth", 10)
        if not path.exists():
            raise FileNotFoundError(f"path not found: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"not a directory: {path}")

        # Load .gitignore patterns
        ignore_patterns = self._load_gitignore(path)

        def _index_dir(dir_path: Path, depth: int) -> dict[str, Any]:
            if depth > max_depth:
                return {"name": dir_path.name, "type": "dir", "truncated": True}
            entries: list[dict[str, Any]] = []
            try:
                for entry in sorted(dir_path.iterdir()):
                    rel = entry.relative_to(path)
                    # Check gitignore
                    if self._is_ignored(rel, ignore_patterns):
                        continue
                    if entry.is_dir():
                        if entry.name in (
                            "__pycache__",
                            ".git",
                            "node_modules",
                            ".venv",
                        ):
                            continue
                        entries.append(_index_dir(entry, depth + 1))
                    elif entry.is_file():
                        stat = entry.stat()
                        entries.append(
                            {
                                "name": entry.name,
                                "type": "file",
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(
                                    stat.st_mtime, UTC
                                ).isoformat(),
                                "suffix": entry.suffix,
                            }
                        )
            except PermissionError:
                pass
            file_count = sum(1 for e in entries if e.get("type") == "file")
            dir_count = sum(1 for e in entries if e.get("type") == "dir")
            return {
                "name": dir_path.name,
                "type": "dir",
                "entries": entries,
                "file_count": file_count,
                "dir_count": dir_count,
            }

        tree = _index_dir(path, 0)
        total_files = self._count_files(tree)
        total_dirs = self._count_dirs(tree)
        return {
            "path": str(path),
            "tree": tree,
            "total_files": total_files,
            "total_dirs": total_dirs,
        }

    @staticmethod
    def _load_gitignore(root: Path) -> list[str]:
        """Load .gitignore patterns from ``root``."""
        gitignore = root / ".gitignore"
        if not gitignore.exists():
            return []
        try:
            lines = gitignore.read_text().splitlines()
            return [
                line.strip()
                for line in lines
                if line.strip() and not line.startswith("#")
            ]
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _is_ignored(rel_path: Path, patterns: list[str]) -> bool:
        """Check if ``rel_path`` matches any gitignore pattern."""
        if not patterns:
            return False
        name = rel_path.name
        parts = rel_path.parts
        for pattern in patterns:
            if pattern == name:
                return True
            if pattern in parts:
                return True
            if pattern.endswith("/*") and len(parts) > 0:
                if pattern[:-2] in parts:
                    return True
            if pattern.startswith("*"):
                suffix = pattern[1:]
                if name.endswith(suffix):
                    return True
        return False

    @staticmethod
    def _count_files(node: dict[str, Any]) -> int:
        """Count files in an index tree."""
        count = node.get("file_count", 0)
        for entry in node.get("entries", []):
            if entry.get("type") == "dir":
                count += FilesystemConnector._count_files(entry)
        return count

    @staticmethod
    def _count_dirs(node: dict[str, Any]) -> int:
        """Count directories in an index tree."""
        count = node.get("dir_count", 0)
        for entry in node.get("entries", []):
            if entry.get("type") == "dir":
                count += 1 + FilesystemConnector._count_dirs(entry)
        return count

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def _push_undo(self, entry: dict[str, Any]) -> None:
        """Push an undo entry onto the stack."""
        self._undo_stack.append(entry)
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack = self._undo_stack[-self._max_undo :]

    def _undo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Undo the last write/delete operation."""
        if not self._undo_stack:
            return {"undone": False, "reason": "undo stack is empty"}
        entry = self._undo_stack.pop()
        op = entry.get("op", "")
        path_str = entry.get("path", "")
        if not path_str:
            return {"undone": False, "reason": "no path in undo entry"}
        path = Path(path_str)
        try:
            if op == "write":
                old_content = entry.get("old_content", "")
                if old_content:
                    path.write_text(old_content, encoding=self.encoding)
                    return {"undone": True, "op": "write", "path": str(path)}
                elif path.exists():
                    path.unlink()
                    return {
                        "undone": True,
                        "op": "write",
                        "path": str(path),
                        "deleted": True,
                    }
                return {"undone": False, "reason": "nothing to undo"}
            if op == "delete":
                content = entry.get("content", "")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding=self.encoding)
                return {"undone": True, "op": "delete", "path": str(path)}
        except Exception as exc:  # noqa: BLE001
            return {"undone": False, "reason": str(exc)}
        return {"undone": False, "reason": f"unknown op: {op}"}

    def undo_stack_size(self) -> int:
        """Return the number of undoable operations."""
        return len(self._undo_stack)

    # ------------------------------------------------------------------
    # Git-aware operations
    # ------------------------------------------------------------------

    def _git_aware_info(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return git-aware information about a file or directory.

        Checks whether the path is in a git repo, whether it's tracked,
        ignored, or modified.
        """
        path = self._resolve(params.get("path", "."))
        info: dict[str, Any] = {
            "path": str(path),
            "exists": path.exists(),
            "is_file": path.is_file() if path.exists() else False,
            "is_dir": path.is_dir() if path.exists() else False,
        }
        # Find the git root
        git_root = self._find_git_root(path)
        info["in_git_repo"] = git_root is not None
        if git_root:
            info["git_root"] = str(git_root)
            rel = path.relative_to(git_root) if path.is_absolute() else path
            # Check if ignored
            ignore_patterns = self._load_gitignore(git_root)
            info["git_ignored"] = self._is_ignored(rel, ignore_patterns)
            # Check git status
            try:
                import git  # type: ignore[import-not-found]

                repo = git.Repo(str(git_root))
                # Check if tracked
                tracked_files = set(
                    item[0] if isinstance(item, (list, tuple)) else str(item)
                    for item in repo.index.entries
                )
                rel_str = str(rel).replace("\\", "/")
                info["git_tracked"] = rel_str in tracked_files
                # Check if modified
                if path.is_file():
                    info["git_modified"] = rel_str in [
                        item.a_path for item in repo.index.diff(None)
                    ]
                else:
                    info["git_modified"] = False
                # Current branch
                info["git_branch"] = (
                    repo.active_branch.name if not repo.head.is_detached else "detached"
                )
            except Exception:  # noqa: BLE001
                info["git_tracked"] = False
                info["git_modified"] = False
                info["git_branch"] = ""
        return info

    @staticmethod
    def _find_git_root(path: Path) -> Path | None:
        """Walk up from ``path`` to find the nearest .git directory."""
        current = path.resolve()
        if current.is_file():
            current = current.parent
        while True:
            if (current / ".git").exists():
                return current
            if current.parent == current:
                return None
            current = current.parent


__all__ = ["FilesystemConnector"]
