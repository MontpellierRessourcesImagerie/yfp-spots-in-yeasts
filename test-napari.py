import napari
from tifffile import imread, imsave
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
from qtpy.QtWidgets import QToolBar, QWidget
from napari.qt.threading import thread_worker, create_worker
from napari.utils import progress
from spotsInYeasts.spotsInYeasts import segment_transmission, create_random_lut, segment_spots, estimateUniformity, associate_spots_yeasts, create_reference


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
    _state_.clear_data()
    return True


@magicgui(call_button="Split channels")
def split_channels_gui():
    global _state_

    nImages = len(_state_.current_viewer().layers)

    if not _state_.is_batch():
        if nImages != 1:
            print(colored("Only one image must be loaded at a time.", 'red'))
            return False

    # (2, 2048, 2048)
    # (9, 2, 2048, 2048)

    imIn = _state_.get_image("_temp_") if _state_.is_batch() else _state_.current_viewer().layers[0].data
    imSp = imIn.shape

    if len(imSp) not in [3, 4]:
        print(colored(f"Images must have 3 or 4 dimensions. {len(imSp)} found.", 'red'))
        return False

    axis      = 0 if (len(imSp) == 3) else 1
    nChannels = imSp[axis]

    if nChannels != 2:
        print(colored(f"Only 2 channels are expected. {nChannels} found.", 'red'))
        return False
    
    if not _state_.is_batch():
        _state_.set_current_name(_state_.current_viewer().layers[0].name)
        _state_.current_viewer().layers.clear()

    a, b = np.split(imIn, indices_or_sections=2, axis=axis)
    
    _state_.set_image(_yfp, np.squeeze(a), {
        'rgb'      : False,
        'colormap' : 'yellow',
        'blending' : 'opaque'
    })

    _state_.set_image(_bf, np.squeeze(b), {
        'rgb'      : False,
        'blending' : 'opaque'
    })

    return True


@magicgui(call_button="Segment cells")
def segment_brightfield_gui():
    global _state_

    if not _state_.required_key(_bf):
        print(colored(_bf, 'red', attrs=['underline']), end="")
        print(colored(" channel not found.", 'red'))
        return False

    start = time.time()
    labeled, projection = segment_transmission(_state_.get_image(_bf), True)
    
    random_lut = create_random_lut(True)
    _state_.set_image(_bf, projection) # current_viewer().layers[_bf].data = projection
    _state_.set_image(_lbl_c, labeled, {
        'blending': "additive", 
        'rgb'     : False, 
        'colormap': random_lut
    })
    
    print(colored(f"Segmented cells from `{_state_.get_current_name()}` in {round(time.time()-start, 1)}s.", 'green'))
    return True


@magicgui(call_button="Segment YFP spots")
def segment_fluo_gui():
    global _state_

    if not _state_.required_key(_yfp):
        print(colored(_yfp, 'red', attrs=['underline']), end="")
        print(colored(" channel not found.", 'red'))
        return False

    start = time.time()
    spots_locations, labeled_spots, yfp = segment_spots(_state_.get_image(_yfp), _state_.get_image(_lbl_c))
    _state_.set_image(_yfp, yfp)

    # Checking whether the distribution is uniform or not.
    # We consider that the segmentation has failed if it is uniform.
    ttl, ref = estimateUniformity(spots_locations, labeled_spots.shape)
    if ttl <= ref:
        print(colored(f"The image `{_state_.get_current_name()}` failed to be processed.", 'red'))
        return False
    
    random_lut = create_random_lut(True)
    _state_.set_spots(spots_locations)
    _state_.set_image(_lbl_s, labeled_spots, {
        'visible' : False, 
        'colormap': random_lut
    })
    
    print(colored(f"Segmented spots from `{_state_.get_current_name()}` in {round(time.time()-start, 1)}s.", 'green'))
    return True


