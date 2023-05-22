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

from cellpose import models, utils, io
import glob
import fnmatch
import argparse
import random


def create_random_lut():
    """
    Creates a random LUT of 256 slots to display labeled images with colors far apart from each other.
    Black is reserved for the background.

    Returns:
        A cmap object that can be used with the imshow() function. ex: `imshow(image, cmap=create_random_lut())`
    """
    lut = np.random.uniform(0.0, 1.0, (256, 3))
    np.random.shuffle(lut)
    lut[0] = (0.0, 0.0, 0.0)
    cmap = LinearSegmentedColormap.from_list('random_lut', lut)
    return cmap


def build_sets(root_dir, channels):
    """
    Locates the different channels of a same image in case they were saved individually. ex: (_w1yfp.tif, _w2bf.tif, .nd)
    For example, in this project, brightfield images don't have the same number of slices as fluorescent channel, so they are saved individually.
    For this function to work, you need to save your images with a common name and a varying suffix.

    Args:
        root_dir (str): The path to the folder containing the images
        channels ([(str, str)]): A list of tuples. Each tuple contains what this channel is (brightfield, yfp, gfp, ...) and the corresponding suffix without the file extension.
    
    Returns:
        A list of dict. Each dict contains the name of the channels. An image is present only if all its channels were found.
    """

    # Safety check. Do we actually have the path of a folder?
    if not os.path.isdir(root_dir):
        print(f"`root_dir` is not the path of a folder.")
        return []

    # List of not hidden files.
    content = [c for c in os.listdir(root_dir) if (not c.startswith('.')) and os.path.isfile(os.path.join(root_dir, c))]
    items   = {}
    images  = []

    # Scanning content of the folder and assigning each file to an image.
    for c in content:
        for title, suffix in channels:
            if c.lower().endswith(suffix):
                root_name = c.replace(suffix, "")
                items.setdefault(root_name, {})
                items[root_name][title] = c
                continue

    # Removing elements where some component is missing.
    for key in items.keys():
        if len(items[key]) == len(channels):
            images.append(items[key])
    
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


def segment_yeasts_cells(transmission):
    """
    Takes the transmission channel (brightfield) of yeast cells and segments it (instances segmentation).
    | CPU: 43s
    | GPU: 11s
    
    Args:
        transmission (image): Single channeled image, in brightfield, representing yeasts
    
    Returns:
        (image) An image containing labels (one value == one individual).
    """
    model = models.Cellpose(gpu=True, model_type='cyto')
    chan = [0, 1]
    masks, flows, styles, diams = model.eval(transmission, diameter=None, channels=chan)

    return masks


def increase_contrast(image, factor):
    """
    Increases the contrast of the provided image according to the alpha-beta-expension method.
    The resulting image occupies the whole range of possible values according to its data type (uint8, uint16, ...)
    Be careful, the modification is applied in place (the original image is modified).

    Returns:
        void

    Args:
        image: The image that will beneficiate of a contrast enhancement
        factor: A percentage in the range [0.0, 1.0] that determines what percentage of the histogram at the begining AND at the end will be destroyed.
    """
    start = 0 # Target start of histogram
    end   = np.iinfo(image.dtype).max # Target end of histogram

    hist, bin_edges = np.histogram(image, bins=end+1)
    
    total = np.sum(hist)
    limit = int(factor * total)

    count = 0
    index = 0
    while count < limit:
        count += hist[index]
        index += 1

    lower = index
    index = end
    count = 0

    while count < limit:
        count += hist[index]
        index -= 1

    upper = index
    sub = upper - lower

    for (l, c), val in np.ndenumerate(image):
        if val < lower:
            image[l, c] = 0
            continue
        if val > upper:
            image[l, c] = end
            continue
        image[l, c] = int(end * ((val - lower) / sub))


def place_markers(img, m_list):
    """
    Places pixels having the maximal intensity allowed by the data type, according to a list of 2D coordinates.

    Returns:
        A mask with black background and some pixels at their maximam intensity. The mask's width and height are the same as the input image.

    Args:
        img: An image, but it will just be used to copy its shape.
        m_list: A list of 2-sized elements representing 2D coordinates.
    """
    tmp = np.zeros(img.shape[0:2], dtype=np.uint16)

    for i, (x, y) in enumerate(m_list):
        tmp[x, y] = i+1
    
    return tmp


#################################################################################


