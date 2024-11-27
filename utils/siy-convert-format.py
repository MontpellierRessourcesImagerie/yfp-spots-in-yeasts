from javax.swing import JFrame, JPanel, JButton, JComboBox, JLabel, BoxLayout, Box, JTextField
from javax.swing.border import EmptyBorder
from java.awt import GridLayout, Dimension, Font, Color, FlowLayout, BorderLayout
from java.awt.event import ActionListener
from javax.swing.filechooser import FileNameExtensionFilter
from javax.swing import JFileChooser
from java.lang import RuntimeException
import os
from ij import IJ
from ij.plugin import ChannelSplitter, Commands, RGBStackMerge
from ij.macro import Interpreter

# =========== Target output ===========
#
# Order: spots, bf, nuclei
# File format: Aggregated ".tif"
#
# =====================================

_desired_order_ = ['Spots', 'Brightfield', 'Nuclei']

def remap_indices(provided_order):
    """
    Function taking the provided order and tells where each channel of the original order must go to get the desired order.

    Returns:
        A list of indices.
        Example: If the returned list is [2, 0, 1], it means that in the provided images, the first channel will become the third, the second will become the first and the third will become the second.
    """
    remaped = []
    for compo in provided_order:
        if compo == "-":
            break
        try:
            idx = _desired_order_.index(compo)
        except:
            continue
        else:
            remaped.append(idx)
    
    if len(remaped) < 2:
        print("An error has occured. At least brightfield and spots are required.")
        return None
    
    return remaped


def aggregated_to_tif(order, path, output_dir, name):
    IJ.run("Bio-Formats Importer", "open=[" + path +"] color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT")
    img = IJ.getImage()
    channels = ChannelSplitter.split(img)
    img.close()
    zipped = zip(order, channels)
    sorted_pairs = sorted(zipped)
    elements_rearranges = [element for index, element in sorted_pairs]
    new_img = RGBStackMerge.mergeChannels(elements_rearranges, False)
    export_path = os.path.join(output_dir, name)
    IJ.save(new_img, export_path)
    new_img.close()


def convert_name(original, extension):
    return original.lower().replace(extension.lower(), ".tif").replace(" ", "-")


