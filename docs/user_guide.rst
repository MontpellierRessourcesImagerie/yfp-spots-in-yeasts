==========================================
Quick start: A user guide
==========================================

Install the plugin 
------------------------------------------

**With pip**

Simply launch your conda environment, and type :code:`pip install spots-in-yeasts`.
The plugin should then appear in your plugins list.

**From Napari Hub**

Go in the plugins menu of Napari and search for "Spots in yeasts"

**From GitHub**

You can also install the last development version. To do so, start by launching your conda environment and then use the command :code:`pip install git+https://github.com/MontpellierRessourcesImagerie/spots-in-yeasts.git`.

Quick demonstration 
------------------------------------------

.. raw:: html

   <iframe width="560" height="315" src="https://www.youtube.com/embed/VkqufgHlTcU" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>


Before starting 
------------------------------------------

:code:`Spots in yeasts` expects a very precise file as its input:

* The file must be a TIFF (no .czi, .nd, ...)
* Both channels must be packed in this TIFF.
* The first channel must contain the spots and the second the brightfield.
* The number of slices is arbitrary.

If your images don't respect the previous conditions, you can check the page explaining :doc:`how to conform your data <convert_data>`.

Processing 
------------------------------------------

Process a single image
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- If something is already present in the Napari viewer, click on :code:`Clear layers`. It will flush everything present in your current viewer.
- Drag'N'drop your TIFF file into the Napari viewer. It should appear in the left column.
- Click on :code:`Split channels`. Now, your original image should have disappeared (in the left column) and two new layers took its place.They represent the brightfield and the fluo channel of your image. Layers are opaque, which means that as long as you don't toggle the little eye icon in the left column, the viewer shows you the uppermost layer.
- You can now click the :code:`Segment cells` button. This operation can take quite a while depending on your hardware. The presence of a dedicated GPU on your machine would help a lot. The result will spawn as a new layer containing a label for each cell in the brightfield. At this point, cells cut by the borders have already been discarded. If you make this new layer active (just click on it in the left column until its name turns blue), you can pass your mouse over each label to verify its value. These values match the indices present in the results file.
- Click the :code:`Segment spots` button. This step is much quicker. You can zoom on your image to see where spots were detected. Note that the white circles only represent the position of detected spots, they do not represent the segmentation. If you prefer to see the segmentation, you can hide the :code:`spots-positions` layer and use the :code:`labeled-spots` one instead. Of the same way as in the previous step, you can make this layer active to see the indices, which are the same as in the results file.
- Finally, you can use the :code:`Extract stats` button. This will open a CSV file in your default spreadsheet software. Keep in mind that it is a temporary file, it is not saved anywhere and will disappear as soon as you close it if you don't save it.

Batch processing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Start by making a folder in which you place all the images that you need to get processed. Note that a unique CSV file is produced for the whole batch, so make sure that your folder contains images that can be compared to each other (same acquisition conditions), otherwise, you may end up with inconsistant data.
- Now, you need to create the folder that will receive the control images produced by the plugin. Indeed, in case you observe odd results, the plugin produces a bunch of control images in batch mode that you can inspect if required. It is not required that the output folder is empty, but it is recommended though.
- Then, you can set your input and output path.
- Finally, you can click the :code:`Run batch` button.
- In Napari's GUI, you can click on :code:`activity` in the lower right corner to see a progress bar. You can monitor way more precisely what is going on thanks to the terminal that tells in real time what is being done.
- At the end of the execution, the produced CSV is located at the root of the output folder. Each folder ending with :code:`.yfp` is a set of control images for one input image.

Results control
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Each control is a folder (instead of an image)
- You can simply drag'n'drop the folder into Napari instead of opening each image that it contains. A plugin recognizing folders ending with :code:`ysc` (yeasts spots control) is bundled with the plugin.
- In there, each cell is represented by its outline. 
- Also, spots are not represented by white dots anymore, but are directly circled on the fluo channel.

How to read the results?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- :code:`source`: The name of the image (without its extension) from which the following data was extracted.
- :code:`cell-index`: A unique number assigned to each cell. This number corresponds to the label on the control image. Please note that some numbers may be missing from the list if cells were cut by the image's border (resulting in their labels being erased).
- :code:`spot-index`: Similarly to 'cell-index', this value corresponds to the label on the control image.
- :code:`area`: The number of pixels covered by the spot.
- :code:`intensity-mean`: The average intensity recorded for all the pixels within the spot.
- :code:`intensity-min`: The lowest intensity recorded among all the pixels within the spot.
- :code:`intensity-max`: The highest intensity recorded among all the pixels within the spot.
- :code:`intensity-sum`: Also known as integrated intensity, this is the sum of intensities across all pixels within the spot.
- :code:`perimeter`: The length of the perimeter around the spot, measured in steps with diagonal connectivity.
- :code:`solidity`: The ratio of the spot's area to the area of its convex hull. A star-shaped spot will have a value close to 0, while a more circular spot will have a value close to 1.
- :code:`extent`: The ratio of the spot's area to the area of its bounding box, which is the smallest rectangle that contains the spot. This metric gives an idea of how elongated the spot is. For example, a perfect circle and a perfect ellipse will both have a solidity of 1.0, however, their extent will vary.
- :code:`# spots`: The number of spots detected in the given cell.


Notes 
------------------------------------------

- The plugin provides verbose output, so it's recommended to monitor the terminal if you want detailed information about its actions.
- If a crash occurs, please create an issue and include the relevant image(s) for further investigation.
- Napari currently supports only open file formats, so make sure to convert your images to TIFF format before using them with Napari.