@magicgui(call_button="Extract stats")
def extract_stats_gui():
    global _state_

    if not _state_.required_key(_lbl_c):
        print(colored("Cells segmentation not available yet.", 'yellow'))
        return False

    if not _state_.required_key(_lbl_s):
        print(colored("Spots segmentation not available yet.", 'yellow'))
        return False

    labeled_cells = _state_.get_image(_lbl_c)
    yfp_original  = _state_.get_image(_yfp)
    labeled_spots = _state_.get_image(_lbl_s)
    ownership     = associate_spots_yeasts(labeled_cells, labeled_spots, yfp_original)

    measures_path = os.path.join(_state_.get_export_path(), _state_.get_current_name()+".json")
    try:
        with open(measures_path, 'w') as measures_file:
            json.dump(ownership, measures_file, indent=2)
    except:
        print(colored("Failed to export measures to: ", 'red'), end="")
        print(colored(measures_path,'red', attrs=['underline']))
        return False
    else:
        print(colored("Spots exported to: ", 'green'), end="")
        print(colored(measures_path,'green', attrs=['underline']))

        if not _state_.is_batch():
            if platform.system() == 'Windows':
                os.startfile(measures_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.call(('open', measures_path))
            else:  # linux variants
                subprocess.call(('xdg-open', measures_path))

    return True


def batch_folder_worker(input_folder, output_folder, nElements):
    global _state_
    
    exec_start = time.time()
    iteration = 0

    while _state_.next_item():
        go = _state_.load()
        if go:
            print(colored(f"\n============ Working on: {_state_.get_current_name()} ({iteration+1}/{nElements})============", 'green'))
            go = split_channels_gui()
        if go:
            go = segment_brightfield_gui()
        if go:
            go = segment_fluo_gui()
        if go:
            go = extract_stats_gui()
        if go:
            ref = create_reference(_state_.get_spots(), _state_.get_image(_lbl_c), _state_.get_image(_bf), _state_.marker_path())
            imsave(os.path.join(_state_.get_export_path(), _state_.get_current_name()+".tif"), ref)
        
        yield iteration
        iteration += 1

        if not _state_.current_viewer().window._qt_window.isVisible():
            print(colored("\n========= INTERRUPTED. =========\n", 'red', attrs=['bold']))
            return

    _state_.set_batch(False)
    print(colored(f"\n========= DONE. ({round(time.time()-exec_start, 1)}s) =========\n", 'green', attrs=['bold']))

    return True


@magicgui(
    input_folder = {'mode': 'd'},
    output_folder= {'mode': 'd'},
    call_button  = "Run batch"
)
def batch_folder_gui(input_folder: Path=Path.home(), output_folder: Path=Path.home()):
    global _state_
    _state_.set_batch(True)
    
    _state_.set_export_path(str(output_folder))
    path = str(input_folder)
    clear_layers_gui()

    _state_.set_path(path)
    nElements = len(_state_.queue)

    if nElements == 0:
        print(colored(f"Can't work on {path}", 'red'))
        return False
    
    worker = create_worker(batch_folder_worker, input_folder, output_folder, nElements, _progress={'total': nElements})
    worker.start()

class State(object):

    def __init__(self):
        # Images currently associated with out process
        self.images = {}
        # Array of coordinates representing detected spots
        self.spots_data = None
        # Boolean representing whether we are running in batch mode
        self.batch = False
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
        toolbar = QToolBar()
        toolbar.addSeparator()
        self.dock    = self.viewer.window.add_dock_widget(
            [
                clear_layers_gui,
                split_channels_gui,
                segment_brightfield_gui,
                segment_fluo_gui,
                extract_stats_gui,
                toolbar,
                batch_folder_gui
            ], 
            name="Spots In Yeasts")
    
    def is_batch(self):
        return self.batch

    def total_item(self):
        return len(self.queue)

    def set_batch(self, val):
        self.batch = val

    def clear_data(self):
        self.spots_data = None
        self.images = {}

    def set_spots(self, spots):
        self.spots_data = spots

        if self.batch:
            return

        if _spots in self.current_viewer().layers:
            self.current_viewer().layers[_spots].data = spots
        else:
            self.current_viewer().add_points(self.spots_data, name=_spots)

    def get_spots(self):
        return self.spots_data

    def set_image(self, key, data, args={}):
        self.images[key] = data
        
        if self.batch:
            return 
        
        if key in self.current_viewer().layers:
            self.current_viewer().layers[key].data = data
        else:
            self.current_viewer().add_image(
                data,
                name=key,
                **args
            )
    
    def get_image(self, key):
        return self.images.get(key)

    def required_key(self, key):
        return key in self.images

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
                self.set_current_name(item.split(os.sep)[-1].split('.')[0])
                return True
        
        return False

    # Loads the image stored in "self.current" in Napari.
    # A safety check ensures that several images can't be loaded simulteanously
    def load(self):
        hyperstack = np.array(imread(str(self.current)))

        if hyperstack is None:
            print(colored(f"Failed to open: `{str(self.current)}`.", 'red'))
            return False

        self.set_image('_temp_', hyperstack)

        return True

    def current_viewer(self):
        return self.viewer

    def set_path(self, path):
        self.path    = str(path)
        self._init_queue_()

    def marker_path(self):
        p = Path(__file__)
        return p.parent / "utils" / "marker.pgm"

    def _init_queue_(self):
        if os.path.isdir(self.path):
            self.queue = [os.path.join(self.path, i) for i in os.listdir(self.path) if i.lower().endswith('.tif')]
        
        if os.path.isfile(self.path):
            self.queue = [self.path] if self.path.lower().endswith('.tif') else []

        print(f"{len(self.queue)} files found.")


_state_ = State()


napari.run()

