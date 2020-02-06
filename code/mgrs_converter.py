def lat_lon_boundary(cls, mgrs_index):
    """
    Public:
        Class method to convert mgrs index into bounding box coordinates
    Args:
        mgrs_index: Tile index for the granule file based on MGRS
    Returns:
        [left_lon, top_lat, right_lon, bottom_lat]
    """
    column = int(mgrs_index[:-1])
    row = ord(mgrs_index[-1]) - 65
    unwrapped_col = column * 6
    lons = [unwrapped_col - 186, unwrapped_col - 180]
    lats = [-90, -80]
    if row <= 1:
        lons = sorted([180 * ((-1) ** (row + 1)), 0])
    elif row >= 24:
        lats = [84, 90]
        lons = sorted([180 * ((-1) ** (row - 23)), 0])
    elif row == 23:
        lats = [72, 84]
        if column == 31:
            lons = [0, 9]
        elif column == 33:
            lons = [9, 21]
        elif column == 35:
            lons = [21, 33]
    elif row == 22:
        lats = [64, 72]
    elif row == 21:
        lats = [56, 64]
        if column == 31 or column == 32:
            index = abs(column - 32)
            lons[index] = lons[index] - 3
    elif row <= 8:
        unwrapped_row = (row - 2) * 8
        lats = [unwrapped_row - 80, unwrapped_row - 72]
    elif row >= 9 and row < 15:
        unwrapped_row = (row - 3) * 8
        lats = [unwrapped_row - 80, unwrapped_row - 72]
    elif row >= 15:
        unwrapped_row = (row - 4) * 8
        lats = [unwrapped_row - 80, unwrapped_row - 72]
    return [lons[0], lats[0], lons[1], lats[1]]


