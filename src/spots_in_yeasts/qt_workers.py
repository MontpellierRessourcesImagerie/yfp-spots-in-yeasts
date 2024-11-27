from qtpy.QtCore import QObject
from PyQt5.QtCore import pyqtSignal

class QtSegmentCells(QObject):
    
    finished = pyqtSignal()
    update   = pyqtSignal(str, int, int)

    def __init__(self, pbr, siy):
        super().__init__()
        self.pbr = pbr
        self.siy = siy

    def run(self):
        self.siy.segment_cells()
        self.finished.emit()