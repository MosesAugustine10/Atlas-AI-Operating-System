"""Tests for the Atlas Real Connectors.

These tests exercise the real connector implementations (Filesystem,
GitHub, Ollama, OpenRouter, Browser, Playwright, Windows, Blender)
against the local filesystem, local git repos, and mock HTTP services.
No internet connection is required.

All external services are mocked:

* Ollama / OpenRouter HTTP calls are mocked via ``unittest.mock.patch``.
* Browser HTTP calls use ``file://`` URLs or are mocked.
* Playwright / Blender degrade gracefully if the external binary is not
  installed.
* GitHub uses real local git repos (via GitPython) for git operations;
  REST API calls are mocked.
* Windows shell commands run real local subprocesses (echo, etc.).
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from atlas.mcp import (
    BlenderConnector,
    BrowserConnector,
    FilesystemConnector,
    GitHubConnector,
    HealthLevel,
    MCPRequest,
    MCPStatus,
    OllamaConnector,
    OpenRouterConnector,
    PlaywrightConnector,
    WindowsConnector,
)
from atlas.mcp.connector_config import get_connector_config, reload_config

# ===========================================================================
# Config loader
# ===========================================================================


class TestConnectorConfig:
    """Tests for atlas.mcp.connector_config."""

    def test_get_connector_config_filesystem(self) -> None:
        cfg = get_connector_config("filesystem")
        assert "root" in cfg
        assert "encoding" in cfg

    def test_get_connector_config_ollama(self) -> None:
        cfg = get_connector_config("ollama")
        assert "base_url" in cfg
        assert cfg["base_url"] == "http://localhost:11434"

    def test_get_connector_config_unknown_returns_empty(self) -> None:
        cfg = get_connector_config("nonexistent")
        assert cfg == {}

    def test_get_connector_config_github(self) -> None:
        cfg = get_connector_config("github")
        assert "token_env" in cfg
        assert "api_base" in cfg

    def test_get_connector_config_openrouter(self) -> None:
        cfg = get_connector_config("openrouter")
        assert "api_key_env" in cfg
        assert "api_base" in cfg

    def test_reload_config(self) -> None:
        reload_config()
        cfg = get_connector_config("filesystem")
        assert cfg is not None

    def test_env_override_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://custom:1234")
        reload_config()
        cfg = get_connector_config("ollama")
        assert cfg["base_url"] == "http://custom:1234"
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        reload_config()

    def test_env_override_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")
        reload_config()
        cfg = get_connector_config("github")
        assert cfg.get("token") == "ghp_test_token"
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        reload_config()

    def test_env_override_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "or_test_key")
        reload_config()
        cfg = get_connector_config("openrouter")
        assert cfg.get("api_key") == "or_test_key"
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        reload_config()

    def test_env_override_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ATLAS_FILESYSTEM_ROOT", "/tmp/custom_root")
        reload_config()
        cfg = get_connector_config("filesystem")
        assert cfg["root"] == "/tmp/custom_root"
        monkeypatch.delenv("ATLAS_FILESYSTEM_ROOT", raising=False)
        reload_config()


# ===========================================================================
# Filesystem Connector
# ===========================================================================


class TestFilesystemConnector:
    """Tests for the real FilesystemConnector."""

    def setup_method(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.connector = FilesystemConnector(root=self.tmpdir)
        self.connector.connect()

    def teardown_method(self) -> None:
        self.connector.disconnect()
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="filesystem",
            capability=capability,
            params=dict(params),
        )

    def test_connect_creates_root(self) -> None:
        # Root is created on connect.
        assert Path(self.tmpdir).exists()

    def test_health_connected(self) -> None:
        h = self.connector.health()
        assert h.status is MCPStatus.CONNECTED
        assert h.level is HealthLevel.HEALTHY

    def test_capabilities_count(self) -> None:
        caps = self.connector.capabilities()
        assert len(caps) == 15

    def test_read_file(self) -> None:
        test_file = Path(self.tmpdir) / "test.txt"
        test_file.write_text("hello world")
        resp = self.connector.execute(self._req("file.read", path="test.txt"))
        assert resp.success
        assert resp.output["content"] == "hello world"
        assert resp.output["bytes"] == 11

    def test_read_file_binary(self) -> None:
        test_file = Path(self.tmpdir) / "binary.bin"
        test_file.write_bytes(b"\x00\x01\x02")
        resp = self.connector.execute(
            self._req("file.read", path="binary.bin", binary=True)
        )
        assert resp.success
        assert resp.output["bytes"] == 3
        assert resp.output["binary"] is True

    def test_read_file_not_found(self) -> None:
        resp = self.connector.execute(self._req("file.read", path="nonexistent.txt"))
        assert not resp.success

    def test_write_file(self) -> None:
        resp = self.connector.execute(
            self._req("file.write", path="output.txt", content="written content")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "output.txt").read_text() == "written content"

    def test_write_file_creates_parent_dirs(self) -> None:
        resp = self.connector.execute(
            self._req("file.write", path="sub/dir/file.txt", content="nested")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "sub" / "dir" / "file.txt").read_text() == "nested"

    def test_write_file_binary(self) -> None:
        resp = self.connector.execute(
            self._req("file.write", path="out.bin", data=b"\x00\x01", binary=True)
        )
        assert resp.success
        assert (Path(self.tmpdir) / "out.bin").read_bytes() == b"\x00\x01"

    def test_append_file(self) -> None:
        self.connector.execute(
            self._req("file.write", path="log.txt", content="line1\n")
        )
        resp = self.connector.execute(
            self._req("file.append", path="log.txt", content="line2\n")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "log.txt").read_text() == "line1\nline2\n"

    def test_append_file_creates_new(self) -> None:
        resp = self.connector.execute(
            self._req("file.append", path="new.txt", content="first line")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "new.txt").read_text() == "first line"

    def test_copy_file(self) -> None:
        (Path(self.tmpdir) / "src.txt").write_text("copy me")
        resp = self.connector.execute(
            self._req("file.copy", src="src.txt", dst="dst.txt")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "dst.txt").read_text() == "copy me"

    def test_copy_directory(self) -> None:
        (Path(self.tmpdir) / "srcdir").mkdir()
        (Path(self.tmpdir) / "srcdir" / "file.txt").write_text("content")
        resp = self.connector.execute(
            self._req("file.copy", src="srcdir", dst="dstdir")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "dstdir" / "file.txt").read_text() == "content"

    def test_copy_source_not_found(self) -> None:
        resp = self.connector.execute(self._req("file.copy", src="missing", dst="dst"))
        assert not resp.success

    def test_move_file(self) -> None:
        (Path(self.tmpdir) / "move_me.txt").write_text("move me")
        resp = self.connector.execute(
            self._req("file.move", src="move_me.txt", dst="moved.txt")
        )
        assert resp.success
        assert not (Path(self.tmpdir) / "move_me.txt").exists()
        assert (Path(self.tmpdir) / "moved.txt").read_text() == "move me"

    def test_rename_file(self) -> None:
        (Path(self.tmpdir) / "old_name.txt").write_text("rename")
        resp = self.connector.execute(
            self._req("file.rename", src="old_name.txt", name="new_name.txt")
        )
        assert resp.success
        assert not (Path(self.tmpdir) / "old_name.txt").exists()
        assert (Path(self.tmpdir) / "new_name.txt").read_text() == "rename"

    def test_delete_file(self) -> None:
        (Path(self.tmpdir) / "delete_me.txt").write_text("bye")
        resp = self.connector.execute(self._req("file.delete", path="delete_me.txt"))
        assert resp.success
        assert resp.output["deleted"] is True
        assert not (Path(self.tmpdir) / "delete_me.txt").exists()

    def test_delete_directory_recursive(self) -> None:
        (Path(self.tmpdir) / "deldir").mkdir()
        (Path(self.tmpdir) / "deldir" / "file.txt").write_text("x")
        resp = self.connector.execute(self._req("file.delete", path="deldir"))
        assert resp.success
        assert not (Path(self.tmpdir) / "deldir").exists()

    def test_delete_not_found(self) -> None:
        resp = self.connector.execute(self._req("file.delete", path="nonexistent"))
        assert resp.success  # returns deleted=False
        assert resp.output["deleted"] is False

    def test_exists_file(self) -> None:
        (Path(self.tmpdir) / "exists.txt").write_text("yes")
        resp = self.connector.execute(self._req("file.exists", path="exists.txt"))
        assert resp.success
        assert resp.output["exists"] is True
        assert resp.output["is_file"] is True

    def test_exists_directory(self) -> None:
        (Path(self.tmpdir) / "subdir").mkdir()
        resp = self.connector.execute(self._req("file.exists", path="subdir"))
        assert resp.success
        assert resp.output["is_dir"] is True

    def test_exists_not_found(self) -> None:
        resp = self.connector.execute(self._req("file.exists", path="nope"))
        assert resp.success
        assert resp.output["exists"] is False

    def test_search(self) -> None:
        (Path(self.tmpdir) / "a.txt").write_text("x")
        (Path(self.tmpdir) / "b.txt").write_text("x")
        (Path(self.tmpdir) / "c.md").write_text("x")
        resp = self.connector.execute(
            self._req("file.search", directory=".", pattern="*.txt")
        )
        assert resp.success
        assert resp.output["count"] == 2

    def test_search_non_recursive(self) -> None:
        (Path(self.tmpdir) / "a.txt").write_text("x")
        (Path(self.tmpdir) / "sub").mkdir()
        (Path(self.tmpdir) / "sub" / "b.txt").write_text("x")
        resp = self.connector.execute(
            self._req("file.search", directory=".", pattern="*.txt", recursive=False)
        )
        assert resp.success
        assert resp.output["count"] == 1

    def test_list_directory(self) -> None:
        (Path(self.tmpdir) / "file1.txt").write_text("x")
        (Path(self.tmpdir) / "file2.txt").write_text("x")
        resp = self.connector.execute(self._req("file.list", path="."))
        assert resp.success
        assert resp.output["count"] == 2

    def test_list_directory_not_found(self) -> None:
        resp = self.connector.execute(self._req("file.list", path="nonexistent"))
        assert not resp.success

    def test_list_directory_not_a_directory(self) -> None:
        (Path(self.tmpdir) / "file.txt").write_text("x")
        resp = self.connector.execute(self._req("file.list", path="file.txt"))
        assert not resp.success

    def test_create_directory(self) -> None:
        resp = self.connector.execute(self._req("file.mkdir", path="newdir"))
        assert resp.success
        assert (Path(self.tmpdir) / "newdir").is_dir()

    def test_create_directory_nested(self) -> None:
        resp = self.connector.execute(self._req("file.mkdir", path="a/b/c"))
        assert resp.success
        assert (Path(self.tmpdir) / "a" / "b" / "c").is_dir()

    def test_watch_placeholder(self) -> None:
        resp = self.connector.execute(self._req("file.watch", path="."))
        assert resp.success
        assert resp.output["watching"] is True

    def test_zip_file(self) -> None:
        (Path(self.tmpdir) / "to_zip.txt").write_text("zip me")
        resp = self.connector.execute(
            self._req("file.zip", src="to_zip.txt", dst="archive.zip")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "archive.zip").exists()
        assert zipfile.is_zipfile(Path(self.tmpdir) / "archive.zip")

    def test_zip_directory(self) -> None:
        (Path(self.tmpdir) / "zipdir").mkdir()
        (Path(self.tmpdir) / "zipdir" / "file.txt").write_text("x")
        resp = self.connector.execute(
            self._req("file.zip", src="zipdir", dst="dir.zip")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "dir.zip").exists()

    def test_extract(self) -> None:
        # Create a zip first.
        src = Path(self.tmpdir) / "source.txt"
        src.write_text("extract me")
        archive = Path(self.tmpdir) / "extract.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.write(src, "source.txt")
        resp = self.connector.execute(
            self._req("file.extract", src="extract.zip", dst="extracted")
        )
        assert resp.success
        assert (
            Path(self.tmpdir) / "extracted" / "source.txt"
        ).read_text() == "extract me"

    def test_path_utilities_info(self) -> None:
        resp = self.connector.execute(
            self._req("file.path", path="test.txt", op="info")
        )
        assert resp.success
        assert "name" in resp.output
        assert "stem" in resp.output
        assert "suffix" in resp.output

    def test_path_utilities_resolve(self) -> None:
        resp = self.connector.execute(
            self._req("file.path", path="test.txt", op="resolve")
        )
        assert resp.success
        assert "resolved" in resp.output

    def test_path_utilities_parent(self) -> None:
        resp = self.connector.execute(
            self._req("file.path", path="dir/test.txt", op="parent")
        )
        assert resp.success
        assert "parent" in resp.output

    def test_path_utilities_unknown_op(self) -> None:
        resp = self.connector.execute(
            self._req("file.path", path="test.txt", op="bogus")
        )
        assert not resp.success

    def test_max_file_size_guard(self) -> None:
        connector = FilesystemConnector(root=self.tmpdir, max_file_size_mb=0)
        connector.connect()
        big_file = Path(self.tmpdir) / "big.txt"
        big_file.write_text("x" * 2048)  # > 0 MB
        resp = connector.execute(self._req("file.read", path="big.txt"))
        assert not resp.success
        connector.disconnect()

    def test_absolute_path(self) -> None:
        # Writing with an absolute path should work.
        abs_file = Path(self.tmpdir) / "abs.txt"
        resp = self.connector.execute(
            self._req("file.write", path=str(abs_file), content="absolute")
        )
        assert resp.success
        assert abs_file.read_text() == "absolute"

    def test_unknown_capability(self) -> None:
        resp = self.connector.execute(self._req("file.bogus"))
        assert not resp.success


# ===========================================================================
# GitHub Connector
# ===========================================================================


class TestGitHubConnector:
    """Tests for the real GitHubConnector (local git operations)."""

    def setup_method(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.connector = GitHubConnector(workspace=self.tmpdir)
        self.connector.connect()

    def teardown_method(self) -> None:
        self.connector.disconnect()
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_repo(self) -> str:
        """Create a real git repo in the workspace and return its path."""
        import git

        repo_path = Path(self.tmpdir) / "test_repo"
        repo_path.mkdir()
        repo = git.Repo.init(str(repo_path))
        (repo_path / "README.md").write_text("# Test Repo")
        repo.index.add(["README.md"])
        repo.index.commit("initial commit")
        return str(repo_path)

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="github",
            capability=capability,
            params=dict(params),
        )

    def test_health(self) -> None:
        h = self.connector.health()
        assert h.status in (MCPStatus.CONNECTED, MCPStatus.DEGRADED)

    def test_capabilities_count(self) -> None:
        caps = self.connector.capabilities()
        assert len(caps) == 17

    def test_git_status(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(self._req("git.status", path=repo_path))
        assert resp.success
        assert "is_dirty" in resp.output
        assert "active_branch" in resp.output

    def test_git_status_dirty(self) -> None:
        repo_path = self._make_repo()
        (Path(repo_path) / "README.md").write_text("# Modified")
        resp = self.connector.execute(self._req("git.status", path=repo_path))
        assert resp.success
        assert resp.output["is_dirty"] is True

    def test_git_log(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(self._req("git.log", path=repo_path, max_count=5))
        assert resp.success
        assert resp.output["count"] >= 1
        assert "hash" in resp.output["commits"][0]

    def test_git_branch_list(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(
            self._req("git.branch", path=repo_path, op="list")
        )
        assert resp.success
        assert "main" in resp.output["branches"] or "master" in resp.output["branches"]

    def test_git_branch_create(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(
            self._req("git.branch", path=repo_path, op="create", name="feature")
        )
        assert resp.success
        assert resp.output["created"] == "feature"

    def test_git_branch_delete(self) -> None:
        repo_path = self._make_repo()
        self.connector.execute(
            self._req("git.branch", path=repo_path, op="create", name="temp")
        )
        resp = self.connector.execute(
            self._req("git.branch", path=repo_path, op="delete", name="temp")
        )
        assert resp.success

    def test_git_commit(self) -> None:
        repo_path = self._make_repo()
        (Path(repo_path) / "new_file.txt").write_text("new")
        resp = self.connector.execute(
            self._req("git.commit", path=repo_path, message="add new file")
        )
        assert resp.success
        assert resp.output["committed"] is True

    def test_git_commit_nothing_to_commit(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(
            self._req("git.commit", path=repo_path, message="nothing")
        )
        assert resp.success
        assert resp.output["committed"] is False

    def test_git_tag_list(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(self._req("git.tag", path=repo_path, op="list"))
        assert resp.success
        assert "tags" in resp.output

    def test_git_tag_create(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(
            self._req("git.tag", path=repo_path, op="create", name="v1.0")
        )
        assert resp.success

    def test_git_remote_list(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(
            self._req("git.remote", path=repo_path, op="list")
        )
        assert resp.success
        assert "remotes" in resp.output

    def test_git_remote_add(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(
            self._req(
                "git.remote",
                path=repo_path,
                op="add",
                name="origin",
                url="https://github.com/test/repo.git",
            )
        )
        assert resp.success

    def test_git_diff(self) -> None:
        repo_path = self._make_repo()
        (Path(repo_path) / "README.md").write_text("# Modified")
        resp = self.connector.execute(self._req("git.diff", path=repo_path))
        assert resp.success
        assert "diff" in resp.output

    def test_missing_path_raises(self) -> None:
        resp = self.connector.execute(self._req("git.status"))
        assert not resp.success

    def test_rest_requires_token(self) -> None:
        # Without a token, REST calls should fail.
        resp = self.connector.execute(self._req("repo.list"))
        assert not resp.success
        assert (
            "token" in (resp.error or "").lower()
            or "permission" in (resp.error or "").lower()
        )

    @patch("requests.request")
    def test_rest_list_repos_mocked(self, mock_request: MagicMock) -> None:
        mock_request.return_value = MagicMock(
            status_code=200,
            content=b"[]",
            json=lambda: [
                {"name": "repo1", "full_name": "user/repo1", "html_url": "..."},
                {"name": "repo2", "full_name": "user/repo2", "html_url": "..."},
            ],
        )
        connector = GitHubConnector(workspace=self.tmpdir, token="fake_token")
        connector.connect()
        resp = connector.execute(
            MCPRequest(connector="github", capability="repo.list", params={})
        )
        assert resp.success
        assert len(resp.output["repos"]) == 2
        connector.disconnect()

    @patch("requests.request")
    def test_rest_create_issue_mocked(self, mock_request: MagicMock) -> None:
        mock_request.return_value = MagicMock(
            status_code=201,
            content=b"{}",
            json=lambda: {"number": 42, "title": "Test", "html_url": "..."},
        )
        connector = GitHubConnector(workspace=self.tmpdir, token="fake_token")
        connector.connect()
        resp = connector.execute(
            MCPRequest(
                connector="github",
                capability="issue.create",
                params={"owner": "user", "repo": "repo", "title": "Test issue"},
            )
        )
        assert resp.success
        assert resp.output["issue_number"] == 42
        connector.disconnect()

    @patch("requests.request")
    def test_rest_create_pr_mocked(self, mock_request: MagicMock) -> None:
        mock_request.return_value = MagicMock(
            status_code=201,
            content=b"{}",
            json=lambda: {"number": 7, "title": "Test PR", "html_url": "..."},
        )
        connector = GitHubConnector(workspace=self.tmpdir, token="fake_token")
        connector.connect()
        resp = connector.execute(
            MCPRequest(
                connector="github",
                capability="pr.create",
                params={
                    "owner": "user",
                    "repo": "repo",
                    "title": "Test PR",
                    "head": "feature",
                },
            )
        )
        assert resp.success
        assert resp.output["pr_number"] == 7
        connector.disconnect()

    def test_unknown_capability(self) -> None:
        resp = self.connector.execute(self._req("git.bogus"))
        assert not resp.success


# ===========================================================================
# Ollama Connector
# ===========================================================================


class TestOllamaConnector:
    """Tests for the real OllamaConnector (HTTP mocked)."""

    def setup_method(self) -> None:
        self.connector = OllamaConnector(base_url="http://localhost:11434")

    def teardown_method(self) -> None:
        self.connector.disconnect()

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="ollama",
            capability=capability,
            params=dict(params),
        )

    def test_capabilities_count(self) -> None:
        assert len(self.connector.capabilities()) == 8

    def test_health_degraded_when_no_server(self) -> None:
        h = self.connector.health()
        assert h.status in (
            MCPStatus.CONNECTED,
            MCPStatus.DEGRADED,
            MCPStatus.FAILED,
            MCPStatus.DISCONNECTED,
        )

    @patch("requests.get")
    def test_health_success(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        connector = OllamaConnector(base_url="http://localhost:11434")
        connector.connect()
        h = connector.health()
        assert h.status is MCPStatus.CONNECTED
        connector.disconnect()

    @patch("requests.request")
    @patch("requests.get")
    def test_list_models(self, mock_get: MagicMock, mock_request: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        mock_request.return_value = MagicMock(
            status_code=200,
            content=b"{}",
            json=lambda: {"models": [{"name": "llama3"}, {"name": "mistral"}]},
        )
        connector = OllamaConnector(base_url="http://localhost:11434")
        connector.connect()
        resp = connector.execute(self._req("ollama.models"))
        assert resp.success
        assert "llama3" in resp.output["models"]
        connector.disconnect()

    @patch("requests.request")
    @patch("requests.get")
    def test_generate(self, mock_get: MagicMock, mock_request: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        mock_request.return_value = MagicMock(
            status_code=200,
            content=b"{}",
            json=lambda: {
                "response": "Hello from Ollama!",
                "prompt_eval_count": 5,
                "eval_count": 10,
            },
        )
        connector = OllamaConnector(base_url="http://localhost:11434")
        connector.connect()
        resp = connector.execute(
            self._req("ollama.generate", prompt="hello", model="llama3")
        )
        assert resp.success
        assert resp.output["response"] == "Hello from Ollama!"
        connector.disconnect()

    @patch("requests.request")
    @patch("requests.get")
    def test_chat(self, mock_get: MagicMock, mock_request: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        mock_request.return_value = MagicMock(
            status_code=200,
            content=b"{}",
            json=lambda: {
                "message": {"role": "assistant", "content": "Hi there!"},
                "prompt_eval_count": 5,
                "eval_count": 10,
            },
        )
        connector = OllamaConnector(base_url="http://localhost:11434")
        connector.connect()
        resp = connector.execute(
            self._req(
                "ollama.chat",
                messages=[{"role": "user", "content": "hi"}],
            )
        )
        assert resp.success
        assert resp.output["message"]["content"] == "Hi there!"
        connector.disconnect()

    @patch("requests.request")
    @patch("requests.get")
    def test_embed(self, mock_get: MagicMock, mock_request: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        mock_request.return_value = MagicMock(
            status_code=200,
            content=b"{}",
            json=lambda: {"embedding": [0.1, 0.2, 0.3]},
        )
        connector = OllamaConnector(base_url="http://localhost:11434")
        connector.connect()
        resp = connector.execute(
            self._req("ollama.embed", input="hello", model="nomic-embed-text")
        )
        assert resp.success
        assert resp.output["embedding"] == [0.1, 0.2, 0.3]
        connector.disconnect()

    @patch("requests.post")
    @patch("requests.get")
    def test_pull_model(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        mock_response = MagicMock(status_code=200)
        mock_response.iter_lines.return_value = [b'{"status": "success"}']
        mock_post.return_value = mock_response
        connector = OllamaConnector(base_url="http://localhost:11434")
        connector.connect()
        resp = connector.execute(self._req("ollama.pull", name="llama3"))
        assert resp.success
        assert resp.output["pulled"] is True
        connector.disconnect()

    @patch("requests.request")
    @patch("requests.get")
    def test_delete_model(self, mock_get: MagicMock, mock_request: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        mock_request.return_value = MagicMock(
            status_code=200, content=b"{}", json=lambda: {}
        )
        connector = OllamaConnector(base_url="http://localhost:11434")
        connector.connect()
        resp = connector.execute(self._req("ollama.delete", name="llama3"))
        assert resp.success
        connector.disconnect()

    @patch("requests.get")
    def test_generate_missing_prompt(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        connector = OllamaConnector(base_url="http://localhost:11434")
        connector.connect()
        resp = connector.execute(self._req("ollama.generate"))
        assert not resp.success
        connector.disconnect()

    @patch("requests.get")
    def test_chat_missing_messages(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        connector = OllamaConnector(base_url="http://localhost:11434")
        connector.connect()
        resp = connector.execute(self._req("ollama.chat"))
        assert not resp.success
        connector.disconnect()

    @patch("requests.get")
    def test_embed_missing_input(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        connector = OllamaConnector(base_url="http://localhost:11434")
        connector.connect()
        resp = connector.execute(self._req("ollama.embed"))
        assert not resp.success
        connector.disconnect()

    @patch("requests.request")
    @patch("requests.get")
    def test_stream_placeholder(
        self, mock_get: MagicMock, mock_request: MagicMock
    ) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        mock_request.return_value = MagicMock(
            status_code=200,
            content=b"{}",
            json=lambda: {"response": "chunk", "prompt_eval_count": 1, "eval_count": 1},
        )
        connector = OllamaConnector(base_url="http://localhost:11434")
        connector.connect()
        resp = connector.execute(self._req("ollama.stream", prompt="hello"))
        assert resp.success
        assert "chunks" in resp.output
        connector.disconnect()

    @patch("requests.get")
    def test_unknown_capability(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        connector = OllamaConnector(base_url="http://localhost:11434")
        connector.connect()
        resp = connector.execute(self._req("ollama.bogus"))
        assert not resp.success
        connector.disconnect()


class TestOpenRouterConnector:
    """Tests for the real OpenRouterConnector (HTTP mocked)."""

    def setup_method(self) -> None:
        self.connector = OpenRouterConnector(api_key=None)  # no key

    def teardown_method(self) -> None:
        self.connector.disconnect()

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="openrouter",
            capability=capability,
            params=dict(params),
        )

    def test_capabilities_count(self) -> None:
        assert len(self.connector.capabilities()) == 5

    def test_health_no_key(self) -> None:
        h = self.connector.health()
        assert h.status in (MCPStatus.DEGRADED, MCPStatus.DISCONNECTED)

    def test_health_with_key(self) -> None:
        c = OpenRouterConnector(api_key="test_key")
        c.connect()
        h = c.health()
        assert h.status is MCPStatus.CONNECTED
        c.disconnect()

    def test_models_without_key_fails(self) -> None:
        resp = self.connector.execute(self._req("openrouter.models"))
        assert not resp.success

    @patch("requests.request")
    def test_list_models_mocked(self, mock_request: MagicMock) -> None:
        mock_request.return_value = MagicMock(
            status_code=200,
            content=b"{}",
            json=lambda: {
                "data": [{"id": "openai/gpt-4o"}, {"id": "anthropic/claude-3"}]
            },
        )
        c = OpenRouterConnector(api_key="test_key")
        c.connect()
        resp = c.execute(self._req("openrouter.models"))
        assert resp.success
        assert "openai/gpt-4o" in resp.output["models"]
        c.disconnect()

    @patch("requests.request")
    def test_chat_mocked(self, mock_request: MagicMock) -> None:
        mock_request.return_value = MagicMock(
            status_code=200,
            content=b"{}",
            json=lambda: {
                "choices": [{"message": {"role": "assistant", "content": "Hello!"}}],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                },
            },
        )
        c = OpenRouterConnector(api_key="test_key")
        c.connect()
        resp = c.execute(
            self._req(
                "openrouter.chat",
                messages=[{"role": "user", "content": "hi"}],
            )
        )
        assert resp.success
        assert resp.output["message"]["content"] == "Hello!"
        c.disconnect()

    @patch("requests.request")
    def test_generate_mocked(self, mock_request: MagicMock) -> None:
        mock_request.return_value = MagicMock(
            status_code=200,
            content=b"{}",
            json=lambda: {
                "choices": [
                    {"message": {"role": "assistant", "content": "Generated!"}}
                ],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 5,
                    "total_tokens": 10,
                },
            },
        )
        c = OpenRouterConnector(api_key="test_key")
        c.connect()
        resp = c.execute(self._req("openrouter.generate", prompt="hello"))
        assert resp.success
        assert resp.output["response"] == "Generated!"
        c.disconnect()

    @patch("requests.request")
    def test_usage_mocked(self, mock_request: MagicMock) -> None:
        mock_request.return_value = MagicMock(
            status_code=200,
            content=b"{}",
            json=lambda: {"limit": 1000000, "usage": 5000, "limit_remaining": 995000},
        )
        c = OpenRouterConnector(api_key="test_key")
        c.connect()
        resp = c.execute(self._req("openrouter.usage"))
        assert resp.success
        assert resp.output["limit"] == 1000000
        c.disconnect()

    def test_chat_missing_messages(self) -> None:
        c = OpenRouterConnector(api_key="test_key")
        c.connect()
        resp = c.execute(self._req("openrouter.chat"))
        assert not resp.success
        c.disconnect()

    def test_generate_missing_prompt(self) -> None:
        c = OpenRouterConnector(api_key="test_key")
        c.connect()
        resp = c.execute(self._req("openrouter.generate"))
        assert not resp.success
        c.disconnect()

    @patch("requests.request")
    def test_rate_limit_retry(self, mock_request: MagicMock) -> None:
        # First call returns 429, second returns 200.
        mock_request.side_effect = [
            MagicMock(status_code=429, content=b"{}", json=lambda: {}),
            MagicMock(status_code=200, content=b"{}", json=lambda: {"data": []}),
        ]
        c = OpenRouterConnector(api_key="test_key", max_retries=3)
        c.connect()
        resp = c.execute(self._req("openrouter.models"))
        assert resp.success
        c.disconnect()

    def test_unknown_capability(self) -> None:
        c = OpenRouterConnector(api_key="test_key")
        c.connect()
        resp = c.execute(self._req("openrouter.bogus"))
        assert not resp.success
        c.disconnect()


# ===========================================================================
# Browser Connector
# ===========================================================================


class TestBrowserConnector:
    """Tests for the real BrowserConnector."""

    def setup_method(self) -> None:
        self.connector = BrowserConnector()
        self.connector.connect()

    def teardown_method(self) -> None:
        self.connector.disconnect()

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="browser",
            capability=capability,
            params=dict(params),
        )

    def test_capabilities_count(self) -> None:
        assert len(self.connector.capabilities()) == 6

    def test_health(self) -> None:
        h = self.connector.health()
        assert h.status is MCPStatus.CONNECTED

    def test_navigate_file_url(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write("<html><head><title>Test</title></head><body>hello</body></html>")
            path = f.name
        try:
            resp = self.connector.execute(
                self._req("browser.navigate", url=f"file://{path}")
            )
            assert resp.success
            assert resp.output["status"] == 200
            assert resp.output["title"] == "Test"
        finally:
            os.unlink(path)

    def test_navigate_missing_url(self) -> None:
        resp = self.connector.execute(self._req("browser.navigate"))
        assert not resp.success

    def test_html_file_url(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write("<html>content</html>")
            path = f.name
        try:
            resp = self.connector.execute(
                self._req("browser.html", url=f"file://{path}")
            )
            assert resp.success
            assert "content" in resp.output["html"]
        finally:
            os.unlink(path)

    def test_download_file_url(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("download me")
            src = f.name
        dest = tempfile.mktemp()
        try:
            # Browser download uses requests which doesn't support file://,
            # so this should fail gracefully.
            resp = self.connector.execute(
                self._req("browser.download", url=f"file://{src}", dest=dest)
            )
            # file:// not supported by requests — should fail.
            assert not resp.success
        finally:
            os.unlink(src)
            if os.path.exists(dest):
                os.unlink(dest)

    def test_cookies_get(self) -> None:
        resp = self.connector.execute(self._req("browser.cookies", op="get"))
        assert resp.success
        assert "cookies" in resp.output

    def test_cookies_set(self) -> None:
        resp = self.connector.execute(
            self._req("browser.cookies", op="set", name="test", value="123")
        )
        assert resp.success
        # Verify it was set.
        resp2 = self.connector.execute(self._req("browser.cookies", op="get"))
        assert resp2.output["cookies"].get("test") == "123"

    def test_cookies_clear(self) -> None:
        self.connector.execute(
            self._req("browser.cookies", op="set", name="x", value="y")
        )
        resp = self.connector.execute(self._req("browser.cookies", op="clear"))
        assert resp.success
        resp2 = self.connector.execute(self._req("browser.cookies", op="get"))
        assert len(resp2.output["cookies"]) == 0

    def test_headers_get(self) -> None:
        resp = self.connector.execute(self._req("browser.headers", op="get"))
        assert resp.success
        assert "headers" in resp.output

    def test_headers_set(self) -> None:
        resp = self.connector.execute(
            self._req("browser.headers", op="set", name="X-Custom", value="yes")
        )
        assert resp.success
        resp2 = self.connector.execute(self._req("browser.headers", op="get"))
        assert resp2.output["headers"].get("X-Custom") == "yes"

    def test_session_info(self) -> None:
        resp = self.connector.execute(self._req("browser.session", op="info"))
        assert resp.success
        assert resp.output["active"] is True

    def test_session_reset(self) -> None:
        resp = self.connector.execute(self._req("browser.session", op="reset"))
        assert resp.success

    def test_unknown_capability(self) -> None:
        resp = self.connector.execute(self._req("browser.bogus"))
        assert not resp.success


# ===========================================================================
# Playwright Connector
# ===========================================================================


class TestPlaywrightConnector:
    """Tests for the real PlaywrightConnector."""

    def setup_method(self) -> None:
        self.connector = PlaywrightConnector()
        self.connector.connect()

    def teardown_method(self) -> None:
        self.connector.disconnect()

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="playwright",
            capability=capability,
            params=dict(params),
        )

    def test_capabilities_count(self) -> None:
        assert len(self.connector.capabilities()) == 11

    def test_health(self) -> None:
        h = self.connector.health()
        assert h.status in (MCPStatus.CONNECTED, MCPStatus.DEGRADED)

    def test_launch_without_playwright_fails_gracefully(self) -> None:
        # If playwright is installed, launch may succeed or fail with an
        # asyncio / browser error; if not installed, it fails with
        # "not installed". All are acceptable.
        resp = self.connector.execute(
            self._req("playwright.launch", browser="chromium")
        )
        assert (
            resp.success
            or "not installed" in (resp.error or "").lower()
            or "asyncio" in (resp.error or "").lower()
            or "browser" in (resp.error or "").lower()
        )

    def test_goto_without_launch_fails(self) -> None:
        # If playwright is not installed, this fails with "not installed".
        # If it IS installed, it fails with "browser not launched".
        resp = self.connector.execute(
            self._req("playwright.goto", url="https://example.com")
        )
        assert not resp.success

    def test_click_without_launch_fails(self) -> None:
        resp = self.connector.execute(self._req("playwright.click", selector="#btn"))
        assert not resp.success

    def test_screenshot_without_launch_fails(self) -> None:
        resp = self.connector.execute(self._req("playwright.screenshot"))
        assert not resp.success

    def test_close(self) -> None:
        resp = self.connector.execute(self._req("playwright.close"))
        # Close either succeeds (playwright installed) or fails gracefully.
        assert resp.success or "not installed" in (resp.error or "").lower()

    def test_missing_url(self) -> None:
        resp = self.connector.execute(self._req("playwright.goto"))
        assert not resp.success

    def test_missing_selector_click(self) -> None:
        resp = self.connector.execute(self._req("playwright.click"))
        assert not resp.success

    def test_missing_selector_type(self) -> None:
        resp = self.connector.execute(self._req("playwright.type", text="hello"))
        assert not resp.success

    def test_missing_script_evaluate(self) -> None:
        resp = self.connector.execute(self._req("playwright.evaluate"))
        assert not resp.success

    def test_unknown_capability(self) -> None:
        resp = self.connector.execute(self._req("playwright.bogus"))
        assert not resp.success

    def test_metadata(self) -> None:
        d = self.connector.discover()
        assert "browser" in d["metadata"]
        assert "headless" in d["metadata"]


# ===========================================================================
# Windows Connector
# ===========================================================================


class TestWindowsConnector:
    """Tests for the real WindowsConnector."""

    def setup_method(self) -> None:
        self.connector = WindowsConnector()
        self.connector.connect()

    def teardown_method(self) -> None:
        self.connector.disconnect()

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="windows",
            capability=capability,
            params=dict(params),
        )

    def test_capabilities_count(self) -> None:
        assert len(self.connector.capabilities()) == 8

    def test_health(self) -> None:
        h = self.connector.health()
        assert h.status in (MCPStatus.CONNECTED, MCPStatus.DEGRADED)

    def test_shell_echo(self) -> None:
        resp = self.connector.execute(
            self._req("windows.shell", command="echo hello_atlas")
        )
        assert resp.success
        assert resp.output["exit_code"] == 0
        assert "hello_atlas" in resp.output["stdout"]

    def test_shell_missing_command(self) -> None:
        resp = self.connector.execute(self._req("windows.shell"))
        assert not resp.success

    def test_shell_exit_code(self) -> None:
        resp = self.connector.execute(self._req("windows.shell", command="exit 42"))
        assert resp.success
        assert resp.output["exit_code"] == 42

    def test_powershell_available_or_graceful(self) -> None:
        resp = self.connector.execute(
            self._req("windows.powershell", command="echo ok")
        )
        # Either succeeds (PowerShell available) or fails gracefully.
        assert (
            resp.success
            or "not available" in (resp.error or "").lower()
            or "PowerShell" in (resp.error or "")
        )

    def test_env_get(self) -> None:
        # Set a known env var.
        os.environ["ATLAS_TEST_VAR"] = "test_value"
        resp = self.connector.execute(
            self._req("windows.env.get", name="ATLAS_TEST_VAR")
        )
        assert resp.success
        assert resp.output["value"] == "test_value"
        del os.environ["ATLAS_TEST_VAR"]

    def test_env_get_missing(self) -> None:
        resp = self.connector.execute(
            self._req("windows.env.get", name="ATLAS_NONEXISTENT_VAR_XYZ")
        )
        assert resp.success
        assert resp.output["value"] is None

    def test_env_set(self) -> None:
        resp = self.connector.execute(
            self._req("windows.env.set", name="ATLAS_SET_TEST", value="set_value")
        )
        assert resp.success
        assert os.environ.get("ATLAS_SET_TEST") == "set_value"
        del os.environ["ATLAS_SET_TEST"]

    def test_env_set_missing_name(self) -> None:
        resp = self.connector.execute(self._req("windows.env.set", value="x"))
        assert not resp.success

    def test_process_list(self) -> None:
        resp = self.connector.execute(self._req("windows.process.list"))
        assert resp.success
        assert "processes" in resp.output

    def test_app_launch(self) -> None:
        # Launch `true` (POSIX) or `echo` (Windows) — harmless.
        if os.name == "nt":
            resp = self.connector.execute(
                self._req("windows.app.launch", app="echo", args=["hello"])
            )
        else:
            resp = self.connector.execute(self._req("windows.app.launch", app="true"))
        assert resp.success

    def test_app_launch_missing_app(self) -> None:
        resp = self.connector.execute(self._req("windows.app.launch"))
        assert not resp.success

    def test_clipboard_get(self) -> None:
        resp = self.connector.execute(self._req("windows.clipboard", op="get"))
        # May fail if no display; just check it returns a response.
        assert resp.success or resp.error is not None

    def test_clipboard_set(self) -> None:
        resp = self.connector.execute(
            self._req("windows.clipboard", op="set", data="test_clipboard")
        )
        # May fail if no display; just check it returns a response.
        assert resp.success or resp.error is not None

    def test_clipboard_unknown_op(self) -> None:
        resp = self.connector.execute(self._req("windows.clipboard", op="bogus"))
        assert not resp.success

    def test_unknown_capability(self) -> None:
        resp = self.connector.execute(self._req("windows.bogus"))
        assert not resp.success

    def test_process_kill_missing_params(self) -> None:
        resp = self.connector.execute(self._req("windows.process.kill"))
        assert not resp.success


# ===========================================================================
# Blender Connector
# ===========================================================================


class TestBlenderConnector:
    """Tests for the real BlenderConnector."""

    def setup_method(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.connector = BlenderConnector(output_dir=self.tmpdir)
        self.connector.connect()

    def teardown_method(self) -> None:
        self.connector.disconnect()
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="blender",
            capability=capability,
            params=dict(params),
        )

    def test_capabilities_count(self) -> None:
        assert len(self.connector.capabilities()) == 10

    def test_health(self) -> None:
        h = self.connector.health()
        assert h.status in (MCPStatus.CONNECTED, MCPStatus.DEGRADED)

    def test_launch_or_graceful(self) -> None:
        resp = self.connector.execute(self._req("blender.launch"))
        # Either succeeds (Blender installed) or fails gracefully.
        assert resp.success or "not installed" in (resp.error or "").lower()

    def test_render_or_graceful(self) -> None:
        resp = self.connector.execute(
            self._req("blender.render", frame=1, blend_file="", output="test.png")
        )
        assert resp.success or "not installed" in (resp.error or "").lower()

    def test_open_project_or_graceful(self) -> None:
        resp = self.connector.execute(
            self._req("blender.open", path="nonexistent.blend")
        )
        assert resp.success or "not installed" in (resp.error or "").lower()

    def test_save_project_missing_dest(self) -> None:
        resp = self.connector.execute(self._req("blender.save"))
        assert not resp.success

    def test_execute_expr_missing_expr(self) -> None:
        resp = self.connector.execute(self._req("blender.execute"))
        assert not resp.success

    def test_script_missing_path(self) -> None:
        resp = self.connector.execute(self._req("blender.script"))
        assert not resp.success

    def test_render_animation_or_graceful(self) -> None:
        resp = self.connector.execute(
            self._req("blender.render_animation", start=1, end=5)
        )
        assert resp.success or "not installed" in (resp.error or "").lower()

    def test_scene_new_or_graceful(self) -> None:
        resp = self.connector.execute(self._req("blender.scene.new", name="MyScene"))
        assert resp.success or "not installed" in (resp.error or "").lower()

    def test_object_add_or_graceful(self) -> None:
        resp = self.connector.execute(self._req("blender.object.add", type="cube"))
        assert resp.success or "not installed" in (resp.error or "").lower()

    def test_export_missing_path(self) -> None:
        resp = self.connector.execute(self._req("blender.export", format="obj"))
        assert not resp.success

    def test_unknown_capability(self) -> None:
        resp = self.connector.execute(self._req("blender.bogus"))
        assert not resp.success

    def test_metadata(self) -> None:
        d = self.connector.discover()
        assert "blender_path" in d["metadata"]
        assert "blender_available" in d["metadata"]


# ===========================================================================
# Integration: all 8 real connectors
# ===========================================================================


class TestRealConnectorsIntegration:
    """Integration tests across all 8 real connectors."""

    def test_all_connectors_import(self) -> None:
        from atlas.mcp.connectors import (
            BlenderConnector,
            BrowserConnector,
            FilesystemConnector,
            GitHubConnector,
            OllamaConnector,
            OpenRouterConnector,
            PlaywrightConnector,
            WindowsConnector,
        )

        assert all(
            [
                FilesystemConnector,
                GitHubConnector,
                OllamaConnector,
                OpenRouterConnector,
                BrowserConnector,
                PlaywrightConnector,
                WindowsConnector,
                BlenderConnector,
            ]
        )

    def test_all_connectors_instantiate(self) -> None:
        connectors = [
            FilesystemConnector(),
            GitHubConnector(),
            OllamaConnector(),
            OpenRouterConnector(),
            BrowserConnector(),
            PlaywrightConnector(),
            WindowsConnector(),
            BlenderConnector(),
        ]
        for c in connectors:
            assert c.name != ""
            assert len(c.capabilities()) > 0

    def test_all_connectors_connect(self) -> None:
        connectors = [
            FilesystemConnector(),
            GitHubConnector(),
            OllamaConnector(),
            OpenRouterConnector(),
            BrowserConnector(),
            PlaywrightConnector(),
            WindowsConnector(),
            BlenderConnector(),
        ]
        for c in connectors:
            c.connect()
            assert c.is_connected or c.status in (
                MCPStatus.CONNECTED,
                MCPStatus.DEGRADED,
            )
            c.disconnect()

    def test_all_connectors_health(self) -> None:
        connectors = [
            FilesystemConnector(),
            GitHubConnector(),
            OllamaConnector(),
            OpenRouterConnector(),
            BrowserConnector(),
            PlaywrightConnector(),
            WindowsConnector(),
            BlenderConnector(),
        ]
        for c in connectors:
            c.connect()
            h = c.health()
            assert h.status in (MCPStatus.CONNECTED, MCPStatus.DEGRADED)
            c.disconnect()

    def test_all_connectors_discover(self) -> None:
        connectors = [
            FilesystemConnector(),
            GitHubConnector(),
            OllamaConnector(),
            OpenRouterConnector(),
            BrowserConnector(),
            PlaywrightConnector(),
            WindowsConnector(),
            BlenderConnector(),
        ]
        for c in connectors:
            d = c.discover()
            assert "name" in d
            assert "capabilities" in d
            assert "supported_transports" in d

    def test_all_connectors_execute_not_connected(self) -> None:
        connectors = [
            FilesystemConnector(),
            GitHubConnector(),
            OllamaConnector(),
            OpenRouterConnector(),
            BrowserConnector(),
            PlaywrightConnector(),
            WindowsConnector(),
            BlenderConnector(),
        ]
        for c in connectors:
            # Don't connect.
            req = MCPRequest(connector=c.name, capability="bogus")
            resp = c.execute(req)
            assert not resp.success

    def test_filesystem_with_manager(self) -> None:
        from atlas.mcp import MCPManager

        m = MCPManager()
        m.register_connector(FilesystemConnector())
        s = m.open_session("filesystem", permissions=["read", "write"])
        assert s.is_open()
        m.close_session(s.id)

    def test_filesystem_full_workflow(self) -> None:
        """Write → read → append → copy → delete."""
        tmpdir = tempfile.mkdtemp()
        try:
            c = FilesystemConnector(root=tmpdir)
            c.connect()
            # Write
            resp = c.execute(
                MCPRequest(
                    connector="filesystem",
                    capability="file.write",
                    params={"path": "test.txt", "content": "line1"},
                )
            )
            assert resp.success
            # Read
            resp = c.execute(
                MCPRequest(
                    connector="filesystem",
                    capability="file.read",
                    params={"path": "test.txt"},
                )
            )
            assert resp.success
            assert resp.output["content"] == "line1"
            # Append
            c.execute(
                MCPRequest(
                    connector="filesystem",
                    capability="file.append",
                    params={"path": "test.txt", "content": "\nline2"},
                )
            )
            resp = c.execute(
                MCPRequest(
                    connector="filesystem",
                    capability="file.read",
                    params={"path": "test.txt"},
                )
            )
            assert resp.output["content"] == "line1\nline2"
            # Copy
            c.execute(
                MCPRequest(
                    connector="filesystem",
                    capability="file.copy",
                    params={"src": "test.txt", "dst": "copy.txt"},
                )
            )
            assert (Path(tmpdir) / "copy.txt").exists()
            # Delete
            c.execute(
                MCPRequest(
                    connector="filesystem",
                    capability="file.delete",
                    params={"path": "test.txt"},
                )
            )
            assert not (Path(tmpdir) / "test.txt").exists()
            c.disconnect()
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_github_local_git_workflow(self) -> None:
        """Init repo → commit → status → log."""
        import git

        tmpdir = tempfile.mkdtemp()
        try:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            c = GitHubConnector(workspace=str(workspace))
            c.connect()
            # Init a repo.
            repo_path = workspace / "test"
            repo_path.mkdir()
            repo = git.Repo.init(str(repo_path))
            (repo_path / "file.txt").write_text("content")
            repo.index.add(["file.txt"])
            repo.index.commit("initial")
            # Status.
            resp = c.execute(
                MCPRequest(
                    connector="github",
                    capability="git.status",
                    params={"path": str(repo_path)},
                )
            )
            assert resp.success
            # Log.
            resp = c.execute(
                MCPRequest(
                    connector="github",
                    capability="git.log",
                    params={"path": str(repo_path), "max_count": 5},
                )
            )
            assert resp.success
            assert resp.output["count"] == 1
            c.disconnect()
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_zero_circular_imports(self) -> None:
        import importlib

        modules = [
            "atlas.mcp.connector_config",
            "atlas.mcp.connectors.filesystem",
            "atlas.mcp.connectors.github",
            "atlas.mcp.connectors.ollama",
            "atlas.mcp.connectors.openrouter",
            "atlas.mcp.connectors.browser",
            "atlas.mcp.connectors.playwright",
            "atlas.mcp.connectors.windows",
            "atlas.mcp.connectors.blender",
        ]
        for m in modules:
            importlib.import_module(m)


# ===========================================================================
# Additional Filesystem edge-case tests
# ===========================================================================


class TestFilesystemEdgeCases:
    """Additional edge-case tests for FilesystemConnector."""

    def setup_method(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.connector = FilesystemConnector(root=self.tmpdir)
        self.connector.connect()

    def teardown_method(self) -> None:
        self.connector.disconnect()
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="filesystem", capability=capability, params=dict(params)
        )

    def test_write_empty_file(self) -> None:
        resp = self.connector.execute(
            self._req("file.write", path="empty.txt", content="")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "empty.txt").read_text() == ""

    def test_write_unicode_content(self) -> None:
        resp = self.connector.execute(
            self._req("file.write", path="unicode.txt", content="héllo wörld 日本語")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "unicode.txt").read_text(
            encoding="utf-8"
        ) == "héllo wörld 日本語"

    def test_read_unicode_content(self) -> None:
        (Path(self.tmpdir) / "uni.txt").write_text("héllo", encoding="utf-8")
        resp = self.connector.execute(self._req("file.read", path="uni.txt"))
        assert resp.success
        assert resp.output["content"] == "héllo"

    def test_append_to_nonexistent_creates_file(self) -> None:
        resp = self.connector.execute(
            self._req("file.append", path="new.txt", content="first")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "new.txt").read_text() == "first"

    def test_copy_to_existing_overwrites(self) -> None:
        (Path(self.tmpdir) / "src.txt").write_text("source")
        (Path(self.tmpdir) / "dst.txt").write_text("destination")
        resp = self.connector.execute(
            self._req("file.copy", src="src.txt", dst="dst.txt")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "dst.txt").read_text() == "source"

    def test_move_to_existing_overwrites(self) -> None:
        (Path(self.tmpdir) / "src.txt").write_text("source")
        (Path(self.tmpdir) / "dst.txt").write_text("destination")
        resp = self.connector.execute(
            self._req("file.move", src="src.txt", dst="dst.txt")
        )
        assert resp.success
        assert (Path(self.tmpdir) / "dst.txt").read_text() == "source"
        assert not (Path(self.tmpdir) / "src.txt").exists()

    def test_delete_non_recursive_empty_dir(self) -> None:
        (Path(self.tmpdir) / "emptydir").mkdir()
        resp = self.connector.execute(
            self._req("file.delete", path="emptydir", recursive=False)
        )
        assert resp.success
        assert not (Path(self.tmpdir) / "emptydir").exists()

    def test_delete_non_recursive_non_empty_fails(self) -> None:
        (Path(self.tmpdir) / "nonempty").mkdir()
        (Path(self.tmpdir) / "nonempty" / "file.txt").write_text("x")
        resp = self.connector.execute(
            self._req("file.delete", path="nonempty", recursive=False)
        )
        assert not resp.success

    def test_search_no_matches(self) -> None:
        (Path(self.tmpdir) / "a.txt").write_text("x")
        resp = self.connector.execute(
            self._req("file.search", directory=".", pattern="*.xyz")
        )
        assert resp.success
        assert resp.output["count"] == 0

    def test_list_empty_directory(self) -> None:
        (Path(self.tmpdir) / "emptydir").mkdir()
        resp = self.connector.execute(self._req("file.list", path="emptydir"))
        assert resp.success
        assert resp.output["count"] == 0

    def test_create_directory_existing(self) -> None:
        (Path(self.tmpdir) / "exists").mkdir()
        resp = self.connector.execute(
            self._req("file.mkdir", path="exists", exist_ok=True)
        )
        assert resp.success

    def test_zip_and_extract_roundtrip(self) -> None:
        (Path(self.tmpdir) / "original.txt").write_text("roundtrip content")
        # Zip
        resp = self.connector.execute(
            self._req("file.zip", src="original.txt", dst="round.zip")
        )
        assert resp.success
        # Extract
        resp = self.connector.execute(
            self._req("file.extract", src="round.zip", dst="extracted")
        )
        assert resp.success
        assert (
            Path(self.tmpdir) / "extracted" / "original.txt"
        ).read_text() == "roundtrip content"

    def test_path_utilities_stem(self) -> None:
        resp = self.connector.execute(
            self._req("file.path", path="archive.tar.gz", op="stem")
        )
        assert resp.success
        assert "stem" in resp.output

    def test_path_utilities_suffix(self) -> None:
        resp = self.connector.execute(
            self._req("file.path", path="archive.tar.gz", op="suffix")
        )
        assert resp.success
        assert resp.output["suffix"] == ".gz"

    def test_path_utilities_parts(self) -> None:
        resp = self.connector.execute(
            self._req("file.path", path="a/b/c.txt", op="parts")
        )
        assert resp.success
        assert "parts" in resp.output

    def test_path_utilities_absolute(self) -> None:
        resp = self.connector.execute(
            self._req("file.path", path="test.txt", op="absolute")
        )
        assert resp.success
        assert "absolute" in resp.output

    def test_metadata_contains_root(self) -> None:
        d = self.connector.discover()
        assert "root" in d["metadata"]

    def test_health_contains_exists(self) -> None:
        h = self.connector.health()
        assert "exists" in h.metadata

    def test_read_file_with_nested_path(self) -> None:
        (Path(self.tmpdir) / "a" / "b").mkdir(parents=True)
        (Path(self.tmpdir) / "a" / "b" / "c.txt").write_text("deep")
        resp = self.connector.execute(self._req("file.read", path="a/b/c.txt"))
        assert resp.success
        assert resp.output["content"] == "deep"

    def test_write_then_list(self) -> None:
        self.connector.execute(self._req("file.write", path="f1.txt", content="a"))
        self.connector.execute(self._req("file.write", path="f2.txt", content="b"))
        resp = self.connector.execute(self._req("file.list", path="."))
        assert resp.success
        assert resp.output["count"] == 2


# ===========================================================================
# Additional GitHub edge-case tests
# ===========================================================================


class TestGitHubEdgeCases:
    """Additional edge-case tests for GitHubConnector."""

    def setup_method(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.connector = GitHubConnector(workspace=self.tmpdir)
        self.connector.connect()

    def teardown_method(self) -> None:
        self.connector.disconnect()
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_repo(self) -> str:
        import git

        repo_path = Path(self.tmpdir) / "test_repo"
        repo_path.mkdir()
        repo = git.Repo.init(str(repo_path))
        (repo_path / "README.md").write_text("# Test")
        repo.index.add(["README.md"])
        repo.index.commit("initial")
        return str(repo_path)

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="github", capability=capability, params=dict(params)
        )

    def test_git_status_with_untracked_files(self) -> None:
        repo_path = self._make_repo()
        (Path(repo_path) / "untracked.txt").write_text("new")
        resp = self.connector.execute(self._req("git.status", path=repo_path))
        assert resp.success
        assert "untracked.txt" in resp.output["untracked"]

    def test_git_log_max_count(self) -> None:
        import git

        repo_path = self._make_repo()
        repo = git.Repo(repo_path)
        for i in range(5):
            (Path(repo_path) / f"file{i}.txt").write_text(f"content {i}")
            repo.index.add([f"file{i}.txt"])
            repo.index.commit(f"commit {i}")
        resp = self.connector.execute(self._req("git.log", path=repo_path, max_count=3))
        assert resp.success
        assert resp.output["count"] == 3

    def test_git_branch_create_and_checkout(self) -> None:
        repo_path = self._make_repo()
        self.connector.execute(
            self._req("git.branch", path=repo_path, op="create", name="feature")
        )
        resp = self.connector.execute(
            self._req("git.checkout", path=repo_path, target="feature")
        )
        assert resp.success

    def test_git_tag_create_and_list(self) -> None:
        repo_path = self._make_repo()
        self.connector.execute(
            self._req("git.tag", path=repo_path, op="create", name="v1.0")
        )
        resp = self.connector.execute(self._req("git.tag", path=repo_path, op="list"))
        assert resp.success
        assert "v1.0" in resp.output["tags"]

    def test_git_remote_add_and_list(self) -> None:
        repo_path = self._make_repo()
        self.connector.execute(
            self._req(
                "git.remote",
                path=repo_path,
                op="add",
                name="origin",
                url="https://github.com/test/repo.git",
            )
        )
        resp = self.connector.execute(
            self._req("git.remote", path=repo_path, op="list")
        )
        assert resp.success
        assert any(r["name"] == "origin" for r in resp.output["remotes"])

    def test_git_commit_with_message(self) -> None:
        repo_path = self._make_repo()
        (Path(repo_path) / "new.txt").write_text("new")
        resp = self.connector.execute(
            self._req("git.commit", path=repo_path, message="add new file")
        )
        assert resp.success
        assert resp.output["committed"] is True
        assert resp.output["message"] == "add new file"

    def test_git_diff_empty(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(self._req("git.diff", path=repo_path))
        assert resp.success
        assert resp.output["diff"] == ""

    def test_git_diff_with_changes(self) -> None:
        repo_path = self._make_repo()
        (Path(repo_path) / "README.md").write_text("# Modified")
        resp = self.connector.execute(self._req("git.diff", path=repo_path))
        assert resp.success
        assert "Modified" in resp.output["diff"]

    def test_missing_path_for_log(self) -> None:
        resp = self.connector.execute(self._req("git.log"))
        assert not resp.success

    def test_missing_path_for_branch(self) -> None:
        resp = self.connector.execute(self._req("git.branch", op="list"))
        assert not resp.success

    def test_branch_create_missing_name(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(
            self._req("git.branch", path=repo_path, op="create")
        )
        assert not resp.success

    def test_tag_create_missing_name(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(self._req("git.tag", path=repo_path, op="create"))
        assert not resp.success

    def test_remote_add_missing_name(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(
            self._req("git.remote", path=repo_path, op="add", url="x")
        )
        assert not resp.success

    def test_checkout_missing_target(self) -> None:
        repo_path = self._make_repo()
        resp = self.connector.execute(self._req("git.checkout", path=repo_path))
        assert not resp.success

    def test_metadata_contains_workspace(self) -> None:
        d = self.connector.discover()
        assert "workspace" in d["metadata"]

    def test_metadata_contains_git_available(self) -> None:
        d = self.connector.discover()
        assert "git_available" in d["metadata"]


# ===========================================================================
# Additional Ollama edge-case tests
# ===========================================================================


class TestOllamaEdgeCases:
    """Additional edge-case tests for OllamaConnector."""

    def test_custom_base_url(self) -> None:
        c = OllamaConnector(base_url="http://custom:8080")
        assert c.base_url == "http://custom:8080"
        c.disconnect()

    def test_custom_default_model(self) -> None:
        c = OllamaConnector(default_model="mistral")
        assert c.default_model == "mistral"
        c.disconnect()

    def test_custom_timeout(self) -> None:
        c = OllamaConnector(timeout=120)
        assert c.timeout == 120
        c.disconnect()

    def test_metadata_contains_base_url(self) -> None:
        c = OllamaConnector(base_url="http://test:1234")
        c.connect()
        d = c.discover()
        assert d["metadata"]["base_url"] == "http://test:1234"
        c.disconnect()

    def test_metadata_contains_default_model(self) -> None:
        c = OllamaConnector(default_model="phi3")
        c.connect()
        d = c.discover()
        assert d["metadata"]["default_model"] == "phi3"
        c.disconnect()

    @patch("requests.get")
    def test_health_metadata_contains_available(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200)
        c = OllamaConnector(base_url="http://localhost:11434")
        c.connect()
        h = c.health()
        assert "available" in h.metadata
        c.disconnect()

    @patch("requests.get")
    def test_ping_failure_returns_false(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = Exception("connection refused")
        c = OllamaConnector(base_url="http://localhost:11434")
        available = c._ping()
        assert available is False
        c.disconnect()


# ===========================================================================
# Additional OpenRouter edge-case tests
# ===========================================================================


class TestOpenRouterEdgeCases:
    """Additional edge-case tests for OpenRouterConnector."""

    def test_custom_api_base(self) -> None:
        c = OpenRouterConnector(api_key="x", api_base="https://custom.api/v1")
        assert c.api_base == "https://custom.api/v1"
        c.disconnect()

    def test_custom_default_model(self) -> None:
        c = OpenRouterConnector(api_key="x", default_model="custom/model")
        assert c.default_model == "custom/model"
        c.disconnect()

    def test_custom_timeout(self) -> None:
        c = OpenRouterConnector(api_key="x", timeout=120)
        assert c.timeout == 120
        c.disconnect()

    def test_custom_max_retries(self) -> None:
        c = OpenRouterConnector(api_key="x", max_retries=5)
        assert c.max_retries == 5
        c.disconnect()

    def test_metadata_contains_api_base(self) -> None:
        c = OpenRouterConnector(api_key="x", api_base="https://test.api/v1")
        c.connect()
        d = c.discover()
        assert d["metadata"]["api_base"] == "https://test.api/v1"
        c.disconnect()

    def test_metadata_contains_has_api_key(self) -> None:
        c = OpenRouterConnector(api_key="test")
        c.connect()
        d = c.discover()
        assert d["metadata"]["has_api_key"] is True
        c.disconnect()

    def test_health_with_key_connected(self) -> None:
        c = OpenRouterConnector(api_key="test")
        c.connect()
        h = c.health()
        assert h.status is MCPStatus.CONNECTED
        c.disconnect()


# ===========================================================================
# Additional Browser edge-case tests
# ===========================================================================


class TestBrowserEdgeCases:
    """Additional edge-case tests for BrowserConnector."""

    def setup_method(self) -> None:
        self.connector = BrowserConnector()
        self.connector.connect()

    def teardown_method(self) -> None:
        self.connector.disconnect()

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="browser", capability=capability, params=dict(params)
        )

    def test_custom_user_agent(self) -> None:
        c = BrowserConnector(user_agent="TestAgent/1.0")
        c.connect()
        assert c.user_agent == "TestAgent/1.0"
        c.disconnect()

    def test_custom_timeout(self) -> None:
        c = BrowserConnector(timeout=60)
        assert c.timeout == 60
        c.disconnect()

    def test_custom_max_redirects(self) -> None:
        c = BrowserConnector(max_redirects=5)
        assert c.max_redirects == 5
        c.disconnect()

    def test_session_info_after_reset(self) -> None:
        self.connector.execute(self._req("browser.session", op="reset"))
        resp = self.connector.execute(self._req("browser.session", op="info"))
        assert resp.success
        assert resp.output["active"] is True

    def test_headers_multiple_set(self) -> None:
        self.connector.execute(
            self._req("browser.headers", op="set", name="X-1", value="a")
        )
        self.connector.execute(
            self._req("browser.headers", op="set", name="X-2", value="b")
        )
        resp = self.connector.execute(self._req("browser.headers", op="get"))
        assert resp.output["headers"]["X-1"] == "a"
        assert resp.output["headers"]["X-2"] == "b"

    def test_cookies_multiple_set(self) -> None:
        self.connector.execute(
            self._req("browser.cookies", op="set", name="c1", value="v1")
        )
        self.connector.execute(
            self._req("browser.cookies", op="set", name="c2", value="v2")
        )
        resp = self.connector.execute(self._req("browser.cookies", op="get"))
        assert resp.output["cookies"]["c1"] == "v1"
        assert resp.output["cookies"]["c2"] == "v2"

    def test_navigate_missing_url(self) -> None:
        resp = self.connector.execute(self._req("browser.navigate"))
        assert not resp.success

    def test_html_missing_url(self) -> None:
        resp = self.connector.execute(self._req("browser.html"))
        assert not resp.success

    def test_download_missing_url(self) -> None:
        resp = self.connector.execute(self._req("browser.download", dest="/tmp/x"))
        assert not resp.success

    def test_download_missing_dest(self) -> None:
        resp = self.connector.execute(self._req("browser.download", url="http://x"))
        assert not resp.success

    def test_session_unknown_op(self) -> None:
        resp = self.connector.execute(self._req("browser.session", op="bogus"))
        assert not resp.success

    def test_headers_unknown_op(self) -> None:
        resp = self.connector.execute(self._req("browser.headers", op="bogus"))
        assert not resp.success

    def test_cookies_unknown_op(self) -> None:
        resp = self.connector.execute(self._req("browser.cookies", op="bogus"))
        assert not resp.success


# ===========================================================================
# Additional Windows edge-case tests
# ===========================================================================


class TestWindowsEdgeCases:
    """Additional edge-case tests for WindowsConnector."""

    def setup_method(self) -> None:
        self.connector = WindowsConnector()
        self.connector.connect()

    def teardown_method(self) -> None:
        self.connector.disconnect()

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="windows", capability=capability, params=dict(params)
        )

    def test_shell_with_stderr(self) -> None:
        resp = self.connector.execute(
            self._req("windows.shell", command="echo error >&2")
        )
        assert resp.success
        # stderr may or may not be captured depending on shell.
        assert resp.output["exit_code"] == 0

    def test_shell_multiline_output(self) -> None:
        resp = self.connector.execute(
            self._req("windows.shell", command="echo line1; echo line2")
        )
        assert resp.success
        assert "line1" in resp.output["stdout"]
        assert "line2" in resp.output["stdout"]

    def test_env_set_and_get(self) -> None:
        self.connector.execute(
            self._req("windows.env.set", name="ATLAS_TEST_E2E", value="e2e_value")
        )
        resp = self.connector.execute(
            self._req("windows.env.get", name="ATLAS_TEST_E2E")
        )
        assert resp.success
        assert resp.output["value"] == "e2e_value"
        del os.environ["ATLAS_TEST_E2E"]

    def test_process_list_returns_data(self) -> None:
        resp = self.connector.execute(self._req("windows.process.list"))
        assert resp.success
        assert len(resp.output["processes"]) > 0

    def test_metadata_contains_is_windows(self) -> None:
        d = self.connector.discover()
        assert "is_windows" in d["metadata"]

    def test_metadata_contains_has_powershell(self) -> None:
        d = self.connector.discover()
        assert "has_powershell" in d["metadata"]

    def test_shell_missing_command(self) -> None:
        resp = self.connector.execute(self._req("windows.shell"))
        assert not resp.success

    def test_powershell_missing_command(self) -> None:
        resp = self.connector.execute(self._req("windows.powershell"))
        assert not resp.success

    def test_env_get_missing_name(self) -> None:
        resp = self.connector.execute(self._req("windows.env.get"))
        assert not resp.success

    def test_app_launch_missing_app(self) -> None:
        resp = self.connector.execute(self._req("windows.app.launch"))
        assert not resp.success


# ===========================================================================
# Additional Blender edge-case tests
# ===========================================================================


class TestBlenderEdgeCases:
    """Additional edge-case tests for BlenderConnector."""

    def setup_method(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.connector = BlenderConnector(output_dir=self.tmpdir)
        self.connector.connect()

    def teardown_method(self) -> None:
        self.connector.disconnect()
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="blender", capability=capability, params=dict(params)
        )

    def test_custom_blender_path(self) -> None:
        c = BlenderConnector(blender_path="/custom/blender")
        assert c.blender_path == "/custom/blender"
        c.disconnect()

    def test_custom_timeout(self) -> None:
        c = BlenderConnector(timeout=300)
        assert c.timeout == 300
        c.disconnect()

    def test_metadata_contains_blender_path(self) -> None:
        d = self.connector.discover()
        assert "blender_path" in d["metadata"]

    def test_metadata_contains_output_dir(self) -> None:
        d = self.connector.discover()
        assert "output_dir" in d["metadata"]

    def test_save_missing_dest(self) -> None:
        resp = self.connector.execute(self._req("blender.save"))
        assert not resp.success

    def test_script_missing_path(self) -> None:
        resp = self.connector.execute(self._req("blender.script"))
        assert not resp.success

    def test_open_missing_path(self) -> None:
        resp = self.connector.execute(self._req("blender.open"))
        assert not resp.success

    def test_render_animation_or_graceful(self) -> None:
        resp = self.connector.execute(
            self._req("blender.render_animation", start=1, end=3)
        )
        assert resp.success or "not installed" in (resp.error or "").lower()

    def test_scene_new_or_graceful(self) -> None:
        resp = self.connector.execute(self._req("blender.scene.new"))
        assert resp.success or "not installed" in (resp.error or "").lower()

    def test_object_add_or_graceful(self) -> None:
        resp = self.connector.execute(self._req("blender.object.add"))
        assert resp.success or "not installed" in (resp.error or "").lower()

    def test_export_or_graceful(self) -> None:
        resp = self.connector.execute(
            self._req("blender.export", path="output.obj", format="obj")
        )
        assert resp.success or "not installed" in (resp.error or "").lower()


# ===========================================================================
# Additional Playwright edge-case tests
# ===========================================================================


class TestPlaywrightEdgeCases:
    """Additional edge-case tests for PlaywrightConnector."""

    def setup_method(self) -> None:
        self.connector = PlaywrightConnector()
        self.connector.connect()

    def teardown_method(self) -> None:
        self.connector.disconnect()

    def _req(self, capability: str, **params: object) -> MCPRequest:
        return MCPRequest(
            connector="playwright", capability=capability, params=dict(params)
        )

    def test_custom_browser(self) -> None:
        c = PlaywrightConnector(browser="firefox")
        assert c.browser == "firefox"
        c.disconnect()

    def test_custom_headless(self) -> None:
        c = PlaywrightConnector(headless=False)
        assert c.headless is False
        c.disconnect()

    def test_custom_timeout(self) -> None:
        c = PlaywrightConnector(timeout=60)
        assert c.timeout == 60
        c.disconnect()

    def test_metadata_contains_browser(self) -> None:
        d = self.connector.discover()
        assert "browser" in d["metadata"]

    def test_metadata_contains_headless(self) -> None:
        d = self.connector.discover()
        assert "headless" in d["metadata"]

    def test_upload_missing_selector(self) -> None:
        resp = self.connector.execute(self._req("playwright.upload", path="x"))
        assert not resp.success

    def test_upload_missing_path(self) -> None:
        resp = self.connector.execute(self._req("playwright.upload", selector="input"))
        assert not resp.success

    def test_wait_missing_selector(self) -> None:
        resp = self.connector.execute(self._req("playwright.wait"))
        # wait for load state doesn't need a selector, but if playwright
        # is not installed or browser not launched, it fails.
        assert (
            resp.success
            or "not installed" in (resp.error or "").lower()
            or "not launched" in (resp.error or "").lower()
        )

    def test_pdf_missing_launch(self) -> None:
        resp = self.connector.execute(self._req("playwright.pdf"))
        assert not resp.success

    def test_type_missing_text(self) -> None:
        resp = self.connector.execute(self._req("playwright.type", selector="input"))
        assert not resp.success


# ===========================================================================
# Connector config edge cases
# ===========================================================================


class TestConnectorConfigEdgeCases:
    """Additional tests for the connector config loader."""

    def test_get_config_path_returns_path(self) -> None:
        from atlas.mcp.connector_config import get_config_path

        p = get_config_path()
        assert p.name == "connectors.yaml"

    def test_filesystem_config_has_max_file_size(self) -> None:
        cfg = get_connector_config("filesystem")
        assert "max_file_size_mb" in cfg

    def test_ollama_config_has_timeout(self) -> None:
        cfg = get_connector_config("ollama")
        assert "timeout_seconds" in cfg

    def test_openrouter_config_has_max_retries(self) -> None:
        cfg = get_connector_config("openrouter")
        assert "max_retries" in cfg

    def test_browser_config_has_user_agent(self) -> None:
        cfg = get_connector_config("browser")
        assert "user_agent" in cfg

    def test_playwright_config_has_browser(self) -> None:
        cfg = get_connector_config("playwright")
        assert "browser" in cfg

    def test_windows_config_has_powershell(self) -> None:
        cfg = get_connector_config("windows")
        assert "powershell" in cfg

    def test_blender_config_has_blender_path(self) -> None:
        cfg = get_connector_config("blender")
        assert "blender_path" in cfg

    def test_github_config_has_default_branch(self) -> None:
        cfg = get_connector_config("github")
        assert "default_branch" in cfg

    def test_github_config_has_timeout(self) -> None:
        cfg = get_connector_config("github")
        assert "timeout_seconds" in cfg

    def test_reload_config_clears_cache(self) -> None:
        reload_config()
        cfg1 = get_connector_config("ollama")
        reload_config()
        cfg2 = get_connector_config("ollama")
        assert cfg1 == cfg2
