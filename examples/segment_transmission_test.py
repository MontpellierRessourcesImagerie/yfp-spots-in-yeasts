from spotsInYeasts.spotsInYeasts import create_random_lut, segment_transmission, build_sets
import matplotlib.pyplot as plt
import os

def launch_test_transmission():
    # Creating random LUT for labels displaying:
    random_lut = create_random_lut()

    # Path where segmentations will be saved:
    save_path = "/home/benedetti/Bureau/testing/yeasts"

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
        print(f"Processing transmission segmentation on: {image['brightfield']}")
        t, o = segment_transmission(os.path.join(root_path, image['brightfield']))
        plt.imsave(os.path.join(save_path, image['brightfield'].replace(".tif", ".png")), t, cmap=random_lut)