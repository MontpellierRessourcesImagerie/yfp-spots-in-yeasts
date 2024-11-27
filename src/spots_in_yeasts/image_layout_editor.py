from qtpy.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QApplication, QMainWindow, 
                            QHeaderView, QTableWidget, QComboBox, 
                            QColorDialog, QLineEdit)

from PyQt5.QtGui import QColor, QFont
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal

import json
import os
import re

from spots_in_yeasts.utils import get_config, set_config

from napari.utils.notifications import show_info

_COLUMNS = ['Channel name', 'LUT', 'Type', 'Move']
_COLORS  = ['gray', 'red', 'green', 'blue', 'magenta', 'yellow', 'cyan']
VALID_FILENAME_REGEX = re.compile(r'^[a-zA-Z0-9\-_\@\#\$\%\^\&\(\)\{\}\[\]\~\!]+$')

class ImageLayoutEditor(QMainWindow):

    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Channels Layout Editor")
        self.font = QFont()
        self.font.setFamily("Arial Unicode MS, Segoe UI Emoji, Apple Color Emoji, Noto Color Emoji")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.init_ui()

    def init_ui(self):
        # Central widget
        centralWidget = QWidget(self)
        self.setCentralWidget(centralWidget)
        self.layout = QVBoxLayout(centralWidget)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.layout.addWidget(self.table)

        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)  # Make "Name" stretchable
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Adjust to content
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Adjust to content
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Adjust to content

        # Buttons layout
        buttonsLayout = QHBoxLayout()

        # Add Row Button
        self.addRowButton = QPushButton('➕ Add channel')
        self.addRowButton.setFont(self.font)
        self.addRowButton.clicked.connect(self.add_row)
        buttonsLayout.addWidget(self.addRowButton)

        # Remove Row Button
        self.removeRowButton = QPushButton('➖ Remove channel')
        self.removeRowButton.setFont(self.font)
        self.removeRowButton.clicked.connect(self.remove_row)
        buttonsLayout.addWidget(self.removeRowButton)

        self.layout.addLayout(buttonsLayout)

        # Saving layout
        savingLayout = QHBoxLayout()

        # Saving name input
        self.savingNameInput = QLineEdit()
        self.savingNameInput.setPlaceholderText("Layout name")
        self.savingNameInput.textEdited.connect(self.on_saving_name_change)
        savingLayout.addWidget(self.savingNameInput)

        # Export Button
        self.exportButton = QPushButton('💾 Save layout')
        self.exportButton.setFont(self.font)
        self.exportButton.clicked.connect(self.export_layout_callback)
        savingLayout.addWidget(self.exportButton)

        self.layout.addLayout(savingLayout)

    def closeEvent(self, event):
        super().closeEvent(event)

    def init_working_directory(self):
        config = get_config()
        working_directory = config.get('working_directory', None)
        if working_directory is None:
            return False
        path = os.path.join(working_directory, "layouts")
        os.makedirs(path, exist_ok=True)
        return True

    def is_name_valid(self, candidate):
        if candidate is None:
            return False
        return bool(VALID_FILENAME_REGEX.fullmatch(candidate))

    def on_saving_name_change(self):
        config = get_config()
        working_directory = config.get('working_directory', None)
        candidate = self.savingNameInput.text()
        color = "#ffffff00" # Init transparent
        if self.is_name_valid(candidate):
            color = '#4dff7c' # Green if the name is valid
            if working_directory is not None and os.path.isdir(working_directory):
                path = os.path.join(working_directory, "layouts", f"{candidate}.json")
                if os.path.isfile(path):
                    color = '#ffe74d' # Turns to yellow if the file already exists
        else:
            color = '#ff4d4d' # Red if the name is invalid
        self.savingNameInput.setStyleSheet(f"background-color: {color}")
    
    def on_color_change(self, colorComboBox):
        colorComboBox.setStyleSheet(f"background-color: {colorComboBox.currentText()}")

    def add_row(self):
        rowPosition = self.table.rowCount()
        self.table.insertRow(rowPosition)

        # Name (String Input)
        nameItem = QLineEdit()
        self.table.setCellWidget(rowPosition, 0, nameItem)

        # Color (Color Picker Button)
        colorComboBox = QComboBox()
        for color in _COLORS:
            colorComboBox.addItem(color)
            colorComboBox.setItemData(colorComboBox.count()-1, QColor(color), Qt.BackgroundRole)
        colorComboBox.currentIndexChanged.connect(lambda: self.on_color_change(colorComboBox))
        self.table.setCellWidget(rowPosition, 1, colorComboBox)

        # Type (Drop-down Menu)
        typeComboBox = QComboBox()
        typeComboBox.addItems(["---", "Brightfield", "Spots", "Nuclei"])
        self.table.setCellWidget(rowPosition, 2, typeComboBox)

        # Move Up/Down Buttons
        moveButtonsWidget = QWidget()
        moveButtonsLayout = QHBoxLayout(moveButtonsWidget)
        moveButtonsLayout.setContentsMargins(0, 0, 0, 0)

        moveUpButton = QPushButton('⬆️')
        moveUpButton.clicked.connect(lambda: self.move_row_up(rowPosition))
        moveButtonsLayout.addWidget(moveUpButton)

        moveDownButton = QPushButton('⬇️')
        moveDownButton.clicked.connect(lambda: self.move_row_down(rowPosition))
        moveButtonsLayout.addWidget(moveDownButton)

        self.table.setCellWidget(rowPosition, 3, moveButtonsWidget)
    
    def move_row_up(self, row):
        self.swap_rows(row, max(row - 1, 0))

    def move_row_down(self, row):
        self.swap_rows(row, min(row + 1, self.table.rowCount() - 1))

    def swap_rows(self, row1, row2):
        if row1 == row2:
            return
        src_name = self.table.cellWidget(row1, 0).text()
        src_color = self.table.cellWidget(row1, 1).text()
        src_type = self.table.cellWidget(row1, 2).currentText()
        self.table.cellWidget(row1, 0).setText(self.table.cellWidget(row2, 0).text())
        self.table.cellWidget(row1, 1).setText(self.table.cellWidget(row2, 1).text())
        self.table.cellWidget(row1, 1).setStyleSheet(f"background-color: {self.table.cellWidget(row2, 1).text()}")
        self.table.cellWidget(row1, 2).setCurrentText(self.table.cellWidget(row2, 2).currentText())
        self.table.cellWidget(row2, 0).setText(src_name)
        self.table.cellWidget(row2, 1).setText(src_color)
        self.table.cellWidget(row2, 1).setStyleSheet(f"background-color: {src_color}")
        self.table.cellWidget(row2, 2).setCurrentText(src_type)

    def remove_row(self):
        currentRow = self.table.currentRow()
        if currentRow >= 0:
            self.table.removeRow(currentRow)

    def choose_color(self, row):
        color = QColorDialog.getColor()
        if color.isValid():
            colorButton = self.table.cellWidget(row, 1)
            colorButton.setStyleSheet(f"background-color: {color.name()}")
            colorButton.setText(color.name())

    def export_layout_callback(self):
        if not self.is_name_valid(self.savingNameInput.text()):
            show_info("Invalid name")
            return
        config = get_config()
        working_directory = config.get('working_directory', None)
        if (working_directory is None) or (not os.path.isdir(working_directory)):
            show_info("Invalid working directory")
            return
        self.export_layout()
    
    def table_to_list(self):
        layout = []
        for row in range(self.table.rowCount()):
            name = self.table.cellWidget(row, 0).text()
            if len(name) == 0:
                return (None, "Name cannot be empty")
            color = self.table.cellWidget(row, 1).currentText()
            type = self.table.cellWidget(row, 2).currentText()
            layout.append({
                'name' : name,
                'color': color,
                'type' : type
            })
        return layout, ""
    
    def export_layout(self):
        data, status = self.table_to_list()
        if not self.init_working_directory():
            show_info("Invalid working directory")
            return
        if data is None:
            show_info(status)
            return
        config = get_config()
        working_directory = config.get('working_directory', None)
        path = os.path.join(working_directory, "layouts", f"{self.savingNameInput.text()}.json")
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)
        show_info(f"Layout saved as {self.savingNameInput.text()}")


if __name__ == '__main__':
    app = QApplication([])
    window = ImageLayoutEditor()
    window.show()
    app.exec_()