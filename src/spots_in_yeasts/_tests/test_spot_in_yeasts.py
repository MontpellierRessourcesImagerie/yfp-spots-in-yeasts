import pytest
import sys
import os
from tifffile import imread, imsave, imshow
from spots_in_yeasts.spotsInYeasts import *
import matplotlib.pyplot as plt
import numpy as np

def get_data_path():
    return "/home/benedetti/Bureau/unit-tests-data"


# >>>  SEGMENT YEAST CELLS <<<

def test_segment_yeasts():
    bf_path  = os.path.join(get_data_path(), "seg-yeasts-bf.tif")
    lbd_path = os.path.join(get_data_path(), "seg-yeasts-lbld.tif")
    bf  = imread(bf_path)
    lbd = imread(lbd_path)
    lbd_try = segment_yeasts_cells(bf)

    # Count labels
    expe = np.unique(lbd_try)
    theo = np.unique(lbd)
    assert abs(len(expe)-len(theo)) <= 5
    
    # Compare labels repartition
    lbd = lbd > 0
    lbd_try = lbd_try > 0
    s = lbd_try.shape
    m = np.count_nonzero(lbd_try ^ lbd) / (s[0]*s[1])
    assert m < 0.02

# >>>  PLACE MARKERS <<<

def test_place_markers():
    shp = (800, 800)
    n_pts = 40
    pts_list = np.floor(np.random.uniform(0, min(shp[0], shp[1]), (n_pts, 2))).astype(int)
    canvas = place_markers(shp, pts_list)
    uqs = np.unique(canvas)
    expected_values = np.arange(n_pts + 1)
    # Check nb of values
    assert len(uqs) == n_pts+1 # background is counted in np.unique
    # Check values repartition
    assert np.array_equal(uqs, expected_values)

# >>>  FIND FOCUS SLICES <<<

def test_focus_finder_stack():
    img_path = os.path.join(get_data_path(), "find-focus.tif")
    img = imread(img_path)
    found = find_focused_slice(img, 2)
    assert found == (1, 5)

def test_focus_finder_flat():
    img_path = os.path.join(get_data_path(), "find-focus-flat.tif")
    img = imread(img_path)
    found = find_focused_slice(img, 2)
    assert found == (0, 0)

def test_focus_finder_out_of_range():
    img_path = os.path.join(get_data_path(), "find-focus-oor.tif")
    img = imread(img_path)
    found = find_focused_slice(img, 2)
    assert found == (1, 4)
