import numpy as np
import napari
from tifffile import imread
import os

def napari_get_reader(path):
    p = path if isinstance(path, str) else path[0]
    
    # ysc = Yeast Spots Control
    if not p.lower().endswith(".ysc"):
        return None

    return reader_function


def reader_function(paths):
    # Check that we have the path of a folder.    
    path = paths if isinstance(paths, str) else paths[0]
    if not os.path.isdir(path):
        return []

    print(f"Opening control: {path}")
    napari.current_viewer().layers.clear()

    # Acquiring properties from index (name, date, source images, ...)
    properties = {}
    ppts_path  = os.path.join(path, "index.txt")
    if not os.path.isfile(ppts_path):
        return []

    f = open(ppts_path, 'r')
    if f.closed:
        return []
    data = f.read()
    f.close()

    # Parsing the different available files.
    data = [d for d in data.split("\n") if (len(d) > 1)]
    data = [(data[i], data[i + 1]) for i in range(0, len(data), 2)]
    
    for (key, value) in data:
        properties[key] = value

    print(f"Loaded control for:       {properties['name']}")
    print(f"Original images location: {properties['sources']}")
    print(f"Process performed on:     {properties['time']}")

    control_paths = {
        'spots_list'      : os.path.join(path, properties['name']+".csv"),
        'labeled_cells'   : os.path.join(path, properties['name']+"_segmented_cells.tif"),
        'labeled_spots'   : os.path.join(path, properties['name']+"_segmented_spots.tif"),
        'labeled_nuclei'  : os.path.join(path, properties['name']+"_segmented_nuclei.tif"),
        'projected_cells' : os.path.join(path, properties['name']+"_bf.tif"),
        'projected_spots' : os.path.join(path, properties['name']+"_fluo_spots.tif"),
        'projected_nuclei': os.path.join(path, properties['name']+"_fluo_nuclei.tif"),
        'spots_colors'    : os.path.join(path, properties['name']+"_spots_colors.txt"),
        'cells_indices'   : os.path.join(path, properties['name']+"_indices.tif"),
        'measures'        : os.path.join(path, properties['name']+".json")
    }

    # Removing unavailable paths
    keys = [str(k) for k in control_paths.keys()]
    for key in keys:
        p = os.path.join(path, control_paths[key])
        if not os.path.isfile(p):
            print(f"Property `{key}` not available.")
            control_paths.pop(key)

    # |-|~|-|~|-|~|-|~|-|~|-|~|-|~|-|~|-|~|-|~|-|~|-|~|-|~|-|~|-|~|-|

    components = []

    # ======================= PROJECTED CELLS =======================
    projected_cells = control_paths.get('projected_cells')
    if projected_cells is not None:
        components.append((
            imread(projected_cells), 
            {
                'name': "projected-cells"
            },
            "image"
        ))

    # ======================= PROJECTED NUCLEI =======================
    projected_nuclei = control_paths.get('projected_nuclei')
    if projected_nuclei is not None:
        components.append((
            imread(projected_nuclei), 
            {
                'name': "fluo-nuclei",
                'blending': 'opaque',
                'colormap': 'cyan'
            }, 
            'image'
        ))

    # ======================= PROJECTED SPOTS =======================
    projected_spots = control_paths.get('projected_spots')
    if projected_spots is not None:
        components.append((
            imread(projected_spots), 
            {
                'name': "fluo-spots",
                'blending': 'opaque',
                'colormap': 'yellow'
            }, 
            'image'
        ))
    
    # ======================= LABELED SPOTS =======================
    labeled_spots = control_paths.get('labeled_spots')
    if labeled_spots is not None:
        components.append((
            imread(labeled_spots), 
            {
                'name'   : "labeled-spots",
                'visible': False,
                'opacity': 1.0
            }, 
            "labels"
        ))
    
    # ======================= LABELED CELLS =======================
    labeled_cells = control_paths.get('labeled_cells')
    if labeled_cells is not None:
        components.append((
            imread(labeled_cells), 
            {
                'name': "labeled-cells"
            }, 
            "labels"
        ))
    
    # ======================= LABELED NUCLEI =======================
    labeled_nuclei = control_paths.get('labeled_nuclei')
    if labeled_nuclei is not None:
        components.append((
            imread(labeled_nuclei), 
            {
                'name'   : "labeled-nuclei"
            }, 
            "labels"
        ))

    # ======================= SPOTS COLORS ==========================
    spots_colors = control_paths.get('spots_colors')
    face_colors  = '#00000000'
    edge_colors  = '#ffffffff'

    if spots_colors is not None:
        with open(spots_colors, 'r') as f:
            edge_colors = [f.read().split('\n')]

    # ======================= SPOTS LOCATIONS =======================
    spots_list = control_paths.get('spots_list')
    if spots_list is not None:
        components.append((
            np.loadtxt(spots_list, delimiter=',', skiprows=1, dtype=int), 
            {
                'name'      : "spots-positions",
                'edge_color': "#ff0000ff",
                'face_color': face_colors,
                'edge_color': edge_colors
            },
            "points"
        ))
    
    # ======================= PROJECTED SPOTS =======================
    cells_indices = control_paths.get('cells_indices')
    if cells_indices is not None:
        components.append((
            imread(cells_indices), 
            {
                'name': "cells-indices",
                'blending': 'additive',
                'visible': False
            }, 
            'image'
        ))

    return components
