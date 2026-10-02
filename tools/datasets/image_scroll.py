#!/usr/bin/env python3
"""Fetch and verify the immutable image-scroll/v1 dataset using stdlib only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
HEX_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
FORMATS = {"jpeg": (b"\xff\xd8\xff",), "png": (b"\x89PNG\r\n\x1a\n",)}
OBJECT_NAMES = ("SHA256SUMS", "manifest.json", "totalcross-image-scroll-v1.zip")


class DatasetError(Exception):
    """A dataset descriptor, download, archive, or payload failed validation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DatasetError("cannot read JSON file: " + str(path)) from error
    if not isinstance(value, dict):
        raise DatasetError("expected a JSON object in " + str(path))
    return value


def load_descriptor(root: Path, dataset_ref: str) -> tuple[Path, dict[str, Any]]:
    parts = dataset_ref.split("/")
    if len(parts) != 2 or any(part in ("", ".", "..") for part in parts):
        raise DatasetError("dataset must be written as <id>/<version>")
    descriptor_path = root / "datasets" / parts[0] / parts[1] / "dataset.json"
    descriptor = read_json(descriptor_path)
    if descriptor.get("id") != parts[0] or descriptor.get("version") != parts[1]:
        raise DatasetError("dataset reference does not match its descriptor")
    artifacts = descriptor.get("artifacts")
    if not isinstance(artifacts, dict):
        raise DatasetError("dataset descriptor has no artifacts object")
    for key in ("archive", "manifest", "sha256sums"):
        if not isinstance(artifacts.get(key), str) or not artifacts[key].startswith("https://"):
            raise DatasetError("dataset descriptor has no HTTPS artifact URL: " + key)
    integrity = descriptor.get("integrity")
    if not isinstance(integrity, dict):
        raise DatasetError("dataset descriptor has no pinned integrity metadata")
    for key in ("archiveSha256", "manifestSha256"):
        if not isinstance(integrity.get(key), str) or not HEX_SHA256.fullmatch(integrity[key]):
            raise DatasetError("dataset descriptor has no valid pinned " + key)
    if not isinstance(descriptor.get("expectedFileCount"), int):
        raise DatasetError("dataset descriptor has no expectedFileCount")
    expected_formats = descriptor.get("historicalFormatCounts")
    if not isinstance(expected_formats, dict) or not expected_formats:
        raise DatasetError("dataset descriptor has no historicalFormatCounts")
    return descriptor_path, descriptor


