from qtpy.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, 
                            QSpinBox, QHBoxLayout, QPushButton, 
                            QFileDialog, QComboBox, QLabel, QTabWidget,
                            QSlider, QSpinBox, QFrame, QLineEdit)

from qtpy.QtCore import QThread, Qt

from PyQt5.QtGui import QFont, QDoubleValidator
from PyQt5.QtCore import pyqtSignal

import napari
from napari.utils.notifications import show_info
from napari.utils import progress

import tifffile
import numpy as np
import math
import os
import json

from spots_in_yeasts.image_layout_editor import ImageLayoutEditor
from spots_in_yeasts.utils import get_config, set_config, find_focused_slice
from spots_in_yeasts.siy_processor import SpotsInYeasts
from spots_in_yeasts.qt_workers import QtSegmentCells

class SpotsInYeastsWidget(QWidget):

    patches_displayed = pyqtSignal()
    export_done       = pyqtSignal()
    labels_ready      = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.viewer        = napari.current_viewer()
        self.processor     = None # Contains operations
        self.ile           = None # Image Layout Editor
        self.channels_lt   = None # Dict of channels layout
        self.worker        = None
        self.active_worker = False

        self.layout = QVBoxLayout()
        self.init_ui()
        self.setLayout(self.layout)

        self.retrieve()
        self.clear_layers()

    # # # # # # # # # # # # #  UI  # # # # # # # # # # # # #

    def init_ui(self):
        self.font = QFont()
        self.font.setFamily("Arial Unicode MS, Segoe UI Emoji, Apple Color Emoji, Noto Color Emoji")
        self.channels_layout_ui()
        self.stack_settings_ui()
        self.yeasts_ui()
        self.nuclei_ui()
        self.spots_ui()
        self.toolbox_ui()

    def channels_layout_ui(self):
        self.channelsGroup = QGroupBox("•  Channels layout")
        self.channelsLayout = QVBoxLayout()

        # Clear state
        self.clearLayersButton = QPushButton("❌ Clear layers")
        self.clearLayersButton.setFont(self.font)
        self.clearLayersButton.clicked.connect(self.clear_layers)
        self.channelsLayout.addWidget(self.clearLayersButton)

        # Vertical padding (white space)
        self.channelsLayout.addSpacing(20)
        
        # Select directory button
        self.workingDirButton = QPushButton("📂 Working directory")
        self.workingDirButton.setFont(self.font)
        self.workingDirButton.clicked.connect(self.select_working_dir)
        self.channelsLayout.addWidget(self.workingDirButton)

        # Edit channels layout button
        self.editLayoutButton = QPushButton("♻️ Edit channels layout")
        self.editLayoutButton.setFont(self.font)
        self.editLayoutButton.clicked.connect(self.launch_layout_editor)
        self.channelsLayout.addWidget(self.editLayoutButton)

        # Set channels layout combobox
        self.layoutComboBox = QComboBox()
        self.layoutComboBox.addItem("---")
        self.layoutComboBox.currentIndexChanged.connect(self.update_layout)
        self.channelsLayout.addWidget(self.layoutComboBox)

        # Name of the current channels layout
        self.selectedLayout = QLabel("---", self)
        self.selectedLayout.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.selectedLayout.setAlignment(Qt.AlignCenter)
        self.selectedLayout.setStyleSheet("QLabel { font-weight: bold; }")
        self.channelsLayout.addWidget(self.selectedLayout)

        # Apply layout button
        self.applyLayoutButton = QPushButton("🔧 Split channels")
        self.applyLayoutButton.setFont(self.font)
        self.applyLayoutButton.clicked.connect(self.apply_layout)
        self.channelsLayout.addWidget(self.applyLayoutButton)

        self.channelsGroup.setLayout(self.channelsLayout)
        self.layout.addWidget(self.channelsGroup)
    
    def stack_settings_ui(self):
        self.stackGroup = QGroupBox("•  Stack settings")
        self.stackLayout = QVBoxLayout()

        # Slices around focus spinbox
        around_focus_layout = QHBoxLayout()
        around_focus_label = QLabel("Slices around focus:")
        self.slicesAroundFocus = QSpinBox()
        self.slicesAroundFocus.setRange(0, 10)
        self.slicesAroundFocus.setValue(2)
        around_focus_layout.addWidget(around_focus_label)
        around_focus_layout.addWidget(self.slicesAroundFocus)
        self.stackLayout.addLayout(around_focus_layout)

        # Create MIP button
        self.createMIPButton = QPushButton("📥 Create MIP")
        self.createMIPButton.setFont(self.font)
        self.createMIPButton.clicked.connect(self.mip_flatten)
        self.stackLayout.addWidget(self.createMIPButton)

        self.stackGroup.setLayout(self.stackLayout)
        self.layout.addWidget(self.stackGroup)

    def yeasts_ui(self):
        self.yeastsGroup = QGroupBox("•  Segment yeasts")
        self.yeastsLayout = QVBoxLayout()

        # Median cell diameter input
        median_diameter_layout = QHBoxLayout()
        median_diameter_label = QLabel("Cells ⌀ (pxl):")
        self.medianDiameter = QSpinBox()
        self.medianDiameter.setRange(20, 100)
        self.medianDiameter.setValue(35)
        median_diameter_layout.addWidget(median_diameter_label)
        median_diameter_layout.addWidget(self.medianDiameter)
        self.yeastsLayout.addLayout(median_diameter_layout)

        # Launch segmentation button
        self.segmentCellsButton = QPushButton("📍 Segment cells")
        self.segmentCellsButton.setFont(self.font)
        self.segmentCellsButton.clicked.connect(self.segment_cells)
        self.yeastsLayout.addWidget(self.segmentCellsButton)

        self.yeastsGroup.setLayout(self.yeastsLayout)
        self.layout.addWidget(self.yeastsGroup)

    def nuclei_ui(self):
        self.nucleiGroup = QGroupBox("•  Segment nuclei")
        self.nucleiLayout = QVBoxLayout()

        # Vertical padding (white space)
        self.nucleiLayout.addSpacing(10)

        # Percentage of nuclei in yeasts for death (slider)
        death_percentage_layout = QHBoxLayout()
        death_ratio_label = QLabel("Max N/C ratio:")
        self.deathPercentage = QSlider(Qt.Horizontal)
        self.deathPercentage.setRange(0, 100)
        self.deathPercentage.setValue(50)
        self.deathPercentageLabel = QLabel(f"{self.deathPercentage.value()}%")
        self.deathPercentage.valueChanged.connect(self.update_death_percentage)
        death_percentage_layout.addWidget(death_ratio_label)
        death_percentage_layout.addWidget(self.deathPercentage)
        death_percentage_layout.addWidget(self.deathPercentageLabel)
        self.nucleiLayout.addLayout(death_percentage_layout)

        # Vertical padding (white space)
        self.nucleiLayout.addSpacing(10)

        # Launch nuclei segmentation button
        self.segmentNucleiButton = QPushButton("📍 Segment nuclei")
        self.segmentNucleiButton.setFont(self.font)
        self.segmentNucleiButton.clicked.connect(self.segment_nuclei)
        self.nucleiLayout.addWidget(self.segmentNucleiButton)

        # Button to launch the Hopcroft-Karp algorithm
        self.hopcroftButton = QPushButton("🔗 Hopcroft-Karp")
        self.hopcroftButton.setFont(self.font)
        self.hopcroftButton.clicked.connect(self.hk_pairing)
        self.nucleiLayout.addWidget(self.hopcroftButton)

        self.nucleiGroup.setLayout(self.nucleiLayout)
        self.layout.addWidget(self.nucleiGroup)
    
    def add_spots_tab_ui(self, name):
        if name == "":
            show_info("Please provide a name for the channel.")
            return
        tab = QWidget()
        self.spotsSettings.addTab(tab, name)

        tab_layout = QVBoxLayout()
        tab.setLayout(tab_layout)

        # Reset input text field
        self.channel_name.setText("")

        # Minimal distance between spots
        min_distance_layout = QHBoxLayout()
        min_distance_label = QLabel("Min spots distance (pxl):")
        min_distance = QSpinBox()
        min_distance.setRange(1, 100)
        min_distance.setValue(4)
        min_distance_layout.addWidget(min_distance_label)
        min_distance_layout.addWidget(min_distance)
        tab_layout.addLayout(min_distance_layout)

        # Input for the LoG radius
        log_filter_layout = QHBoxLayout()
        log_filter_label = QLabel("LoG radius (pxl):")
        log_filter_radius = QSlider(Qt.Horizontal)
        log_filter_radius.setRange(1, 50)
        log_filter_radius.setValue(2)
        log_filter_value = QLabel(f"{log_filter_radius.value()/10}")
        log_filter_radius.valueChanged.connect(lambda: log_filter_value.setText(f"{log_filter_radius.value()/10}"))
        log_filter_value.setFixedHeight(20)
        log_filter_layout.addWidget(log_filter_label)
        log_filter_layout.addWidget(log_filter_radius)
        log_filter_layout.addWidget(log_filter_value)
        tab_layout.addLayout(log_filter_layout)

        # Minimal spots area
        min_area_layout = QHBoxLayout()
        min_area_label = QLabel("Min spots area (pxl²):")
        min_area = QSpinBox()
        min_area.setRange(1, 100)
        min_area_layout.addWidget(min_area_label)
        min_area_layout.addWidget(min_area)
        tab_layout.addLayout(min_area_layout)

        # Maximal spots area
        max_area_layout = QHBoxLayout()
        max_area_label = QLabel("Max spots area (pxl²):")
        max_area = QSpinBox()
        max_area.setRange(1, 100)
        max_area_layout.addWidget(max_area_label)
        max_area_layout.addWidget(max_area)
        tab_layout.addLayout(max_area_layout)

        # Intensity threshold
        intensity_threshold_layout = QHBoxLayout()
        intensity_threshold_label = QLabel("Intensity threshold (%):")
        intensity_threshold = QSlider(Qt.Horizontal)
        intensity_threshold.setRange(1, 100)
        intensity_threshold.setValue(20)
        intensity_threshold_value = QLabel(f"{intensity_threshold.value()}%")
        intensity_threshold.valueChanged.connect(lambda: intensity_threshold_value.setText(f"{intensity_threshold.value()}%"))
        intensity_threshold_value.setFixedHeight(20)
        intensity_threshold_layout.addWidget(intensity_threshold_label)
        intensity_threshold_layout.addWidget(intensity_threshold)
        intensity_threshold_layout.addWidget(intensity_threshold_value)
        tab_layout.addLayout(intensity_threshold_layout)

        # Segment spots button
        segment_spots = QPushButton("💡 Find spots")
        segment_spots.setFont(self.font)
        segment_spots.clicked.connect(lambda: self.segment_spots(name))

        # Save configuration button
        save_configuration = QPushButton("💾 Save settings")
        save_configuration.setFont(self.font)
        save_configuration.clicked.connect(lambda: self.save_configuration(name))
        
        # Layout button
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(segment_spots)
        buttons_layout.addWidget(save_configuration)
        tab_layout.addLayout(buttons_layout)

        widgets = {
            'name'               : name,
            'log_radius'         : log_filter_radius,
            'min_distance'       : min_distance,
            'min_area'           : min_area,
            'max_area'           : max_area,
            'intensity_threshold': intensity_threshold,
            'segment_spots'      : segment_spots,
            'save_configuration' : save_configuration
        }
        self.spots_tabs_widgets.append(widgets)
    
    def add_settings_tab_ui(self):
        # Adds all the settings in a new tab in 'self.spotsSettings'
        tab = QWidget()
        self.spotsSettings.addTab(tab, "   ⚙️   ")

        tab_layout = QVBoxLayout()
        tab.setLayout(tab_layout)

        # Name of the channel
        channel_name_layout = QHBoxLayout()
        channel_name_label = QLabel("Name:")
        self.channel_name = QLineEdit()
        channel_name_layout.addWidget(channel_name_label)
        channel_name_layout.addWidget(self.channel_name)
        tab_layout.addLayout(channel_name_layout)

        # Add config button
        add_config = QPushButton("☑️ Create config")
        add_config.setFont(self.font)
        add_config.clicked.connect(lambda: self.add_spots_tab_ui(self.channel_name.text().strip()))
        tab_layout.addWidget(add_config)

        # Separator
        separator = QLabel("───────")
        separator.setAlignment(Qt.AlignCenter)
        separator.setStyleSheet("QLabel { color: #aaaaaa; }")
        separator.setFixedHeight(20)
        tab_layout.addWidget(separator)

        # Clear loaded configs button
        clear_configs = QPushButton("❌ Clear loaded configs")
        clear_configs.setFont(self.font)
        clear_configs.clicked.connect(self.reset_all_tabs_ui)
        tab_layout.addWidget(clear_configs)

        # Load config label + combobox
        load_config_layout = QHBoxLayout()
        load_config_label = QLabel("Load config:")
        self.load_config = QComboBox()
        self.load_config.addItem("---")
        load_config_layout.addWidget(load_config_label)
        load_config_layout.addWidget(self.load_config)
        tab_layout.addLayout(load_config_layout)

        self.settings_widgets = {
            'add_config'    : add_config,
            'clear_configs' : clear_configs,
            'load_config'   : self.load_config,
            'channel_name'  : self.channel_name
        }
        self.spots_tabs_widgets = []

    def reset_all_tabs_ui(self):
        self.spotsSettings.clear()
        self.spots_tabs_widgets = []
        self.add_settings_tab_ui()

    def spots_ui(self):
        self.spotsGroup = QGroupBox("•  Segment spots")
        self.spotsLayout = QVBoxLayout()
        self.spots_tabs_widgets = []

        # A tab of settings for each spots channel (one at init)
        self.spotsSettings = QTabWidget()
        self.spotsLayout.addWidget(self.spotsSettings)
        self.add_settings_tab_ui()
        tab_bar = self.spotsSettings.tabBar()
        tab_bar.setStyleSheet("""
            QTabBar::tab:first {
                background: lightcoral;
            }
            QTabBar::tab:first:selected {
                background: coral;
            }
        """)
        self.spotsSettings.update()

        # Segment all spots button
        self.segmentAllSpotsButton = QPushButton("📍 Segment all spots")
        self.segmentAllSpotsButton.setFont(self.font)
        self.segmentAllSpotsButton.clicked.connect(self.segment_all_spots)
        self.spotsLayout.addWidget(self.segmentAllSpotsButton)

        self.spotsGroup.setLayout(self.spotsLayout)
        self.layout.addWidget(self.spotsGroup)

    def toolbox_ui(self):
        self.toolboxGroup = QGroupBox("•  Toolbox")
        self.toolboxLayout = QVBoxLayout()

        # Deletion mode button
        self.deletionModeButton = QPushButton("🗑️ Deletion mode")
        self.deletionModeButton.setFont(self.font)
        self.deletionModeButton.setCheckable(True)
        self.deletionModeButton.clicked.connect(self.deletion_mode)
        self.toolboxLayout.addWidget(self.deletionModeButton)

        # Fusion mode button
        self.fusionModeButton = QPushButton("🔗 Fusion mode")
        self.fusionModeButton.setFont(self.font)
        self.fusionModeButton.setCheckable(True)
        self.fusionModeButton.clicked.connect(self.fusion_mode)
        self.toolboxLayout.addWidget(self.fusionModeButton)

        # Export measures button
        self.exportMeasuresButton = QPushButton("💾 Export measures")
        self.exportMeasuresButton.setFont(self.font)
        self.exportMeasuresButton.clicked.connect(self.export_measures)
        self.toolboxLayout.addWidget(self.exportMeasuresButton)

        self.toolboxGroup.setLayout(self.toolboxLayout)
        self.layout.addWidget(self.toolboxGroup)
    
    # # # # # # # # # # # # #  CALLBACKS  # # # # # # # # # # # # #

    def clear_layers(self):
        self.viewer.layers.clear()
        self.processor = SpotsInYeasts()

    def select_working_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select a working directory")
        if not folder:
            return
        self.set_working_directory(folder)

    def launch_layout_editor(self):
        self.ile = ImageLayoutEditor()
        self.ile.destroyed.connect(self.update_layouts_list)
        self.ile.show()
    
    def update_layouts_list(self):
        config = get_config()
        working_dir = config.get('working_directory', None)
        layouts_dir = os.path.join(working_dir, "layouts")
        if not working_dir or not os.path.isdir(layouts_dir):
            return
        layouts = sorted([f.replace('.json', '') for f in os.listdir(layouts_dir) if f.endswith('.json')])
        self.layoutComboBox.clear()
        self.layoutComboBox.addItems(["---"] + layouts)

    def update_layout(self):
        tgt_layout = self.layoutComboBox.currentText()
        if tgt_layout == "---":
            return
        self.selectedLayout.setText(tgt_layout)
        self.set_current_layout(tgt_layout)

    # 2D: C, Y, X
    # 3D: Z, C, Y, X
    def apply_layout(self):
        if self.channels_lt is None:
            return
        layer = self.viewer.layers.selection.active
        if layer is None:
            return
        img = layer.data
        if len(img.shape) == 3:
            self.split_2d_channels(img)
        elif len(img.shape) == 4:
            self.split_3d_channels(img)
        self.viewer.layers.remove(layer)
    
    def split_2d_channels(self, img):
        for i, channel in enumerate(self.channels_lt):
            if channel['type'] == '---':
                continue
            data = img[i, :, :].copy()
            target = channel['name'] + '.' + channel['type']
            if target in self.viewer.layers:
                self.viewer.layers[target].data = data
            else:
                self.viewer.add_image(data, name=target, colormap=channel['color'])

    def split_3d_channels(self, img):
        for i, channel in enumerate(self.channels_lt):
            if channel['type'] == '---':
                continue
            data = img[:, i, :, :].copy()
            target = channel['name'] + '.' + channel['type']
            if target in self.viewer.layers:
                self.viewer.layers[target].data = data
            else:
                self.viewer.add_image(data, name=target, colormap=channel['color'])

    def segment_cells(self):
        self.processor.set_cells_diameter(self.medianDiameter.value())
        data, target = self.get_first_of('Brightfield')
        self.processor.set_brightfield(data, target)
        self.pbr = progress()
        self.pbr.set_description("Segmenting cells...")
        self.set_active_ui(False)
        self.thread = QThread()

        self.worker = QtSegmentCells(self.pbr, self.processor)
        self.worker.update.connect(self.update_pbr)
        self.active_worker = True

        self.worker.moveToThread(self.thread)
        self.worker.finished.connect(self.acquire_cells_segmentation)
        self.thread.started.connect(self.worker.run)
        
        self.thread.start()
    
    def acquire_cells_segmentation(self):
        self.end_worker()
        labeled_cells = self.processor.labeled_cells
        layer_name = self.processor.cells_target + "-labeled"
        layer = None
        if layer_name in self.viewer.layers:
            layer = self.viewer.layers[layer_name]
            layer.data = labeled_cells
        else:
            layer = self.viewer.add_labels(labeled_cells, name=layer_name)
        layer.contour = 4
        show_info(f"Found {np.max(labeled_cells)} cells.")

    def get_first_of(self, name):
        for layer in self.viewer.layers:
            _, t = layer.name.split('.')
            if t == name:
                return layer.data, layer.name
        return None, None

    def update_death_percentage(self, value):
        self.deathPercentageLabel.setText(f"{value}%")

    def segment_nuclei(self):
        pass

    def hk_pairing(self):
        pass

    def segment_spots(self, name):
        pass

    def save_configuration(self, name):
        pass

    def segment_all_spots(self):
        pass

    def deletion_mode(self, value):
        font_weight = "bold" if value else "normal"
        self.deletionModeButton.setStyleSheet(f"QPushButton {{ font-weight: {font_weight}; }}")

    def fusion_mode(self, value):
        font_weight = "bold" if value else "normal"
        self.fusionModeButton.setStyleSheet(f"QPushButton {{ font-weight: {font_weight}; }}")

    def export_measures(self):
        pass

    def set_working_directory(self, folder):
        if not os.path.isdir(folder):
            show_info("The selected directory does not exist.")
            return
        config = get_config()
        config['working_directory'] = folder
        set_config(config)
        self.update_layouts_list()
        self.load_spots_configs()
    
    def end_worker(self):
        if self.active_worker:
            self.active_worker = False
            self.pbr.close()
            self.thread.quit()
            self.thread.wait()
            self.thread.deleteLater()
            self.set_active_ui(True)
            self.total = -1
    
    def update_pbr(self, text, current, total):
        self.pbr.set_description(text)
        if (total != self.total):
            self.pbr.reset(total=total)
            self.total = total
        self.pbr.update(current)

    def set_active_ui(self, status):
        self.clearLayersButton.setEnabled(status)
        self.workingDirButton.setEnabled(status)
        self.editLayoutButton.setEnabled(status)
        self.layoutComboBox.setEnabled(status)
        self.applyLayoutButton.setEnabled(status)
        self.slicesAroundFocus.setEnabled(status)
        self.createMIPButton.setEnabled(status)
        self.medianDiameter.setEnabled(status)
        self.segmentCellsButton.setEnabled(status)
        self.deathPercentage.setEnabled(status)
        self.segmentNucleiButton.setEnabled(status)
        self.hopcroftButton.setEnabled(status)
        self.segmentAllSpotsButton.setEnabled(status)
        self.deletionModeButton.setEnabled(status)
        self.fusionModeButton.setEnabled(status)
        self.exportMeasuresButton.setEnabled(status)
        for k, v in self.settings_widgets.items():
            if isinstance(v, QPushButton):
                v.setEnabled(status)
            elif isinstance(v, QComboBox):
                v.setEnabled(status)
            elif isinstance(v, QLineEdit):
                v.setEnabled(status)
        for tab in self.spots_tabs_widgets:
            for k, v in tab.items():
                if isinstance(v, QPushButton):
                    v.setEnabled(status)
                elif isinstance(v, QSlider):
                    v.setEnabled(status)
                elif isinstance(v, QSpinBox):
                    v.setEnabled(status)
                elif isinstance(v, QLineEdit):
                    v.setEnabled(status)
        for tab in range(self.spotsSettings.count()):
            self.spotsSettings.setTabEnabled(tab, status)
    
    # # # # # # # # # # # # #  METHODS  # # # # # # # # # # # # #

    def retrieve(self):
        self.update_layouts_list()
        self.load_last_layout()
    
    def load_last_layout(self):
        config = get_config()
        last_layout = config.get('last_layout', None)
        working_dir = config.get('working_directory', None)
        if last_layout is None or working_dir is None:
            return
        self.set_current_layout(last_layout)
    
    def set_current_layout(self, name):
        config = get_config()
        working_dir = config.get('working_directory', None)
        if working_dir is None:
            return
        path = os.path.join(working_dir, "layouts", f"{name}.json")
        if not os.path.isfile(path):
            return
        self.layoutComboBox.setCurrentText(name)
        config['last_layout'] = name
        set_config(config)
        with open(path, 'r') as f:
            self.channels_lt = json.load(f)

    def load_spots_configs(self):
        pass

    def mip_flatten(self):
        for layer in self.viewer.layers:
            img = layer.data
            if len(img.shape) != 3:
                continue
            _, t = layer.name.split('.')
            r = find_focused_slice(img, 0 if t == 'Brightfield' else int(self.slicesAroundFocus.value()))
            mip = np.max(img[r[0]:r[1]], axis=0)
            layer.data = mip



def justLaunchWidget():
    viewer = napari.Viewer()
    siyw = SpotsInYeastsWidget()
    viewer.window.add_dock_widget(siyw)
    print("--- Workflow: XXX ---")
    napari.run()


####################################################################################


if __name__ == "__main__":
    justLaunchWidget()
    print("DONE.")
