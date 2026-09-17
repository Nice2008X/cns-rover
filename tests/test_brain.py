import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from cns_car.brain import safe_unpack, sha256, verify_directory


class AssetTests(unittest.TestCase):
    def test_reject_path_traversal_and_links(self):
        for name, link in (("../escape", False), ("/absolute", False), ("link", True)):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                archive = root/"bad.tar.gz"
                with tarfile.open(archive, "w:gz") as tar:
                    item = tarfile.TarInfo(name)
                    if link:
                        item.type = tarfile.SYMTYPE
                        item.linkname = "/tmp"
                        tar.addfile(item)
                    else:
                        item.size = 1
                        tar.addfile(item, io.BytesIO(b"x"))
                with self.assertRaises(ValueError):
                    safe_unpack(archive, root/"output")
                self.assertFalse((root/"output").exists())

    def test_detect_modified_asset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/"asset").write_bytes(b"original")
            (root/"manifest.json").write_text(json.dumps({"files": {"asset": sha256(root/"asset")}}))
            verify_directory(root)
            (root/"asset").write_bytes(b"modified")
            with self.assertRaises(ValueError):
                verify_directory(root)

    def test_regular_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root/"good.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                item = tarfile.TarInfo("nested/test")
                item.size = 2
                tar.addfile(item, io.BytesIO(b"ok"))
            safe_unpack(archive, root/"output")
            self.assertEqual((root/"output/nested/test").read_bytes(), b"ok")