def safe_relative_path(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise DatasetError("manifest contains an invalid relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or re.match(r"^[A-Za-z]:", value) or any(part in ("", ".", "..") for part in path.parts):
        raise DatasetError("manifest contains an unsafe path: " + value)
    return path


def detect_format(path: Path) -> str:
    with path.open("rb") as stream:
        header = stream.read(8)
    for name, signatures in FORMATS.items():
        if any(header.startswith(signature) for signature in signatures):
            return name
    return "other"


def manifest_entries(manifest: dict[str, Any], descriptor: dict[str, Any], enforce_expected: bool = True) -> dict[str, dict[str, Any]]:
    raw_entries = manifest.get("files")
    if not isinstance(raw_entries, list):
        raise DatasetError("manifest must contain a files array")
    entries: dict[str, dict[str, Any]] = {}
    for item in raw_entries:
        if not isinstance(item, dict):
            raise DatasetError("manifest files must be objects")
        relative = safe_relative_path(item.get("path"))
        name = relative.as_posix()
        size = item.get("bytes")
        digest = item.get("sha256")
        if not isinstance(size, int) or size < 0 or not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest):
            raise DatasetError("invalid size or SHA-256 for " + name)
        if name in entries:
            raise DatasetError("manifest contains a duplicate path: " + name)
        entries[name] = {"path": relative, "bytes": size, "sha256": digest.lower()}
    count = manifest.get("fileCount", len(entries))
    expected_count = descriptor["expectedFileCount"]
    if count != len(entries):
        raise DatasetError("manifest file count does not match its entries: manifest=" + str(count)
                           + ", entries=" + str(len(entries)))
    if enforce_expected and count != expected_count:
        raise DatasetError("published manifest disagrees with expected file count: actual=" + str(count)
                           + ", expected=" + str(expected_count))
    return entries


def parse_sums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as error:
        raise DatasetError("cannot read SHA256SUMS") from error
    hashes: dict[str, str] = {}
    for line in lines:
        pieces = line.strip().split()
        if not line.strip():
            continue
        if len(pieces) != 2 or not HEX_SHA256.fullmatch(pieces[0]):
            raise DatasetError("malformed SHA256SUMS entry")
        name = PurePosixPath(pieces[1].lstrip("*"))
        if name.is_absolute() or ".." in name.parts:
            raise DatasetError("unsafe filename in SHA256SUMS")
        key = name.name
        if key in hashes:
            raise DatasetError("duplicate SHA256SUMS object: " + key)
        hashes[key] = pieces[0].lower()
    return hashes


def validate_archive(archive: Path, manifest_path: Path, descriptor: dict[str, Any], destination: Path) -> dict[str, Any]:
    integrity = descriptor["integrity"]
    if sha256_file(archive) != integrity["archiveSha256"].lower():
        raise DatasetError("archive SHA-256 does not match the pinned descriptor")
    if sha256_file(manifest_path) != integrity["manifestSha256"].lower():
        raise DatasetError("manifest SHA-256 does not match the pinned descriptor")
    manifest = read_json(manifest_path)
    if manifest.get("dataset") not in (None, descriptor["id"]) or manifest.get("id") not in (None, descriptor["id"]):
        raise DatasetError("manifest dataset id does not match the descriptor")
    if manifest.get("version") not in (None, descriptor["version"]):
        raise DatasetError("manifest version does not match the descriptor")
    entries = manifest_entries(manifest, descriptor, enforce_expected=False)
    expected_formats = {str(key).lower(): int(value) for key, value in descriptor["historicalFormatCounts"].items()}
    seen: set[str] = set()
    counts = {key: 0 for key in expected_formats}
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(archive) as zipped:
            for info in zipped.infolist():
                raw_name = info.filename
                if raw_name.endswith("/"):
                    safe_relative_path(raw_name[:-1])
                    continue
                relative = safe_relative_path(raw_name)
                name = relative.as_posix()
                if name in seen:
                    raise DatasetError("archive contains a duplicate file: " + name)
                seen.add(name)
                entry = entries.get(name)
                if entry is None:
                    raise DatasetError("archive contains an unlisted file: " + name)
                mode = (info.external_attr >> 16) & 0xFFFF
                file_type = stat.S_IFMT(mode)
                if file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise DatasetError("archive contains a non-regular file: " + name)
                if info.file_size != entry["bytes"]:
                    raise DatasetError("archive size differs from manifest: " + name)
                output = destination.joinpath(*relative.parts)
                try:
                    output.resolve().relative_to(destination.resolve())
                except ValueError:
                    raise DatasetError("archive path escapes the extraction directory: " + name)
                output.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                written = 0
                with zipped.open(info) as source, output.open("xb") as target:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        digest.update(chunk)
                        target.write(chunk)
                if written != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
                    raise DatasetError("extracted payload differs from manifest: " + name)
                detected = detect_format(output)
                counts[detected] = counts.get(detected, 0) + 1
        if seen != set(entries):
            missing = sorted(set(entries) - seen)
            raise DatasetError("archive is missing manifest files: " + ", ".join(missing[:5]))
        expected_count = descriptor["expectedFileCount"]
        if len(entries) != expected_count or counts != expected_formats:
            raise DatasetError("published dataset disagrees with expected shape: files=" + str(len(entries))
                               + " (expected " + str(expected_count) + "), content-derived formatCounts="
                               + repr(counts) + " (expected " + repr(expected_formats) + ")")
        return {"fileCount": len(entries), "formatCounts": counts, "manifestSha256": integrity["manifestSha256"].lower()}
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise DatasetError("cannot safely extract dataset archive: " + str(error)) from error
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def verify_cache(cache: Path, descriptor: dict[str, Any]) -> dict[str, Any]:
    objects = cache / "objects"
    sums = parse_sums(objects / "SHA256SUMS")
    expected = {
        "manifest.json": descriptor["integrity"]["manifestSha256"].lower(),
        "totalcross-image-scroll-v1.zip": descriptor["integrity"]["archiveSha256"].lower(),
    }
    for name, digest in expected.items():
        path = objects / name
        if sums.get(name) != digest:
            raise DatasetError("SHA256SUMS identity differs from descriptor for " + name)
        if not path.is_file() or sha256_file(path) != digest:
            raise DatasetError("cached artifact is missing or corrupt: " + name)
    payload = cache / "files"
    temporary = Path(tempfile.mkdtemp(prefix="verify-image-scroll-"))
    extracted = temporary / "files"
    try:
        result = validate_archive(objects / "totalcross-image-scroll-v1.zip", objects / "manifest.json", descriptor, extracted)
        actual = {path.relative_to(payload).as_posix() for path in payload.rglob("*") if path.is_file()}
        expected_paths = {item["path"].as_posix() for item in manifest_entries(read_json(objects / "manifest.json"), descriptor).values()}
        if actual != expected_paths or any(path.is_symlink() for path in payload.rglob("*")):
            raise DatasetError("cached extracted files are missing, extra, or symlinked")
        for name in expected_paths:
            if sha256_file(payload / name) != sha256_file(extracted / name):
                raise DatasetError("cached extracted payload is corrupt: " + name)
        return result
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "totalcross-performance-lab/1"})
    try:
        try:
            response = urllib.request.urlopen(request, timeout=60)
        except urllib.error.HTTPError as error:
            if error.code != 403:
                raise
            error.close()
            parts = urllib.parse.urlsplit(url)
            query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
            query.append(("cache_bust", str(time.time_ns())))
            retry_url = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))
            retry = urllib.request.Request(retry_url, headers={"User-Agent": "totalcross-performance-lab/1"})
            response = urllib.request.urlopen(retry, timeout=60)
        with response, destination.open("xb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
    except Exception as error:
        raise DatasetError("download failed for " + url + ": " + str(error)) from error


def fetch(root: Path, descriptor: dict[str, Any], cache: Path, force: bool) -> dict[str, Any]:
    if cache.exists() and not force:
        return verify_cache(cache, descriptor)
    parent = cache.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".image-scroll-v1-", dir=parent))
    try:
        objects = staging / "objects"
        objects.mkdir()
        artifacts = descriptor["artifacts"]
        download(artifacts["sha256sums"], objects / "SHA256SUMS")
        hashes = parse_sums(objects / "SHA256SUMS")
        required = {
            "manifest.json": descriptor["integrity"]["manifestSha256"].lower(),
            "totalcross-image-scroll-v1.zip": descriptor["integrity"]["archiveSha256"].lower(),
        }
        for filename, url_key in (("manifest.json", "manifest"), ("totalcross-image-scroll-v1.zip", "archive")):
            if hashes.get(filename) != required[filename]:
                raise DatasetError("published SHA256SUMS does not match pinned " + filename)
            download(artifacts[url_key], objects / filename)
            if sha256_file(objects / filename) != required[filename]:
                raise DatasetError("downloaded artifact SHA-256 mismatch: " + filename)
        staging_files = staging / "files"
        result = validate_archive(objects / "totalcross-image-scroll-v1.zip", objects / "manifest.json", descriptor, staging_files)
        if cache.exists():
            backup = cache.with_name(cache.name + ".previous-" + str(os.getpid()))
            os.replace(cache, backup)
        os.replace(staging, cache)
        return result
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fetch", "verify"))
    parser.add_argument("dataset", help="versioned dataset reference, for example image-scroll/v1")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--cache-dir", type=Path, help="override ignored local dataset cache")
    parser.add_argument("--force", action="store_true", help="download a new copy even when cache validates")
    arguments = parser.parse_args(argv)
    try:
        _, descriptor = load_descriptor(arguments.root.resolve(), arguments.dataset)
        cache = arguments.cache_dir or arguments.root / ".local-data" / "datasets" / descriptor["id"] / descriptor["version"]
        cache = cache.resolve()
        if arguments.action == "verify":
            result = verify_cache(cache, descriptor)
        else:
            result = fetch(arguments.root.resolve(), descriptor, cache, arguments.force)
        print(json.dumps({"status": "ok", "dataset": arguments.dataset, **result}, sort_keys=True))
        return 0
    except DatasetError as error:
        print("dataset error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
