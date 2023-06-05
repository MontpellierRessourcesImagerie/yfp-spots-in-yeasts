import numpy as np
import napari
from tifffile import imread
import os

def napari_get_reader(path):
    """
    Generate reader handling the opening of control images.

    Args:
        path: Path or list of paths. Only the first path of the list will be opened.

    Returns:
        An instance of the function used to handle a such folder.
    """
    p = path if isinstance(path, str) else path[0]

    # ysc = Yeast Spots Control
    if not p.endswith(".ysc"):
        return None

    return reader_function



def reader_function(paths):
    """Take a path or list of paths and return a list of LayerData tuples.

    Readers are expected to return data as a list of tuples, where each tuple
    is (data, [add_kwargs, [layer_type]]), "add_kwargs" and "layer_type" are
    both optional.

    Parameters
    ----------
    path : str or list of str
        Path to file, or list of paths.

    Returns
    -------
    layer_data : list of tuples
        A list of LayerData tuples where each tuple in the list contains
        (data, metadata, layer_type), where data is a numpy array, metadata is
        a dict of keyword arguments for the corresponding viewer.add_* method
        in napari, and layer_type is a lower-case string naming the type of
        layer. Both "meta", and "layer_type" are optional. napari will
        default to layer_type=="image" if not provided
    """
    
    path = paths if isinstance(paths, str) else paths[0]
    if not os.path.isdir(path):
        return []

    print(f"Opening control: {path}")
    napari.current_viewer().layers.clear()

    # Acquiring properties from index (name, date, source images, ...)
    properties = {}
    f = open(os.path.join(path, "index.txt"), 'r')
    if f.closed:
        return []
    
    data = f.read()
    f.close()
    data = [d for d in data.split("\n") if (len(d) > 1)]
    data = [(data[i], data[i + 1]) for i in range(0, len(data), 2)]
    
    for (key, value) in data:
        properties[key] = value

    print(f"Loaded control for: {properties['name']}")
    print(f"Original images location: {properties['sources']}")
    print(f"Process performed on: {properties['time']}")

    control_paths = {
        'spots_list'     : os.path.join(path, properties['name']+".csv"),
        'outlines'       : os.path.join(path, properties['name']+"_outlines.tif"),
        'labeled_cells'  : os.path.join(path, properties['name']+"_cells.tif"),
        'labeled_spots'  : os.path.join(path, properties['name']+"_spots.tif"),
        'projected_cells': os.path.join(path, properties['name']+"_bf.tif"),
        'projected_spots': os.path.join(path, properties['name']+"_fluo.tif"),
        'measures'       : os.path.join(path, properties['name']+".json")
    }

    # Removing unavailable paths
    keys = [str(k) for k in control_paths.keys()]
    for key in keys:
        p = os.path.join(path, control_paths[key])
        if not os.path.isfile(p):
            print(f"Property `{key}` not available.")
            control_paths.pop(key)

    # ===========================

    components = []

    # ===== PROJECTED CELLS =====
    projected_cells = control_paths.get('projected_cells')
    if projected_cells is not None:
        components.append((
            imread(projected_cells), 
            {
                'name': "projected_cells"
            },
            "image"
        ))

    # ===== PROJECTED SPOTS =====
    projected_spots = control_paths.get('projected_spots')
    if projected_spots is not None:
        components.append((
            imread(projected_spots), 
            {
                'name': "yfp",
                'blending': 'opaque'
            }, 
            'image'
        ))
    
    # ===== LABELED SPOTS =====
    labeled_spots = control_paths.get('labeled_spots')
    if labeled_spots is not None:
        components.append((
            imread(labeled_spots), 
            {
                'name'   : "labeled_spots",
                'visible': False,
                'opacity': 1.0
            }, 
            "labels"
        ))

    # ===== SPOTS LOCATIONS =====
    spots_list = control_paths.get('spots_list')
    if spots_list is not None:
        components.append((
            np.loadtxt(spots_list, delimiter=',', skiprows=1, dtype=int), 
            {
                'name'      : "spots",
                'edge_color': "#ff0000ff",
                'face_color': "#00000000"
            },
            "points"
        ))

    # ===== CELLS OUTLINES =====
    outlines = control_paths.get('outlines')
    if outlines is not None:
        components.append((
            imread(outlines), 
            {
                'name'    : "outlines",
                'blending': "additive"
            },
            "image"
        ))

    return components
