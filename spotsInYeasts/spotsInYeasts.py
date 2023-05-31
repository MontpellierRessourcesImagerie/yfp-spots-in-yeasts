from skimage.io import imread
from skimage.filters import threshold_isodata
from skimage.segmentation import watershed, clear_border
from skimage.morphology import dilation, disk
from skimage.measure import regionprops
from skimage.feature import peak_local_max
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import median_filter, gaussian_laplace, distance_transform_edt, label
from cellpose import models, utils, io
from termcolor import colored
import os, cv2
import matplotlib.pyplot as plt
import numpy as np


def create_random_lut(raw=False):
    """
    Creates a random LUT of 256 slots to display labeled images with colors far apart from each other.
    Black is reserved for the background.

    Returns:
        A cmap object that can be used with the imshow() function. ex: `imshow(image, cmap=create_random_lut())`
    """
    lut    = np.random.uniform(0.01, 1.0, (256, 3))
    lut[0] = (0.0, 0.0, 0.0)
    return lut if raw else LinearSegmentedColormap.from_list('random_lut', lut)


def make_outlines(labeled_cells, thickness=3):
    """
    Turns a labeled image into a mask showing the outline of each label.
    The resulting image is boolean.

    Args:
        labeled_cells: The image containing labels.
        thickness: The desired thickness of outlines.
    
    Returns:
        A mask representing outlines of cells.
    """
    selem   = disk(thickness)
    dilated = dilation(labeled_cells, selem) - labeled_cells
    return dilated > 0


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
    if selected[1]-selected[0] != 2*around:
        print(colored("Not enough slices available!", 'yellow'))

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


def segment_spots(stack, labeled_cells=None):
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

    # >>> Contrast augmentation + noise reduction
    print("Starting spots segmentation...")
    save_yfp  = np.copy(input_yfp)
    input_yfp = increase_contrast(input_yfp)
    input_yfp = median_filter(input_yfp, size=3)

    # >>> LoG filter + thresholding
    asf = input_yfp.astype(np.float64)
    LoG = gaussian_laplace(asf, sigma=3.0)
    t = threshold_isodata(LoG)
    mask = LoG < t

    # >>> Detection of spots location
    asf     = mask.astype(np.float64)
    chamfer = distance_transform_edt(asf)
    maximas = peak_local_max(chamfer, min_distance=6)

    if labeled_cells is not None:
        clean_points = []
        for l, c in maximas:
            if labeled_cells[l, c] > 0:
                clean_points.append((l, c))
        maximas = np.array(clean_points)
    print(f"{len(maximas)} spots found.")

    # >>> Isolating instances of spots
    m_shape   = mask.shape[0:2]
    markers   = place_markers(m_shape, maximas)
    lbd_spots = watershed(~mask, markers, mask=mask).astype(np.uint16)

    # >>> Returning the results
    return maximas, lbd_spots, save_yfp


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
    if len(points) <= 0:
        return (0, 0)

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


def associate_spots_yeasts(labeled_cells, labeled_spots, yfp):
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

    spots_props = regionprops(labeled_spots, intensity_image=yfp)
    removed     = []
    true_spots  = []

    for spot in spots_props:
        (r, c) = spot.centroid
        lbl = int(labeled_cells[int(r), int(c)])

        if lbl == 0:
            removed.append(spot.label)
            continue # We are in the background
        
        ownership[lbl].append({
            'location'      : (int(r), int(c)),
            'intensity_mean': float(spot['intensity_mean']),
            'area'          : float(spot['area']),
            'perimeter'     : float(spot['perimeter'])
        })
        
        true_spots.append((r, c))
    
    removed_mask = np.isin(labeled_spots, removed)
    labeled_spots[removed_mask] = 0

    return ownership


def place_marker_visual(canvas, marker, l, c, val):
    height, width = canvas.shape
    mH, mW = marker.shape
    l -= int(mH/2)
    c -= int(mW/2)

    for y in range(mH):
        for x in range(mW):
            p_y = l+y
            p_x = c+x
            if (p_y >= height) or (p_x >= width):
                continue
            if canvas[l+y, c+x] or marker[y, x]:
                canvas[l+y, c+x] = val

def place_markers_visual(points_list, canvas, marker, val):
    for (l, c) in points_list:
        place_marker_visual(canvas, marker, l, c, val)


def create_reference(spots_list, labeled_cells, brightfield, marker_path):
    # [RED]: Location of spots
    marker = imread(marker_path)
    canvas = np.zeros(brightfield.shape, dtype=brightfield.dtype)
    place_markers_visual(spots_list, canvas, marker, np.iinfo(brightfield.dtype).max)

    # [GREEN]: Segmented cells outlines
    outlines = (make_outlines(labeled_cells) * np.iinfo(brightfield.dtype).max).astype(brightfield.dtype)

    # [BLUE]: Original brightfield

    return np.stack([canvas, outlines, brightfield], axis=-1)