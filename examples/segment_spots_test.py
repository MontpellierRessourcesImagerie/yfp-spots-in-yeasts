from spotsInYeasts.spotsInYeasts import segment_spots, build_sets, place_markers
import matplotlib.pyplot as plt
import warnings
import os

def launch_test_fluo():
    # Path where segmentations will be saved:
    save_path = "/home/benedetti/Bureau/testing/spots"

    # Folder containing the original images:
    root_path = "/home/benedetti/Documents/projects/10-spots-in-yeasts/testing-set-4/d1-test"

    # Sets of channels representing the same image:
    components = [
        ('brightfield', '_w2bf.tif'),
        ('yfp'        , '_w1yfp.tif'),
        ('config'     , '.nd')
    ]
    image_sets = build_sets(root_path, components)

    for image in image_sets:
        t = segment_spots(os.path.join(root_path, image['yfp']))
        marked = place_markers(t['mask'], t['locations'])
        plt.imsave(os.path.join(save_path, image['yfp'].replace(".tif", ".png")), marked, cmap='gray')
