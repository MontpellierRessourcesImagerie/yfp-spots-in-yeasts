
# Spots in yeasts

> The goal of this project is to count the spots in yeast cells, measure their mean intensity, and determine their size. To get these results, we will start by segmenting the cells with the transmission channel, and then, segmenting the spots in the fluorescence channel (marked with YFP).

The final product of this project should be a Napari plugin.

For now, the code produces a JSON file compiling the data as well as histograms representing:
- The number of spots per cell.
- The average intensity of a spot.
- The area of each spot.
- The location of each spot.

## Segmentation of yeasts

- The Cellpose's Python module was used for this step. It outputs a labeled image with one label per individual.
- We make sure to remove cells touching the border to avoid partial data.
- We still need to implement a way to merge mother and daughter cells together.
- The brightfield channel can't be used to determine if a cell is alive.

## Segmentation of spots:

- The fluorescent channel is very noisy. This is due to the low intensity of the YFP signal. We start by applying a __median filter__ to the image to reduce noise and prevent false positives.
- A __Laplacian of Gaussian__ filter emphasizes the presence of spots.
- Otsu thresholding was formerly used to turn the result of the LoG filter into a mask, but the results were rather unstable, so we switched to an __isodata thresholding__.
- A __distance transform__ is applied to the mask we just created to locate the center of every spots. This operation will also separate spots merged together on the mask.
- Seeking for local maximas will result in the creation of a points list, representing the center of spots.
- Finally, a marker based watershed is used to segment the mask into different spots.

## Napari side:

Here are three images representing the results. These images are layers in Napari.

![Brightfield](https://dev.mri.cnrs.fr/attachments/download/3009/brightfield.png)
![Segmentation](https://dev.mri.cnrs.fr/attachments/download/3010/labels.png)
![Spots](https://dev.mri.cnrs.fr/attachments/download/3011/spots.png)

---

## TODO

- [ ] Browse all images to determine the optimal number of slices.
- [X] Determine an implementation to locate and isolate dead cells.
- [ ] Finish the report to keep track of previous implementations.
- [ ] Implement a GUI-less batch mode (that doesn't show images in the viewer)
- [ ] Finish writing the unit tests.
- [ ] We would like to be able to remove labels by clicking in the viewer.
- [ ] We would like to add the possibility to add/remove spots by clicking in the viewer.
- [ ] Move the execution in another thread to avoid the GUI freezing.
- [X] Add settings for spots detection.
- [X] Try to make a cleaner GUI.
- [ ] Use a threshold on the number of spots to detect dead cells.
- [X] Write a Fiji macro to perform the conversion: ".nd" ---> ".tif".
- [?] Ajouter une image de controle aux calques à chaque itération.