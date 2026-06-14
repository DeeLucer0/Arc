"""`/api/agents/{id}/skills` route handler + skill-folder discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arcgateway import fs_reader
from arcgateway.fs_reader import FileTooLargeError, PathTraversalError
from starlette.requests import Request
from starlette.responses import JSONResponse

from arcui.routes.agent_detail._common import (
    _CALLER_DID,
    _FRONTMATTER_RE,
    _agent_root,
    logger,
)
from arcui.schemas import ErrorResponse, SkillsResponse


def _scan_skills_dir(
    agent_id: str, scope_root: Path, rel_dir: str, source: str
) -> list[dict[str, Any]]:
    """Walk one skills directory through fs_reader (audited + sandboxed).

    `source` tags each row so the UI can show where a skill came from
    (workspace / agent-dir / module). Folders containing SKILL.md are
    treated as compound skills; loose .md files are treated as flat.
    """
    out: list[dict[str, Any]] = []
    try:
        entries = fs_reader.list_tree(
            scope="agent",
            agent_id=agent_id,
            agent_root=scope_root,
            rel_path=rel_dir,
            caller_did=_CALLER_DID,
            max_depth=2,
        )
    except (PathTraversalError, FileNotFoundError):
        return out

    # Two valid skill shapes:
    #   1. Compound skill: skills/<name>/SKILL.md (one level deep)
    #   2. Flat skill:     skills/<name>.md       (immediate child)
    # Everything else under a skill folder (references/*.md, examples/*.md,
    # nested helpers) is supporting material and must NOT be surfaced as a
    # top-level skill. Filter strictly by relative depth.
    rel_prefix = (rel_dir + "/") if rel_dir else ""
    for entry in entries:
        if entry.type == "dir":
            continue
        if not entry.path.endswith(".md"):
            continue
        # entry.path is relative to scope_root; subtract the rel_dir prefix
        # so we can reason about depth from the skills/ root.
        sub = entry.path[len(rel_prefix) :] if entry.path.startswith(rel_prefix) else entry.path
        depth = sub.count("/")
        is_skill_md = sub.endswith("/SKILL.md") and depth == 1
        is_flat_md = depth == 0
        if not (is_skill_md or is_flat_md):
            continue
        try:
            content = fs_reader.read_file(
                scope="agent",
                agent_id=agent_id,
                agent_root=scope_root,
                rel_path=entry.path,
                caller_did=_CALLER_DID,
            )
        except (FileNotFoundError, PathTraversalError, FileTooLargeError):
            continue
        skill = _parse_skill(entry.path, content.content)
        skill["mtime"] = entry.mtime
        skill["source"] = source
        # Inline the body so the UI doesn't have to make a second
        # /files/read call (which only resolves workspace paths and
        # would 404 for builtin/global skills that live outside).
        skill["body"] = content.content
        out.append(skill)
    return out


async def get_skills(request: Request) -> JSONResponse:
    agent_id = request.path_params["id"]
    agent_root = _agent_root(request, agent_id)
    if agent_root is None:
        return JSONResponse(
            ErrorResponse(error="Agent not found").model_dump(mode="json"),
            status_code=404,
        )
    return JSONResponse(
        SkillsResponse(skills=discover_skills(agent_id, agent_root)).model_dump(mode="json")
    )


def discover_skills(agent_id: str, agent_root: Path) -> list[dict[str, Any]]:
    """Collect an agent's skills from the exact roots the loader scans.

    Mirrors ``CapabilityLoader``: skills are subfolders containing a
    ``SKILL.md`` under the ``skills/`` subdir of each capabilities root.
    ``create_skill``/``update_skill`` write to ``capabilities/skills/<name>/``,
    and the loader registers a per-root ``skills/`` directory (see the
    ``builtins-skills`` root in ``agent_lifecycle.setup_capabilities``). Roots,
    in loader precedence order:
      - arcagent builtins  → builtins/capabilities/skills/   (create-skill, ...)
      - global             → ~/.arc/capabilities/skills/
      - agent              → team/<agent>/capabilities/skills/
      - workspace          → team/<agent>/workspace/capabilities/skills/

    The fleet Tools & Skills page and the agent-detail Skills tab both call
    this, so they surface the identical set the agent loads into its prompt.
    """
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _merge(rows: list[dict[str, Any]]) -> None:
        for s in rows:
            key = s.get("name") or s.get("path")
            if key and key not in seen:
                seen.add(key)
                skills.append(s)

    # Each capabilities root's skills live one level down in ``skills/``.
    # Scan that subdir directly (rel_dir="") so a skill at
    # ``<root>/capabilities/skills/<name>/SKILL.md`` lands at depth 1, the
    # shape _scan_skills_dir recognizes. fs_reader skips dot-children, so the
    # scan root must be the skills/ dir itself, not its parent.
    workspace = agent_root / "workspace"
    roots: list[tuple[Path, str]] = [
        (agent_root / "capabilities" / "skills", "agent_dir"),
        (workspace / "capabilities" / "skills", "workspace"),
        (Path.home() / ".arc" / "capabilities" / "skills", "global"),
    ]
    for skills_root, source in roots:
        if skills_root.is_dir():
            _merge(_scan_skills_dir(agent_id, skills_root, "", source))

    # System-wide built-in skills shipped with arcagent (create-skill,
    # update-skill, create-tool, update-tool, ...) — the builtins-skills root.
    try:
        # importlib.util.find_spec preserves the arcui→arcagent boundary
        # (SPEC-023 §2.2) — we only need arcagent's filesystem path, never
        # its runtime behaviour.
        import importlib.util as _ilu

        spec = _ilu.find_spec("arcagent")
        if spec is not None and spec.origin is not None:
            builtin_skills = Path(spec.origin).parent / "builtins" / "capabilities" / "skills"
            if builtin_skills.is_dir():
                _merge(_scan_skills_dir(agent_id, builtin_skills, "", "builtin"))
    except Exception:  # reason: fail-open — log + continue
        logger.debug("builtin skills scan failed", exc_info=True)

    return skills


def _parse_skill(rel_path: str, text: str) -> dict[str, Any]:
    """Parse YAML-ish frontmatter (``key: value`` lines) into a dict.

    Skill markdown frontmatter is intentionally simple — flat ``key: value``
    pairs only, no nested mappings. We keep the parser equally simple to
    avoid pulling in PyYAML for one feature.
    """
    name = rel_path.removesuffix(".md").rsplit("/", 1)[-1]
    fm: dict[str, Any] = {}
    match = _FRONTMATTER_RE.match(text)
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                fm[key.strip()] = value.strip()
    return {
        "name": fm.get("name", name),
        "description": fm.get("description", ""),
        "version": fm.get("version", ""),
        "path": f"skills/{rel_path.split('skills/', 1)[-1]}"
        if "skills/" in rel_path
        else f"skills/{rel_path}",
    }
