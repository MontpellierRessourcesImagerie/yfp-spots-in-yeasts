import numpy as np
from skimage.io import imsave, imread, imshow, ImageCollection
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import median_filter, distance_transform_edt, center_of_mass, label
from skimage.measure import regionprops
from skimage.feature import peak_local_max
import time, os, sys
from urllib.parse import urlparse
import cv2
from scipy.ndimage import gaussian_laplace
from skimage.filters import threshold_otsu
from skimage.segmentation import watershed, clear_border
from skimage.morphology import dilation, disk

from cellpose import models, utils, io
import glob
import fnmatch
import argparse
import random


def create_random_lut(raw=False):
    """
    Creates a random LUT of 256 slots to display labeled images with colors far apart from each other.
    Black is reserved for the background.

    Returns:
        A cmap object that can be used with the imshow() function. ex: `imshow(image, cmap=create_random_lut())`
    """
    lut = np.random.uniform(0.0, 1.0, (256, 3))
    np.random.shuffle(lut)
    lut[0] = (0.0, 0.0, 0.0)
    
    if raw:
        return lut

    cmap = LinearSegmentedColormap.from_list('random_lut', lut)
    return cmap


def make_outlines(labeled_cells, thickness=4):
    """
    Turns a labeled image into a mask showing the outline of each label.
    The resulting image is boolean.

    Args:
        labeled_cells: The image containing labels.
        thickness: The desired thickness of outlines.
    
    Returns:
        A mask representing outlines of cells.
    """
    selem    = disk(thickness)
    dilated  = dilation(labeled_cells, selem)
    dilated -= labeled_cells
    
    return dilated > 0


def seek_channels(root_dir, channels):
    """
    This function is useful only if the machine that produced the images doesn't provide the user with multi-channel images.
    In this case, each channel is in its own image, with some suffix to indicate the channel.
    If your machine creates a multi-channels image, you don't need this function.

    Args:
        root_dir: The absolute path of a folder containing images.
        channels: A list of tuples. Each tuple is of size 2. The first element is the name of what the channel represents (brightfield, spots, ...) and the second is the suffix used to represent this channel (_w2yfp.tif, _w1bf.tif, ...).
    
    Returns:
        A list of dictionary. Each dict has the same size and keys, which are the names provided in the tuples. Each key points of the associated file.
        Ex: If in the parameters you provided channels=[('brightfield', "_w2bf.tif"), ('spots', "_w1yfp.tif")], you will get a result like:
        [
            {
                'brightfield': "some_file_w2bf.tif",
                'spots'      : "some_file_w1yfp.tif"
            },
            {
                'brightfield': "other_file_w2bf.tif",
                'spots'      : "other_file_w1yfp.tif"
            }
        ]
    """
    # Safety check. Do we actually have the path of a folder?
    if not os.path.isdir(root_dir):
        print(f"`{root_dir}` is not the path of a folder.")
        return []
    
    # Make a list of all the .nd files that are not hidden
    headers = [c for c in os.listdir(root_dir) if (c.endswith(".nd")) and (not c.startswith('.')) and os.path.isfile(os.path.join(root_dir, c))]
    images  = []

    for header in headers:
        raw_title = header.replace(".nd", "")
        item      = {
            'header' : header,
            'control': raw_title + "_control.tif",
            'raw'    : raw_title,
            'metrics': raw_title + "_measures.json"
        }
        baselen = len(item)

        for channel, suffix in channels:
            item[channel] = raw_title + suffix
        
        if len(item) != len(channels)+baselen:
            print(f"Images associated with `{header}` couldn't be retreived.")
            continue

        images.append(item)

    print(f"{len(images)} full images were detected:")
    for item in images:
        print(f"  - {item['header']}")
    print("")

    return images


