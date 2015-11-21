import unittest
from grenier.helpers import *
from grenier.grenier import Grenier


class TestClass(unittest.TestCase):

    def setUp(self):
        self.grenier = Grenier(Path("test_files", "test.yaml"))

    def tearDown(self):
        del self.grenier

    def test_open_config(self):
        self.assertTrue(self.grenier.open_config())
        self.assertIsNotNone(self.grenier.repositories)
        self.assertEqual(len(self.grenier.repositories), 1)

        # repositories
        test_repo = self.grenier.repositories[0]
        self.assertEqual(test_repo.name, "test1")
        self.assertEqual(test_repo.backup_dir, Path("test_files/backup/bup_test1"))
        self.assertTrue(test_repo.backup_dir.exists())
        self.assertEqual(test_repo.passphrase, "test1_passphrase")

        # sources
        self.assertEqual(len(test_repo.sources), 2)
        for source in test_repo.sources:
            self.assertIn(source.name, ["folder1", "folder2"])
            if source.name == "folder1":
                self.assertEqual(source.target_dir, Path("test_files/folder1"))
                self.assertListEqual(source.excluded_extensions, ["ignored"])
            else:
                self.assertEqual(source.target_dir, Path("test_files/folder2"))
                self.assertListEqual(source.excluded_extensions, [])

        # remotes
        self.assertEqual(len(test_repo.remotes), 3)

    def test_save(self):
        pass

    def test_sync_to_disk(self):
        pass

    def test_sync_to_gdrive(self):
        pass

    def test_sync_to_hubic(self):
        pass

    def test_check(self):
        pass

    def test_fuse(self):
        pass

    def test_restore(self):
        pass

if __name__ == '__main__':
    unittest.main()
