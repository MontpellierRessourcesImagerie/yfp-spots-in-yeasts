
def seek_channels(root_dir, channels):
    """
    This function is useful only if the machine that produced the images doesn't provide the user with multi-channel images.
    In this case, each channel is in its own image, with some suffix to indicate the channel.
    If your machine creates a multi-channels image, you don't need this function.

    Args:
        root_dir: The absolute path of a folder containing images.
        channels: A list of tuples. Each tuple is of size 2. The first element is the name of what the channel represents (brightfield, spots, ...) and the second is the suffix used to represent this channel (_w2yfp.tif, _w1bf.tif, ...).
    
    Returns:
        A list of dictionary. Each dict has the same size and keys, which are the names provided in the tuples. Each key points of the associated file.
        Ex: If in the parameters you provided channels=[('brightfield', "_w2bf.tif"), ('spots', "_w1yfp.tif")], you will get a result like:
        [
            {
                'brightfield': "some_file_w2bf.tif",
                'spots'      : "some_file_w1yfp.tif"
            },
            {
                'brightfield': "other_file_w2bf.tif",
                'spots'      : "other_file_w1yfp.tif"
            }
        ]
    """
    # Safety check. Do we actually have the path of a folder?
    if not os.path.isdir(root_dir):
        print(f"`{root_dir}` is not the path of a folder.")
        return []
    
    # Make a list of all the .nd files that are not hidden
    headers = [c for c in os.listdir(root_dir) if (c.endswith(".nd")) and (not c.startswith('.')) and os.path.isfile(os.path.join(root_dir, c))]
    images  = []

    for header in headers:
        raw_title = header.replace(".nd", "")
        item      = {
            'header' : header,
            'control': raw_title + "_control.tif",
            'raw'    : raw_title,
            'metrics': raw_title + "_measures.json"
        }
        baselen = len(item)

        for channel, suffix in channels:
            item[channel] = raw_title + suffix
        
        if len(item) != len(channels)+baselen:
            print(f"Images associated with `{header}` couldn't be retreived.")
            continue

        images.append(item)

    print(f"{len(images)} full images were detected:")
    for item in images:
        print(f"  - {item['header']}")
    print("")

    return images