#!/usr/bin/env python3
"""Validate the official tt-env manifest catalog without executing manifests."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
RELEASES_DIR = ROOT / "releases"
MANIFESTS_DIR = ROOT / "manifests"

SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SYSTEM_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SHA256_RE = re.compile(r"^[A-Fa-f0-9]{64}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9_./:+-]*$")
SCALAR_RE = re.compile(r'^\s*([A-Z_][A-Z0-9_]*)="([A-Za-z0-9_./:+-]*)"\s*$', re.ASCII)
EMPTY_ARRAY_RE = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)=\(\s*\)\s*$", re.ASCII)
INLINE_ARRAY_RE = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)=\(\s*(.*?)\s*\)\s*$", re.ASCII)
OPEN_ARRAY_RE = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)=\(\s*$", re.ASCII)
CLOSE_ARRAY_RE = re.compile(r"^\s*\)\s*$", re.ASCII)
TOKEN_RE = re.compile(r'^"([A-Za-z0-9_./:+-]*)"(.*)$', re.ASCII)
OS_FILENAME_RE = re.compile(
    r"^(?P<os_id>[a-z0-9](?:[a-z0-9_-]*[a-z0-9])?)-"
    r"(?P<os_version>[0-9](?:[a-z0-9._-]*[a-z0-9])?)\.env$",
    re.ASCII,
)

TOP_LEVEL_FIELDS = {
    "release",
    "description",
    "components",
    "system_packages",
    "python_packages",
    "git_components",
    "container_components",
}
REQUIRED_OS_SCALARS = {
    "PKG_MANAGER",
    "USE_SYSTEM_PACKAGES",
    "VIRT_PKG_CMAKE",
    "VIRT_PKG_NINJA",
    "VIRT_PKG_ZLIB",
    "VIRT_PKG_KMD",
    "VIRT_PKG_SMI",
    "VIRT_PKG_FLASH",
    "VIRT_PKG_TOPOLOGY",
    "VIRT_PKG_METALIUM",
}
REQUIRED_OS_ARRAYS = {"REQUIRED_REPOS", "WORKAROUNDS"}


class ValidationError(ValueError):
    """A manifest failed catalog validation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def require_object(value: Any, where: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{where} must be an object")
    return value


def require_string(value: Any, where: str) -> str:
    require(isinstance(value, str) and value != "", f"{where} must be a non-empty string")
    return value


def reject_unknown(obj: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(obj) - allowed)
    require(not unknown, f"{where} has unknown field(s): {', '.join(unknown)}")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def validate_https_url(value: Any, where: str) -> str:
    url = require_string(value, where)
    require(
        all(not char.isspace() and ord(char) >= 0x20 and ord(char) != 0x7F for char in url),
        f"{where} must not contain whitespace or control characters",
    )
    require("#" not in url, f"{where} must not contain a fragment")
    require(re.search(r"%(?![0-9A-Fa-f]{2})", url) is None, f"{where} has malformed percent encoding")
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError as exc:
        raise ValidationError(f"{where} has an invalid URL authority") from exc
    require(parsed.scheme == "https" and parsed.hostname is not None, f"{where} must be an absolute HTTPS URL")
    require(parsed.username is None and parsed.password is None, f"{where} must not contain credentials")
    require(not parsed.netloc.endswith(":"), f"{where} has an invalid port")
    require(port is None or 0 <= port <= 65535, f"{where} has an invalid port")
    return url


def validate_release(path: Path) -> None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid JSON: {exc}") from exc

    root = require_object(value, "manifest")
    missing = sorted(TOP_LEVEL_FIELDS - set(root))
    require(not missing, f"manifest is missing field(s): {', '.join(missing)}")
    reject_unknown(root, TOP_LEVEL_FIELDS, "manifest")

    release = require_string(root["release"], "release")
    require(SEMVER_RE.fullmatch(release) is not None, "release must be a stable semantic version without a leading v")
    require(path.stem == release, f"filename {path.name!r} does not match release {release!r}")
    require_string(root["description"], "description")

    components = require_object(root["components"], "components")
    require("tt-metal" in components, 'components must include "tt-metal"')
    metal = components["tt-metal"]
    metal_version = metal if isinstance(metal, str) else metal.get("version") if isinstance(metal, dict) else None
    require(metal_version == "v" + release, f'tt-metal component must be "v{release}"')
    for name, component in components.items():
        require(NAME_RE.fullmatch(name) is not None, f"invalid component name {name!r}")
        if isinstance(component, str):
            require(component != "", f"component {name!r} has an empty version")
            continue
        item = require_object(component, f"component {name!r}")
        allowed = {"version", "download_url", "sha256"}
        reject_unknown(item, allowed, f"component {name!r}")
        require(set(item) == allowed, f"component {name!r} object must contain version, download_url, and sha256")
        require_string(item["version"], f"component {name!r} version")
        validate_https_url(item["download_url"], f"component {name!r} download_url")
        digest = require_string(item["sha256"], f"component {name!r} sha256")
        require(SHA256_RE.fullmatch(digest) is not None, f"component {name!r} has an invalid sha256")

    for field, key_re in (("system_packages", SYSTEM_KEY_RE), ("python_packages", NAME_RE)):
        packages = require_object(root[field], field)
        for name, version in packages.items():
            require(key_re.fullmatch(name) is not None, f"{field} has invalid package name {name!r}")
            require_string(version, f"{field}.{name}")

    git_components = require_object(root["git_components"], "git_components")
    for name, component in git_components.items():
        require(NAME_RE.fullmatch(name) is not None, f"invalid git component name {name!r}")
        item = require_object(component, f"git component {name!r}")
        reject_unknown(item, {"url", "version"}, f"git component {name!r}")
        require(set(item) == {"url", "version"}, f"git component {name!r} must contain url and version")
        validate_https_url(item["url"], f"git component {name!r} url")
        require_string(item["version"], f"git component {name!r} version")

    containers = require_object(root["container_components"], "container_components")
    for name, component in containers.items():
        require(NAME_RE.fullmatch(name) is not None, f"invalid container component name {name!r}")
        item = require_object(component, f"container component {name!r}")
        reject_unknown(item, {"ref", "image_url", "image_tag"}, f"container component {name!r}")
        if "ref" in item:
            require(set(item) == {"ref"}, f"container component {name!r} must use either ref or image fields")
            target = require_string(item["ref"], f"container component {name!r} ref")
            require(target != name, f"container component {name!r} cannot reference itself")
            require(target in containers, f"container component {name!r} references missing component {target!r}")
        else:
            require(set(item) == {"image_url", "image_tag"}, f"container component {name!r} must contain image_url and image_tag")
            image = require_string(item["image_url"], f"container component {name!r} image_url")
            require(re.fullmatch(r"ghcr\.io/[a-z0-9][a-z0-9._/-]*", image) is not None, f"container component {name!r} image_url must be a valid GHCR repository")
            digest = require_string(item["image_tag"], f"container component {name!r} image_tag")
            require(DIGEST_RE.fullmatch(digest) is not None, f"container component {name!r} image_tag must be an immutable sha256 digest")

    for start in containers:
        seen: set[str] = set()
        current = start
        while "ref" in containers[current]:
            require(current not in seen, f"container component reference cycle includes {current!r}")
            seen.add(current)
            current = containers[current]["ref"]


def parse_tokens(text: str, line_number: int) -> list[str]:
    values: list[str] = []
    remaining = text.lstrip()
    while remaining and not remaining.startswith("#"):
        match = TOKEN_RE.fullmatch(remaining)
        if match is None:
            raise ValidationError(f"line {line_number}: invalid array item: {remaining}")
        values.append(match.group(1))
        remaining = match.group(2).lstrip()
    return values


def validate_os_manifest(path: Path) -> None:
    scalars: dict[str, str] = {}
    arrays: dict[str, list[str]] = {}
    open_key: str | None = None

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValidationError(str(exc)) from exc
    require(content.isascii(), "OS manifest must contain ASCII text only")
    lines = content.splitlines()

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if any(char in line for char in "$`;\\<>&|"):
            raise ValidationError(f"line {line_number}: unsafe shell character")

        if open_key is not None:
            if CLOSE_ARRAY_RE.fullmatch(line):
                open_key = None
                continue
            arrays[open_key].extend(parse_tokens(stripped, line_number))
            continue

        if match := SCALAR_RE.fullmatch(line):
            key, value = match.groups()
            require(key not in scalars and key not in arrays, f"line {line_number}: duplicate key {key}")
            require(SAFE_VALUE_RE.fullmatch(value) is not None, f"line {line_number}: unsafe value")
            scalars[key] = value
        elif match := EMPTY_ARRAY_RE.fullmatch(line):
            key = match.group(1)
            require(key not in scalars and key not in arrays, f"line {line_number}: duplicate key {key}")
            arrays[key] = []
        elif match := OPEN_ARRAY_RE.fullmatch(line):
            key = match.group(1)
            require(key not in scalars and key not in arrays, f"line {line_number}: duplicate key {key}")
            arrays[key] = []
            open_key = key
        elif match := INLINE_ARRAY_RE.fullmatch(line):
            key, body = match.groups()
            require(key not in scalars and key not in arrays, f"line {line_number}: duplicate key {key}")
            arrays[key] = parse_tokens(body, line_number)
        else:
            raise ValidationError(f"line {line_number}: invalid syntax")

    require(open_key is None, f"unterminated array {open_key}")
    missing_scalars = sorted(REQUIRED_OS_SCALARS - set(scalars))
    missing_arrays = sorted(REQUIRED_OS_ARRAYS - set(arrays))
    require(not missing_scalars, f"missing scalar field(s): {', '.join(missing_scalars)}")
    require(not missing_arrays, f"missing array field(s): {', '.join(missing_arrays)}")
    require(scalars["PKG_MANAGER"] in {"apt", "dnf"}, "PKG_MANAGER must be apt or dnf")
    require(scalars["USE_SYSTEM_PACKAGES"] in {"true", "false"}, "USE_SYSTEM_PACKAGES must be true or false")


def catalog_paths(directory: Path, suffix: str, root: Path, errors: list[str]) -> list[Path]:
    if not directory.is_dir():
        errors.append(f"{directory.relative_to(root)}: directory is missing")
        return []
    paths: list[Path] = []
    for path in sorted(directory.iterdir()):
        relative = path.relative_to(root)
        if path.name == ".gitkeep":
            continue
        if path.is_symlink():
            errors.append(f"{relative}: symlinks are not allowed")
        elif not path.is_file() or path.suffix != suffix:
            errors.append(f"{relative}: unexpected catalog entry")
        elif suffix == ".env" and OS_FILENAME_RE.fullmatch(path.name) is None:
            errors.append(f"{relative}: filename must match <os_id>-<os_version>.env")
        else:
            paths.append(path)
    return paths


def validate_catalog(root: Path = ROOT, allow_empty: bool = False) -> list[str]:
    errors: list[str] = []
    release_paths = catalog_paths(root / "releases", ".json", root, errors)
    manifest_paths = catalog_paths(root / "manifests", ".env", root, errors)
    if not allow_empty:
        if not release_paths:
            errors.append("releases: at least one release manifest is required")
        if not manifest_paths:
            errors.append("manifests: at least one OS manifest is required")
    for path in release_paths:
        try:
            validate_release(path)
        except ValidationError as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
    for path in manifest_paths:
        try:
            validate_os_manifest(path)
        except ValidationError as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-empty", action="store_true", help="allow an empty catalog during repository bootstrap")
    args = parser.parse_args()
    errors = validate_catalog(allow_empty=args.allow_empty)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    release_count = len(list(RELEASES_DIR.glob("*.json")))
    manifest_count = len(list(MANIFESTS_DIR.glob("*.env")))
    print(f"Validated {release_count} release manifest(s) and {manifest_count} OS manifest(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
