==========================================
Conform your data
==========================================

:code:`Spots in yeasts` expects a very precise file as its input:

* The file must be a TIFF (no .czi, .nd, ...)
* Both channels must be packed in this TIFF.
* The first channel must contain the spots and the second the brightfield.
* The number of slices is arbitrary.

If your images don't have this form, we provide you with a Fiji/ImageJ plugin that can achieve the conversion. To use it, just proceed as follow:

Install the macro 
------------------------------------------

1. Start by opening Fiji.
2. In the menu bar, go in :code:`File` → :code:`New` → :code:`Text Window`.
3. In the new window that just appeared, click on the :code:`Language` button in the menu bar, and choose :code:`Python`.
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
      
   # # # At this point, the folder shoud exist and be empty # # #

   files = [
      "siy-convert-format.py"
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

   print("DONE.")

5. Below the text area in the window, you can click the :code:`Run` button.
6. You can now close Fiji without saving anything, the macro is installed.


Use the macro 
------------------------------------------

1. Launch Fiji/ImageJ
2. In the search area (lower-right of Fiji's window), start typing :code:`siy-convert-format` until the macro shows up.
3. Launch the macro.
4. Launching the macro should open a new window, divided in three sections: I/O, Data and Order.
5. In the I/O section, select your input folder (the folder containing your original images with the inproper format) and your output folder (an empty folder that will receive the converted images).
6. In the Data section, fill the extension used by your images **with the dot** (ex: .czi, .nd)
7. In the Order section, fill the order in which your channels are when you open an image. If you don't have one of the proposed channels (like the nuclei marking for example), leave the field empty (with a "-").
8. Verify a last time your settings and click on the "Launch conversion!" button.

Video tutorial 
------------------------------------------

.. raw:: html

   <iframe width="560" height="315" src="https://www.youtube.com/embed/LqbifHUVYpw" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>