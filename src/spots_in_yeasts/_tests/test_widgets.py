import pytest
import napari
from spots_in_yeasts._widget import SpotsInYeastsDock
import numpy as np
from tifffile import imread
import os

"""
This file contains behavior tests for the  `SpotsInYeastsDock` widget.
"""

def get_data_path():
    return "/home/benedetti/Bureau/unit-tests-data"

def test_split_channels_shape(make_napari_viewer, capsys):
    """
    Tries to split images according to their shape.
    Compatible images have 2 channels, and optionaly some slices.
    Hence their shape must have 3 or 4 elements (depending on the presence of slices)
    """
    viewer    = make_napari_viewer()
    my_widget = SpotsInYeastsDock(viewer)

    images = [
        ("hw_c1_s1_f1.tif" , False),
        ("hw_c1_s24_f1.tif", False),
        ("hw_c2_s12_f1.tif", True),
        ("hw_c2_s6_f2.tif" , False)]
    
    for imp, expected in images:
        my_widget.clear_layers_gui()
        full_path = os.path.join(get_data_path(), imp)
        img = imread(full_path)
        viewer.add_image(img, name=imp)
        success = my_widget.split_channels_gui()
        assert success == expected

def test_split_channels_empty(make_napari_viewer, capsys):
    """
    Try to split channels when nothing is loaded.
    The expected result is a failure (return False).
    """
    viewer    = make_napari_viewer()
    my_widget = SpotsInYeastsDock(viewer)
    success = my_widget.split_channels_gui()
    assert success == False

def test_split_channels_too_many(make_napari_viewer, capsys):
    """
    Try to split channels when several images are loaded at a time.
    The expected result is a failure. To know what image we are working on, only one has to be opened.
    """
    viewer    = make_napari_viewer()
    viewer.add_image(np.random.random((100, 100)))
    viewer.add_image(np.random.random((100, 100)))
    viewer.add_image(np.random.random((100, 100)))
    my_widget = SpotsInYeastsDock(viewer)
    success = my_widget.split_channels_gui()
    assert success == False

def test_split_channels_batch(make_napari_viewer, capsys):
    """
    Try to split channels in batch mode when an image is loaded.
    """
    viewer    = make_napari_viewer()
    viewer.add_image(np.random.random((100, 100)))
    my_widget = SpotsInYeastsDock(viewer)
    success   = my_widget.split_channels_gui()
    assert success == False

# make_napari_viewer is a pytest fixture that returns a napari viewer object
# capsys is a pytest fixture that captures stdout and stderr output streams
def test_clear_layers_n(make_napari_viewer, capsys):
    """
    Checking that deleting layers works if several layers are present.
    """
    viewer = make_napari_viewer()
    viewer.add_image(np.random.random((100, 100)))
    my_widget = SpotsInYeastsDock(viewer)
    assert len(viewer.layers) > 0
    my_widget.clear_layers_gui()
    assert len(viewer.layers) == 0


def test_clear_layers_0(make_napari_viewer, capsys):
    """
    Checking that deleting layers doesn't crash if there is no layer present.
    """
    viewer    = make_napari_viewer()
    my_widget = SpotsInYeastsDock(viewer)
    assert len(viewer.layers) == 0
    my_widget.clear_layers_gui()
    assert len(viewer.layers) == 0