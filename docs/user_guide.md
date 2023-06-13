
# Quick start: user guide

## Install the plugin

### With pip

Simply launch your conda environment, and type `pip install spots-in-yeasts`.
The plugin should then appear in your plugins list.

### From Napari Hub

Go in the plugins menu of Napari and search for "Spots in yeasts"

## Quick demonstration

<iframe width="560" height="315" src="https://www.youtube.com/embed/VkqufgHlTcU" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>

## Process a single image

- If something is already present in the Napari viewer, click on "Clear layers".
- Drag'N'drop your TIFF file into the Napari viewer. It should appear in the left column.
- Click on `Split channels`. Now, your original image should have disappeared (in the left column) and two new layers have appeared, which are the brightfield and the fluo marking spots.
- You can now click the "Segment cells" button. This operation can take quite a while depending on your hardware. The presence of a dedicated GPU on your machine helps a lot. This operation should result in the spawing of a new layer containing a label for each cell in the brightfield. At this point, cells cut by the borders have already been discarded.

## Batch processing

placeholder

## Notes

- The plugin is very chatty, you should keep an eye on the terminal if you want to know precisely what is going on.
- In case of crash, please fill an issue and provide us with the incriminated image(s).
- Napari is only able to open open file formats (for now), so your images must be converted to TIFF before you start using it.