class ImageConverter(ActionListener):
    def __init__(self):
        # Path to the input directory.
        self.input_dir  = ""
        # Path to the output directory.
        self.output_dir = ""
        # Order in which the channels are.
        self.order      = []
        # Image's format represented by extension. It must start with a "." (".tiff", ".czi", ".nd", ...)
        self.format     = "."
        # List of files to be processed.
        self.queue      = []
        
        # # # # # # # # # # # # # # # # # # # # #

        # Text field collecting the extension.
        self.ext = None
        # Dropdown menus collecting the order of channels.
        self.c1_dropdown = None
        self.c2_dropdown = None
        self.c3_dropdown = None

        # # # # # # # # # # # # # # # # # # # # #

        # Frame containing the menu
        self.frame = JFrame("Image format converter")
        self.frame.setDefaultCloseOperation(JFrame.DISPOSE_ON_CLOSE)
        self.frame.setSize(300, 350)
        contentPanel = JPanel()
        contentPanel.setLayout(BoxLayout(contentPanel, BoxLayout.Y_AXIS))
        contentPanel.setBorder(EmptyBorder(10, 10, 30, 10))
        
        self.add_io_section(contentPanel)
        contentPanel.add(Box.Filler(Dimension(0,10), Dimension(0,10), Dimension(0,32767)))
        self.add_mode_section(contentPanel)
        contentPanel.add(Box.Filler(Dimension(0,10), Dimension(0,10), Dimension(0,32767)))
        self.add_order_section(contentPanel)
        contentPanel.add(Box.Filler(Dimension(0,10), Dimension(0,10), Dimension(0,32767)))
        self.frame.add(contentPanel)
        
        ok_button = JButton('Launch conversion!', actionPerformed=self.ok_clicked)
        self.frame.getContentPane().add(ok_button, BorderLayout.SOUTH)
        self.frame.setVisible(True)
    

    def launch_conversion(self):
        e = self.format.lower()
        self.queue = [str(f) for f in os.listdir(self.input_dir) if f.lower().endswith(e)]
        Commands.closeAll()
        Interpreter.batchMode = True

        remaped = remap_indices(self.order)
        for q in self.queue:
            IJ.log("Processing image: " + q)
            aggregated_to_tif(
                remaped,
                os.path.join(self.input_dir, q),
                self.output_dir,
                convert_name(q, self.format)
            )
        IJ.log("DONE.")

        Interpreter.batchMode = False


    def ok_clicked(self, event):
        # Closing menu
        self.frame.dispose()

        # Acquiring I/O elements
        print("Input directory: "  + self.input_dir)
        print("Output directory: " + self.output_dir)

        self.format = str(self.ext.getText())
        print("Files with extension '" + self.format + "' will be converted.")

        # Acquiring order elements
        self.order = [
            str(self.c1_dropdown.getSelectedItem()),
            str(self.c2_dropdown.getSelectedItem()),
            str(self.c3_dropdown.getSelectedItem())
        ]
        print("Input order : " + str(self.order))
        print("Target order: " + str(_desired_order_))

        if not self.validate_settings():
            raise RuntimeException("Invalid settings detected. Check console for more details.")
        
        self.launch_conversion()


    def validate_settings(self):
        # Check that both directories exist
        if not os.path.isdir(self.input_dir):
            print("`" + self.input_dir + "` is not a valid input directory.")
            return False
        
        if not os.path.isdir(self.output_dir):
            print("`" + self.output_dir + "` is not a valid output directory")
            return False
        
        # Check that extension starts with a dot.
        if not self.format.startswith("."):
            print("An extension should start with a '.'")
            return False

        # Check that there is no duplicate in the provided order.
        s = set(self.order)
        if len(s) != len(self.order):
            print("There should not be any duplicate in the provided order. Found: " + str(self.order))
            return False
        
        # Check that the first hyphen marks the end of the order.
        found = False
        for element in self.order:
            found = found or (element == "-")
            if not found:
                continue
            if element != "-":
                print("There should not be any element following the first hyphen in the order. Found: " + str(self.order))
                return False

        return True


    def add_io_section(self, contentPanel):
        io_label = JLabel("---------- I/O ----------")
        io_label.setFont(Font("Sans-Serif", Font.BOLD, 18)) # Change font size and style
        titlePanel = JPanel(FlowLayout(FlowLayout.CENTER))
        titlePanel.add(io_label)
        contentPanel.add(titlePanel)

        panel = JPanel()
        panel.setLayout(GridLayout(2, 2))

        # Input directory
        input_dir_button = JButton('Input Directory', actionPerformed=self.choose_input_dir)
        panel.add(JLabel("Input Directory:"))
        panel.add(input_dir_button)

        # Output directory
        output_dir_button = JButton('Output Directory', actionPerformed=self.choose_output_dir)
        panel.add(JLabel("Output Directory:"))
        panel.add(output_dir_button)

        contentPanel.add(panel)

    
    def add_order_section(self, contentPanel):
        order_label = JLabel("---------- Order ----------")
        order_label.setFont(Font("Sans-Serif", Font.BOLD, 18)) # Change font size and style
        titlePanel = JPanel(FlowLayout(FlowLayout.CENTER))
        titlePanel.add(order_label)
        contentPanel.add(titlePanel)

        panel = JPanel()
        panel.setLayout(GridLayout(2, 3))

        panel.add(JLabel("C1"))
        panel.add(JLabel("C2"))
        panel.add(JLabel("C3"))

        self.c1_dropdown = JComboBox(["-", "Brightfield", "Spots", "Nuclei"])
        self.c2_dropdown = JComboBox(["-", "Brightfield", "Spots", "Nuclei"])
        self.c3_dropdown = JComboBox(["-", "Brightfield", "Spots", "Nuclei"])

        panel.add(self.c1_dropdown)
        panel.add(self.c2_dropdown)
        panel.add(self.c3_dropdown)

        contentPanel.add(panel)

    
    def add_mode_section(self, contentPanel):
        order_label = JLabel("---------- Data ----------")
        order_label.setFont(Font("Sans-Serif", Font.BOLD, 18)) # Change font size and style
        titlePanel = JPanel(FlowLayout(FlowLayout.CENTER))
        titlePanel.add(order_label)
        contentPanel.add(titlePanel)

        panel = JPanel()
        panel.setLayout(GridLayout(1, 2))

        panel.add(JLabel("Extension:"))
        self.ext = JTextField(20)
        panel.add(self.ext)
        
        contentPanel.add(panel)
    

    def choose_input_dir(self, event):
        chooser = JFileChooser()
        chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY)
        returnVal = chooser.showOpenDialog(self.frame)
        if returnVal == JFileChooser.APPROVE_OPTION:
            self.input_dir = chooser.getSelectedFile().getAbsolutePath()


    def choose_output_dir(self, event):
        chooser = JFileChooser()
        chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY)
        returnVal = chooser.showOpenDialog(self.frame)
        if returnVal == JFileChooser.APPROVE_OPTION:
            self.output_dir = chooser.getSelectedFile().getAbsolutePath()


ImageConverter()
