import json
import threading
import unittest
from types import SimpleNamespace
from server import Controller

class ButtonStatusTest(unittest.TestCase):
    def test_compact_does_not_scan_library(self):
        c=Controller.__new__(Controller)
        c.presets={"1":{"nam1_enabled":True}}
        c.settings={"last":"1"}
        c.active="1"
        c.proc=SimpleNamespace(poll=lambda:None)
        c.button_revision=3
        c.library_files=lambda: self.fail("library scan")
        c.library_folders=lambda: self.fail("folder scan")
        data=c.button_status()
        self.assertEqual(data["button_revision"],3)
        self.assertTrue(data["running"])
        data["presets"]["1"]["nam1_enabled"]=False
        self.assertTrue(c.presets["1"]["nam1_enabled"])
        self.assertNotIn("files",data)
        json.dumps(data)

if __name__=="__main__": unittest.main()
