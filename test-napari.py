import napari
from skimage.io import ImageCollection
import numpy as np
from magicgui import magicgui, widgets
from pathlib import Path
from termcolor import colored
import os
import json
import tempfile
import time
import subprocess
import platform

from spotsInYeasts.spotsInYeasts import segment_transmission, create_random_lut, segment_spots, estimateUniformity, associate_spots_yeasts


_state_ = None
_bf     = "brightfield"
_yfp    = "yfp"
_lbl_c  = "labeled-cells"
_lbl_s  = "labeled-spots"
_spots  = "spots-positions"


@magicgui(call_button="Clear layers")
def clear_layers_gui():
    """
    Removes all the layers currently present in the Napari's viewer, and resets the state machine used by the scipt.
    """
    global _state_
    _state_.current_viewer().layers.clear()
    _state_.reset_current()


@magicgui(call_button="Split channels")
def split_channels_gui():
    global _state_

    nImages = len(_state_.current_viewer().layers)
    if nImages != 1:
        print(colored("Only one image must be loaded at a time.", 'red'))
        return False

    # (2, 2048, 2048)
    # (9, 2, 2048, 2048)

    imIn = _state_.current_viewer().layers[0].data
    imSp = imIn.shape

    if len(imSp) not in [3, 4]:
        print(colored(f"Images must have 3 or 4 dimensions. {len(imSp)} found.", 'red'))
        return False

    axis      = 0 if (len(imSp) == 3) else 1
    nChannels = imSp[axis]

    if nChannels != 2:
        print(colored(f"Only 2 channels are expected. {nChannels} found.", 'red'))
        return False
    
    _state_.set_current_name(_state_.current_viewer().layers[0].name)
    _state_.current_viewer().layers.clear()
    
    a, b = np.split(imIn, indices_or_sections=2, axis=axis)
    
    _state_.current_viewer().add_image(
        np.squeeze(a),
        rgb      = False,
        name     = _yfp,
        colormap = 'yellow',
        blending = 'opaque'
    )

    _state_.current_viewer().add_image(
        np.squeeze(b),
        rgb      = False,
        name     = _bf,
        blending = 'opaque'
    )

    return True


@magicgui(call_button="Segment cells")
def segment_brightfield_gui():
    global _state_

    if _bf not in _state_.current_viewer().layers:
        print(colored(_bf, 'red', attrs=['underline']))
        print(colored(" channel not found.", 'red'))
        return False

    start = time.time()
    labeled, projection = segment_transmission(_state_.current_viewer().layers[_bf].data, True)
    _state_.current_viewer().layers[_bf].data = projection

    if _lbl_c in _state_.current_viewer().layers:
        _state_.current_viewer().layers[_lbl_c].data = labeled
    else:
        random_lut = create_random_lut(True)
        _state_.current_viewer().add_image(
            labeled, 
            name     = _lbl_c, 
            blending = "additive", 
            rgb      = False, 
            colormap = random_lut
        )
    
    print(colored(f"Segmented cells from `{_state_.get_current_name()}` in {round(time.time()-start, 1)}s.", 'green'))
    return True


@magicgui(call_button="Segment YFP spots")
def segment_fluo_gui():
    global _state_

    if _yfp not in _state_.current_viewer().layers:
        print(colored(_yfp, 'red', attrs=['underline']))
        print(colored(" channel not found.", 'red'))
        return False

    start = time.time()
    spots_locations, labeled_spots, yfp = segment_spots(_state_.current_viewer().layers[_yfp].data)
    _state_.current_viewer().layers[_yfp].data = yfp

    # Checking whether the distribution is uniform or not.
    # We consider that the segmentation has failed if it is uniform.
    ttl, ref = estimateUniformity(spots_locations, labeled_spots.shape)
    if ttl <= ref:
        print(colored(f"The image `{_state_.get_current_name()}` failed to be processed.", 'red'))
        return False
    
    # Avoid duplicating layers in case we relaunch analysis.
    if _spots in _state_.current_viewer().layers:
        _state_.current_viewer().layers[_spots].data = spots_locations
    else:
        _state_.current_viewer().add_points(spots_locations, name=_spots)

    # Avoid duplicating layers in case we relaunch analysis.
    if _lbl_s in _state_.current_viewer().layers:
        _state_.current_viewer().layers[_lbl_s].data = labeled_spots
    else:
        random_lut = create_random_lut(True)
        _state_.current_viewer().add_image(labeled_spots, name=_lbl_s, visible=False, colormap=random_lut)
    
    print(colored(f"Segmented spots from `{_state_.get_current_name()}` in {round(time.time()-start, 1)}s.", 'green'))
    return True


