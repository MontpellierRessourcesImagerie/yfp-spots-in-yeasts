==========================================
Conform your data
==========================================

`Spots in yeasts` expects a very precise file as its input:
* The file must be a TIFF (no .czi, .nd, ...)
* Both channels must be packed in this TIFF.
* The first channel must contain the spots and the second the brightfield.
* The number of slices is arbitrary.

If your images don't have this form, we provide you with a Fiji/ImageJ plugin that can achieve the conversion.

Install the macro
------------------------------------------

1. Start by opening Fiji.
2. In the menu bar, go in `File` → `New` → `Text Window`.
3. In the new window that just appeared, click on the `Language` button in the menu bar, and search choose `Python`.
4. Copy the following code, and paste it in your code window.

.. code:: python

   from ij import IJ, Menus
   import os
   import urllib2
   import sys

   def empty_folder(folder_path):
       for f in os.listdir(folder_path):
           file_path = os.path.join(folder_path, f)
           if os.path.isfile(file_path):
               os.remove(file_path)
           elif os.path.isdir(file_path):
               empty_folder(file_path)
               os.rmdir(file_path)

   plugins_folder = IJ.getDirectory("plugins")
   convert_folder = os.path.join(plugins_folder, "siy-data-cast")

   if os.path.isdir(convert_folder):
       empty_folder(convert_folder)
   else:
       os.mkdir(convert_folder)
       
   files = [
       "convert-format.py",
       "convert_format.ijm"
   ]

   base_url = "https://raw.githubusercontent.com/MontpellierRessourcesImagerie/spots-in-yeasts/master/src/spots_in_yeasts/"

   for name in files:
       fullPath = os.path.join(convert_folder, name)
       fullURL  = base_url + name
       try:
           with open(fullPath,'wb') as fi:
               fi.write(urllib2.urlopen(fullURL).read())
               fi.close()
       except:
           print("Failed to download " + name)
       else:
           print("Downloaded " + name + " successfully.")