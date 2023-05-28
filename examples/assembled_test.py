from spotsInYeasts.spotsInYeasts import place_reference_marker, create_reference, segment_spots, seek_channels, place_markers, create_random_lut, segment_transmission, associate_spots_yeasts, estimateUniformity, increase_contrast
from skimage.io import imsave, imread, imshow, ImageCollection
from skimage.morphology import dilation, disk
import matplotlib.pyplot as plt
import warnings
import os
import json
import time
import numpy as np
import cv2
from termcolor import colored


def launch_assembled_test():
    # Create random LUT:
    random_lut = create_random_lut()

    # Path where segmentations will be saved:
    save_path = "/home/clement/Desktop/test-napari/data"

    # Folder containing the original images:
    root_path = "/home/clement/Downloads/testing-set-2"

    # Sets of channels representing the same image:
    components = [
        ('brightfield', '_w2bf.tif'),
        ('yfp'        , '_w1yfp.tif')
    ]
    image_sets = seek_channels(root_path, components)
    exec_start = time.time()

    image_sets = [i for i in os.listdir(root_path) if i.startswith('V26-MAX') and i.endswith(".tif")]

    for i, image in enumerate(image_sets):
        print("")
        print(colored(f"========= Processing: `{image}` ({i+1}/{len(image_sets)}) =========", 'white', attrs=['bold']))

        start = time.time()
        transmission_stack = np.array(ImageCollection(os.path.join(root_path, image))[0])
        fluo_stack         = np.array(ImageCollection(os.path.join(root_path, image))[1])

        lbld, ori = segment_transmission(transmission_stack)
        spots     = segment_spots(fluo_stack)

        ttl, ref = estimateUniformity(spots['locations'], lbld.shape)

        if ttl <= ref:
            print(colored(f"The image `{image}` failed to be processed.", 'red'))
            continue

        ownership, lbl_spots, spots_list = associate_spots_yeasts(lbld, spots['locations'], spots['original'], spots['mask'])
        
        measures = open(os.path.join(save_path, image+"_measures.json"), 'w')
        json.dump(ownership, measures)
        measures.close()

        print(colored(f"{image} processed in {round(time.time()-start, 1)}s.", 'green'))

        reference = create_reference(lbld, ori, spots['original'], spots_list)
        imsave(os.path.join(save_path, image+"_control.tif"), reference)
        print(f"Control image saved as: ", end="")
        print(colored(image+"_control.tif", 'white', attrs=['underline']))
    
    print("")
    print(colored(f"========= DONE. ({round(time.time()-exec_start, 1)}s) =========", 'green', attrs=['bold']))
    print("")


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

