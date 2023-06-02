############################################################################################
#                                                                                          #
#                          UNIT TESTS                                                      #
#                                                                                          #
############################################################################################

import sys
import os

sys.path.append(os.path.abspath(".."))

from spotsInYeasts.spotsInYeasts import *
import numpy as np

import unittest
from unittest.mock import patch

_stock_std_out_ = sys.stdout
_is_on_ = True

def toggleOutput():
    global _stock_std_out_, _is_on_
    if _is_on_:
        sys.stdout = open(os.devnull, 'w')
    else:
        sys.stdout.close()
        sys.stdout = _stock_std_out_
    _is_on_ = not _is_on_

def testing_data_root():
    return "/home/benedetti/Bureau/unit-tests"


class TestSegmentYeasts(unittest.TestCase):

    def setUp(self):
        pass


class TestContrastEnhance(unittest.TestCase):

    def setUp(self):
        self.root = testing_data_root()
        self.file_name = os.path.join(self.root, "contrast-enhance.tif")
        self.image = np.array(ImageCollection(self.file_name))
        toggleOutput()

    def tearDown(self):
        toggleOutput()
    
    def test_contrast_stretch(self):
        new_image_u16 = increase_contrast(self.image, np.uint16)
        self.assertEqual(new_image_u16.min(), 0, "Image contrast not correctly rescaled.")
        self.assertEqual(new_image_u16.max(), 65535, "Image contrast not correctly rescaled.")

        new_image_u8 = increase_contrast(self.image, np.uint8)
        self.assertEqual(new_image_u8.min(), 0, "Image contrast not correctly rescaled.")
        self.assertEqual(new_image_u8.max(), 255, "Image contrast not correctly rescaled.")


class TestPlaceMarkers(unittest.TestCase):
    def setUp(self):
        self.root = testing_data_root()
        self.file_name = os.path.join(self.root, "contrast-enhance.tif")
        self.image = np.array(ImageCollection(self.file_name))
        toggleOutput()
    
    def tearDown(self):
        toggleOutput()

    def test_placed_markers(self):
        coordsList = [(i*2, i*3) for i in range(int(min(self.image.shape[1:3])/3))]
        m_shape = self.image.shape[1:3]
        marked = place_markers(m_shape, coordsList)
        vals = np.unique(marked)
        # The "+ 1" comes from the fact that 'np.unique' counts the background as a value.
        self.assertEqual(len(vals), len(coordsList)+1, "Inconsistant number of markers placed.")


class TestAssociateSpots(unittest.TestCase):
    def setUp(self):
        self.root = testing_data_root()
        self.file_labeled = os.path.join(self.root, "labeled-cells.tif")
        self.file_mask = os.path.join(self.root, "spots-mask.tif")
        self.file_coords = os.path.join(self.root, "spots_list.data")
        self.file_labels = os.path.join(self.root, "truth_cells.data")

        self.labeled = np.squeeze(np.array(ImageCollection(self.file_labeled)))
        self.mask = np.squeeze(np.array(ImageCollection(self.file_mask)))

        f = open(self.file_coords, 'r')
        t = f.read()
        f.close()
        self.coords = np.array(eval(t))

        f = open(self.file_labels, 'r')
        t = f.read()
        f.close()
        self.labels = eval(t)

        toggleOutput()
    
    def tearDown(self):
        toggleOutput()

    def test_associate_spots(self):
        ownership, labels, true_spots = associate_spots_yeasts(self.labeled, self.coords, self.labeled, self.mask)

        for label, spots in ownership.items():
            for spot in spots:
                p1 = np.array(spot['location'])
                p2 = np.array(self.labels[label])
                print(label, np.linalg.norm(p1-p2))
                # self.assertEqual(spot['location'], self.labels[label])

        self.assertEqual(len(true_spots), len(self.coords), "Not all spots were retreived.")


class TestFocusFinder(unittest.TestCase):
    """
    Tests the function responsible for finding the most in-focus slice within a z-stack.
    This function is supposed to be safe even if we give it something that is not a stack or if the range is supposed to fall outside the existing slices.
    """

    def setUp(self):
        self.root = testing_data_root()
        self.file_name = os.path.join(self.root, "focus-detector.tif")
        self.image = np.array(ImageCollection(self.file_name))
        toggleOutput()

    def tearDown(self):
        toggleOutput()

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


if __name__ == '__main__':
    unittest.main(verbosity=2)