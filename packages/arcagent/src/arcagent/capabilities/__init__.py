"""Capability subsystem: loading, registry, and skill-folder validation.

Moved out of ``arcagent.core`` to keep the nucleus under the 3,500-LOC budget
(ADR-004 / SPEC-018 G1.5). Capability discovery, registry coordination, and
skill-folder validation are orchestration concerns, not nucleus concerns, per
CLAUDE.md's rule: "complexity lives in extensions, plugins, and modules —
never in the nucleus."

Callers import submodules directly, e.g.::

    from arcagent.capabilities.capability_loader import CapabilityLoader
    from arcagent.capabilities.capability_registry import CapabilityRegistry
    from arcagent.capabilities.skill_validator import validate_skill_folder
"""
