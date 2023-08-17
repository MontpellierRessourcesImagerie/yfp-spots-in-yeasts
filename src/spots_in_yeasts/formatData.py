import os
import csv

class CSVtable(object):

    def __init__(self, ttls, d="-"):
        self.titles  = [str(t) for t in ttls]
        self.lines   = []
        self.default = d
    
    def getTitles(self):
        return self.titles

    def newRow(self):
        self.lines.append([self.default for i in range(len(self.titles))])
        return self

    def cancelRow(self):
        self.lines.pop()
        return self
    
    def _nameToIndex(self, name):
        n = str(name)
        for i, c in enumerate(self.titles):
            if c == n:
                return i

        return -1

    def setValue(self, col, val):
        idx = self._nameToIndex(col)
        if idx < 0:
            return self
        self.lines[-1][idx] = str(val)
        return self
    
    def exportTo(self, fullPath):
        with open(fullPath, 'w') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(self.titles)
            for row in self.lines:
                writer.writerow(row)


def get_header_1844():
    return [
        'source',
        'cell-index',
        'spot-index',
        'area',
        'intensity-mean',
        'intensity-min',
        'intensity-max',
        'intensity-sum',
        'perimeter',
        'solidity',
        'extent',
        '# spots'
    ]


def format_data_1844(data, source, table=None):
    csv_table = CSVtable(get_header_1844(), "") if (table is None) else table
    csv_table.newRow()
    csv_table.setValue('source', source)
    for cell_label, spots_data in data.items():
        csv_table.setValue('cell-index', cell_label)
        csv_table.setValue('# spots'   , len(spots_data))
        for spot_data in spots_data:
            csv_table.setValue('spot-index'    , spot_data['label'])
            csv_table.setValue('area'          , spot_data['area'])
            csv_table.setValue('intensity-mean', spot_data['intensity_mean'])
            csv_table.setValue('intensity-min' , spot_data['intensity_min'])
            csv_table.setValue('intensity-max' , spot_data['intensity_max'])
            csv_table.setValue('intensity-sum' , spot_data['intensity_sum'])
            csv_table.setValue('perimeter'     , spot_data['perimeter'])
            csv_table.setValue('solidity'      , spot_data['solidity'])
            csv_table.setValue('extent'        , spot_data['extent'])
            csv_table.newRow()
        if len(spots_data) == 0:
            csv_table.newRow()
    return csv_table


#########################################################################################


def get_header_1895():
    return [
        'source',
        'cell-index',
        '# cytoplasmic-spots',
        '# nuclear-spots',
        '# peripheral-spots'
    ]


def format_data_1895(data, source, table=None):
    csv_table = CSVtable(get_header_1895(), "") if (table is None) else table
    csv_table.newRow()
    csv_table.setValue('source', source)
    
    for cell_label, spots_data in data.items():
        csv_table.setValue('cell-index', cell_label)
        nuclear = 0
        cyto    = 0
        peri    = 0
        for spot_data in spots_data:
            if spot_data['category'] == 'NUCLEAR':
                nuclear += 1
            elif spot_data['category'] == 'PERIPHERAL':
                peri += 1
            else:
                cyto += 1
            
        csv_table.setValue('# cytoplasmic-spots', cyto)
        csv_table.setValue('# nuclear-spots', nuclear)
        csv_table.setValue('# peripheral-spots', peri)
        csv_table.newRow()

    return csv_table