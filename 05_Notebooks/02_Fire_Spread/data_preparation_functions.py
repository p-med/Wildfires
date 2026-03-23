"""
CA Model Data Preparation Pipeline
Chaco Wildfire Spread Model - Paulo Medina
"""

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
import pandas as pd

# ============================================================================
# STEP 1: INGEST TOPOGRAPHY (MASTER GRID)
# ============================================================================
# This is your REFERENCE GRID - all other layers snap to this

def load_topography(srtm_path):
    """
    Load SRTM elevation (30m) as master grid template.
    Returns: elevation array, metadata (transform, CRS, shape)
    """
    with rasterio.open(srtm_path) as src:
        elevation = src.read(1)  # Read band 1
        meta = {
            'transform': src.transform,
            'crs': src.crs,
            'shape': elevation.shape,
            'nodata': src.nodata
        }
        
    # Handle nodata (if any)
    if meta['nodata'] is not None:
        elevation = np.where(elevation == meta['nodata'], np.nan, elevation)
    
    return elevation, meta

# ============================================================================
# STEP 2: DERIVE SLOPE AND ASPECT FROM ELEVATION
# ============================================================================
# These are CRITICAL for CA spread (ps factor in Rui model)

def calculate_slope_aspect(elevation, cell_size=30):
    """
    Calculate slope (degrees) and aspect (radians, 0=North, clockwise)
    
    Args:
        elevation: 2D array of elevation (meters)
        cell_size: Grid resolution in meters (default 30m for SRTM)
    
    Returns:
        slope: 2D array, slope in degrees
        aspect: 2D array, aspect in radians [0, 2π], 0=North
    """
    # Calculate gradients (dz/dx, dz/dy)
    dzdx = np.gradient(elevation, cell_size, axis=1)  # East-West
    dzdy = np.gradient(elevation, cell_size, axis=0)  # North-South
    
    # Slope in radians, then convert to degrees
    slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
    slope = np.degrees(slope_rad)
    
    # Aspect in radians [0, 2π], 0 = North, clockwise
    # Note: np.arctan2 gives [-π, π], so we convert to [0, 2π]
    aspect = np.arctan2(-dzdx, dzdy)  # Note the negative sign for dzdx
    aspect = np.where(aspect < 0, aspect + 2*np.pi, aspect)
    
    return slope, aspect

# ============================================================================
# STEP 3: INGEST LAND USE (MAPBIOMAS)
# ============================================================================

def load_land_use(land_use_path):
    """
    Load MapBiomas land use raster (30m native resolution)
    Returns: land_use array (integer codes)
    """
    with rasterio.open(land_use_path) as src:
        land_use = src.read(1).astype(np.int16)
        lu_meta = {
            'transform': src.transform,
            'crs': src.crs,
            'shape': land_use.shape
        }
    
    return land_use, lu_meta

# ============================================================================
# STEP 4: SNAP LAND USE TO TOPOGRAPHY GRID (IF NEEDED)
# ============================================================================
# Only needed if grids don't already align

def snap_to_master_grid(array, src_transform, src_crs, 
                        dst_transform, dst_crs, dst_shape,
                        resampling_method=Resampling.nearest):
    """
    Reproject array to match master grid (elevation).
    
    Args:
        array: 2D array to reproject
        src_transform, src_crs: Source raster metadata
        dst_transform, dst_crs, dst_shape: Destination (master) grid metadata
        resampling_method: Resampling.nearest for categorical, 
                          Resampling.bilinear for continuous
    
    Returns:
        reprojected: Array aligned to master grid
    """
    # Create destination array
    reprojected = np.empty(dst_shape, dtype=array.dtype)
    
    # Reproject
    reproject(
        source=array,
        destination=reprojected,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=resampling_method
    )
    
    return reprojected

# ============================================================================
# STEP 5: MAP LAND USE TO FUEL TYPES (Ks VALUES)
# ============================================================================