def find_focused_slice(stack, around=2):
    """
    Determines which is the slice with the best focus, and pick a range of slices around it.
    The process is based on the variance recorded on each slice.

    Returns:
        A tuple centered around the most in-focus slice. If we call 'F' the index of that slice, then the tuple is: `(F-around, F+around)`.

    Args:
        stack: (image stack) The stack in which we search the focused area.
        around: (int) Number of slices to select around the most in-focus one.
    """
    # If we don't have a stack, we just return a tuple filled with zeros.
    if len(stack.shape) < 3:
        return (0, 0)

    nSlices, width, height = stack.shape
    maxSlice = np.argmax([cv2.Laplacian(stack[s], cv2.CV_64F).var() for s in range(nSlices)])
    selected = (max(0, maxSlice-around), min(nSlices-1, maxSlice+around))
    print(f"Selected slices: {selected}. ({nSlices} slices available)")

    # We make sure to stay in-bounds.
    return selected


def segment_yeasts_cells(transmission, gpu=True):
    """
    Takes the transmission channel (brightfield) of yeast cells and segments it (instances segmentation).
    | CPU: 43s
    | GPU: 11s
    
    Args:
        transmission (image): Single channeled image, in brightfield, representing yeasts
    
    Returns:
        (image) An image containing labels (one value == one individual).
    """
    
    model = models.Cellpose(gpu=gpu, model_type='cyto')
    chan = [0, 0]
    print("Segmenting cells...")
    masks, flows, styles, diams = model.eval(transmission, diameter=None, channels=chan)

    return masks


def increase_contrast(image, targetType=np.uint16):
    """
    The resulting image occupies the whole range of possible values according to its data type (uint8, uint16, ...)

    Returns:
        void

    Args:
        image: The image that will beneficiate of a contrast enhancement
    """
    image = image.astype(np.float64)
    image -= image.min()
    image /= image.max()
    image *= np.iinfo(targetType).max
    image = image.astype(targetType)
    
    return image


def place_markers(shp, m_list):
    """
    Places pixels with an incremental intensity (from 1) at each position contained in the list.

    Returns:
        A mask with black background and one pixel at each intensity from 1 to len(m_list).

    Args:
        shp: A 2D tuple representing the shape of the mask to be created.
        m_list: A list of tuples representing 2D coordinates.
    """
    tmp = np.zeros(shp, dtype=np.uint16)

    for i, (l, c) in enumerate(m_list, start=1):
        tmp[l, c] = i
    
    return tmp


#################################################################################


def segment_transmission(stack, gpu=True):
    """
    Takes the path of an image that contains some yeasts in transmission.

    Args:
        stack: A numpy array representing the transmission channel

    Returns:
        A uint16 image containing labels. Each label corresponds to an instance of yeast cell.
    """

    # Boolean value determining if we want to use all the slices of the stack, or just the most in-focus.
    pick_slices   = True
    slices_around = 2

    # >>> Opening stack as an image collection:
    stack_sz  = stack.shape
    input_bf  = None
    
    if len(stack_sz) > 2: # We have a stack, not a single image.
        # >>> Finding a range of slices in the focus area:
        if pick_slices:
            in_focus = find_focused_slice(stack, slices_around)
        else:
            in_focus = (0, stack.shape[0])

        # >>> Max projection of the stack:
        max_proj = np.max(stack[in_focus[0]:in_focus[1]], axis=0)
        input_bf = max_proj
    else:
        print("Image is a single slice.")
        input_bf = np.squeeze(stack)
    
    # >>> Labeling the transmission channel:
    labeled_transmission = segment_yeasts_cells(input_bf, gpu)

    # >>> Finding and removing the labels touching the borders:
    cleared_bd = clear_border(labeled_transmission, buffer_size=3)
    print(f"Cells segmentation done. {len(np.unique(cleared_bd))-1} cells found.")

    return cleared_bd, input_bf


#################################################################################


