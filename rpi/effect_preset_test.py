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
        self.assertEqual(len(self.c.proc.stdin.getvalue().split()),20)
        saved=json.loads(self.c.statefile.read_text())["1"]
        for k in FX_DEFAULT_AMOUNTS:
            self.assertEqual(saved[k],0);self.assertEqual(saved[k+"_amount"],.73)
        for k in FX_DEFAULT_AMOUNTS:p[k]=.73
        self.c.live_controls("1",p)
        values=list(map(float,self.c.proc.stdin.getvalue().splitlines()[-1].split()))
        for i in (6,8,14,17):self.assertAlmostEqual(values[i],.73)
    def test_bad_values(self):
        for value in (float("nan"),float("inf"),-1,2,".5",True,0):
            p=dict(DEFAULT,comp_amount=value)
            with self.assertRaises(ValueError):self.c.validate(p)
    def test_decay_legacy(self):
        self.assertEqual(self.c.validate(dict(DEFAULT,decay=.2))["decay"],.3)
if __name__=="__main__":unittest.main(verbosity=2)
