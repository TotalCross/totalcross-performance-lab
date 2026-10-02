import io
import hashlib
import json
import shutil
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest import mock

from tools.datasets import image_scroll


JPEG = b"\xff\xd8\xffsynthetic-jpeg"
PNG = b"\x89PNG\r\n\x1a\nsynthetic-png"


def digest(data):
    return hashlib.sha256(data).hexdigest()


class DatasetFixture:
    def __init__(self, root, traversal=False):
        self.root = Path(root)
        self.work = self.root / "source"
        self.work.mkdir(parents=True)
        self.archive = self.work / "totalcross-image-scroll-v1.zip"
        self.manifest = self.work / "manifest.json"
        self.sums = self.work / "SHA256SUMS"
        files = [
            {"path": "photo.jpg", "bytes": len(JPEG), "sha256": digest(JPEG)},
            {"path": "graphics/data.bin", "bytes": len(PNG), "sha256": digest(PNG)},
        ]
        manifest = {
            "dataset": "image-scroll",
            "version": "v1",
            "fileCount": 2,
            "files": files,
        }
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            zipped.writestr(files[0]["path"], JPEG)
            zipped.writestr(files[1]["path"], PNG)
            if traversal:
                zipped.writestr("../escape.bin", b"escape")
        archive_hash = digest(self.archive.read_bytes())
        manifest_hash = digest(self.manifest.read_bytes())
        self.sums.write_text(
            archive_hash + "  totalcross-image-scroll-v1.zip\n"
            + manifest_hash + "  manifest.json\n",
            encoding="ascii",
        )
        self.descriptor = {
            "id": "image-scroll",
            "version": "v1",
            "expectedFileCount": 2,
            "historicalFormatCounts": {"jpeg": 1, "png": 1},
            "integrity": {"archiveSha256": archive_hash, "manifestSha256": manifest_hash},
            "artifacts": {
                "archive": "https://example.invalid/totalcross-image-scroll-v1.zip",
                "manifest": "https://example.invalid/manifest.json",
                "sha256sums": "https://example.invalid/SHA256SUMS",
            },
        }
        self.descriptor_path = self.root / "datasets/image-scroll/v1/dataset.json"
        self.descriptor_path.parent.mkdir(parents=True)
        self.descriptor_path.write_text(json.dumps(self.descriptor), encoding="utf-8")


class DatasetToolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_download_retries_403_with_cache_busted_url(self):
        calls = []

        def fake_urlopen(request, timeout):
            calls.append(request.get_full_url())
            if len(calls) == 1:
                raise urllib.error.HTTPError(calls[-1], 403, "Access Denied", None, io.BytesIO(b"denied"))
            return io.BytesIO(b"updated object")

        destination = self.root / "download.bin"
        with mock.patch.object(image_scroll.urllib.request, "urlopen", side_effect=fake_urlopen):
            image_scroll.download("https://example.invalid/object?version=1", destination)

        self.assertEqual("https://example.invalid/object?version=1", calls[0])
        self.assertIn("version=1", calls[1])
        self.assertIn("cache_bust=", calls[1])
        self.assertEqual(b"updated object", destination.read_bytes())

    def test_sha_manifest_and_content_derived_formats(self):
        fixture = DatasetFixture(self.root)
        sums = image_scroll.parse_sums(fixture.sums)
        self.assertEqual(fixture.descriptor["integrity"]["archiveSha256"], sums["totalcross-image-scroll-v1.zip"])
        extracted = self.root / "payload"
        result = image_scroll.validate_archive(fixture.archive, fixture.manifest, fixture.descriptor, extracted)
        self.assertEqual({"jpeg": 1, "png": 1}, result["formatCounts"])
        self.assertEqual(PNG, (extracted / "graphics/data.bin").read_bytes())

    def test_rejects_absolute_and_parent_paths(self):
        for value in ("/tmp/file.jpg", "../escape.jpg", "images/../../escape.jpg", "C:/escape.jpg", "\\\\host\\share"):
            with self.subTest(value=value), self.assertRaises(image_scroll.DatasetError):
                image_scroll.safe_relative_path(value)

    def test_rejects_traversal_entry_in_zip(self):
        fixture = DatasetFixture(self.root, traversal=True)
        with self.assertRaisesRegex(image_scroll.DatasetError, "unsafe path|unlisted file"):
            image_scroll.validate_archive(
                fixture.archive, fixture.manifest, fixture.descriptor, self.root / "payload"
            )

    def test_rejects_missing_archive_file(self):
        fixture = DatasetFixture(self.root)
        with zipfile.ZipFile(fixture.archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            zipped.writestr("photo.jpg", JPEG)
        fixture.descriptor["integrity"]["archiveSha256"] = digest(fixture.archive.read_bytes())
        with self.assertRaisesRegex(image_scroll.DatasetError, "missing manifest files"):
            image_scroll.validate_archive(
                fixture.archive, fixture.manifest, fixture.descriptor, self.root / "payload"
            )

    def test_rejects_unlisted_archive_file(self):
        fixture = DatasetFixture(self.root)
        with zipfile.ZipFile(fixture.archive, "a", zipfile.ZIP_DEFLATED) as zipped:
            zipped.writestr("unexpected.bin", b"extra")
        fixture.descriptor["integrity"]["archiveSha256"] = digest(fixture.archive.read_bytes())
        with self.assertRaisesRegex(image_scroll.DatasetError, "unlisted file"):
            image_scroll.validate_archive(
                fixture.archive, fixture.manifest, fixture.descriptor, self.root / "payload"
            )

    def test_rejects_duplicate_manifest_paths(self):
        fixture = DatasetFixture(self.root)
        manifest = json.loads(fixture.manifest.read_text(encoding="utf-8"))
        manifest["files"].append(dict(manifest["files"][0]))
        manifest["fileCount"] = 3
        fixture.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        fixture.descriptor["integrity"]["manifestSha256"] = digest(fixture.manifest.read_bytes())
        with self.assertRaisesRegex(image_scroll.DatasetError, "duplicate path"):
            image_scroll.manifest_entries(manifest, fixture.descriptor)

    def test_fetch_cache_is_idempotent(self):
        fixture = DatasetFixture(self.root)
        cache = self.root / ".local-data/image-scroll/v1"
        objects = {
            fixture.descriptor["artifacts"]["sha256sums"]: fixture.sums,
            fixture.descriptor["artifacts"]["manifest"]: fixture.manifest,
            fixture.descriptor["artifacts"]["archive"]: fixture.archive,
        }
        calls = []

        def fake_download(url, destination):
            calls.append(url)
            shutil.copyfile(objects[url], destination)

        with mock.patch.object(image_scroll, "download", side_effect=fake_download):
            first = image_scroll.fetch(self.root, fixture.descriptor, cache, force=False)
            second = image_scroll.fetch(self.root, fixture.descriptor, cache, force=False)
        self.assertEqual(3, len(calls))
        self.assertEqual(first, second)
        self.assertEqual(2, len(list((cache / "files").rglob("*.*"))))

    def test_verify_rejects_extra_extracted_file(self):
        fixture = DatasetFixture(self.root)
        cache = self.root / ".local-data/image-scroll/v1"
        objects = {
            fixture.descriptor["artifacts"]["sha256sums"]: fixture.sums,
            fixture.descriptor["artifacts"]["manifest"]: fixture.manifest,
            fixture.descriptor["artifacts"]["archive"]: fixture.archive,
        }
        with mock.patch.object(image_scroll, "download", side_effect=lambda url, path: shutil.copyfile(objects[url], path)):
            image_scroll.fetch(self.root, fixture.descriptor, cache, force=False)
        (cache / "files/extra.jpg").write_bytes(JPEG)
        with self.assertRaisesRegex(image_scroll.DatasetError, "extra"):
            image_scroll.verify_cache(cache, fixture.descriptor)

    def test_corrupt_download_fails_without_installing_partial_cache(self):
        fixture = DatasetFixture(self.root)
        cache = self.root / ".local-data/image-scroll/v1"
        objects = {
            fixture.descriptor["artifacts"]["sha256sums"]: fixture.sums,
            fixture.descriptor["artifacts"]["manifest"]: fixture.manifest,
            fixture.descriptor["artifacts"]["archive"]: fixture.archive,
        }

        def corrupt_download(url, destination):
            shutil.copyfile(objects[url], destination)
            if url == fixture.descriptor["artifacts"]["archive"]:
                destination.write_bytes(b"corrupt")

        with mock.patch.object(image_scroll, "download", side_effect=corrupt_download):
            with self.assertRaisesRegex(image_scroll.DatasetError, "SHA-256 mismatch"):
                image_scroll.fetch(self.root, fixture.descriptor, cache, force=False)
        self.assertFalse(cache.exists())

    def test_rejects_manifest_count_mismatch(self):
        fixture = DatasetFixture(self.root)
        fixture.descriptor["expectedFileCount"] = 3
        with self.assertRaisesRegex(image_scroll.DatasetError, "expected file count"):
            image_scroll.manifest_entries(image_scroll.read_json(fixture.manifest), fixture.descriptor)

    def test_descriptor_requires_pinned_hashes(self):
        fixture = DatasetFixture(self.root)
        fixture.descriptor.pop("integrity")
        fixture.descriptor_path.write_text(json.dumps(fixture.descriptor), encoding="utf-8")
        with self.assertRaisesRegex(image_scroll.DatasetError, "pinned integrity"):
            image_scroll.load_descriptor(self.root, "image-scroll/v1")


if __name__ == "__main__":
    unittest.main()
