import napari
from tifffile import imread
from datetime import datetime
import numpy as np
from magicgui import magicgui, widgets
from magicclass import magicclass
from pathlib import Path
from termcolor import colored
import os, json, tempfile, time, subprocess, platform, sys
from qtpy.QtWidgets import QToolBar, QWidget, QVBoxLayout
from napari.qt.threading import thread_worker, create_worker
from napari.utils import progress
from spots_in_yeasts.spotsInYeasts import segment_transmission, segment_spots, estimate_uniformity, associate_spots_yeasts, create_reference_to, prepare_directory, write_labels_image, segment_nuclei
from spots_in_yeasts.formatData import format_data_1844, format_data_1895
from enum import Enum, auto

_bf      = "brightfield"
_f_spots = "fluo-spots"
_lbl_c   = "labeled-cells"
_lbl_s   = "labeled-spots"
_spots   = "spots-positions"
_n_cells = "cells-indices"
_nuclei  = "fluo-nuclei"
_lbl_n   = "labeled-nuclei"

class FormatsList(Enum):
    format_1844 = auto()
    format_1895 = auto()

def default_export():
    return FormatsList.format_1844

_global_settings = {
    'gaussian_radius'   : 3.0,
    'neighbour_slices'  : 2,
    'peak_distance'     : 5,
    'area_threshold'    : 90,
    'extent_threshold'  : 0.6,
    'solidity_threshold': 0.87,
    'death_threshold'   : 4,
    'cover_threshold'   : 0.75,
    'nuclei_threshold'  : 15,
    'export_mode'       : FormatsList.format_1844
}

