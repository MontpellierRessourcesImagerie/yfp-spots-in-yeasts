// @File(label="Select a directory", style="directory") input_dir
// @File(label="Select a directory", style="directory") output_dir
// @String(label="Provide order", description="Give the order in which channels are in the original image.") order
// @String(label="Suffixes", description="Give the suffix of each channel in the right order.") suffixes

/*
 * 
 *        Notes: 
 *    
 * - The `order` parameter is used only for aggregated file formats (like .czi) in which all channels are already bundled in one file.
 * - The `suffixes` parameter is exclusively used for scattered file formats (like .nd) in which all channels are in an individual file.
 * 
 */

function main() {
	if (File.isDirectory(output_dir)) {
		print("Output directory doesn't exist...");
		return 1;
	}
	
	files_list = getFileList(input_dir);
	
	for (i = 0 ; i < files_list.length ; i++) {
		original_name = files_list[i];
		lowered_name  = toLowerCase(original_name);
		
	    if (endsWith(lowered_name, ".czi")) { 
	        
	    }
	    else if (endsWith(lowered_name, ".nd")) {
	    	
	    }
	    else {
	    	print("Format of `" + original_name + "` not handled");
	    }
	}
	
	return 0;
}


function joinPath(directory, leaf) {
	if (endsWith(directory, File.separator)) { return directory + leaf; }
	else { return directory + File.separator + leaf; }
}






