############################################################################################
#                                                                                          #
#                          UNIT TESTS                                                      #
#                                                                                          #
############################################################################################

import sys
import os

sys.path.append(os.path.abspath(".."))

from spotsInYeasts.spotsInYeasts import *

import unittest
from unittest.mock import patch

def testing_data_root():
    return "/home/benedetti/Bureau/unit-tests"

class TestSegmentYeasts(unittest.TestCase):

    def setUp(self):
        pass

class TestFocusFinder(unittest.TestCase):

    def setUp(self):
        self.root = testing_data_root()
        self.file_name = os.path.join(self.root, "focus-detector.tif")
        self.image = np.array(ImageCollection(self.file_name))

    def test_focus_finder(self):
        in_focus = find_focused_slice(self.image, around=2)
        self.assertEqual(in_focus, (1, 5), "The focus detection failed.")

    def test_no_stack(self):
        in_focus = find_focused_slice(self.image[0], around=2)
        self.assertEqual(in_focus, (0, 0), "The focus detector didn't notice that its input is not a stack.")

    def test_no_out_of_bounds(self):
        in_focus = find_focused_slice(self.image, around=18)
        self.assertGreaterEqual(in_focus[0], 0, "The range is out-of-bounds.")
        self.assertLessEqual(in_focus[1], len(self.image)-1, "The range is out-of-bounds.")

