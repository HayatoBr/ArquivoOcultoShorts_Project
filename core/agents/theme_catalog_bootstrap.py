from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, Any, Tuple, List

from core.agents.theme_catalog_validator import (
    load_catalog,
    validate_catalog,
    ensure_default_catalog,
    ensure_minimum_themes,
    write_catalog,
)
from core.agents.theme_catalog_normalizer import normalize_catalog, catalogs_equal


def _safe_backup(path: Path) -> str:
    if not path.exists():
        return ""
    base = path.with_suffix("")
    n = 1
    while True:
        dst = Path(f"{base}.backup.{n}.json")
        if not dst.exists():
            shutil.copyfile(path, dst)
            return str(dst)
        n += 1


def bootstrap_theme_catalog(cfg: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], List[str]]:
    images = cfg.get("images") or {}
    tp = images.get("theme_presets") or {}

    enabled = bool(tp.get("enabled", True))
    if not enabled:
        return True, {"enabled": False, "status": "disabled"}, []

    catalog_path = Path(tp.get("catalog_path") or "presets/theme_presets_catalog.json")

    auto_validate = bool(tp.get("auto_validate_catalog", True))
    auto_create = bool(tp.get("auto_create_default_if_missing", True))
    auto_fill_minimum = bool(tp.get("auto_fill_minimum_themes", True))
    auto_normalize = bool(tp.get("auto_normalize_catalog", True))
    hard_fail = bool(tp.get("hard_fail_on_invalid_catalog", False))

    created = False
    if not catalog_path.exists() and auto_create:
        created = ensure_default_catalog(catalog_path)

    if not catalog_path.exists():
        msg = [f"Catalog ausente: {catalog_path}"]
        ok = not hard_fail
        return ok, {
            "enabled": True,
            "status": "missing",
            "catalog_path": str(catalog_path),
            "created_default": created,
            "hard_fail_on_invalid_catalog": hard_fail,
            "auto_fill_minimum_themes": auto_fill_minimum,
            "auto_normalize_catalog": auto_normalize,
        }, msg

    try:
        cat = load_catalog(catalog_path)
    except Exception as e:
        errs = [f"Falha ao ler catalog JSON: {e}"]
        ok = not hard_fail
        return ok, {
            "enabled": True,
            "status": "read_error",
            "catalog_path": str(catalog_path),
            "created_default": created,
            "hard_fail_on_invalid_catalog": hard_fail,
            "auto_fill_minimum_themes": auto_fill_minimum,
            "auto_normalize_catalog": auto_normalize,
        }, errs

    backup_path = ""
    fill_changes: List[str] = []
    norm_changes: List[str] = []

    if auto_fill_minimum:
        cat2, fill_changes = ensure_minimum_themes(cat)
        if fill_changes:
            backup_path = _safe_backup(catalog_path)
            write_catalog(catalog_path, cat2)
            cat = cat2

    if auto_normalize:
        cat_norm, norm_changes = normalize_catalog(cat)
        if norm_changes and not catalogs_equal(cat_norm, cat):
            if not backup_path:
                backup_path = _safe_backup(catalog_path)
            write_catalog(catalog_path, cat_norm)
            cat = cat_norm

    if not auto_validate:
        return True, {
            "enabled": True,
            "status": "skipped_validation",
            "catalog_path": str(catalog_path),
            "created_default": created,
            "hard_fail_on_invalid_catalog": hard_fail,
            "auto_fill_minimum_themes": auto_fill_minimum,
            "auto_normalize_catalog": auto_normalize,
            "autofill_changes": fill_changes,
            "normalize_changes": norm_changes,
            "backup_path": backup_path,
        }, []

    ok, errors = validate_catalog(cat)
    meta = {
        "enabled": True,
        "status": "ok" if ok else "invalid",
        "catalog_path": str(catalog_path),
        "created_default": created,
        "hard_fail_on_invalid_catalog": hard_fail,
        "auto_fill_minimum_themes": auto_fill_minimum,
        "auto_normalize_catalog": auto_normalize,
        "autofill_changes": fill_changes,
        "normalize_changes": norm_changes,
        "backup_path": backup_path,
        "errors_count": len(errors),
    }

    if ok:
        return True, meta, []

    if not backup_path:
        backup_path = _safe_backup(catalog_path)
        meta["backup_path"] = backup_path

    if auto_create:
        ensure_default_catalog(catalog_path)
        meta["replaced_with_default"] = True
        meta["status"] = "invalid_replaced_with_default"
        if hard_fail:
            return False, meta, errors
        return True, meta, errors

    if hard_fail:
        return False, meta, errors
    return True, meta, errors
