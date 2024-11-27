import cellpose
from spots_in_yeasts.utils import find_focused_slice

class SpotsInYeasts(object):
    def __init__(self):
        self.cells = None
        self.cells_target = None
        self.nuclei = None
        self.nuclei_target = None
        self.spots = []
        self.spots_settings = []
        self.spots_targets = []
        self.cell_diam = 30
        self.labeled_cells = None

    def set_brightfield(self, image, name):
        self.cells = image
        self.cells_target = name

    def set_nuclei(self, image, name):
        self.nuclei = image
        self.nuclei_target = name

    def add_spots(self, image, settings, name):
        self.spots.append(image)
        self.spots_settings.append(settings)
        self.spots_targets.append(name)
    
    def set_cells_diameter(self, diameter):
        self.cell_diam = int(diameter)

    def segment_cells(self):
        model = cellpose.models.Cellpose(gpu=True, model_type='cyto2')
        masks, _, _, _ = model.eval(
            self.cells,
            diameter=self.cell_diam,
            channels=[0, 0],
            flow_threshold=0.4,
            cellprob_threshold=0.3
        )
        self.labeled_cells = masks


if __name__ == "__main__":
    import tifffile
    import matplotlib.pyplot as plt
    import numpy as np
    image = tifffile.imread('/home/benedetti/Documents/projects/yeasts/Opi1localization_MM670_-ino_MMS_0min-01.tif')
    image = np.transpose(image, (1, 0, 2, 3)) # Shape: (Z, C, Y, X) -> (C, Z, Y, X)
    siy = SpotsInYeasts()
    siy.add_brightfield(image[0])
    siy.add_nuclei(image[1])
    siy.add_spots('channel1', image[2])
    siy.add_spots('channel2', image[3])
    siy.process_focus_slice_from('channel1')
    siy.apply_mip()
    for k, v in siy.images_data.items():
        tifffile.imsave(f'/tmp/dump/{k}.tif', v)