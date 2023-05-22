
# Spots in yeasts

> The goal of this project is to count the spots in yeast cells, measure their mean intensity, and determine their size. To get these results, we will start by segmenting the cells with the transmission channel, and then, segmenting the spots in the fluorescence channel (marked with YFP).

The final product of this project should be a Napari plugin.

For now, the code produces a JSON file compiling the data as well as histograms representing:
- The number of spots per cell.
- The average intensity of a spot.

## Segmentation of yeasts

- The Cellpose's Python module was used for this step. It outputs a labeled image with one label per individual.
- In the future, we want to let the user chose if he wants the dividing cell to be counted as a unique cell, or two individual ones.

## Segmentation of spots:

__Workflow:__

- Median filter of the original fluo channel to reduce the noise.
- Laplacian of Gaussian filter to emphasize the position of spots.
- Otsu thresholding to create a binary mask from the LoG. FG=spot.
- Distance transform to prepare the splitting of merged spots.
- Find maxima to get one point per spot (useful in case of merged spots).
- Marker based watershed to isolate spots areas.

---

## TODO

- [X] Find a good implementation of marker based watershed.
- [ ] Turn the monolithic block of code into a modular Napari plugin.
- [X] Evaluate the focus of each slice and select usable slices.
- [X] Determine an implementation to locate individual spots.
- [ ] Browse all images to determine the optimal number of slices.
- [X] Remove labels touching the border in the transmission channel.
- [X] Start dividing the code into pieces executable independently.
- [ ] Revise the code to work only on float64 images in [0.0, 1.0].
- [ ] Determine an implementation to locate and isolate dead cells.
- [X] Fix the code associating each spot to its owner cell.
- [ ] Start writing the report to keep track of previous implementations.
- [ ] Finish writing the unit tests.