def segment_transmission(full_path):
    """
    Takes the path of an image that contains some yeasts in transmission.

    Args:
        full_path: A string representing the absolute path of an image

    Returns:
        A uint16 image containing labels. Each label corresponds to an instance of yeast cell.
    """

    # Boolean value determining if we want to use all the slices of the stack, or just the most in-focus.
    pick_slices   = True
    slices_around = 2

    # >>> Opening stack as an image collection:
    stack     = np.array(ImageCollection(full_path))
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
        input_bf = stack
    
    # >>> Labeling the transmission channel:
    labeled_transmission = segment_yeasts_cells(input_bf)
    
    # >>> Finding and removing the labels touching the borders:
    cleared_bd = np.zeros(labeled_transmission.shape, dtype=labeled_transmission.dtype)
    clear_border(labeled_transmission, buffer_size=3, out=cleared_bd)
    
    return cleared_bd, input_bf


#################################################################################


def segment_spots(full_path):

    # >>> Opening YFP stack
    stack     = np.array(ImageCollection(full_path))
    stack_sz  = stack.shape
    input_yfp = None

    # >>> Max projection of the stack
    if len(stack_sz) > 2: # We have a stack, not a single image.
        input_yfp = np.max(stack, axis=0)
    else:
        input_yfp = stack

    increase_contrast(input_yfp, 0.001)
    save_yfp  = input_yfp
    input_yfp = median_filter(input_yfp, size=3)

    asf = input_yfp.astype(np.float64)
    LoG = gaussian_laplace(asf, sigma=3.0)
    t = threshold_otsu(LoG)
    mask = LoG < t

    asf = mask.astype(np.float64)
    chamfer = distance_transform_edt(asf)
    maximas = peak_local_max(chamfer, min_distance=6)

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

    for p in points:
        x = int(gridSize * (p[0] / float(shape[0])))
        y = int(gridSize * (p[1] / float(shape[1])))
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
    markers     = place_markers(mask, spots_list)
    labels      = watershed(~mask, markers, mask=mask).astype(np.uint16)
    spots_props = regionprops(labels, intensity_image=original_yfp)
    removed     = []

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
    
    removed_mask = np.isin(labels, removed)
    labels[removed_mask] = 0

    return ownership, labels


"""
    >>> IMPLEMENTATION:

- [X] Faire en sorte que même les cellules qui n'ont aucun spot soient comptées.
- [ ] Modifier les fonctions de segmentation pour qu'elles ne prennent pas un chemin mais une image pour pouvoir s'adapter aux ".czi".
- [ ] Rajouter des lignes de logs dans l'exécution.
- [X] {create_random_lut} Comment faire en sorte que les points consécutifs soient aussi loin que possible les uns des autres ?
- [ ] Stocker les résultats intermédiaires pour pouvoir découper en plugin.
- [X] {estimateUniformity} Le 2048 devrait être emprunté à la taille des images, ne pas être hard-codée.
- [X] Le masque peut encore être utilisé pour le marker based watershed.
- [ ] Changer l'implémentation pour qu'on puisse gérer les fichiers (.nd + .tif + .tif) et les fichiers (.czi).
      Le problème se pose pour le batching.
- [ ] Refaire l'implémentation du détecteur de cellules mortes.
- [X] Faire des histogrammes du nombre de spots, de leur intensité, ... ?
- [X] Ajouter le marker based watershed dans la méthode de détection de spots.
- [X] On veut l'aire, la position et l'intensité au centre des spots.
- [ ] Pour l'image de controle de la transmission, plutôt produire des contours que des labels qui sont complexes à distinguer à cause de leur proximité.
- [X] Essayer de détecter les mauvaises détections automatiquement. 
      Cela peut être fait en estimant la distribution des spots, ou on peut essayer de voir s'il y a plus de N points par cellule.
- [ ] Est-ce qu'on doit retirer le background pour faires les mesures sur la couche de fluo ?
      Si oui, est-ce qu'on utilise un algo ou simplement l'image qui représente le background ?

    >>> TESTS:

- [build_sets] Check that isolated elements are correctly suppressed, that hidden elements are ignored, that every image has its associated components.
- [create_random_lut] Check that points are uniformely scattered in space.
- [segment_yeasts_cells] Verify the number of labels on a known image.

    >>> À DEMANDER:

- [ ] Quelle forme ont les fichiers originaux s'ils ne sont pas renommés ?
- [ ] Prendre RDV en invitant un microscopiste.

"""
