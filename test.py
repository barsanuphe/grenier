import unittest
from grenier.helpers import *
from grenier.grenier import Grenier


class TestClass(unittest.TestCase):

    def setUp(self):
        self.grenier = Grenier(Path("test_files", "test.yaml"))

    def tearDown(self):
        del self.grenier

    def test_1_open_config(self):
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

    def test_2_save(self):
        self.grenier.open_config()
        for r in self.grenier.repositories:
            number_of_files = r.backup(display=False)
            self.assertEqual(number_of_files, 5)
            repo_contents = [str(el) for el in r.backup_dir.rglob("*")]
            self.assertNotEqual(len(repo_contents), 0)

    def test_3_fuse(self):
        self.grenier.open_config()
        for r in self.grenier.repositories:
            r.fuse(str(r.temp_dir), display=False)
            fuse_contents = [str(el.relative_to(r.temp_dir)) for el in r.temp_dir.rglob("*")]
            self.assertNotEqual(len(fuse_contents), 0)
            for s in r.sources:
                self.assertTrue(s.name in fuse_contents)
                # verifying contents
                if s.name == "folder1":
                    self.assertTrue("folder1/latest/test1.txt" in fuse_contents)
                    self.assertFalse("folder1/latest/test2.ignored" in fuse_contents)
                if s.name == "folder2":
                    self.assertTrue("folder2/latest/test3.txt" in fuse_contents)
                    self.assertTrue("folder2/latest/test4.ignored" in fuse_contents)

    def test_4_unfuse(self):
        self.grenier.open_config()
        for r in self.grenier.repositories:
            r.unfuse(r.temp_dir, display=False)
            fuse_contents = [str(el) for el in r.temp_dir.rglob("*")]
            self.assertEqual(len(fuse_contents), 0)
            self.assertFalse(is_fuse_mounted(r.temp_dir))

    def test_sync_to_disk(self):
        pass

    def test_sync_to_gdrive(self):
        pass

    def test_sync_to_hubic(self):
        pass

    def test_check(self):
        pass



    def test_restore(self):
        pass

if __name__ == '__main__':
    unittest.main()
