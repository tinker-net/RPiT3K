import unittest
from capture_info import capture_info
class CaptureInfoTests(unittest.TestCase):
    def test_metadata(self):
        m={"architecture":"WaveNet","version":"0.5.4","sample_rate":48000,"metadata":{"name":"Amp","input_level_dbu":1.2},"weights":[1,2],"config":{"layers":[1]}}
        self.assertEqual(capture_info(m),{k:m[k] for k in ("architecture","version","sample_rate","metadata")})
    def test_missing(self):
        self.assertEqual(capture_info({"architecture":"WaveNet"}),{"architecture":"WaveNet"})
    def test_submodels(self):
        m={"architecture":"SlimmableContainer","config":{"submodels":[{"max_value":.5,"model":{"architecture":"WaveNet","metadata":{"name":"Lite"},"weights":[1]}}]}}
        self.assertEqual(capture_info(m)["submodels"],[{"architecture":"WaveNet","metadata":{"name":"Lite"},"max_value":.5}])
    def test_invalid(self):
        with self.assertRaises(ValueError):capture_info([])
if __name__=="__main__":unittest.main(verbosity=2)
