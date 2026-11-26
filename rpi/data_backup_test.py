import tempfile, pathlib, tarfile, io, unittest
import data_backup as b
class BackupTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td);d=p/"data";d.mkdir();(d/"library").mkdir()
            (d/"library"/"test.nam").write_text("example");(d/"presets.json").write_text("{}")
            (d/"tone3000-session.json").write_text("secret")
            a=p/"backup.tar.gz";self.assertEqual(b.backup(d,a),2)
            (d/"library"/"test.nam").write_text("changed")
            n,old,_=b.restore(d,a);self.assertEqual(n,2)
            self.assertEqual((d/"library"/"test.nam").read_text(),"example")
            self.assertEqual((old/"library"/"test.nam").read_text(),"changed")
            self.assertFalse((d/"tone3000-session.json").exists())
    def test_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td);a=p/"bad.tar.gz";d=p/"data";d.mkdir()
            (d/"settings.json").write_text("{}")
            with tarfile.open(a,"w:gz") as t:
                m=tarfile.TarInfo("../escape");m.size=1;t.addfile(m,io.BytesIO(b"x"))
            with self.assertRaises(ValueError):b.restore(d,a)
            self.assertTrue((d/"settings.json").exists())
    def test_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td);d=p/"data";d.mkdir();(d/"settings.json").write_text("{}")
            a=p/"backup.tar.gz";b.backup(d,a);(d/"settings.json").write_text('{"old":true}')
            def fail():raise ValueError("controller invalid")
            with self.assertRaises(ValueError):b.restore(d,a,fail)
            self.assertEqual((d/"settings.json").read_text(),'{"old":true}')
if __name__=="__main__":unittest.main()