class TestImagesFinder(unittest.TestCase):

    def test_number_images(self):
        with patch("os.listdir") as ldir, patch("os.path.isfile") as is_file:
            ldir.return_value = self.folder_content
            is_file.return_value = True

            input_dir  = "/some/path/to/a/folder"
            components = [
                ('brightfield', '_w2bf.tif'),
                ('yfp'        , '_w1yfp.tif'),
                ('config'     , '.nd')
            ]
            image_sets = build_sets(input_dir, components)

            self.assertEqual(len(image_sets), 32, "Not all images were found.")
            for group in image_sets:
                self.assertEqual(len(components), len(group), "Some group is missing a component, or has one in excess.")
                for key, value in group.items():
                    self.assertNotEqual('.', value[0], "Hidden files should be ignored.")

    def setUp(self):
        self.folder_content = [
            "d1-230421-7s_5_w1yfp.tif", 
            "d1-230421-9s_d-_w1yfp.tif", 
            "max_d1-230421--6s.c-_w1yfp.tif", 
            "d1-230421-7s_5_w2bf.tif", 
            "d1-230421-9s_d-_w2bf.tif", 
            "._MAX_d1-230421--6S.C-_w1YFP.tif", 
            "d1-230421-11s_1.nd", 
            "d1-230421-7s_.nd", 
            "d1-230421_bg-.nd", 
            "max_d1-230421-7s_1_w1yfp.tif", 
            "d1-230421-11s_1_w1yfp.tif", 
            "d1-230421-7s__w1yfp.tif", 
            "d1-230421_bg-_w1yfp.tif", 
            "._MAX_d1-230421-7S_1_w1YFP.tif", 
            "d1-230421-11s_1_w2bf.tif", 
            "d1-230421-7s__w2bf.tif", 
            "d1-230421_bg-_w2bf.tif", 
            "max_d1-230421-7s_2_w1yfp.tif", 
            "d1-230421-11s_2.nd", 
            "d1-230421-9s_4.nd", 
            "d1-230421-e-1.nd", 
            "._MAX_d1-230421-7S_2_w1YFP.tif", 
            "d1-230421-11s_2_w1yfp.tif", 
            "d1-230421-9s_4_w1yfp.tif", 
            "d1-230421-e-1_w1yfp.tif", 
            "max_d1-230421-7s_3_w1yfp.tif", 
            "d1-230421-11s_2_w2bf.tif", 
            "d1-230421-9s_4_w2bf.tif", 
            "d1-230421-e-1_w2bf.tif", 
            "._MAX_d1-230421-7S_3_w1YFP.tif", 
            "d1-230421-11s_3.nd", 
            "d1-230421-9s_5.nd", 
            "d1-230421-e-2.nd", 
            "max_d1-230421-7s_4_w1yfp.tif", 
            "d1-230421-11s_3_w1yfp.tif", 
            "d1-230421-9s_5_w1yfp.tif", 
            "d1-230421-e-2_w1yfp.tif", 
            "._MAX_d1-230421-7S_4_w1YFP.tif", 
            "d1-230421-11s_3_w2bf.tif", 
            "d1-230421-9s_5_w2bf.tif", 
            "d1-230421-e-2_w2bf.tif", 
            "max_d1-230421-7s__w1yfp.tif", 
            "d1-230421-11s_4.nd", 
            "d1-230421-9s_6.nd", 
            "d1-230421-e-.nd", 
            "._MAX_d1-230421-7S__w1YFP.tif", 
            "d1-230421-11s_4_w1yfp.tif", 
            "d1-230421-9s_6_w1yfp.tif", 
            "d1-230421-e-_w1yfp.tif", 
            "max_d1-230421-9s_4_w1yfp.tif", 
            "d1-230421-11s_4_w2bf.tif", 
            "d1-230421-9s_6_w2bf.tif", 
            "d1-230421-e-_w2bf.tif", 
            "._MAX_d1-230421-9S_4_w1YFP.tif", 
            "d1-230421--11s_c.nd", 
            "d1-230421-9s_7.nd", 
            "d1-230421-g-1.nd", 
            "max_d1-230421-9s_5_w1yfp.tif", 
            "d1-230421--11s_c_w1yfp.tif", 
            "d1-230421-9s_7_w1yfp.tif", 
            "d1-230421-g-1_w1yfp.tif", 
            "._MAX_d1-230421-9S_5_w1YFP.tif", 
            "d1-230421--11s_c_w2bf.tif", 
            "d1-230421-9s_7_w2bf.tif", 
            "d1-230421-g-1_w2bf.tif", 
            "max_d1-230421-9s_6_w1yfp.tif", 
            "d1-230421-11s_.nd", 
            "d1-230421-9s_8.nd", 
            "d1-230421-g-.nd", 
            "._MAX_d1-230421-9S_6_w1YFP.tif", 
            "d1-230421-11s__w1yfp.tif", 
            "d1-230421-9s_8_w1yfp.tif", 
            "d1-230421-g-_w1yfp.tif", 
            "max_d1-230421-9s_7_w1yfp.tif", 
            "d1-230421-11s__w2bf.tif", 
            "d1-230421-9s_8_w2bf.tif", 
            "d1-230421-g-_w2bf.tif", 
            "._MAX_d1-230421-9S_7_w1YFP.tif", 
            "d1-230421--6s_c-.nd", 
            "d1-230421-9s_b-1.nd", 
            "d1-230421-h-1.nd", 
            "max_d1-230421-9s_8_w1yfp.tif", 
            "d1-230421--6s_c-_w1yfp.tif", 
            "d1-230421-9s_b-1_w1yfp.tif", 
            "d1-230421-h-1_w1yfp.tif", 
            "._MAX_d1-230421-9S_8_w1YFP.tif", 
            "d1-230421--6s_c-_w2bf.tif", 
            "d1-230421-9s_b-1_w2bf.tif", 
            "d1-230421-h-1_w2bf.tif", 
            "max_d1-230421--9s.c_w1yfp.tif", 
            "d1-230421-7s_1.nd", 
            "d1-230421-9s_b-2.nd", 
            "d1-230421-h-.nd", 
            "._MAX_d1-230421--9S.C_w1YFP.tif", 
            "d1-230421-7s_1_w1yfp.tif", 
            "d1-230421-9s_b-2_w1yfp.tif", 
            "d1-230421-h-_w1yfp.tif", 
            "max_d1-230421-b--11s_w1yfp.tif", 
            "d1-230421-7s_1_w2bf.tif", 
            "d1-230421-9s_b-2_w2bf.tif", 
            "d1-230421-h-_w2bf.tif", 
            "._MAX_d1-230421-b--11S_w1YFP.tif", 
            "d1-230421-7s_2.nd", 
            "d1-230421-9s_b-.nd", 
            "max_d1-230421-11s_1_w1yfp.tif", 
            "max_d1-230421-b--6s_w1yfp.tif", 
            "d1-230421-7s_2_w1yfp.tif", 
            "d1-230421-9s_b-_w1yfp.tif", 
            "._MAX_d1-230421-11S_1_w1YFP.tif", 
            "._MAX_d1-230421-b--6S_w1YFP.tif", 
            "d1-230421-7s_2_w2bf.tif", 
            "d1-230421-9s_b-_w2bf.tif", 
            "max_d1-230421-11s_2_w1yfp.tif", 
            "max_d1-230421-b--9s_w1yfp.tif", 
            "d1-230421-7s_3.nd", 
            "d1-230421--9s_c.nd", 
            "._MAX_d1-230421-11S_2_w1YFP.tif", 
            "._MAX_d1-230421-b--9S_w1YFP.tif", 
            "d1-230421-7s_3_w1yfp.tif", 
            "d1-230421--9s_c_w1yfp.tif", 
            "max_d1-230421-11s_3_w1yfp.tif", 
            "max_d1-230421-e-1_w1yfp.tif", 
            "d1-230421-7s_3_w2bf.tif", 
            "d1-230421--9s_c_w2bf.tif", 
            "._MAX_d1-230421-11S_3_w1YFP.tif", 
            "._MAX_d1-230421-E-1_w1YFP.tif", 
            "d1-230421-7s_4.nd", 
            "d1-230421-9s_d-1.nd", 
            "max_d1-230421-11s_4_w1yfp.tif", 
            "max_d1-230421-e-2_w1yfp.tif", 
            "d1-230421-7s_4_w1yfp.tif", 
            "d1-230421-9s_d-1_w1yfp.tif", 
            "._MAX_d1-230421-11S_4_w1YFP.tif", 
            "._MAX_d1-230421-E-2_w1YFP.tif", 
            "d1-230421-7s_4_w2bf.tif", 
            "d1-230421-9s_d-1_w2bf.tif", 
            "max_d1-230421--11s.c_w1yfp.tif", 
            "max_d1-230421-e-_w1yfp.tif", 
            "d1-230421-7s_5.nd", 
            "d1-230421-9s_d-.nd", 
            "._MAX_d1-230421--11S.C_w1YFP.tif", 
            "._MAX_d1-230421-E-_w1YFP.tif"
        ]

if __name__ == '__main__':
    unittest.main(verbosity=2)