# MapBiomas → Fuel Type mapping (from your earlier dictionary)
MAPBIOMAS_TO_FUEL_TYPE = {
    # Fuel Type 1: Forest (Ks = 0.04)
    1: 1, 2: 1, 3: 1, 6: 1, 9: 1,
    # Fuel Type 2: Savanna (Ks = 0.96)
    4: 2, 45: 2, 49: 2,
    # Fuel Type 3: Grassland (Ks = 1.0)
    12: 3, 42: 3, 43: 3, 44: 3, 50: 3,
    # Fuel Type 4: Cropland (Ks = 0.6)
    14: 4, 15: 4, 18: 4, 19: 4, 20: 4, 21: 4, 
    35: 4, 36: 4, 39: 4, 40: 4, 41: 4, 46: 4, 
    47: 4, 48: 4, 57: 4, 58: 4, 62: 4,
    # Fuel Type 5: Non-combustible (Ks = 0.0)
    5: 5, 10: 5, 11: 5, 13: 5, 22: 5, 23: 5, 24: 5, 
    25: 5, 26: 5, 27: 5, 29: 5, 30: 5, 31: 5, 32: 5, 
    33: 5, 34: 5, 37: 5, 38: 5, 61: 5, 63: 5, 68: 5, 0: 5
}

FUEL_TYPE_TO_KS = {
    1: 0.04,  # Forest
    2: 0.96,  # Savanna/Cerrado
    3: 1.00,  # Grassland (reference)
    4: 0.60,  # Cropland (estimated)
    5: 0.00   # Non-combustible
}

def mapbiomas_to_fuel_array(land_use):
    """
    Convert MapBiomas codes to fuel types and Ks values.
    
    Args:
        land_use: 2D array of MapBiomas integer codes
    
    Returns:
        fuel_type: 2D array of fuel type IDs (1-5)
        Ks: 2D array of fuel coefficients (0.0-1.0)
    """
    # Initialize arrays
    fuel_type = np.zeros_like(land_use, dtype=np.int8)
    Ks = np.zeros_like(land_use, dtype=np.float32)
    
    # Vectorized mapping
    for mapbiomas_code, fuel_id in MAPBIOMAS_TO_FUEL_TYPE.items():
        mask = (land_use == mapbiomas_code)
        fuel_type[mask] = fuel_id
        Ks[mask] = FUEL_TYPE_TO_KS[fuel_id]
    
    return fuel_type, Ks

# ============================================================================
# STEP 6: INGEST WEATHER TIME SERIES (ERA5)
# ============================================================================

def load_weather_timeseries(weather_csv_path):
    """
    Load ERA5 weather data for fire event.
    
    Expected columns from your Notebook 2:
    - time (datetime)
    - temperature_c
    - relative_humidity
    - wind_speed (m/s)
    - wind_direction (radians, 0=North, clockwise)
    
    Returns: DataFrame with hourly weather
    """
    weather = pd.read_csv(weather_csv_path, parse_dates=['timestamp'])
    
    # Ensure required columns exist
    required_cols = ['timestamp', 'temperature_c', 'relative_humidity', 
                    'wind_speed', 'wind_direction']
    missing = set(required_cols) - set(weather.columns)
    if missing:
        raise ValueError(f"Missing columns in weather CSV: {missing}")
    
    # Sort by time
    weather = weather.sort_values('timestamp').reset_index(drop=True)
    
    return weather

# ============================================================================
# STEP 7: CREATE IGNITION RASTER FROM CLUSTER EARLIEST POINT
# ============================================================================

