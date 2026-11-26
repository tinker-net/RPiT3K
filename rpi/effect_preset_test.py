"""Effect preset migration, persistence and native effective values."""
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from io import StringIO
from server import Controller, DEFAULT, FX_DEFAULT_AMOUNTS, normalize_fx

class FXTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.c=Controller.__new__(Controller)
        self.c.presets={"1":dict(DEFAULT)}
        self.c.statefile=Path(self.tmp.name)/"presets.json"
        self.c.active="1"
        self.c.proc=SimpleNamespace(poll=lambda:None,stdin=StringIO())
    def test_legacy(self):
        for k,default in FX_DEFAULT_AMOUNTS.items():
            self.assertEqual(normalize_fx({k:.71})[k+"_amount"],.71)
            self.assertEqual(normalize_fx({k:0})[k+"_amount"],default)
    def test_bypass_restore(self):
        for k in FX_DEFAULT_AMOUNTS:
            p=dict(DEFAULT);p[k]=0;p[k+"_amount"]=.67
            p=self.c.validate(p)
            self.assertEqual(p[k],0)
            self.assertEqual(p[k+"_amount"],.67)
            p[k]=p[k+"_amount"];p=self.c.validate(p)
            self.assertEqual(p[k],.67)
    def test_live_and_disk(self):
        import json
        p=dict(DEFAULT)
        for k in FX_DEFAULT_AMOUNTS:p[k]=0;p[k+"_amount"]=.73
        self.c.live_controls("1",p)
        lines=self.c.proc.stdin.getvalue().splitlines()
        self.assertEqual(len(lines),2)
        self.assertEqual(lines[0],"STOMP 1")
        self.assertEqual(len(list(map(float,lines[1].split()))),20)
        saved=json.loads(self.c.statefile.read_text())["1"]
        for k in FX_DEFAULT_AMOUNTS:
            self.assertEqual(saved[k],0);self.assertEqual(saved[k+"_amount"],.73)
        for k in FX_DEFAULT_AMOUNTS:p[k]=.73
        p["nam1_enabled"]=False
        self.c.live_controls("1",p)
        lines=self.c.proc.stdin.getvalue().splitlines()
        self.assertEqual(len(lines),4)
        self.assertEqual(lines[2],"STOMP 0")
        self.assertFalse(json.loads(self.c.statefile.read_text())["1"]["nam1_enabled"])
        values=list(map(float,lines[3].split()))
        self.assertEqual(len(values),20)
        for i in (6,8,14,17):self.assertAlmostEqual(values[i],.73)
    def test_physical_stomp(self):
        import json
        self.c.file=lambda *args: self.statefile
        self.statefile.touch()
        self.c.settings={"last":"1"}
        self.c.presets["1"].update(model="drive.nam",second="amp.nam",bypass=False)
        before=dict(self.c.presets["1"])
        self.c.toggle_stomp()
        self.assertEqual(self.c.proc.stdin.getvalue(),"STOMP 0\n")
        self.assertEqual(self.c.presets["1"],dict(before,nam1_enabled=False))
        self.assertFalse(json.loads(self.c.statefile.read_text())["1"]["nam1_enabled"])
        self.c.toggle_stomp()
        self.assertEqual(self.c.proc.stdin.getvalue(),"STOMP 0\nSTOMP 1\n")
        self.assertEqual(self.c.presets["1"],before)
    def test_physical_stomp_audio_off(self):
        self.c.file=lambda *args: self.statefile
        self.statefile.touch()
        self.c.settings={"last":"1"}
        self.c.presets["1"].update(model="drive.nam",bypass=False)
        self.c.proc=None
        self.c.active=None
        self.c.toggle_stomp()
        self.assertFalse(self.c.presets["1"]["nam1_enabled"])
        self.assertIsNone(self.c.proc)
    def test_physical_stomp_without_capture(self):
        self.c.settings={"last":"1"}
        with self.assertRaises(ValueError):self.c.toggle_stomp()
        self.assertEqual(self.c.proc.stdin.getvalue(),"")
    def test_physical_preset_cycle_audio_off(self):
        self.c.presets={str(i):dict(DEFAULT) for i in range(1,5)}
        self.c.settings={"last":"1"}
        self.c.proc=None
        self.c.active=None
        self.c.tuner_return=None
        self.c.persist_settings=Mock()
        for expected in ("2","3","4","1"):
            self.c.next_preset()
            self.assertEqual(self.c.settings["last"],expected)
            self.assertIsNone(self.c.proc)
    def test_bad_values(self):
        for value in (float("nan"),float("inf"),-1,2,".5",True,0):
            p=dict(DEFAULT,comp_amount=value)
            with self.assertRaises(ValueError):self.c.validate(p)
    def test_decay_legacy(self):
        self.assertEqual(self.c.validate(dict(DEFAULT,decay=.2))["decay"],.3)
if __name__=="__main__":unittest.main(verbosity=2)