def segment_spots(stack):
    """
    Args:
        stack: A numpy array representing the fluo channel

    Returns:
        A dictionary containing several pieces of information about spots.
         - original: The input image after maximal projection
         - contrasted: A version of the channel stretched on the whole histogram.
         - mask: A labeled image containing an index per detected spot.
         - locations: A list of 2D coordinates representing each spot.
    """

    # >>> Opening YFP stack
    stack_sz  = stack.shape
    input_yfp = None

    # >>> Max projection of the stack
    if len(stack_sz) > 2: # We have a stack, not a single image.
        input_yfp = np.max(stack, axis=0)
    else:
        input_yfp = np.squeeze(stack)

    print("Starting spots segmentation...")
    save_yfp  = np.copy(input_yfp)
    input_yfp = increase_contrast(input_yfp)
    input_yfp = median_filter(input_yfp, size=3)

    asf = input_yfp.astype(np.float64)
    LoG = gaussian_laplace(asf, sigma=3.0)
    t = threshold_otsu(LoG)
    mask = LoG < t

    asf = mask.astype(np.float64)
    chamfer = distance_transform_edt(asf)
    maximas = peak_local_max(chamfer, min_distance=6)
    print(f"{len(maximas)} spots found before filtering.")

    # >>> Returning the results
    return {
        "original"  : save_yfp,
        "contrasted": input_yfp,
        "mask"      : mask,
        "locations" : maximas
    }


def estimateUniformity(points, shape, gridSize=50):
    """
    Uses the chi-squared test to determine whether the distribution of detected spots is uniform.
    If the distribution is uniform, we have a bad detection and the process should be aborted.

    Args:
        points: A list of 2D points
        gridSize: The size of the grid used to quantify the uniformity of the distribution.

    Returns:
        A tuple containing the chi-squared sum and the number of degrees of freedom.
    """
    grid = [0 for i in range(gridSize*gridSize)]

    for (l, c) in points:
        x = int(gridSize * (l / float(shape[0])))
        y = int(gridSize * (c / float(shape[1])))
        grid[gridSize*y+x] += 1

    total    = 0
    expected = float(len(points)) / float(gridSize*gridSize)

    for g in grid:
        total += pow((g - expected), 2) / expected

    return (total, gridSize*gridSize-1)


def associate_spots_yeasts(labeled_cells, spots_list, original_yfp, mask):
    """
    Associates each spot with the label it belongs to.
    A safety check is performed to make sure no spot falls in the background.

    Args:
        labeled_cells: A single-channeled image with dtype=uint16 containing the segmented transmission image.
        spots_list: A list a 2D tuples representing the centroids of detected spots.
        original_yfp: The original image containing the YFP spots (before contrast enhancement).
        mask: The first mask produced that partionates the space in "spot" or "background" but without find different instances.

    Returns:
        A dictionary in which keys are the labels of each cell. Each key points to a list of dictionary. Each element of the list corresponds to a spot.
        An image representing labels in the fluo channel (a label per spot) is also returned.
    """
    unique_values = np.unique(labeled_cells)
    ownership     = {int(u): [] for u in unique_values if (u > 0)}

    # Isolating instances of spots
    m_shape     = mask.shape[0:2]
    markers     = place_markers(m_shape, spots_list)
    labels      = watershed(~mask, markers, mask=mask).astype(np.uint16)
    spots_props = regionprops(labels, intensity_image=original_yfp)
    removed     = []
    true_spots  = []

    for spot in spots_props:
        (r, c) = spot.centroid
        lbl = labeled_cells[int(r), int(c)]

        if lbl == 0:
            removed.append(spot.label)
            continue # We are in the background
        
        ownership[int(lbl)].append({
            'location'      : (int(r), int(c)),
            'intensity_mean': float(spot['intensity_mean']),
            'area'          : float(spot['area']),
            'perimeter'     : float(spot['perimeter'])
        })
        
        true_spots.append((r, c))
    
    print(f"{len(true_spots)} spots still valid after filtering.")
    removed_mask = np.isin(labels, removed)
    labels[removed_mask] = 0

    return ownership, labels, true_spots

