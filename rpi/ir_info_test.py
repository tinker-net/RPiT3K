import struct
import unittest
from ir_info import ir_info
def chunk(tag,data):
    return tag+struct.pack("<I",len(data))+data+(b"\0" if len(data)%2 else b"")
def wav(rate=44100,channels=1,bits=24,frames=2048,code=1,extra=b""):
    align=channels*(bits//8)
    body=b"WAVE"+chunk(b"fmt ",struct.pack("<HHIIHH",code,channels,rate,rate*align,align,bits))+extra+chunk(b"data",bytes(frames*align))
    return b"RIFF"+struct.pack("<I",len(body))+body
class IRTests(unittest.TestCase):
    def test_resampling(self):
        d=ir_info(wav())
        self.assertEqual(d["engine_frames"],2230)
        self.assertAlmostEqual(d["duration_ms"],2048/44.1)
    def test_float(self):
        d=ir_info(wav(rate=48000,bits=32,code=3))
        self.assertEqual(d["encoding"],"IEEE float")
        self.assertEqual(d["engine_frames"],2048)
    def test_info(self):
        d=ir_info(wav(extra=chunk(b"LIST",b"INFO"+chunk(b"IART",b"Author\0")+chunk(b"INAM",b"Cab\0"))))
        self.assertEqual(d["metadata"],{"author":"Author","name":"Cab"})
    def test_binary_metadata_ignored(self):
        info=chunk(b"LIST",b"INFO"+chunk(b"ICMT",b"g,k\x01xNX\x08\xff\xfe")+chunk(b"IART","José".encode("utf-8")+b"\0"))
        bext=chunk(b"bext",b"\x01\xff\x08"+bytes(599))
        d=ir_info(wav(extra=info+bext))
        self.assertEqual(d["metadata"],{"author":"José"})
    def test_clean_bext(self):
        description=b"Cabinet microphone"
        bext=chunk(b"bext",description+bytes(602-len(description)))
        self.assertEqual(ir_info(wav(extra=bext))["metadata"]["description"],"Cabinet microphone")
    def test_limits(self):
        self.assertFalse(ir_info(wav(channels=2))["compatible"])
        self.assertFalse(ir_info(wav(rate=48000,frames=48001))["compatible"])
    def test_invalid(self):
        with self.assertRaises(ValueError):ir_info(wav()[:-2])
if __name__=="__main__":unittest.main(verbosity=2)
