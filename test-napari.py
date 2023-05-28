import napari
from skimage.io import ImageCollection
import numpy as np
from magicgui import magicgui, widgets
from pathlib import Path
from termcolor import colored
import os, json, tempfile, time

from spotsInYeasts.spotsInYeasts import segment_transmission, create_random_lut, segment_spots, estimateUniformity, associate_spots_yeasts


# 00. Generating the global state that will behave like some sort of state machine.
_state_ = None


@magicgui(call_button="Segment cells")
def segment_brightfield_gui():
    global _state_

    start = time.time()
    labeled, projection = segment_transmission(_state_.current_viewer().layers['brightfield'].data, True)
    _state_.current_viewer().layers['brightfield'].data = projection

    if 'labeled-cells' in _state_.current_viewer().layers:
        _state_.current_viewer().layers['labeled-cells'].data = labeled
    else:
        random_lut = create_random_lut(True)
        _state_.current_viewer().add_image(labeled, name="labeled-cells", blending="additive", rgb=False, colormap=random_lut)
    
    print(colored(f"Segmented cells from `{_state_.get_current_name()}` in {round(time.time()-start, 1)}s.", 'green'))


@magicgui(call_button="Segment YFP spots")
def segment_fluo_gui():
    global _state_

    start = time.time()
    spots_properties = segment_spots(_state_.current_viewer().layers['yfp'].data)
    
    # Avoid duplicating layers in case we relaunch analysis.
    if 'spots-positions' in _state_.current_viewer().layers:
        _state_.current_viewer().layers['spots-positions'].data = spots_properties['locations']
    else:
        _state_.current_viewer().add_points(spots_properties['locations'], name="spots-positions")
    
    # Checking whether the distribution is uniform or not.
    # We consider that the segmentation has failed if it is uniform.
    ttl, ref = estimateUniformity(spots_properties['locations'], spots_properties['mask'].shape)
    if ttl <= ref:
        print(colored(f"The image `{_state_.get_current_name()}` failed to be processed.", 'red'))
        return
    
    print(colored(f"Segmented spots from `{_state_.get_current_name()}` in {round(time.time()-start, 1)}s.", 'green'))

    if 'labeled-cells' not in _state_.current_viewer().layers:
        print(colored("Cells segmentation not available yet.", 'yellow'))
        return

    lbld = _state_.current_viewer().layers['labeled-cells'].data
    ownership, lbl_spots, spots_list = associate_spots_yeasts(lbld, spots_properties['locations'], spots_properties['original'], spots_properties['mask'])

    measures = open(os.path.join(_state_.get_export_path(), _state_.get_current_name() + "_measures.json"), 'w')
    json.dump(ownership, measures)
    measures.close()


@magicgui(call_button="Next Image")
def next_image():
    global _state_
    if _state_.next_item():
        _state_.load()
        return
    
    print(colored("No more image.", 'orange', attrs=['bold']))


@magicgui(call_button="Batch Folder")
def batch_folder():
    exec_start = time.time()
    print("")
    print(colored(f"========= DONE. ({round(time.time()-exec_start, 1)}s) =========", 'green', attrs=['bold']))
    print("")


@magicgui(
    call_button="Set export path",
    export_folder={'mode': 'd'}
)
def set_export_path(export_folder: Path=""):
    global _state_
    _state_.set_export_path(export_folder)


# 01. Display a button to load either a file or a folder.
@magicgui(
    call_button="Load"
)
def load_from_disk(whole_folder: bool=True, file_path: Path="/home/clement/Downloads/testing-set-2"):
    global _state_

    path = file_path

    if whole_folder and os.path.isfile(file_path):
        print("The whole folder will be processed.")
        path = file_path.parent
        file_path = path

    _state_.set_path(path)
    nElements = len(_state_.queue)

    if nElements == 0:
        print(colored(f"Can't work on {path}", 'red'))
        return
    
    _state_.next_item()
    _state_.load()



class State(object):

    def __init__(self):
        self.queue   = []
        self.e_path  = tempfile.gettempdir()
        self.current = None
        self.path    = None
        self.viewer  = napari.Viewer()
        self.dock    = self.viewer.window.add_dock_widget(
            [
                set_export_path,
                load_from_disk,
                segment_brightfield_gui,
                segment_fluo_gui,
                next_image,
                batch_folder
            ], 
            name="Spots In Yeasts")
    
    def get_export_path(self):
        return self.e_path

    def set_export_path(self, path):
        d_path = str(path)
        if not os.path.isdir(d_path):
            print(colored(f"{d_path} ", 'red', attrs=['italic']), end="")
            print(colored("is not a directory path.", 'red'))
            d_path = tempfile.gettempdir()
        print("Export directory set to: ", end="")
        print(colored(d_path, attrs=['underline']))
        self.e_path = d_path

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
            name="yfp",
            colormap='yellow',
            blending='opaque'
        )
        self.viewer.add_image(
            bf,
            rgb=False,
            name="brightfield",
            blending='opaque'
        )

        return True

    def current_viewer(self):
        return self.viewer
    
    def get_current_name(self):
        return os.path.basename(self.current).split('.')[0]

    def set_path(self, path):
        self.path    = str(path)
        self._init_queue_()

    def _init_queue_(self):
        if os.path.isdir(self.path):
            self.queue = [os.path.join(self.path, i) for i in os.listdir(self.path) if i.lower().endswith('.tif')]
        
        if os.path.isfile(self.path):
            self.queue = [self.path] if self.path.lower().endswith('.tif') else []

        print(f"{len(self.queue)} files found.")

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
                return True
        
        return False


_state_ = State()



# start the event loop and show the viewer
napari.run()



# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#                              TO DO
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# - [ ] On veut pouvoir retirer les labels en cliquant dessus.
# - [ ] On veut pouvoir éditer les spots (ajout/délétion) en éditant le layer de spots.
# - [ ] Créer un mode debug qui exporte les images intermédiaires dans un dossier pour monitor.
# - [ ] Mettre les exécution dans des threads parallèles pour garder la GUI réactive.
# - [ ] Rajouter des paramètres pour la détection de spots.
# - [ ] Essayer de faire une GUI plus propre.
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #