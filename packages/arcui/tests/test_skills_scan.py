"""Regression: the agent-skills scanner must read the path create_skill writes to.

``create_skill``/``update_skill`` write agent-authored skills to
``<agent_root>/workspace/capabilities/skills/<name>/SKILL.md`` (a ``skills/``
subdir of the capabilities root, mirroring the loader's ``builtins-skills``
root). The UI's discovery previously scanned ``<root>/capabilities`` directly,
so authored skills one level deeper at ``capabilities/skills/<name>/`` never
appeared and the Skills tab under-reported to only the four builtin self-mod
skills. These tests lock discovery onto the real loader paths across every
capabilities root.
"""

from __future__ import annotations

from pathlib import Path

from arcui.routes.agent_detail.skills import _scan_skills_dir, discover_skills

_SKILL_MD = """\
---
name: {name}
version: 1.0.0
description: {desc}
---

## Resources

## Contract
"""


def _write_skill(skills_root: Path, name: str, desc: str = "does stuff") -> None:
    folder = skills_root / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(_SKILL_MD.format(name=name, desc=desc), encoding="utf-8")


def test_scans_workspace_capabilities_skills(tmp_path: Path) -> None:
    """A skill at workspace/capabilities/skills/<name>/SKILL.md is found."""
    skills_root = tmp_path / "workspace" / "capabilities" / "skills"
    _write_skill(skills_root, "researcher")

    names = {s["name"] for s in discover_skills("olivia_agent", tmp_path)}
    assert "researcher" in names


def test_authored_skills_join_builtins(tmp_path: Path) -> None:
    """Authored workspace skills appear alongside the builtin self-mod skills."""
    skills_root = tmp_path / "workspace" / "capabilities" / "skills"
    for n in ("alpha", "beta", "gamma"):
        _write_skill(skills_root, n)

    names = {s["name"] for s in discover_skills("olivia_agent", tmp_path)}
    assert {"alpha", "beta", "gamma"} <= names
    # Builtins are still surfaced (create-skill / update-tool / ...).
    assert {"create-skill", "create-tool", "update-skill", "update-tool"} <= names


def test_agent_dir_capabilities_skills(tmp_path: Path) -> None:
    """Per-agent skills live at <agent_root>/capabilities/skills/<name>/."""
    skills_root = tmp_path / "capabilities" / "skills"
    _write_skill(skills_root, "operator_skill")

    names = {s["name"] for s in discover_skills("olivia_agent", tmp_path)}
    assert "operator_skill" in names


def test_multi_root_dedup(tmp_path: Path) -> None:
    """A name present in two roots surfaces once (first root wins)."""
    agent_skills = tmp_path / "capabilities" / "skills"
    ws_skills = tmp_path / "workspace" / "capabilities" / "skills"
    _write_skill(agent_skills, "shared", desc="agent copy")
    _write_skill(ws_skills, "shared", desc="workspace copy")

    rows = [s for s in discover_skills("olivia_agent", tmp_path) if s["name"] == "shared"]
    assert len(rows) == 1


def test_scan_skill_path_shape(tmp_path: Path) -> None:
    """Discovered rows carry a skills/<name>/SKILL.md path the UI can render."""
    skills_root = tmp_path / "workspace" / "capabilities" / "skills"
    _write_skill(skills_root, "shaped")

    rows = _scan_skills_dir("olivia_agent", skills_root, "", "workspace")
    paths = {r["path"] for r in rows}
    assert "skills/shaped/SKILL.md" in paths


def test_missing_dirs_yield_only_builtins(tmp_path: Path) -> None:
    """With no on-disk capabilities, only the arcagent builtins surface."""
    names = {s["name"] for s in discover_skills("olivia_agent", tmp_path)}
    assert names == {"create-skill", "create-tool", "update-skill", "update-tool"}
