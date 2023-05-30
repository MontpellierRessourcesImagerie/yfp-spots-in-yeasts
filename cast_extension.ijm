
// Settings asked to user:
// var sourceFolder = "/home/benedetti/Documents/projects/10-spots-in-yeasts/testing-set-4/d1";
// var destFolder   = "/home/benedetti/Documents/projects/10-spots-in-yeasts/testing-set-4/d1-test";

#@ File (label = "Input directory", style = "directory") sourceFolder
#@ File (label = "Output directory", style = "directory") destFolder
#@ Boolean (label = "Go batch") go_batch

var extensions   = newArray(".nd", ".czi");

function collectSettings() {
	sourceFolder = getDirectory("Choose the source directory");
	destFolder   = getDirectory("Choose the destination directory");
}

function main() {
	if (go_batch) { setBatchMode(true);	}
	
	// Extraction of working data and formatting settings:
	content      = getFileList(sourceFolder);
	sourceFolder = replace(sourceFolder, "\\", "/");
	destFolder   = replace(destFolder, "\\", "/");
	
	// Filtering + export as ".tif":
	for (i = 0 ; i < content.length ; i++) {
		currentFile = content[i];
		known       = false;
		rawName     = "";
		for (j = 0 ; j < extensions.length ; j++) {
			currentExt = extensions[j];
			if (currentFile.endsWith(currentExt)) {
				print("Processing: "+currentFile);
				known = true;
				rawName = replace(currentFile, currentExt, "");
				break;
			}
		}
		if (!known) { continue; }
		full_path = joinPath(sourceFolder, currentFile);
		// open(full_path);
		run("Bio-Formats Importer", "open=[" + full_path +"] color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT");
		imIn = getImageID();
		export_path = joinPath(destFolder, rawName+".tif");
		saveAs("tif", export_path);
		close();
	}
	print("DONE.");
	setBatchMode("exit and display");
}


function joinPath(root, leaf) {
	if (root.endsWith("/")) {
		return root + leaf;
	}
	return root + "/" + leaf;
}


main();
