from __future__ import annotations

import subprocess

from autoresearch import config


def _git(repo, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Autoresearch Test",
            "-c",
            "user.email=test@example.invalid",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def test_full_repo_files_returns_tracked_utf8_files(monkeypatch, tmp_path):
    repo = tmp_path / "botmap-repo"
    repo.mkdir()
    (repo / "botmap").mkdir()
    (repo / "botmap" / "cli.py").write_text("print('ok')\n", encoding="utf-8")
    (repo / "evals").mkdir()
    (repo / "evals" / "score.py").write_text("print('exam')\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_eval_score.py").write_text("print('exam test')\n", encoding="utf-8")
    (repo / "README.md").write_text("# botmap\n", encoding="utf-8")
    (repo / "image.bin").write_bytes(b"abc\x00def")
    (repo / "untracked.py").write_text("ignored\n", encoding="utf-8")

    _git(repo, "init")
    _git(repo, "add", "botmap/cli.py", "evals/score.py", "tests/test_eval_score.py", "README.md", "image.bin")
    _git(repo, "commit", "-m", "seed")

    monkeypatch.setattr(config, "repo_root", lambda: repo)

    assert config.full_repo_files() == ("README.md", "botmap/cli.py")
    assert config.full_repo_files(include_evaluator=True) == (
        "README.md",
        "botmap/cli.py",
        "evals/score.py",
        "tests/test_eval_score.py",
    )


def test_full_repo_context_includes_bounded_tracked_file_contents(monkeypatch, tmp_path):
    repo = tmp_path / "botmap-repo"
    repo.mkdir()
    (repo / "botmap").mkdir()
    (repo / "botmap" / "cli.py").write_text("print('ok')\n", encoding="utf-8")
    (repo / "README.md").write_text("# botmap\n", encoding="utf-8")

    _git(repo, "init")
    _git(repo, "add", "botmap/cli.py", "README.md")
    _git(repo, "commit", "-m", "seed")

    monkeypatch.setattr(config, "repo_root", lambda: repo)

    context = config.full_repo_context(max_chars=1_000, file_max_chars=1_000)

    assert "--- FILE: README.md ---" in context
    assert "# botmap" in context
    assert "--- FILE: botmap/cli.py ---" in context
    assert "print('ok')" in context


def test_wide_lever_is_discoverable_files_plus_the_prompt_never_never_evolve(monkeypatch, tmp_path):
    repo = tmp_path / "botmap-repo"
    (repo / "botmap" / "data").mkdir(parents=True)
    for name in ("cli.py", "filters.py", "core.py", "skill_installer.py", "__init__.py"):
        (repo / "botmap" / name).write_text("pass\n", encoding="utf-8")
    (repo / "botmap" / "data" / "skill.md").write_text("# skill\n", encoding="utf-8")

    monkeypatch.setattr(config, "repo_root", lambda: repo)

    files = config.lever_files(config.WIDE_LEVER)

    assert set(files) == {
        "botmap/cli.py",
        "botmap/filters.py",
        "botmap/data/skill.md",
    }
    # NEVER_EVOLVE stays out even in the wider lever -- this project's own
    # prior, deliberate call, not something the wide lever should override.
    assert "botmap/core.py" not in files
    assert "botmap/skill_installer.py" not in files
    assert "botmap/__init__.py" not in files


def test_wide_lever_honours_an_explicit_files_override(monkeypatch, tmp_path):
    repo = tmp_path / "botmap-repo"
    (repo / "botmap").mkdir(parents=True)
    (repo / "botmap" / "cli.py").write_text("pass\n", encoding="utf-8")
    monkeypatch.setattr(config, "repo_root", lambda: repo)

    assert config.lever_files(config.WIDE_LEVER, ("botmap/cli.py",)) == ("botmap/cli.py",)


def test_unknown_lever_names_wide_as_a_valid_choice():
    import pytest

    with pytest.raises(ValueError, match="'wide'"):
        config.lever_files("nonsense")
