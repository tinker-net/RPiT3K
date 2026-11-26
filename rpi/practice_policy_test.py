import os, unittest
from unittest.mock import patch
from practice import background_command
class PracticePolicyTest(unittest.TestCase):
    @patch("practice.shutil.which",return_value="/usr/bin/tool")
    @patch("practice.os.sched_getaffinity",return_value={0,1,2,3})
    def test_four_cores(self,*_):
        with patch.dict(os.environ,{"RPIT3K_AUDIO_AFFINITY":"1"}):
            self.assertEqual(background_command(["ffmpeg"]),["taskset","-c","0,1,2","nice","-n","10","ionice","-c","2","-n","7","ffmpeg"])
    @patch("practice.shutil.which",return_value="/usr/bin/tool")
    @patch("practice.os.sched_getaffinity",return_value={2,4})
    def test_small_system(self,*_):
        self.assertNotIn("taskset",background_command(["ffmpeg"]))
if __name__=="__main__":unittest.main()
