from skimage.filters import threshold_otsu
from skimage.measure import label as connected_compos_labeling
from skimage.measure import regionprops
import numpy as np
from skimage.segmentation import find_boundaries, clear_border
from scipy.ndimage import binary_erosion, binary_dilation
from termcolor import colored
import sys
import matplotlib.pyplot as plt
from skimage.io import imshow, imsave
from matplotlib.colors import ListedColormap


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

def remove_labels(image, labels):
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

def generate_random_color(alpha=1.0):
    """ Generates a random color expressed as its hexadecimal notation. """
    r = randrange(0, 256)
    g = randrange(0, 256)
    b = randrange(0, 256)
    a = int(255 * alpha) if (alpha >= 0.0 and alpha <= 1.0) else 255
    return "#{:02x}{:02x}{:02x}{:02x}".format(r,g,b,a)


class YeastsPartitionGraph(object):
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

    def remove_borders(self, labeled_yeasts, labeled_nuclei):
        mask = binary_erosion(np.zeros(labeled_yeasts.shape) == 0)
        working_copy = np.copy(labeled_yeasts)
        working_copy[mask] = 0

        discarded   = np.array([i for i in set(np.unique(working_copy)).difference({0})])
        remove_labels(labeled_yeasts, discarded)
        remove_labels(labeled_nuclei, discarded)
    
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

    def show(self):
        from pprint import pprint
        pprint(self.graph, stream=out_descr)
    
    # mode in {'partition', 'bound_to'}
    def draw_graph(self, width_pixels, height_pixels, mode='partition', path=None):
        import networkx as nx
        import matplotlib.pyplot as plt
        from skimage.io import imshow, imsave

        plt.clf()
        plt.close()

        G = nx.Graph()
        if mode == 'partition':
            G.add_nodes_from([(key, {'pos': (props['coordinates'][0], height_pixels-props['coordinates'][1]), 'color': '#eb4034' if props['partition'] == 1 else '#4287f5'}) for key, props in self.graph.items() if key is not None])
        elif mode == 'bound_to':
            lut = {}
            for key, props in self.graph.items():
                color = lut.get(key)
                if color is None:
                    color = generate_random_color()
                    lut[key] = color
                    lut[props['bound_to']] = color
                position = props['coordinates']
                G.add_node(
                    key, 
                    pos=(position[0], height_pixels-position[1]),
                    color=color
                )
        else:
            raise ValueError(mode + ' is not a valid value.')

        for key, ppts in self.graph.items():
            for n in ppts['neighbors']:
                G.add_edge(key, n)

        pos = nx.get_node_attributes(G, 'pos')
        color = list(nx.get_node_attributes(G, 'color').values())
        
        dpi = 100

        # Convertir les pixels en pouces
        width_inches = width_pixels / dpi
        height_inches = height_pixels / dpi

        # Créer la figure avec la taille spécifiée
        fig = plt.figure(figsize=(width_inches, height_inches), dpi=dpi)

        if mode == 'partition':
            labels = {i: i for i in self.graph.keys()}
        elif mode == 'bound_to':
            labels = {i: ("" if b['bound_to'] is None else b['bound_to']) for i, b in self.graph.items()}

        nx.draw(G, pos, with_labels=True, edge_color='#000000', labels=labels, node_color=color, node_size=650)
        plt.axhline(y=0, color='black', linewidth=5)
        plt.axhline(y=height_pixels, color='black', linewidth=5)
        plt.axvline(x=0, color='black', linewidth=5)
        plt.axvline(x=width_pixels, color='black', linewidth=5)

        if path is None:
            plt.show()
        else:
            plt.savefig(path)

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

    with open("/home/benedetti/Bureau/dump.txt", 'w') as f:
        f.write(str(graph)+"\n\n")
        f.write(str(contacts)+"\n\n")

    if check_undirected:
        if is_undirected(graph):
            print(colored("The graph is undirected.", 'green'))
        else:
            print(colored("Error. The graph is not undirected.", 'red'))

    regions = regionprops(labeled_cells)
    cleaned = {}
    for cell in regions:
        cleaned[cell.label] = {'neighbors': graph[cell.label], 'coordinates': [i for i in cell.centroid]}

    return cleaned

