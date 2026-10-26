"""Small fail-closed validation helpers; these do not provide an OS sandbox."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any


class SafetyError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def validate_finite(value: Any, path: str = "$", depth: int = 0) -> None:
    if depth > 80:
        raise SafetyError("INVALID_ARGUMENT", "Arguments nested too deeply")
    if isinstance(value, float) and not math.isfinite(value):
        raise SafetyError("NONFINITE_NUMBER", f"{path} must be finite")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise SafetyError("INVALID_ARGUMENT", "Object keys must be strings")
            validate_finite(item, f"{path}.{key}", depth + 1)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate_finite(item, f"{path}[{index}]", depth + 1)


class PathPolicy:
    """Canonical allowlist, including existing symlinks. No TOCTOU guarantee."""
    def __init__(self, roots, reserved=()):
        self.roots = tuple(Path(p).expanduser().resolve() for p in roots)
        self.reserved = {str(Path(p).resolve()).casefold() for p in reserved}
        if not self.roots:
            raise SafetyError("PATH_POLICY", "At least one allowed root is required")

    def resolve(self, path: str | Path) -> Path:
        if not str(path).strip():
            raise SafetyError("PATH_DENIED", "Empty paths are not allowed")
        candidate = Path(path).expanduser()
        # Relative paths are always workspace-relative, never cwd-dependent.
        if not candidate.is_absolute():
            candidate = self.roots[0] / candidate
        candidate = candidate.resolve()
        if str(candidate).casefold() in self.reserved:
            raise SafetyError("PATH_RESERVED", "Service journal and sidecars cannot be accessed through CAD tools")
        if not any(candidate == root or root in candidate.parents for root in self.roots):
            raise SafetyError("PATH_DENIED", "Path is outside configured allowed roots")
        # Block Windows alternate data streams as well as device-like paths.
        if any(":" in piece for piece in candidate.parts[1:]):
            raise SafetyError("PATH_DENIED", "Alternate data streams are not allowed")
        return candidate


def failure(code: str, message: str, *, outcome: str = "not_executed") -> dict:
    return {"ok": False, "error": {"code": code, "message": message},
            "effects": {"outcome": outcome, "rollback": False}}


def normalize_result(raw: Any) -> dict:
    """Legacy strings are not proof of geometric validity."""
    if isinstance(raw, str) and any(marker in raw.upper() for marker in
                                    ("FEATURE_NO_EFFECT", "NO_MATERIAL_REMOVED")):
        return failure("FEATURE_NO_EFFECT", raw, outcome="possibly_modified")
    if isinstance(raw, str) and raw.lstrip().lower().startswith(("error:", "error ", "failed:", "failure:", "❌", "错误:", "错误：", "could not enumerate faces:", "could not enumerate edges:")):
        return failure("UPSTREAM_FAILURE", raw, outcome="possibly_modified")
    if isinstance(raw, dict):
        status = str(raw.get("status", "")).lower()
        if status in {"error", "failed", "failure", "no_material_removed"} or raw.get("ok") is False or raw.get("success") is False or raw.get("isError") is True or bool(raw.get("error")):
            result = failure("UPSTREAM_FAILURE", str(raw.get("message", raw.get("error", status))), outcome="possibly_modified")
            result["data"] = raw
            return result
        for key in ("result", "results"):
            nested = raw.get(key)
            values = nested if isinstance(nested, list) else [nested]
            if any(isinstance(item, (str, dict)) and not normalize_result(item)["ok"] for item in values):
                result = failure("UPSTREAM_FAILURE", "Nested upstream result reports failure", outcome="possibly_modified")
                result["data"] = raw
                return result
    return {"ok": True, "data": raw,
            "effects": {"outcome": "call_returned", "rollback": False},
            "verification": "CATIA geometry and engineering suitability not independently verified"}
