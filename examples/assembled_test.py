from spotsInYeasts.spotsInYeasts import segment_spots, build_sets, place_markers, create_random_lut, segment_transmission, associate_spots_yeasts, estimateUniformity
from skimage.io import imsave, ImageCollection
import matplotlib.pyplot as plt
import warnings
import os
import json
import numpy as np


def launch_assembled_test():
    # Create random LUT:
    random_lut = create_random_lut()

    # Path where segmentations will be saved:
    save_path = "/home/benedetti/Bureau/testing/assembled"

    # Folder containing the original images:
    root_path = "/home/benedetti/Documents/projects/10-spots-in-yeasts/testing-set-4/d1-test"

    # Sets of channels representing the same image:
    components = [
        ('brightfield', '_w2bf.tif'),
        ('yfp'        , '_w1yfp.tif'),
        ('config'     , '.nd')
    ]
    image_sets = build_sets(root_path, components)

    for i, image in enumerate(image_sets):
        print(f"Using: {image['brightfield']}")

        lbld, ori = segment_transmission(os.path.join(root_path, image['brightfield']))
        spots     = segment_spots(os.path.join(root_path, image['yfp']))

        ttl, ref = estimateUniformity(spots['locations'], lbld.shape)
        is_non_uniform = ttl > ref

        if not is_non_uniform:
            print(f"The image `{image['brightfield']}` failed to be processed.")
            continue

        ownership, lbl_spots = associate_spots_yeasts(lbld, spots['locations'], spots['original'], spots['mask'])
        
        measures = open(f"/home/benedetti/Bureau/testing/assembled/measures-{str(i).zfill(3)}.json", 'w')
        json.dump(ownership, measures)
        measures.close()

        reference = np.stack([
            lbld,
            ori,
            spots['contrasted'],
            lbl_spots
        ])
        imsave(f"/home/benedetti/Bureau/testing/assembled/reference-{str(i).zfill(3)}.tif", reference)


def make_histograms(root_path, prefix, intensity_bins):
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
    
    content     = [c for c in os.listdir(root_path) if c.startswith(prefix)]
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
    ax2.set_xlim([0, 65535])
    ax2.plot(labels[:-1], hIntensities, '-')
    ax2.set_title("Intensity per spot")

    # Logging
    summed = np.sum(hSpots)
    for i, c in enumerate(hSpots):
        print(f"{round(c/summed*100, 2)}% of cells have {i} spot(s).")

    plt.show()