def remove_excessive_coverage(labeled_cells, labeled_nuclei, covering_threshold):
    """
    Removing cells in which the nucleus occupies too much surface (dead cell).
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


def assign_nucleus(labeled_cells, labeled_nuclei, covering_threshold=0.7, graph=None):
    
    # 1. We remove cells covered too much by some nuclei.
    discarded_cells, discarded_nuclei = remove_excessive_coverage(labeled_cells, labeled_nuclei, covering_threshold)

    # 2. Defining variables.
    nucleus_to_cells = [None for _ in range(max(max(discarded_nuclei), np.max(labeled_nuclei))+1)]
    cell_to_nuclei   = [{
                    'users' : set(), # Nuclei overlaping with this cell.
                    'valid' : True,  # Boolean indicating if the cell will be discarded.
                    'owner' : 0,     # Nucleus owning this cell.
                    'stable': False, # True if we found a nucleus belonging ONLY to this cell (not shared with another).
                    'center': False  # True if the centroid of a nucleus was found in this cell.
                } for _ in range(max(max(discarded_cells), np.max(labeled_cells))+1)]

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
    # /!\ Penser à check à chq fois si l'owner est déjà pris ailleurs, à dicrease le compteur
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
            # nucleus_props['valid'] = False

    return labeled_cells, labeled_nuclei, graph, cell_to_nuclei, nucleus_to_cells


def segment_nuclei(labeled_yeasts, stack_fluo_nuclei, threshold_coverage):
    # Segmentation of nuclei
    flattened_nuclei, labeled_nuclei = nuclei_from_fluo(stack_fluo_nuclei)
    # Adjacency graph of cells
    graph = adjacency_graph(labeled_yeasts)
    # Attributing each nucleus to a cell, and cleaning non-senses (cell with several nuclei, ...).
    labeled_cells, labeled_nuclei, graph, cell_to_nuclei, nucleus_to_cells = assign_nucleus(labeled_yeasts, labeled_nuclei, threshold_coverage, graph)
    # Merging cells in division phase and cleaning
    ypg = YeastsPartitionGraph(graph, cell_to_nuclei, nucleus_to_cells, labeled_yeasts, labeled_nuclei)
    
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # viewer.layers['labeled-cells-test'].data  = labeled_yeasts
    # viewer.layers['labeled-nuclei-test'].data = labeled_nuclei



def main():
    print("It works!")


import time

stamps = []
for i in range(1):
    start = time.time()
    main()
    stamps.append(time.time() - start)




"""
TODO

- [ ] Retirer tout ce qui touche les bordures de l'image (cellules plus les noyaux associés).
- [ ] Intégrer le code expérimental dans l'application.
- [ ] Fonction de vérification de la non-orientation d'un graphe.
- [ ] Calculer la distance entre chaque spot et le noyau.
- [ ] Écrire les tests unitaires.
- [ ] Retirer les cellules qui n'ont toujours pas de noyau après la phase de couplage.
- [ ] Dans l'export de graphe, afficher en faible alpha les cellules qui vont être discarded.
- [ ] Rajouter des labels qui se touchent que par des diagonales dans les "mock-labeled-cells".
- [ ] Essayer d'ajouter une heuristique sur les edges pour déterminer le meilleur candidat s'il y a plusieurs choix possibles (aire de contact, changement du profil de couleur, ...) ?
- [ ] Ajouter une image de Florence et une image de Kseniya au testing set pour check que les 2 workflows fonctionnent.
- [ ] Comment le thresholding avec Otsu varie selon la densité des cellules sur la lame ?
- [ ] Est-ce que remplir les trous du masque de base des noyaux ne pourrait pas être utile à la sortie de 'nuclei_from_fluo' ?
- [ ] Il doit être possible d'accélérer la création du graphe en faisant la moyenne des pixels de chaque intensité vus plutôt qu'en utilisant les regionprops.
- [ ] Est-ce qu'il existe des cas où l'érosion peut modifier le résultat du graphe ?
- [ ] (voir 'problem_01') Certains noyaux peuvent chevaucher plusieurs cellules, qu'en faire ?
- [ ] Garder dans une variable caché la segmentation des cellules à chaque étape pour ne pas avoir à resegmenter si l'utilisateur veut tester les settings.

"""

"""
NOTE

- Nuclei shouldn't (can't?) be agregated together, so a simple thresholding is enough to distinguish them. In the case several of them could
  be bunched togethern, the "typical workflow" (LoG > maxima > watershed) can't be used since divising cells' nuclei are butterfly-shaped.

"""