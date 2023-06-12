import matplotlib.pyplot as plt
import os
import json
import numpy as np
from termcolor import colored

def make_histograms(root_path, suffix, intensity_bins):
    """
    Here we build two histograms.
    The first shows the repartition of the number of spots in cells.
    The second shows the distribution of the mean intensity of spots.
    The number of bins is automatically processed for the number of spots in cells.

    Args:
        root_path: The folder in which results are stored.
        prefix: Prefix in the name of files containing measures.
        intensity_bins: Number of bins in the intensities histogram.

    Returns:
        An array of ints and an array of tuples.
        The array represents the histogram showing the number of spots per cell.
        The dictionary has as keys the ranges (as strings) and as values
    """
    if not os.path.isdir(root_path):
        return [], []
    
    content     = [c for c in os.listdir(root_path) if c.endswith(suffix)]
    counter     = [] # Will contain the number of spots in each cell.
    intensities = [] # Will contain the average intensity of each spot in each cell.

    for c in content:
        # Reading a stats file
        full_path = os.path.join(root_path, c)
        f = open(full_path, 'r')
        measures = json.load(f)
        f.close()
        
        # Adding content of measures to the list.
        for key, item in measures.items():
            counter.append(len(item))
            intensities += [s['intensity_mean'] for s in item]

    fig, (ax1, ax2) = plt.subplots(2, 1)

    # Histogram of number of spots per cell
    counter = np.array(counter)
    hSpots  = np.bincount(counter)
    ax1.bar(np.unique(counter), hSpots)
    ax1.set_title("Spots per yeast")
    
    # Histogram of intensities repartition
    intensities  = np.array(intensities)
    hIntensities, labels = np.histogram(intensities, bins=intensity_bins)
    # ax2.set_xlim([0, 65535])
    ax2.plot(labels[:-1], hIntensities, '-')
    ax2.set_title("Intensity per spot")

    # Logging
    summed = np.sum(hSpots)
    for i, c in enumerate(hSpots):
        print(f"{round(c/summed*100, 2)}% of cells have {i} spot(s).")

    plt.show()

