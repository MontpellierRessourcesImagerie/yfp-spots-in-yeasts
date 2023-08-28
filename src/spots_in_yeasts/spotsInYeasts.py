from skimage.io import imsave
from skimage.filters import threshold_isodata, threshold_otsu
from skimage.segmentation import watershed, clear_border, find_boundaries
from skimage.morphology import dilation, disk
from skimage.measure import regionprops
from skimage.measure import label as connected_compos_labeling
from skimage.feature import peak_local_max
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import median_filter, gaussian_laplace, distance_transform_cdt, label
from termcolor import colored
import os, cv2, shutil
import numpy as np
from cellpose import models, utils, io
from datetime import datetime
from skimage import exposure
from scipy.stats import kstest
from scipy.ndimage import binary_erosion, binary_dilation

_coordinates = {
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1)
}

def create_random_lut():
    """
    Creates a random LUT of 256 slots to display labeled images with colors far apart from each other.
    Black is reserved for the background.

    Returns:
        LinearSegmentedColormap: A cmap object that can be used with the imshow() function. ex: `imshow(image, cmap=create_random_lut())`
    """
    return LinearSegmentedColormap.from_list('random_lut', np.vstack((np.array([(0.0, 0.0, 0.0)]), np.random.uniform(0.01, 1.0, (255, 3)))))