def create_ignition_raster(fire_points_gdf, cluster_id, 
                          master_transform, master_shape):
    """
    Create binary ignition raster from earliest fire point in cluster.
    
    Args:
        fire_points_gdf: GeoDataFrame with fire points (from FIRMS)
                        Must have: CLUSTER_ID, ACQ_DATE, geometry columns
        cluster_id: Which cluster to use
        master_transform: Affine transform from master grid
        master_shape: (rows, cols) of master grid
    
    Returns:
        ignition_raster: 2D binary array (1 = ignition cell, 0 = no ignition)
        ignition_time: datetime of ignition
    """
    # Filter to cluster
    cluster_points = fire_points_gdf[
        fire_points_gdf['CLUSTER_ID'] == cluster_id
    ].copy()
    
    # Find earliest point
    cluster_points = cluster_points.sort_values('ACQ_DATE')
    earliest_point = cluster_points.iloc[0]
    
    ignition_time = earliest_point['ACQ_DATE']
    ignition_geom = earliest_point['geometry']
    
    # Get coordinates
    x, y = ignition_geom.x, ignition_geom.y
    
    # Convert geographic coordinates to array indices
    # Using inverse of affine transform
    col, row = ~master_transform * (x, y)
    row, col = int(row), int(col)
    
    # Create binary raster
    ignition_raster = np.zeros(master_shape, dtype=np.uint8)
    
    # Check bounds
    if 0 <= row < master_shape[0] and 0 <= col < master_shape[1]:
        ignition_raster[row, col] = 1
    else:
        raise ValueError(
            f"Ignition point ({row}, {col}) outside raster bounds {master_shape}"
        )
    
    return ignition_raster, ignition_time

# ============================================================================
# STEP 8: PACKAGE ALL LAYERS INTO CA DATA STRUCTURE
# ============================================================================

def prepare_ca_inputs(event_id, srtm_path, land_use_path, 
                     weather_csv_path, fire_points_gdf):
    """
    Master function to prepare all CA model inputs.
    
    Returns:
        ca_data: Dictionary with all required arrays and metadata
    """
    print(f"Preparing CA inputs for event {event_id}...")
    
    # 1. Load topography (master grid)
    print("  Loading elevation...")
    elevation, master_meta = load_topography(srtm_path)
    
    # 2. Derive slope and aspect
    print("  Calculating slope and aspect...")
    slope, aspect = calculate_slope_aspect(elevation, cell_size=30)
    
    # 3. Load land use
    print("  Loading land use...")
    land_use, lu_meta = load_land_use(land_use_path)
    
    # 4. Snap land use to master grid (if needed)
    if (lu_meta['transform'] != master_meta['transform'] or 
        lu_meta['shape'] != master_meta['shape']):
        print("  Snapping land use to elevation grid...")
        land_use = snap_to_master_grid(
            land_use, 
            lu_meta['transform'], lu_meta['crs'],
            master_meta['transform'], master_meta['crs'], master_meta['shape'],
            resampling_method=Resampling.nearest  # Categorical data
        )
    
    # 5. Map to fuel types
    print("  Mapping to fuel types...")
    fuel_type, Ks = mapbiomas_to_fuel_array(land_use)
    
    # 6. Load weather
    print("  Loading weather time series...")
    weather = load_weather_timeseries(weather_csv_path)
    
    # 7. Create ignition raster
    print("  Creating ignition raster...")
    ignition, ignition_time = create_ignition_raster(
        fire_points_gdf, event_id,
        master_meta['transform'], master_meta['shape']
    )
    
    # Package everything
    ca_data = {
        # Spatial grids (all aligned to master grid)
        'elevation': elevation,
        'slope': slope,          # degrees
        'aspect': aspect,        # radians, 0=North
        'fuel_type': fuel_type,  # integer 1-5
        'Ks': Ks,               # float 0.0-1.0
        'ignition': ignition,    # binary 0/1
        
        # Time series
        'weather': weather,      # DataFrame
        'ignition_time': ignition_time,  # datetime
        
        # Grid metadata
        'transform': master_meta['transform'],
        'crs': master_meta['crs'],
        'shape': master_meta['shape'],
        'cell_size': 30  # meters
    }
    
    print(f"  Grid shape: {ca_data['shape']}")
    print(f"  Grid CRS: {ca_data['crs']}")
    print(f"  Ignition time: {ignition_time}")
    print("Done.")
    
    return ca_data