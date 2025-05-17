def write_concat_list(files, list_name):
    """
    Writes a list of files to a text file in the format required by FFmpeg's concat demuxer.
    
    Parameters:
    - files: List of file paths
    - list_name: Output text file path
    """
    with open(list_name, "w") as f:
        for p in files:
            f.write(f"file '{p}'\n") 