def write_labels_image(image, font_scale):
    """
    Creates an image on which the indices of labels are literally written in the center of each label.

    Args:
        image: A labeled image.
        fonst_scale: Size of the font to write digits.
    
    Returns:
        A binary mask representing the literal index of each label.
    """
    regions   = regionprops(image)
    canvas    = np.zeros(image.shape, dtype=np.uint8)
    thickness = 2

    for region in regions:
        y, x = region.centroid
        size, baseline = cv2.getTextSize(str(region.label), cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        cv2.putText(canvas, str(region.label), (int(x-size[0]/2), int(y+size[1]/2)), cv2.FONT_HERSHEY_SIMPLEX, font_scale, 255, thickness)

    return canvas

def find_focused_slice(stack, around=2):
    """
    Determines which slice has the best focus and selects a range of slices around it.
    The process is based on the variance recorded for each slice.
    Displays a warning if the number of slices is insufficient.
    A safety check is performed to ensure that the returned indices are within the range of the stack's size.

    Args:
        stack: (image stack) The stack in which we search the focused area.
        around: (int) Number of slices to select around the most in-focus one.

    Returns:
        (int, int): A tuple centered around the most in-focus slice. If we call 'F' the index of that slice, then the tuple is: `(F-around, F+around)`.
    """
    # If we don't have a stack, we just return a tuple filled with zeros.
    if len(stack.shape) < 3:
        print("The image is a single slice, not a stack.")
        return (0, 0)

    nSlices, width, height = stack.shape
    maxSlice = np.argmax([cv2.Laplacian(stack[s], cv2.CV_64F).var() for s in range(nSlices)])
    selected = (max(0, maxSlice-around), min(nSlices-1, maxSlice+around))
    
    print(f"Selected slices: ({selected[0]+1}, {selected[1]+1}). ", end="")
    print(colored(f"({nSlices} slices available)", 'dark_grey'))
    if selected[1]-selected[0] != 2*around:
        print(colored("Focused slice too far from center!", 'yellow'))

    return selected


def segment_yeasts_cells(transmission, gpu=True):
    """
    Takes the transmission channel (brightfield) of yeast cells and segments it (instances segmentation).
    
    Args:
        transmission (image): Single channeled image, in brightfield, representing yeasts
    
    Returns:
        (image) An image containing labels (one value == one individual).
    """
    model = models.Cellpose(gpu=gpu, model_type='cyto')
    chan = [0, 0]
    print("Segmenting cells...")
    masks, flows, styles, diams = model.eval(transmission, diameter=None, channels=chan)
    print(f"Cells segmentation done. {len(np.unique(masks))-1} cells detected.")
    return masks


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
    print(f"{len(m_list)} seeds placed.")
    return tmp


#################################################################################


def segment_transmission(stack, gpu=True, slices_around=2):
    """
    Takes the path of an image that contains some yeasts in transmission.

    Args:
        stack: A numpy array representing the transmission channel

    Returns:
        A uint16 image containing labels. Each label corresponds to an instance of yeast cell.
    """
    # Boolean value determining if we want to use all the slices of the stack, or just the most in-focus.
    pick_slices   = True

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
        input_bf = np.squeeze(stack)
    
    # >>> Labeling the transmission channel:
    labeled_transmission = segment_yeasts_cells(input_bf, gpu)

    return labeled_transmission, input_bf


#################################################################################

def associate_spots_yeasts(labeled_cells, labeled_spots, fluo_spots, area_threshold_down, area_threshold_up, solidity_threshold, extent_threshold, classification=None):
    """
    Associates each spot with the label it belongs to.
    A safety check is performed to make sure no spot falls in the background.

    Args:
        labeled_cells: A single-channeled image with dtype=uint16 containing the segmented transmission image.
        labeled_spots: A labelised image representing spots
        fluo_spots: The original fluo image containing spots.

    Returns:
        A dictionary in which keys are the labels of each cell. Each key points to a list of dictionary. Each element of the list corresponds to a spot.
        An image representing labels in the fluo channel (a label per spot) is also returned.
    """
    unique_values = np.unique(labeled_cells)
    ownership     = {int(u): [] for u in unique_values if (u > 0)}
    spots_props   = regionprops(labeled_spots, intensity_image=fluo_spots)

    for spot in spots_props:
        cds = [int(k) for k in spot.centroid]
        r, c = cds
        lbl = int(labeled_cells[r, c])

        if lbl == 0:
            continue # We are in the background

        if (int(spot['area']) > area_threshold_up) or (int(spot['area']) < area_threshold_down):
            continue
        
        if float(spot['solidity']) < solidity_threshold:
            continue
        
        if float(spot['extent']) < extent_threshold:
            continue
        
        ownership[lbl].append({
            'label'         : int(spot['label']),
            'location'      : (r, c),
            'intensity_mean': round(float(spot['intensity_mean']), 3),
            'intensity_min' : round(float(spot['intensity_min']), 3),
            'intensity_max' : round(float(spot['intensity_max']), 3),
            'area'          : round(float(spot['area']), 3),
            'perimeter'     : round(float(spot['perimeter']), 3),
            'solidity'      : round(float(spot['solidity']), 3),
            'extent'        : round(float(spot['extent']), 3),
            'intensity_sum' : int(np.sum(spot.intensity_image)),
            'category'      : classification[int(spot['label'])] if (classification is not None) else None
        })
    
    compare = np.array([item['label'] for sub_list in ownership.values() for item in sub_list])
    removed_mask = np.isin(labeled_spots, compare, invert=True)
    labeled_spots[removed_mask] = 0

    return ownership, np.array([item['location'] for sub_list in ownership.values() for item in sub_list]), labeled_spots


def segment_spots(stack, labeled_cells, death_threshold, sigma=3.0, peak_d=5, threshold_rel=0.7):
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
    # >>> Opening fluo spots stack
    stack_sz     = stack.shape
    input_fSpots = None

    # >>> Max projection of the stack
    if len(stack_sz) > 2: # We have a stack, not a single image.
        input_fSpots = np.max(stack, axis=0)
    else:
        input_fSpots = np.squeeze(stack)

    # >>> Contrast augmentation + noise reduction
    print("Starting spots segmentation...")
    save_fSpots  = np.copy(input_fSpots)
    input_fSpots = median_filter(input_fSpots, size=3)

    # >>> LoG filter + thresholding
    asf  = input_fSpots.astype(np.float64)
    LoG  = gaussian_laplace(asf, sigma=sigma)
    t    = threshold_isodata(LoG)
    mask = LoG < t

    # >>> Detection of spots location
    asf     = mask.astype(np.float64)
    chamfer = distance_transform_cdt(asf)
    maximas = peak_local_max(chamfer, min_distance=peak_d, threshold_rel=threshold_rel)

    spots_props = {props.label: props['intensity_mean'] for props in regionprops(labeled_cells, intensity_image=save_fSpots)}
    maximas = np.array([(l, c) for (l, c) in maximas if (labeled_cells[l, c] > 0) and (spots_props[labeled_cells[l, c]] < death_threshold)])
    print(f"{len(maximas)} spots found.")

    # >>> Isolating instances of spots
    m_shape   = mask.shape[0:2]
    markers   = place_markers(m_shape, maximas)
    lbd_spots = watershed(~mask, markers, mask=mask).astype(np.uint16)

    # Sorting coordinates by label index.
    maximas = np.array([(l, c) for (s, l, c) in sorted([(lbd_spots[l, c], l, c) for (l, c) in maximas])])

    # >>> List of spots coordinates, labeled spots, flattened version of spots' fluo channel.
    return maximas, lbd_spots, save_fSpots


################################################################

def prepare_directory(path):
    """
    Prepares a directory to receive the control images for the batch mode.
    """
    if os.path.exists(path):
        # Empty the folder
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")
    else:
        # Create the folder
        os.makedirs(path)


######################################################################

def remove_labels(image, labels):
    """
    Macro-function removing some labels from an image. The modification is made in-place.

    Args:
        image: A labeled image.
        labels: A set of indices that we want to remove from `image`.
    """
    lbls = np.array([l for l in labels])
    mask = np.isin(image, lbls)
    image[mask] = 0

def fill_holes(image):
    """
    A hole is a background area surrounded by a unique label and from which we can't reach the image's border.
    No in-place editing.

    Args:
        image: A labeled image on black background

    Returns:
        The same image as input but without holes in labels.
    """
    bg_mask = clear_border(connected_compos_labeling(binary_dilation(image == 0))).astype(np.uint16)
    props   = regionprops(bg_mask, intensity_image=image)

    lut = {}
    for region in props:
        if region.label == 0:
            continue
        data = region['image_intensity']
        data[np.logical_not(region['image'])] = 0
        values = set(np.unique(data)).difference({0})
        lut[region.label] = 0 if len(values) > 1 else values.pop()

    def replace_with_dict(x):
        return lut.get(x, 0)
    
    vfunc = np.vectorize(replace_with_dict)
    new_array = vfunc(bg_mask).astype(np.uint16)

    return np.maximum(image, new_array)

class YeastsPartitionGraph(object):
    """
    Class implementing the Hopcroft-Karp algorithm to create a maximal dual-matching.
    """
    def __init__(self, o_graph, cell_to_nuclei, nucleus_to_cells, labeled_yeasts, labeled_nuclei):
        self.graph      = dict()
        self.partitions = {1, 2}
        
        for cell_lbl, neighbor_cells in o_graph.items():
            ppts = self.graph.get(cell_lbl)
            if ppts is not None:
                continue
            vertices = self.find_partition(cell_lbl, cell_to_nuclei, nucleus_to_cells, o_graph)
            for (vertex, partition, bound, coords) in vertices:
                self.graph[vertex] = {
                    'neighbors'  : o_graph[vertex]['neighbors'].copy(),
                    'partition'  : partition,
                    'bound_to'   : bound if (bound > 0) else None,
                    'coordinates': coords,
                    'dist'       : 0
                }
        
        self.launch_hopcroft_karp()
        self.make_new_labels(labeled_yeasts, labeled_nuclei, cell_to_nuclei)
        self.remove_borders(labeled_yeasts, labeled_nuclei)
        print(colored("Maximum bipartite matching of the adjacency graph finished.", 'green'))

    def remove_borders(self, labeled_yeasts, labeled_nuclei):
        mask = binary_erosion(np.zeros(labeled_yeasts.shape) == 0)
        working_copy = np.copy(labeled_yeasts)
        working_copy[mask] = 0

        discarded   = np.array([i for i in set(np.unique(working_copy)).difference({0})])
        remove_labels(labeled_yeasts, discarded)
        remove_labels(labeled_nuclei, discarded)
        print(f"{len(discarded)} cells removed because they are cut by the border.")
    
    def find_partition(self, vertex, cell_to_nuclei, nucleus_to_cells, o_graph):
        nucleus_lbl = cell_to_nuclei[vertex]['owner']
        
        if nucleus_lbl == 0: # 0 means that this cell doesn't have a nucleus.
            return [(vertex, 2, 0, o_graph[vertex]['coordinates'])] # Vertices with no nuclei are stored in the partition 2.
        else:
            n_usage = nucleus_to_cells[nucleus_lbl]['used']

            if n_usage == 2:
                c1, c2 = [cell_lbl for cell_lbl, cell_props in enumerate(cell_to_nuclei) if (cell_props is not None) and (cell_props['owner'] == nucleus_lbl)]
                return [(c1, 1, c2, o_graph[c1]['coordinates']), (c2, 1, c1, o_graph[c2]['coordinates'])]
            
            if n_usage == 1:
                return [(vertex, 1, 0, o_graph[vertex]['coordinates'])]

            raise ValueError(f"This case is not handled. (n_usage={n_usage} for cell {vertex})")
    
    def make_cells_lut(self):
        current = 1
        lut = {}
        # partition 2: pas de nucleus, partition 1: a un nucleus
        for key, props in self.graph.items():
            if props['bound_to'] is None:
                if props['partition'] == 1:
                    # If the cell is bound to nobody but has a nucleus (independent cell)
                    lut[key] = current
                    current += 1
                else:
                    lut[key] = 0 # discarding the cell. Bound to nodoby and no nucleus.
            else:
                n = props['bound_to']
                label = lut.get(key)
                if label is None:
                    lut[key] = current
                    lut[n] = current
                    current += 1
        
        return lut

    def make_nuclei_lut(self, cell_to_nuclei, cells_lut):
        """
        Makes a dictionary to transform the indices of nuclei.
        It is used to make the nuclei indices match their owner cell's index.

        Args:
            cell_to_nuclei: Structure giving for a cell the index of its nucleus.
            cells_lut: LUT used to make mother and daughter cells match each other's label.
        
        Returns:
            A LUT to transform the nuclei indices.
        """
        lut = {}
        for cell_lbl, cell_props in enumerate(cell_to_nuclei):
            if cell_props['owner'] <= 0:
                continue
            lut[cell_props['owner']] = cells_lut[cell_lbl]
        return lut

    def make_new_labels(self, old_labels, old_nuclei, cell_to_nuclei):
        # Cells part
        lut_cells  = self.make_cells_lut()
        lut_nuclei = self.make_nuclei_lut(cell_to_nuclei, lut_cells)
        
        def replace_cells_labels(x):
            return lut_cells.get(x, 0)
        
        vfunc = np.vectorize(replace_cells_labels)
        new_labels = vfunc(old_labels)
        new_labels = fill_holes(new_labels)

        old_labels[:] = new_labels.astype(np.int32)

        # Nuclei part (we want nuclei labels to mach their cell)
        def replace_nuclei_labels(x):
            return lut_nuclei.get(x, 0)

        vfunc = np.vectorize(replace_nuclei_labels)
        new_nuclei = vfunc(old_nuclei)
        old_nuclei[:] = new_nuclei.astype(np.int32)
        print(f"{len(np.unique(old_nuclei)-1)} cells left after merging mothers and daughters.")

    def bfs(self):
        queue = []
        for node, ppts in self.graph.items():
            if ppts['partition'] != 1:
                continue
            if ppts['bound_to'] == None:
                ppts['dist'] = 0
                queue.append(node)
            else:
                ppts['dist'] = float('inf')
        
        self.graph[None]['dist'] = float('inf')
        while queue:
            node = queue.pop(0)
            if self.graph[node]['dist'] < self.graph[None]['dist']:
                for v in self.graph[node]['neighbors']:
                    if self.graph[v]['partition'] == 2:
                        if self.graph[self.graph[v]['bound_to']]['dist'] == float('inf'):
                            self.graph[self.graph[v]['bound_to']]['dist'] = self.graph[node]['dist'] + 1
                            queue.append(self.graph[v]['bound_to'])
        
        return self.graph[None]['dist'] != float('inf')
    
    def dfs(self, node):
        if node is None:
            return True

        for v in self.graph[node]['neighbors']:
            if self.graph[v]['partition'] == 1:
                continue
            if self.graph[self.graph[v]['bound_to']]['dist'] == self.graph[node]['dist'] + 1:
                if self.dfs(self.graph[v]['bound_to']):
                    self.graph[node]['bound_to'] = v
                    self.graph[v]['bound_to'] = node
                    return True
        
        self.graph[node]['dist'] = float('inf')
        return False

    def launch_hopcroft_karp(self):
        matching = 0

        self.graph[None] = {
                'neighbors' : set(),
                'partition'  : 2,
                'coordinates': [0, 0],
                'bound_to': None,
                'dist'    : 0
            }

        while self.bfs():
            for node in self.graph:
                if self.graph[node]['partition'] != 1:
                    continue
                if self.graph[node]['bound_to'] == None and self.dfs(node):
                    matching += 1
        
        del self.graph[None]
        return matching


def nuclei_from_fluo(stack_fluo_nuclei):
    """
    Produces a segmentation of nuclei based on the nuclei marking (either a single slice or a stack).

    Args:
        An image or a stack representing the nuclei marking.
    
    Results:
        The MIP of the provided image and a labeled version of nuclei.
    """
    # Opening fluo spots stack
    stack_sz    = stack_fluo_nuclei.shape
    fluo_nuclei = None

    # Max projection of the stack
    if len(stack_sz) > 2: # We have a stack, not a single image.
        fluo_nuclei = np.max(stack_fluo_nuclei, axis=0)
    else:
        fluo_nuclei = np.squeeze(stack_fluo_nuclei)
    
    # Creating a basic mask representing nuclei.
    t = threshold_otsu(fluo_nuclei)
    mask_nuclei = fluo_nuclei > t
    lbl_nuclei = connected_compos_labeling(mask_nuclei)

    return fluo_nuclei, lbl_nuclei

def is_undirected(graph):
    """ Checks whether a graph is undirected or not. """
    for key, ns in graph.items():
        for n in ns:
            if key not in graph[n]:
                return False
    return True

def get_neighbors(l, c, height, width):
    global _coordinates
    new_coordinates = [(l+y, c+x) for (y, x) in _coordinates]
    return np.array([(y, x) for (y, x) in new_coordinates if (y >= 0) and (x >= 0) and (y < height) and (x < width)]).T

def adjacency_graph(labeled_cells, check_undirected=False):
    """
    Creates the adjacency graph of the segmented cells.
    Two cells are called "adjacent" if their labels are touching one another in 8-connectivity.

    Args:
        labeled_cells: The labeled image representing segmented cells.
        check_undirected: Activate the cheking of the graph essential properties (only for debug purposes).
    
    Returns:
        A dictionary representing the cells as a graph, indexed by cells' labels.
        For each label, gives: its location and its neighbors
    """
    
    height, width = labeled_cells.shape
    graph    = {}
    contacts = {}
    print("Building adjacency graph of the cells.")

    for (l, c), cell_label in np.ndenumerate(labeled_cells):
        if cell_label == 0:
            continue
        graph.setdefault(cell_label, set())
        ys, xs = get_neighbors(l, c, height, width)
        labels = labeled_cells[ys, xs]

        for lbl in labels:
            if (lbl > 0) and (lbl != cell_label):
                tpl = (lbl, cell_label) if (lbl < cell_label) else (cell_label, lbl)
                contacts.setdefault(tpl, 0)
                contacts[tpl] += 1
                graph[cell_label].add(lbl)
    
    for (a, b), count in contacts.items(): # We cut the edge if the contact surface is too small.
        if count < 50:
            graph[a].remove(b)
            graph[b].remove(a)

    if check_undirected:
        if is_undirected(graph):
            print(colored("The graph is undirected.", 'green'))
        else:
            print(colored("Error. The graph is not undirected.", 'red'))

    regions = regionprops(labeled_cells)
    cleaned = {}
    for cell in regions:
        cleaned[cell.label] = {'neighbors': graph[cell.label], 'coordinates': [i for i in cell.centroid]}

    print(colored("Adjacency graph succesfully built.", 'green'))
    return cleaned

def remove_excessive_coverage(labeled_cells, labeled_nuclei, covering_threshold):
    """
    Removing cells in which the nucleus occupies too much surface (dead cell).

    Args:
        labeled_cells: The image containing the labeled cells.
        labeled_nuclei: The image containing the labeled nuclei.
        covering_threshold: Percentage of a cell that must be covered by nuclei for this cell to be considered dead.
    
    Returns:
        Two sets containing the indices of discarded nuclei and the indices of discarded cells.
    """
    
    #
    # Principle:
    #     1. Transform nuclei into mask
    #     2. Create a new image which is a copy of the cells from which we subtract our mask
    #     3. Measure the area of cells labels in both images
    #     4. Make the ratio to determine what was the region occupied by the nucleus in each cell.
    #
    
    mask_nuclei = labeled_nuclei > 0
    remaining_cells = np.copy(labeled_cells)
    remaining_cells[mask_nuclei] = 0 # We punch holes in cells.
    regions_before = {r['label']: (
        r['area'], 
        r['centroid'], 
        sorted([(count, unq) for unq, count in zip(*np.unique(r['image_intensity'], return_counts=True)) if (unq != 0)])
        ) for r in regionprops(labeled_cells, intensity_image=labeled_nuclei)}
    
    regions_after    = {r['label']: (r['area'], r['centroid']) for r in regionprops(remaining_cells)}
    discarded_cells  = set()
    discarded_nuclei = set()

    for cell_lbl, cell_props in regions_before.items():
        c = regions_after.get(cell_lbl)
        if c is None: # The cell was completly obliterated and doesn't exist anymore.
            discarded_cells.add(cell_lbl)
            continue
        ratio = c[0] / cell_props[0] # area_after / area_before
        if ratio < covering_threshold:
            discarded_cells.add(cell_lbl)
            if len(cell_props[2]) > 0:
                discarded_nuclei.add(cell_props[2][-1][1])
    
    print(f"{len(discarded_cells)} cells were discarded due to their nucleus covering them.")
    remove_labels(labeled_cells, discarded_cells)
    remove_labels(labeled_nuclei, discarded_nuclei)
    
    return discarded_cells, discarded_nuclei


def assign_nucleus(labeled_cells, labeled_nuclei, covering_threshold, graph=None):
    """
    First step of the nuclei segmentation. It starts by finding all the cells having "their own nucleus" (== a cell overlaped by a nucleus)

    Args:
        labeled_cells: The image containing the labeled cells.
        labeled_nuclei: The image containing the labeled nuclei.
        covering_threshold: Percentage of a cell that must be covered by nuclei for this cell to be considered dead.
        graph: Adjacency graph of the labeled cells.
    
    Returns:
        - The labeled cells from which we removed invalid individuals.
        - The labeled nuclei
        - The adjacency graph from which we removed dead individuals.
        - A structure mapping cells indices to nuclei indices.
        - A structure mapping nuclei indices to cells indices.
    """
    
    # 1. We remove cells covered too much by some nuclei.
    discarded_cells, discarded_nuclei = remove_excessive_coverage(labeled_cells, labeled_nuclei, covering_threshold)

    # 2. Defining variables.
    nucleus_to_cells = [None for _ in range(max(max(discarded_nuclei.union({0})), np.max(labeled_nuclei))+1)]
    cell_to_nuclei   = [{
                    'users' : set(), # Nuclei overlaping with this cell.
                    'valid' : True,  # Boolean indicating if the cell will be discarded.
                    'owner' : 0,     # Nucleus owning this cell.
                    'stable': False, # True if we found a nucleus belonging ONLY to this cell (not shared with another).
                    'center': False  # True if the centroid of a nucleus was found in this cell.
                } for _ in range(max(max(discarded_cells.union({0})), np.max(labeled_cells))+1)]

    # 3. Building an association table in both ways (nucleus -> cells & cell -> nuclei)
    nuclei_props  = regionprops(labeled_nuclei, intensity_image=labeled_cells)
    for nucleus in nuclei_props: # In this loop, we iterate through nuclei to find by how many cells it's being used.
        nucleus_lbl = nucleus.label
        l, c        = [int(k) for k in nucleus.centroid]
        cell_lbl    = labeled_cells[l, c]

        mask = np.logical_not(nucleus['image'])
        data = nucleus['intensity_image']
        data[mask]  = 0
        unq, counts = np.unique(data, return_counts=True)
        cell_labels = set([(i, c) for i, c in zip(unq, counts) if (i != 0 and c >= 15)]) # Labels of all the cells this nucleus intersects with.

        # Recording which cells the nucleus participates in
        nucleus_to_cells[nucleus_lbl] = {
            'users'   : cell_labels,
            'centroid': (l, c),
            'at'      : cell_lbl,
            'valid'   : True,
            'used'    : 0
        }

        # Recording which nuclei a given cell uses.
        for lbl, count in cell_labels:
            cell_to_nuclei[lbl]['users'].add(nucleus_lbl)
                
    # 4. Validation phase
    for nucleus_lbl, nucleus_props in enumerate(nucleus_to_cells):
        
        # No nucleus with this label or nucleus already discarded.
        if (nucleus_props is None) or (nucleus_props['valid'] == False):
            continue
        
        # An isolated nucleus (falling in the background) can be discarded.
        if len(nucleus_props['users']) == 0:
            nucleus_props['valid'] = False
            continue

        # Nucleus that participates in only one cell (fragmented nucleus, stable cell, ...)
        if len(nucleus_props['users']) == 1: 
            cell_lbl  = list(nucleus_props['users'])[0][0]
            cell_ppts = cell_to_nuclei[cell_lbl]

            if not cell_ppts['valid']: # The only cell it participates in is not valid.
                nucleus_props['valid'] = False
                continue
            
            if (cell_ppts['owner'] != 0):
                if (cell_ppts['stable']): # The cell already has an owner: we are on a fragmented nucleus
                    cell_ppts['valid']  = False
                    cell_ppts['stable'] = False
                    continue
                else: # There was simply another nucleus intersecting before
                    nucleus_to_cells[cell_ppts['owner']]['used'] -= 1

            cell_ppts['owner']  = nucleus_lbl
            cell_ppts['stable'] = True
            cell_ppts['center'] = True
            nucleus_props['used'] += 1
        
        # There are several cells overlaping with this nucleus
        else:
            main_cell = nucleus_props['at']
            for cell_lbl, count in nucleus_props['users']:
                cell_ppts = cell_to_nuclei[cell_lbl]
                
                if cell_ppts['stable'] or cell_ppts['center']:
                    continue

                if cell_ppts['owner'] > 0:
                    nucleus_to_cells[cell_ppts['owner']]['used'] -= 1

                cell_ppts['owner']  = nucleus_lbl
                nucleus_props['used'] += 1
                cell_ppts['center'] = (cell_lbl == main_cell)

    
    for nucleus_lbl, nucleus_props in enumerate(nucleus_to_cells): # Droping nuclei participating in 0 or more than 2 cells.
        if nucleus_props is None:
            continue
        if nucleus_props['used'] > 2:
            for user, count in nucleus_props['users']:
                if cell_to_nuclei[user]['owner'] == nucleus_lbl:
                    cell_to_nuclei[user]['owner'] = 0
            
            nucleus_props['used'] = 0
            usages = sorted(list(nucleus_props['users']), key=lambda x: x[1])
            
            cell1, count1 = usages[0]
            cell_to_nuclei[cell1]['owner'] = nucleus_lbl
            nucleus_props['used'] += 1

            cell2, count2 = usages[1]
            if count2 >= 0.5 * count1:
                cell_to_nuclei[cell2]['owner'] = nucleus_lbl
                nucleus_props['used'] += 1

    return labeled_cells, labeled_nuclei, graph, cell_to_nuclei, nucleus_to_cells


def segment_nuclei(labeled_yeasts, stack_fluo_nuclei, threshold_coverage):
    """
    Launches the procedure to segment nuclei from the dedicated fluo channel, and merge mother cells with their daughter if the division process is still ongoing.

    Args:
        labeled_yeasts: Image containing the labeled yeast cells.
        stack_fluo_nuclei: Image containing the stained nuclei.
        threshold_coverage: Percentage (in [0.0, 1.0]) of a cell that must be covered by a nucleus to be considered dead.
    
    Returns:
        - The maximal projection of the stained nuclei channel.
        - The labeled yeasts from which we removed the dead cells.
        - The image containing the labeled nuclei.
    """
    labeled_yeasts = np.copy(labeled_yeasts)
    flattened_nuclei, labeled_nuclei = nuclei_from_fluo(stack_fluo_nuclei)
    graph = adjacency_graph(labeled_yeasts)
    
    print("Starting nuclei segmentation.")
    labeled_cells, labeled_nuclei, graph, cell_to_nuclei, nucleus_to_cells = assign_nucleus(labeled_yeasts, labeled_nuclei, threshold_coverage, graph)
    ypg = YeastsPartitionGraph(graph, cell_to_nuclei, nucleus_to_cells, labeled_yeasts, labeled_nuclei)
    print(colored("Segmentation of nuclei done.", 'green'))

    return flattened_nuclei, labeled_yeasts, labeled_nuclei


def distance_spot_nuclei(labeled_cells, labeled_nuclei, labeled_spots):
    """
    Assign a class to every spot depending on its location according to the nucleus of the cell it is in.
    It can be 'nuclear', 'cytoplasmic' or 'peripheral'.

    Args:
        labeled_cells: The image containing labeled cells.
        labeled_nuclei: The image containing labeled nuclei.
        labeled_spots: The image containing labeled spots.
    
    Returns:
        A dictionary giving for each spot label (int), its category (str).
    """
    total_regions  = regionprops(labeled_cells, intensity_image=labeled_spots)
    nuclei_regions = regionprops(labeled_nuclei, intensity_image=labeled_spots)
    total_sizes   = {}

    # Extracting total size of every spot.
    for region in total_regions:
        vals, counts = np.unique(region.image_intensity, return_counts=True)
        for spot_label, count in zip(vals, counts):
            total_sizes[spot_label] = count
    
    nuclear_sizes = {k: 0 for k in total_sizes.keys()}
    for region in nuclei_regions:
        vals, counts = np.unique(region.image_intensity, return_counts=True)
        for spot_label, count in zip(vals, counts):
            nuclear_sizes[spot_label] = count
    
    classification = {k: 'UNDEFINED' for k in total_sizes.keys()}
    for label, total_count in total_sizes.items():
        ratio = nuclear_sizes[label] / total_count
        if (ratio > 0.99):
            classification[label] = 'NUCLEAR'
        elif (ratio <= 0.001):
            classification[label] = 'CYTOPLASMIC'
        else:
            classification[label] = 'PERIPHERAL'
    
    print(colored("Spots classified.", 'green'))
    return classification

def create_reference_to(labeled_cells, labeled_spots, spots_list, name, control_dir_path, source_path, projection_cells, projection_spots, indices, labeled_nuclei, nuclei_fluo, spots_colors):
    """
    Creates a folder containing everything a user needs to see in order to check whether the process ended correctly and produced a correct segmentation.
    """
    present = datetime.now()

    # Projection of brightfield
    imsave(
        os.path.join(control_dir_path, name+"_bf.tif"),
        projection_cells)

    # Projection of spots fluo
    imsave(
        os.path.join(control_dir_path, name+"_fluo_spots.tif"),
        projection_spots)

    # Projections of nuclei fluo
    if nuclei_fluo is not None:
        imsave(
            os.path.join(control_dir_path, name+"_fluo_nuclei.tif"),
            nuclei_fluo)

    # ----

    # Cells indices
    imsave(
        os.path.join(control_dir_path, name+"_indices.tif"),
        indices)

    # ----
    
    # Labeled cells
    imsave(
        os.path.join(control_dir_path, name+"_segmented_cells.tif"),
        labeled_cells)

    # labeled spots
    imsave(
        os.path.join(control_dir_path, name+"_segmented_spots.tif"),
        labeled_spots)

    # Labeled nuclei
    if labeled_nuclei is not None:
        imsave(
            os.path.join(control_dir_path, name+"_segmented_nuclei.tif"),
            labeled_nuclei)

    # Class of the spots
    if spots_colors is not None:
        with open(os.path.join(control_dir_path, name+"_spots_colors.txt"), 'w') as f:
            textual = "\n".join(spots_colors)
            f.write(textual)
    
    # ----

    # Create the CSV with spots list, save it along segmented spots
    np.savetxt(
        os.path.join(control_dir_path, name+".csv"),
        spots_list,
        delimiter=',',
        header="axis-0, axis-1")

    # Saving the index to read the folder
    f = open(os.path.join(control_dir_path, "index.txt"), 'w')
    f.write("name\n")
    f.write(name+"\n")
    f.write("sources\n")
    f.write(source_path+"\n")
    f.write("time\n")
    f.write(present.strftime("%d/%B/%Y (%H:%M:%S)")+"\n")
    f.close()
