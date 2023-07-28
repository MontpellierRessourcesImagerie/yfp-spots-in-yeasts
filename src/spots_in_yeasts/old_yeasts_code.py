# 4. Cleaning the cells labels.
    nuclei_props = regionprops(labeled_cells, intensity_image=labeled_nuclei)
    for cell in nuclei_props: # In this loop, we iterate through the cells to find the nucleus of each one.
        cell_lbl = cell['label']
        mask = np.logical_not(cell['image'])
        data = cell['image_intensity']
        data[mask] = 0
        nuclei_lbls = set(np.unique(data))
        nuclei_lbls.discard(0)

        # Droping cells overlaping with more than one nucleus.
        if len(nuclei_lbls) > 1:
            if cell_lbl == 337:
                imshow(data)
                plt.show()
                print("Discarded multiple nuclei", file=out_descr)
                print(nuclei_lbls, file=out_descr)
            discarded_cells.add(cell_lbl)
            discarded_nuclei = discarded_nuclei.union(nuclei_lbls)
            continue

        if len(nuclei_lbls) == 1:
            nucleus_from_cell[cell_lbl] = nuclei_lbls.pop()
            continue
        # If there is no nucleus and no neighbour, we can discard the cell.
        if (len(nuclei_lbls) == 0) and (len(graph[cell_lbl]) == 0):
            if cell_lbl == 337:
                print("Discarded no nuclei and no neighbour")
            discarded_cells.add(cell_lbl)
            discarded_nuclei = discarded_nuclei.union(nuclei_lbls)

    # Modifying labeled nuclei to remove discarded labels.
    discarded_nuclei_array = np.array([i for i in discarded_nuclei])
    discarded_nuclei_mask  = np.isin(labeled_nuclei, discarded_nuclei_array)
    labeled_nuclei[discarded_nuclei_mask] = 0

    # Modifying the cells labels to remove discarded cells
    discarded_cells_array = np.array([i for i in discarded_cells])
    discarded_cells_mask  = np.isin(labeled_cells, discarded_cells_array)
    labeled_cells[discarded_cells_mask] = 0




def _assign_nucleus(labeled_cells, labeled_nuclei, covering_threshold=0.7, graph=None):
    
    # 1. We remove cells covered too much by some nuclei.
    discarded_cells = remove_excessive_coverage(labeled_cells, labeled_nuclei, covering_threshold)

    # 2. Defining variables.
    discarded_nuclei  = set() # Collection of nuclei intersecting with the background.
    cell_to_nucleus   = [(0, False) for i in range(np.max(labeled_cells)+1)] # Array giving for a cell (represented by its label), the nucleus it owns, and whether the centroid of the nucleus is in the cell.
    nuclei_counter    = [0 for i in range(np.max(labeled_nuclei)+1)] # In this array, we count in how many cells a nucleus participates.

    # 3. Cleaning the nuclei labels.
    cells_props  = regionprops(labeled_nuclei, intensity_image=labeled_cells)
    for nucleus in cells_props: # In this loop, we iterate through nuclei to find by how many cells it's being used.
        nucleus_lbl = nucleus['label']
        l, c        = [int(k) for k in nucleus.centroid]
        cell_lbl    = labeled_cells[l, c]

        mask = np.logical_not(nucleus['image'])
        data = nucleus['intensity_image']
        data[mask]  = 0
        cell_labels = set(np.unique(data)).difference({0, cell_lbl}) # Labels of all the cells this nucleus intersects with, excluding the background and its owner.

        if cell_lbl == 0: # Droping nuclei falling in the background
            discarded_nuclei.add(nucleus_lbl)
            continue

        cell_to_nucleus[cell_lbl] = (nucleus_lbl, True) # The centroid of the nucleus determines which cell owns it.
        
        for cb in cell_labels:
            lbl, own = cell_to_nucleus[cb]
            if not own:
                cell_to_nucleus[cb] = (nucleus_lbl, False)

    for cell_lbl, (nucleus_lbl, owner) in enumerate(cell_to_nucleus):
        nuclei_counter[nucleus_lbl] += 1
    
    for nucleus_lbl, n_usage in enumerate(nuclei_counter): # Droping nuclei participating in 0 or more than 2 cells.
        if n_usage not in {1, 2}:
            discarded_nuclei.add(nucleus_lbl)

    for cell_lbl, (nucleus_lbl, owns_nucleus) in enumerate(cell_to_nucleus): # If there is no nucleus and no neighbor, we can discard the cell.
        if nucleus_lbl > 0:
            continue
        neighbors = graph.get(cell_lbl)
        if (neighbors is not None) and (len(neighbors['neighbors']) == 0):
            discarded_cells.add(cell_lbl)

    remove_labels(labeled_cells, discarded_cells)
    remove_labels(labeled_nuclei, discarded_nuclei)

    # 4. Removing discarded cells from the graph
    if graph:
        graph_clean = {}
        for key, values in graph.items():
            if key in discarded_cells:
                continue
            new_vals = set([v for v in values['neighbors'] if v not in discarded_cells])
            graph_clean[key] = {'neighbors': new_vals, 'coordinates': values['coordinates']}
        graph = graph_clean

    print(f"{len(discarded_cells)} cells discarded due to overlap with multiple nuclei.")
    print(f"{len(discarded_nuclei)} nuclei discarded due to overlaping with background.")

    return labeled_cells, labeled_nuclei, graph, cell_to_nucleus, nuclei_counter
