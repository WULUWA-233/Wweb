import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse

from app import create_app
from import_data import import_all
from import_images import ImageImportError, import_images


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "platform_image_manifest.csv"
STATIC_ROOT = ROOT / "static"


class ImageImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp.name)
        self.db_path = self.temp_root / "test.sqlite3"
        import_all(self.db_path)

    def tearDown(self):
        self.temp.cleanup()

    def _read_manifest(self):
        with MANIFEST.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            return list(reader.fieldnames or ()), list(reader)

    def _write_changed_manifest(self, filename, change_last_row):
        fieldnames, rows = self._read_manifest()
        self.assertEqual(len(rows), 22)
        change_last_row(rows[-1])
        path = self.temp_root / filename
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _image_rows(self):
        db = sqlite3.connect(self.db_path)
        try:
            return db.execute(
                "SELECT i.id, p.name, i.local_path, i.source_url, i.source_name, "
                "i.is_primary FROM platform_images i "
                "JOIN platforms p ON p.id = i.platform_id ORDER BY p.id, i.id"
            ).fetchall()
        finally:
            db.close()

    def _reject_any_image_write(self):
        """Make validation-order regressions observable, not just rollback-safe."""
        db = sqlite3.connect(self.db_path)
        try:
            db.execute(
                "CREATE TRIGGER reject_unvalidated_image_write "
                "BEFORE INSERT ON platform_images "
                "BEGIN SELECT RAISE(ABORT, 'image write began before validation finished'); END"
            )
            db.commit()
        finally:
            db.close()

    def test_imports_one_primary_local_image_for_every_platform(self):
        stats = import_images(
            db_path=self.db_path,
            manifest_path=MANIFEST,
            static_root=STATIC_ROOT,
        )

        self.assertIsInstance(stats, dict)
        self.assertTrue({"inserted", "updated", "total"}.issubset(stats))
        self.assertEqual(stats["inserted"], 22)
        self.assertEqual(stats["total"], 22)

        rows = self._image_rows()
        self.assertEqual(len(rows), 22)
        self.assertEqual(len({row[1] for row in rows}), 22)
        static_root = STATIC_ROOT.resolve()
        for _image_id, platform_name, local_path, source_url, source_name, is_primary in rows:
            with self.subTest(platform=platform_name):
                self.assertEqual(is_primary, 1)
                self.assertTrue(local_path)
                asset_path = (STATIC_ROOT / local_path).resolve()
                self.assertEqual(asset_path, static_root / Path(local_path))
                self.assertTrue(asset_path.is_file(), asset_path)
                parsed = urlparse(source_url or "")
                self.assertEqual(parsed.scheme, "https")
                self.assertTrue(parsed.netloc)
                self.assertTrue(source_name)

        db = sqlite3.connect(self.db_path)
        try:
            per_platform = db.execute(
                "SELECT platform_id, COUNT(*), SUM(is_primary) "
                "FROM platform_images GROUP BY platform_id ORDER BY platform_id"
            ).fetchall()
        finally:
            db.close()
        self.assertEqual(len(per_platform), 22)
        self.assertTrue(all(count == 1 and primary_count == 1 for _, count, primary_count in per_platform))

        app = create_app({"TESTING": True, "DATABASE": str(self.db_path)})
        client = app.test_client()
        home = client.get("/")
        self.assertEqual(home.status_code, 200)
        for _image_id, _name, local_path, *_rest in rows:
            self.assertIn(f"/static/{local_path}", home.get_data(as_text=True))
        expected_types = {
            "platform-001.webp": "image/webp",
            "platform-002.avif": "image/avif",
            "platform-005.jpg": "image/jpeg",
        }
        for filename, content_type in expected_types.items():
            with self.subTest(filename=filename):
                response = client.get(f"/static/img/platforms/{filename}")
                try:
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.content_type, content_type)
                finally:
                    response.close()

    def test_repeat_import_is_idempotent_and_keeps_image_ids(self):
        first = import_images(self.db_path, MANIFEST, STATIC_ROOT)
        before = {name: image_id for image_id, name, *_rest in self._image_rows()}

        second = import_images(self.db_path, MANIFEST, STATIC_ROOT)
        after = {name: image_id for image_id, name, *_rest in self._image_rows()}

        self.assertEqual(first["total"], 22)
        self.assertEqual(second["total"], 22)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(before, after)
        self.assertEqual(len(after), 22)

    def test_missing_local_file_fails_without_partial_rows(self):
        manifest = self._write_changed_manifest(
            "missing-file.csv",
            lambda row: row.__setitem__(
                "local_path", "img/platforms/definitely-missing-image-for-test.jpg"
            ),
        )
        self._reject_any_image_write()

        with self.assertRaises((ImageImportError, FileNotFoundError)):
            import_images(self.db_path, manifest, STATIC_ROOT)

        self.assertEqual(self._image_rows(), [])

    def test_unknown_platform_fails_without_partial_rows(self):
        manifest = self._write_changed_manifest(
            "unknown-platform.csv",
            lambda row: row.__setitem__(
                "platform_name", "__UNKNOWN_PLATFORM_FOR_IMAGE_IMPORT_TEST__"
            ),
        )
        self._reject_any_image_write()

        with self.assertRaises(ImageImportError):
            import_images(self.db_path, manifest, STATIC_ROOT)

        self.assertEqual(self._image_rows(), [])


if __name__ == "__main__":
    unittest.main()