@magicclass
class SpotsInYeastsDock:

    def __init__(self, napari_viewer):
        super().__init__()
        # Images currently associated with out process
        self.images = {}
        # Array of coordinates representing detected spots
        self.spots_data = None
        # Boolean representing whether we are running in batch mode
        self.batch = False
        # Queue of files to be processed.
        self.queue = []
        # Path of a directory in which measures will be exported, only in batch mode.
        self.e_path = tempfile.gettempdir()
        # Absolute path of the file currently processed.
        self.current = None
        # Path of the directory in which images will be processed, only in batch mode.
        self.path = None
        # Current Viewer in Napari instance.
        self.viewer = napari_viewer
        # Display name used for the current image
        self.name = ""
        # CSV table containing results for the batch mode
        self.csvtable = None
        # Export path, only for batch mode
        self.csvexport = ""
        # Dictionary containing for each cell's label, the list of spots it owns
        self.ownership = {}

    def _clear_state(self):
        self.images = {}
        self.spots_data = None
        self.batch = False
        self.queue = []
        self.e_path = tempfile.gettempdir()
        self.current = None
        self.path = None
        self.name = ""
        self.csvtable = None
        self.csvexport = ""
        self.ownership = {}

        self.clear_layers_gui()
        
    def _is_batch(self):
        return self.batch
    
    def _set_batch(self, val):
        if val:
            print("Running in batch mode.")
        else:
            print("End of batch mode.")
        self.batch = val

    def _clear_data(self):
        self.spots_data = None
        self.images = {}

    def _set_ownership(self, ownership):
        self.ownership = ownership

    def _get_ownership(self):
        return self.ownership

    def _set_spots(self, spots):
        self.spots_data = spots

        if self.batch:
            return

        if _spots in self._current_viewer().layers:
            self._current_viewer().layers[_spots].data = spots
        else:
            self._current_viewer().add_points(self.spots_data, name=_spots)

    def _get_spots(self):
        return self.spots_data

    def _set_image(self, key, data, args={}, aslabels=False, ctr=0):
        self.images[key] = data
        
        if self.batch:
            return 
        
        if key in self._current_viewer().layers:
            self._current_viewer().layers[key].data = data
        else:
            if aslabels:
                self._current_viewer().add_labels(
                    data,
                    name=key,
                    **args)
            else:
                self._current_viewer().add_image(
                    data,
                    name=key,
                    **args)
        if aslabels:
            self._current_viewer().layers[key].contour = ctr
    
    def _get_image(self, key):
        return self.images.get(key)

    def _required_key(self, key):
        return key in self.images

    def _get_export_path(self):
        return os.path.join(self.e_path, self._get_current_name()+".ysc")

    def _set_export_path(self, path):
        d_path = str(path)
        if not os.path.isdir(d_path):
            print(colored(f"{d_path}", 'red', attrs=['underline']), end="")
            print(colored(" is not a directory path.", 'red'))
            d_path = tempfile.gettempdir()
        print("Export directory set to: ", end="")
        print(colored(d_path, attrs=['underline']))
        self.e_path = d_path

    def _set_current_name(self, n):
        self.name = n
    
    def _get_current_name(self):
        return self.name
    
    def _current_image(self):
        return self.current

    def _reset_current(self):
        self.current = None
        self._set_current_name("")

    def _next_item(self):
        self.current = None

        if self.path is None:
            return False

        if len(self.queue) == 0:
            return False
        
        while len(self.queue) > 0:
            item = self.queue.pop(0)
            if os.path.isfile(item):
                self.current = item
                self._set_current_name(item.split(os.sep)[-1].split('.')[0])
                prepare_directory(self._get_export_path())
                return True
        
        return False

    # Loads the image stored in "self.current" in Napari.
    # A safety check ensures that several images can't be loaded simulteanously
    def _load(self):
        hyperstack = np.array(imread(str(self.current)))

        if hyperstack is None:
            print(colored(f"Failed to open: `{str(self.current)}`.", 'red'))
            return False

        self._set_image(self._get_current_name(), hyperstack)
        print(colored(f"\n===== Currently working on: {self._get_current_name()} =====", 'green', attrs=['bold']))

        return True

    def _current_viewer(self):
        return self.viewer

    def _set_path(self, path):
        self.path    = str(path)
        self._init_queue_()

    def _init_queue_(self):
        if os.path.isdir(self.path):
            self.queue = [os.path.join(self.path, i) for i in os.listdir(self.path) if i.lower().endswith('.tif')]
        
        if os.path.isfile(self.path):
            self.queue = [self.path] if self.path.lower().endswith('.tif') else []

        print(f"{len(self.queue)} files found.")

    
    @magicgui(
        call_button  = "Apply settings"
    )
    def apply_settings_gui(
        self, 
        gaussian_radius: float=_global_settings['gaussian_radius'], 
        neighbour_slices: int=_global_settings['neighbour_slices'], 
        death_threshold: int=_global_settings['death_threshold'], 
        peak_distance: int=_global_settings['peak_distance'], 
        area_threshold: int=_global_settings['area_threshold'], 
        extent_threshold: float=_global_settings['extent_threshold'], 
        solidity_threshold: float=_global_settings['solidity_threshold'], 
        cover_threshold: float=_global_settings['cover_threshold'],
        nuclei_threshold: int=_global_settings['nuclei_threshold'],
        export_mode: FormatsList=default_export()):
        
        global _global_settings

        _global_settings['gaussian_radius']    = gaussian_radius
        _global_settings['neighbour_slices']   = neighbour_slices
        _global_settings['peak_distance']      = peak_distance
        _global_settings['area_threshold']     = area_threshold
        _global_settings['extent_threshold']   = extent_threshold
        _global_settings['solidity_threshold'] = solidity_threshold
        _global_settings['export_mode']        = export_mode
        _global_settings['death_threshold']    = death_threshold    
        _global_settings['nuclei_threshold']   = nuclei_threshold
        _global_settings['cover_threshold']    = cover_threshold

    @magicgui(call_button="Clear layers")
    def clear_layers_gui(self):
        """
        Removes all the layers currently present in the Napari's viewer, and resets the state machine used by the scipt.
        """
        self._current_viewer().layers.clear()
        self._reset_current()
        self._clear_data()
        self.csvtable = None
        return True


    @magicgui(call_button="Split channels")
    def split_channels_gui(self):
        
        nImages = len(self._current_viewer().layers)

        if not self._is_batch():
            if nImages != 1:
                print(colored(f"Excatly one image must be loaded at a time. (found {nImages})", 'red'))
                return False

        imIn = self._get_image(self._get_current_name()) if self._is_batch() else self._current_viewer().layers[0].data
        imSp = imIn.shape

        # (2, 2048, 2048) -> channels, height, width
        # (9, 2, 2048, 2048) -> slices, channels, height, width
        if len(imSp) not in [3, 4]:
            print(colored(f"Images must have 3 or 4 dimensions. {len(imSp)} found.", 'red'))
            return False

        axis      = 0 if (len(imSp) == 3) else 1
        nChannels = imSp[axis]

        if nChannels not in {2, 3}:
            print(colored(f"Exactly 2 or 3 channels are expected. {nChannels} found.", 'red'))
            return False
        
        if not self._is_batch():
            self._set_current_name(self._current_viewer().layers[0].name)
            self._current_viewer().layers.clear()

        if nChannels == 2:
            s, t = np.split(imIn, indices_or_sections=2, axis=axis)
            n = None
        else:
            s, t, n = np.split(imIn, indices_or_sections=3, axis=axis)
        
        if n is not None:
            self._set_image(_nuclei, np.squeeze(n), {
                'rgb'      : False,
                'colormap' : 'cyan',
                'blending' : 'opaque'
            })

        self._set_image(_f_spots, np.squeeze(s), {
            'rgb'      : False,
            'colormap' : 'yellow',
            'blending' : 'opaque'
        })

        self._set_image(_bf, np.squeeze(t), {
            'rgb'      : False,
            'blending' : 'opaque'
        })

        return True


    @magicgui(call_button="Segment cells")
    def segment_brightfield_gui(self):
        
        if not self._required_key(_bf):
            print(colored(_bf, 'red', attrs=['underline']), end="")
            print(colored(" channel not found.", 'red'))
            return False

        start = time.time()
        labeled, projection = segment_transmission(self._get_image(_bf), True, _global_settings['neighbour_slices'])
        indices = write_labels_image(labeled, 0.75)
        
        self._set_image(_bf, projection)
        
        self._set_image(_lbl_c, labeled, {
            'blending': "additive"
        },
        True)

        self._set_image(_n_cells, indices, {
            'visible': False,
            'blending': "additive"
        })
        
        print(colored(f"Segmented cells from `{self._get_current_name()}` in {round(time.time()-start, 1)}s.", 'green'))
        return True
    

    @magicgui(call_button="Segment nuclei")
    def segment_nuclei_gui(self):
        
        if not self._required_key(_bf):
            print(colored(_bf, 'red', attrs=['underline']), end="")
            print(colored(" channel not found.", 'red'))
            return False

        if not self._required_key(_lbl_c):
            print(colored(_lbl_c, 'red', attrs=['underline']), end="")
            print(colored(" channel not found.", 'red'))
            return False
        
        if not self._required_key(_nuclei):
            print(colored(_nuclei, 'red', attrs=['underline']), end="")
            print(colored(" channel not found.", 'red'))
            return False

        start = time.time()
        fluo_nuclei, valid_cells, lbl_nuclei = segment_nuclei(
            self._get_image(_lbl_c), 
            self._get_image(_nuclei), 
            _global_settings['cover_threshold'], 
            _global_settings['nuclei_threshold']
        )

        indices = write_labels_image(valid_cells, 0.75)
        self._set_image(_n_cells, indices, {
            'visible': False,
            'blending': "additive"
        })
        
        self._set_image(_nuclei, fluo_nuclei)

        self._set_image(_lbl_c, valid_cells, {
            'blending': "additive"
        },
        True,
        3)

        self._set_image(_lbl_n, lbl_nuclei, {
            'blending': "additive"
        },
        True)

        print(colored(f"Segmented nuclei from `{self._get_current_name()}` in {round(time.time()-start, 1)}s.", 'green'))
        return True


    @magicgui(call_button="Segment spots")
    def segment_fluo_gui(self):
        
        if not self._required_key(_f_spots):
            print(colored(_f_spots, 'red', attrs=['underline']), end="")
            print(colored(" channel not found.", 'red'))
            return False

        start = time.time()
        spots_locations, labeled_spots, f_spots = segment_spots(self._get_image(_f_spots), self._get_image(_lbl_c), _global_settings['gaussian_radius'], _global_settings['peak_distance'])
        self._set_image(_f_spots, f_spots)

        # Checking whether the distribution is uniform or not.
        # We consider that the segmentation has failed if it is uniform.
        unif = estimate_uniformity(spots_locations, labeled_spots.shape)
        if unif:
            return False
        
        labeled_cells   = self._get_image(_lbl_c)
        ow, spots_locations, labeled_spots = associate_spots_yeasts(labeled_cells, labeled_spots, f_spots, _global_settings['area_threshold'], _global_settings['solidity_threshold'], _global_settings['extent_threshold'], _global_settings['death_threshold'])
        self._set_ownership(ow)

        self._set_spots(spots_locations)
        self._set_image(_lbl_s, labeled_spots, {
            'visible' : False
        },
        True)
        
        print(colored(f"Segmented spots from `{self._get_current_name()}` in {round(time.time()-start, 1)}s.", 'green'))
        return True


    @magicgui(call_button="Extract stats")
    def extract_stats_gui(self):

        if not self._required_key(_lbl_c):
            print(colored("Cells segmentation not available yet.", 'yellow'))
            return False

        if not self._required_key(_lbl_s):
            print(colored("Spots segmentation not available yet.", 'yellow'))
            return False

        if not os.path.isdir(self._get_export_path()):
            prepare_directory(self._get_export_path())

        measures_path = self.csvexport if self._is_batch() else os.path.join(self._get_export_path(), self._get_current_name()+".csv")
        ow = self._get_ownership()
        
        if _global_settings['export_mode'] == FormatsList.format_1844:
            self.csvtable = format_data_1844(ow, self._get_current_name(), self.csvtable)
        elif _global_settings['export_mode'] == FormatsList.format_1895:
            self.csvtable = format_data_1895(ow, self._get_current_name(), self.csvtable)

        try:
            self.csvtable.exportTo(measures_path)
        except:
            print(colored("Failed to export measures to: ", 'red'), end="")
            print(colored(measures_path,'red', attrs=['underline']))
            return False
        else:
            print(colored("Spots exported to: ", 'green'), end="")
            print(colored(measures_path,'green', attrs=['underline']))

            if not self._is_batch():
                if platform.system() == 'Windows':
                    os.startfile(measures_path)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.call(('open', measures_path))
                else:  # linux variants
                    subprocess.call(('xdg-open', measures_path))

        return True

    def _get_path(self):
        return self.path

    def _create_control(self):
        create_reference_to(
            self._get_image(_lbl_c), 
            self._get_image(_lbl_s), 
            self._get_spots(),
            self._get_current_name(),
            self._get_export_path(),
            self._get_path(),
            self._get_image(_bf),
            self._get_image(_f_spots),
            self._get_image(_n_cells)
        )
        return True

    def _batch_folder_worker(self, input_folder, output_folder, nElements):
        
        exec_start = time.time()
        iteration = 0
        procedure = [
            self._load,
            self.split_channels_gui,
            self.segment_brightfield_gui,
            self.segment_fluo_gui,
            self.extract_stats_gui,
            self._create_control
        ]
        now = datetime.now()
        date_time_string = now.strftime("%Y-%m-%d-%H-%M-%S")
        self.csvexport   = os.path.join(self.e_path, f"batch-results-{date_time_string}.csv")

        while self._next_item():
            for step in procedure:
                if not step():
                    print(colored("Failed to process: ", 'red'), end="")
                    print(colored(self._get_current_name(), 'red', attrs=['underline']), end="")
                    print(colored(".", 'red'))
                    break
            
            yield iteration
            iteration += 1
            print(colored(f"{self._get_current_name()} processed. ({iteration}/{nElements})", 'green'))

            if not self._current_viewer().window._qt_window.isVisible():
                print(colored("\n========= INTERRUPTED. =========\n", 'red', attrs=['bold']))
                return

        self._set_batch(False)
        print(colored(f"\n============= DONE. ({round(time.time()-exec_start, 1)}s) =============\n", 'green', attrs=['bold']))
        self._clear_state()
        return True

    @magicgui(
        input_folder = {'mode': 'd'},
        output_folder= {'mode': 'd'},
        call_button  = "Run batch"
    )
    def batch_folder_gui(self, input_folder: Path=Path.home(), output_folder: Path=Path.home()):
        self._clear_state()
        self._set_batch(True)
        self._set_export_path(str(output_folder))
        path = str(input_folder)
        self.clear_layers_gui()

        self._set_path(path)
        nElements = len(self.queue)

        if nElements == 0:
            print(colored(f"{path} doesn't contain any valid file.", 'red'))
            return False
        
        worker = create_worker(self._batch_folder_worker, input_folder, output_folder, nElements, _progress={'total': nElements})
        worker.start()
