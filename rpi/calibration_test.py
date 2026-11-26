import unittest
from calibration import calibration

class CalibrationTest(unittest.TestCase):
    def test_missing(self):
        for model in ({}, {"metadata":None},{"metadata":[]},{"metadata":{"input_level_dbu":True}},{"metadata":{"input_level_dbu":"12"}}):
            self.assertEqual(calibration(model,1.14)["status"],"missing_metadata")
    def test_reference(self):
        model={"metadata":{"input_level_dbu":12}}
        r=calibration(model,1.14)
        self.assertEqual(r["status"],"ready")
        self.assertAlmostEqual(r["db"],-10.86)
        self.assertAlmostEqual(r["gain"],10**(-10.86/20))
        self.assertEqual(calibration(model,None)["status"],"missing_adc")
        self.assertEqual(calibration(model,30)["status"],"out_of_range")
    def test_slim(self):
        model={"architecture":"SlimmableContainer","metadata":{"input_level_dbu":12},"config":{"submodels":[{"max_value":.5,"model":{"metadata":{"input_level_dbu":5}}},{"max_value":1,"model":{"metadata":{"input_level_dbu":8}}}]}}
        self.assertEqual(calibration(model,1.14,0)["model_dbu"],5)
        self.assertEqual(calibration(model,1.14,.5)["model_dbu"],8)
        self.assertEqual(calibration(model,1.14,1)["model_dbu"],8)

if __name__=="__main__": unittest.main()