@magicgui(call_button="Extract stats")
def extract_stats_gui():
    if _lbl_c not in _state_.current_viewer().layers:
        print(colored("Cells segmentation not available yet.", 'yellow'))
        return
    
    if _lbl_s not in _state_.current_viewer().layers:
        print(colored("Spots segmentation not available yet.", 'yellow'))
        return

    labeled_cells = _state_.current_viewer().layers[_lbl_c].data
    yfp_original  = _state_.current_viewer().layers[_yfp].data
    labeled_spots = _state_.current_viewer().layers[_lbl_s].data
    ownership     = associate_spots_yeasts(labeled_cells, labeled_spots, yfp_original)

    measures_temp = tempfile.NamedTemporaryFile(prefix=_state_.get_current_name(), suffix=".json", delete=False)
    measures_temp_path = measures_temp.name
    measures = json.dumps(ownership)
    measures_temp.write(measures.encode())
    measures_temp.close()

    print(colored("Spots exported to: ", 'green'), end="")
    print(colored(measures_temp_path,'green', attrs=['underline']))

    if platform.system() == 'Windows':
        os.startfile(measures_temp_path)
    elif platform.system() == 'Darwin':  # macOS
        subprocess.call(('open', measures_temp_path))
    else:  # linux variants
        subprocess.call(('xdg-open', measures_temp_path))


@magicgui(
    input_folder = {'mode': 'd'},
    output_folder= {'mode': 'd'},
    call_button  = "Run batch"
)
def batch_folder_gui(input_folder: Path=Path.home(), output_folder: Path=Path.home()):
    global _state_
    exec_start = time.time()
    clear_layers_gui()

    _state_.set_path(path)
    nElements = len(_state_.queue)

    if nElements == 0:
        print(colored(f"Can't work on {path}", 'red'))
        return False
    
    while _state_.next_item():
        _state_.load()
    
    clear_layers_gui()
    print(colored(f"\n========= DONE. ({round(time.time()-exec_start, 1)}s) =========\n", 'green', attrs=['bold']))

    return True


class State(object):

    def __init__(self):
        # Queue of files to be processed.
        self.queue   = []
        # Path of a directory in which measures will be exported, only in batch mode.
        self.e_path  = tempfile.gettempdir()
        # Absolute path of the file currently processed.
        self.current = None
        # Path of the directory in which images will be processed, only in batch mode.
        self.path    = None
        # Current Viewer in Napari instance.
        self.viewer  = napari.Viewer()
        # Display name used for the current image
        self.name = ""
        # Side dock containing the plugin.
        self.dock    = self.viewer.window.add_dock_widget(
            [
                clear_layers_gui,
                split_channels_gui,
                segment_brightfield_gui,
                segment_fluo_gui,
                extract_stats_gui,
                batch_folder_gui
            ], 
            name="Spots In Yeasts")
    
    def get_export_path(self):
        return self.e_path

    def set_export_path(self, path):
        d_path = str(path)
        if not os.path.isdir(d_path):
            print(colored(f"{d_path}", 'red', attrs=['underline']), end="")
            print(colored(" is not a directory path.", 'red'))
            d_path = tempfile.gettempdir()
        print("Export directory set to: ", end="")
        print(colored(d_path, attrs=['underline']))
        self.e_path = d_path

    def set_current_name(self, n):
        self.name = n
    
    def get_current_name(self):
        return self.name
    
    def current_image(self):
        return self.current

    def reset_current(self):
        self.current = None
        self.set_current_name("")

    def next_item(self):
        self.current = None

        if self.path is None:
            return False

        if len(self.queue) == 0:
            return False
        
        while len(self.queue) > 0:
            item = self.queue.pop(0)
            if os.path.isfile(item):
                self.current = item
                self.set_current_name(item.split('.')[0])
                return True
        
        return False

    # Loads the image stored in "self.current" in Napari.
    # A safety check ensures that several images can't be loaded simulteanously
    def load(self):
        self.viewer.layers.clear()
        print(colored(f"============ Working on: {self.get_current_name()} ============", 'green'))

        stack = ImageCollection(str(self.current))

        if (stack is None) or (len(stack) != 2):
            print(colored(f"Exactly two channels are required. {0 if (stack is None) else len(stack)} found.", 'red'))
            return False

        bf    = np.array(stack[0])
        yfp   = np.array(stack[1])
        
        self.viewer.add_image(
            yfp,
            rgb=False,
            name=_yfp,
            colormap='yellow',
            blending='opaque'
        )
        self.viewer.add_image(
            bf,
            rgb=False,
            name=_bf,
            blending='opaque'
        )

        return True

    def current_viewer(self):
        return self.viewer

    def set_path(self, path):
        self.path    = str(path)
        self._init_queue_()

    def _init_queue_(self):
        if os.path.isdir(self.path):
            self.queue = [os.path.join(self.path, i) for i in os.listdir(self.path) if i.lower().endswith('.tif')]
        
        if os.path.isfile(self.path):
            self.queue = [self.path] if self.path.lower().endswith('.tif') else []

        print(f"{len(self.queue)} files found.")


_state_ = State()

# start the event loop and show the viewer
napari.run()



# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#                              TO DO
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# - [ ] We would like to be able to remove labels by clicking in the viewer.
# - [ ] We would like to add the possibility to add/remove spots by clicking in the viewer.
# - [ ] Move the execution in another thread to avoid the GUI freezing.
# - [ ] Add settings for spots detection.
# - [ ] Try to make a cleaner GUI.
# - [ ] Use a threshold on the number of spots to detect dead cells.
# - [ ] FWrite a Fiji macro to perform the conversion: ".nd" ---> ".tif".
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #