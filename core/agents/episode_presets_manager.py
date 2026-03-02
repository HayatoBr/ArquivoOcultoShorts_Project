from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional, Tuple

JOB_VISUAL_PROFILE_FILENAME = "job_visual_profile.txt"
JOB_CHARACTER_ANCHOR_FILENAME = "job_character_anchor.txt"
JOB_NEGATIVE_PROFILE_FILENAME = "job_negative_profile.txt"

CHANNEL_VISUAL_PROFILE_FILENAME = "channel_visual_profile.txt"
CHANNEL_CHARACTER_ANCHOR_FILENAME = "channel_character_anchor.txt"
CHANNEL_NEGATIVE_PROFILE_FILENAME = "channel_negative_profile.txt"


def _read_if_exists(p: Path) -> Optional[str]:
    try:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        try:
            return p.read_text(encoding="utf-8-sig").strip()
        except Exception:
            return None
    return None


def resolve_text_with_priority(
    job_dir: Path,
    project_root: Path,
    *,
    job_filename: str,
    channel_filename: str,
    priority: str = "job_first",
    default_text: str = "",
) -> Tuple[str, Dict[str, Any]]:
    """Return (text, meta) with provenance and priority."""
    job_path = job_dir / job_filename
    ch_path = project_root / channel_filename

    job_text = _read_if_exists(job_path) or ""
    ch_text = _read_if_exists(ch_path) or ""

    pr = (priority or "job_first").lower()
    if pr not in ("job_first", "channel_first"):
        pr = "job_first"

    if pr == "job_first":
        effective = job_text or ch_text or default_text
        source = "job" if job_text else ("channel" if ch_text else "default")
    else:
        effective = ch_text or job_text or default_text
        source = "channel" if ch_text else ("job" if job_text else "default")

    return (effective.strip(), {"priority": pr, "source": source, "job_path": str(job_path), "channel_path": str(ch_path)})


def resolve_effective_profiles(
    job_dir: Path,
    project_root: Path,
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    images = cfg.get("images") or {}

    # Visual profile
    vp_cfg = images.get("channel_profile") or {}
    vp_enabled = bool(vp_cfg.get("enabled", True))
    vp_priority = (vp_cfg.get("priority") or "channel_first").lower()
    vp_default = ""

    visual_profile = ""
    visual_meta = {"enabled": vp_enabled}
    if vp_enabled:
        visual_profile, meta = resolve_text_with_priority(
            job_dir,
            project_root,
            job_filename=JOB_VISUAL_PROFILE_FILENAME,
            channel_filename=CHANNEL_VISUAL_PROFILE_FILENAME,
            priority=vp_priority,
            default_text=vp_default,
        )
        visual_meta.update(meta)

    # Negative profile
    neg_cfg = images.get("channel_negative") or {}
    neg_enabled = bool(neg_cfg.get("enabled", True))
    neg_priority = (neg_cfg.get("priority") or "channel_first").lower()
    neg_default = ""

    negative_profile = ""
    negative_meta = {"enabled": neg_enabled}
    if neg_enabled:
        negative_profile, meta = resolve_text_with_priority(
            job_dir,
            project_root,
            job_filename=JOB_NEGATIVE_PROFILE_FILENAME,
            channel_filename=CHANNEL_NEGATIVE_PROFILE_FILENAME,
            priority=neg_priority,
            default_text=neg_default,
        )
        negative_meta.update(meta)

    # Character anchor (may be generated elsewhere; here we only resolve overrides)
    ch_cfg = images.get("channel_character") or {}
    ch_enabled = bool(ch_cfg.get("enabled", True))
    ch_priority = (ch_cfg.get("priority") or "job_first").lower()
    ch_default = ""

    character_anchor = ""
    anchor_meta = {"enabled": ch_enabled}
    if ch_enabled:
        character_anchor, meta = resolve_text_with_priority(
            job_dir,
            project_root,
            job_filename=JOB_CHARACTER_ANCHOR_FILENAME,
            channel_filename=CHANNEL_CHARACTER_ANCHOR_FILENAME,
            priority=ch_priority,
            default_text=ch_default,
        )
        anchor_meta.update(meta)

    return {
        "visual_profile": {"text": visual_profile, "meta": visual_meta},
        "negative_profile": {"text": negative_profile, "meta": negative_meta},
        "character_anchor_override": {"text": character_anchor, "meta": anchor_meta},
    }
