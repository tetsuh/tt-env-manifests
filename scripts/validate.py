#!/usr/bin/env python3
"""Validate the official tt-env manifest catalog without executing manifests."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import stat
import sys
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
RELEASES_DIR = ROOT / "releases"
MANIFESTS_DIR = ROOT / "manifests"
MAX_OS_RECORD_BYTES = 65536
MAX_OS_TOTAL_BYTES = 1 * 1024 * 1024

SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SYSTEM_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SHA256_RE = re.compile(r"^[A-Fa-f0-9]{64}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9_./:+-]*$")
REG_NAME_RE = re.compile(r"^(?:[A-Za-z0-9._~!$&'()*+,;=-]|%[0-9A-Fa-f]{2})+$", re.ASCII)
GHCR_COMPONENT_RE = r"[a-z0-9]+(?:\.(?:[a-z0-9]+)|_{1,2}(?:[a-z0-9]+)|-+(?:[a-z0-9]+))*"
GHCR_REPOSITORY_RE = re.compile(r"^ghcr\.io/" + GHCR_COMPONENT_RE + r"(?:/" + GHCR_COMPONENT_RE + r")*$", re.ASCII)
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
        all(not char.isspace() and unicodedata.category(char) != "Cc" for char in url),
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
    if parsed.netloc.startswith("["):
        try:
            ipaddress.IPv6Address(parsed.hostname)
        except ValueError as exc:
            raise ValidationError(f"{where} has an invalid IPv6 host") from exc
    else:
        require(REG_NAME_RE.fullmatch(parsed.hostname) is not None, f"{where} has an invalid host")
    return url


def validate_release_content(path: Path, content: bytes) -> None:
    try:
        value = json.loads(content.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
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
            require(GHCR_REPOSITORY_RE.fullmatch(image) is not None, f"container component {name!r} image_url must be a valid GHCR repository")
            digest = require_string(item["image_tag"], f"container component {name!r} image_tag")
            require(DIGEST_RE.fullmatch(digest) is not None, f"container component {name!r} image_tag must be an immutable sha256 digest")

    for start in containers:
        seen: set[str] = set()
        current = start
        while "ref" in containers[current]:
            require(current not in seen, f"container component reference cycle includes {current!r}")
            seen.add(current)
            current = containers[current]["ref"]


def validate_release(path: Path) -> None:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ValidationError(f"invalid JSON: {exc}") from exc
    validate_release_content(path, content)


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


def validate_os_manifest_content(path: Path, content_bytes: bytes) -> tuple[dict[str, str], dict[str, list[str]]]:
    scalars: dict[str, str] = {}
    arrays: dict[str, list[str]] = {}
    open_key: str | None = None

    try:
        content = content_bytes.decode("utf-8")
    except UnicodeError as exc:
        raise ValidationError(str(exc)) from exc
    require(content.isascii(), "OS manifest must contain ASCII text only")
    lines = content.split("\n")
    for line_number, line in enumerate(lines, 1):
        require(
            len(line) < MAX_OS_RECORD_BYTES,
            f"line {line_number}: record must be shorter than {MAX_OS_RECORD_BYTES} bytes",
        )
    for index, char in enumerate(content):
        codepoint = ord(char)
        if codepoint == 9 or codepoint == 10:
            continue
        if codepoint == 13 and index + 1 < len(content) and content[index + 1] == "\n":
            continue
        require(codepoint >= 32 and codepoint != 127, "OS manifest contains disallowed control characters")

    for line_number, line in enumerate(lines, 1):
        if line.endswith("\r"):
            line = line[:-1]
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
    for key in sorted(REQUIRED_OS_SCALARS - {"PKG_MANAGER", "USE_SYSTEM_PACKAGES"}):
        require_string(scalars[key], key)
    repositories = arrays["REQUIRED_REPOS"]
    require(len(repositories) == len(set(repositories)), "REQUIRED_REPOS must not contain duplicate entries")
    for index, repository in enumerate(repositories):
        validate_https_url(repository, f"REQUIRED_REPOS[{index}]")
    return scalars, arrays


def validate_os_manifest(path: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ValidationError(str(exc)) from exc
    return validate_os_manifest_content(path, content)


CatalogEntry = tuple[Path, int, str, os.stat_result]


def catalog_paths(directory: Path, suffix: str, root: Path, errors: list[str]) -> tuple[int | None, list[CatalogEntry]]:
    try:
        directory_fd = os.open(
            directory,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
    except OSError:
        if directory.is_symlink():
            errors.append(f"{directory.relative_to(root)}: symlinks are not allowed")
        else:
            errors.append(f"{directory.relative_to(root)}: directory is missing")
        return None, []

    entries: list[CatalogEntry] = []
    try:
        names = sorted(os.listdir(directory_fd))
        for name in names:
            path = directory / name
            relative = path.relative_to(root)
            try:
                metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError:
                errors.append(f"{relative}: catalog entry cannot be inspected")
                continue
            if stat.S_ISLNK(metadata.st_mode):
                errors.append(f"{relative}: symlinks are not allowed")
            elif not stat.S_ISREG(metadata.st_mode):
                errors.append(f"{relative}: unexpected catalog entry")
            elif name == ".gitkeep":
                continue
            elif not name.endswith(suffix):
                errors.append(f"{relative}: unexpected catalog entry")
            elif suffix == ".env" and OS_FILENAME_RE.fullmatch(name) is None:
                errors.append(f"{relative}: filename must match <os_id>-<os_version>.env")
            else:
                entries.append((path, directory_fd, name, metadata))
    except BaseException:
        os.close(directory_fd)
        raise
    return directory_fd, entries


def read_catalog_entry(entry: CatalogEntry, max_bytes: int | None = None) -> bytes:
    path, directory_fd, name, expected = entry
    try:
        file_fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd)
    except OSError as exc:
        raise ValidationError(f"cannot open catalog entry: {exc}") from exc
    try:
        actual = os.fstat(file_fd)
        require(
            stat.S_ISREG(actual.st_mode)
            and (actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino),
            "catalog entry changed during validation",
        )
        chunks: list[bytes] = []
        total = 0
        while True:
            size = 65536 if max_bytes is None else min(65536, max_bytes + 1 - total)
            chunk = os.read(file_fd, size)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                raise ValidationError(f"file exceeds aggregate limit of {max_bytes} bytes")
        return b"".join(chunks)
    except OSError as exc:
        raise ValidationError(f"cannot read catalog entry: {exc}") from exc
    finally:
        os.close(file_fd)


def validate_catalog(root: Path = ROOT, allow_empty: bool = False) -> list[str]:
    errors: list[str] = []
    release_fd, release_entries = catalog_paths(root / "releases", ".json", root, errors)
    manifest_fd, manifest_entries = catalog_paths(root / "manifests", ".env", root, errors)
    try:
        if not allow_empty:
            if not release_entries:
                errors.append("releases: at least one release manifest is required")
            if not manifest_entries:
                errors.append("manifests: at least one OS manifest is required")
        for entry in release_entries:
            path = entry[0]
            try:
                validate_release_content(path, read_catalog_entry(entry))
            except ValidationError as exc:
                errors.append(f"{path.relative_to(root)}: {exc}")
        for entry in manifest_entries:
            path = entry[0]
            try:
                validate_os_manifest_content(path, read_catalog_entry(entry, MAX_OS_TOTAL_BYTES))
            except ValidationError as exc:
                errors.append(f"{path.relative_to(root)}: {exc}")
    finally:
        for directory_fd in (release_fd, manifest_fd):
            if directory_fd is not None:
                os.close(directory_fd)
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
