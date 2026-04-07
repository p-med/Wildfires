"""
CA Model Data Preparation Pipeline - MEMORY-OPTIMIZED
Chaco Wildfire Spread Model - Paulo Medina

CHANGES:
- EARLY CLIPPING: Clips before slope calculation to avoid memory errors
- Added NaN/NoData handling in elevation loading
- Added NaN handling in slope/aspect calculation  
- Added debug_ignition_point() function
- Added export_raster() function for visualization
- Added data quality checks
"""

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin, Affine
import pandas as pd
import ee
from datetime import datetime, timedelta

# ============================================================================
# STEP 1: INGEST TOPOGRAPHY (MASTER GRID)
# ============================================================================

def load_topography(srtm_path):
    """
    Load SRTM elevation (30m) as master grid template.
    Handles NaN and NoData values properly.
    """
    with rasterio.open(srtm_path) as src:
        elevation = src.read(1)
        meta = {
            'transform': src.transform,
            'crs': src.crs,
            'shape': elevation.shape,
            'nodata': src.nodata
        }
    
    # Handle nodata
    if meta['nodata'] is not None:
        elevation = np.where(elevation == meta['nodata'], -9999, elevation)
    
    # Replace any NaN values
    elevation = np.nan_to_num(elevation, nan=-9999.0)
    
    print(f"  Elevation loaded: {elevation.shape}")
    print(f"  Valid cells: {np.sum(elevation != -9999)}")
    print(f"  NoData cells: {np.sum(elevation == -9999)}")
    print(f"  Elevation range: {np.min(elevation[elevation != -9999]):.1f} to {np.max(elevation[elevation != -9999]):.1f} m")
    
    return elevation, meta

# ============================================================================
# STEP 2: DERIVE SLOPE AND ASPECT FROM ELEVATION
# ============================================================================

def calculate_slope_aspect(elevation, cell_size=30):
    """
    Calculate slope (degrees) and aspect (radians, 0=North, clockwise)
    Handles NaN propagation and masks invalid areas.
    """
    # Create mask for valid data
    valid_mask = (elevation != -9999)
    
    # Calculate gradients (dz/dx, dz/dy)
    dzdx = np.gradient(elevation, cell_size, axis=1)  # East-West
    dzdy = np.gradient(elevation, cell_size, axis=0)  # North-South
    
    # Slope in radians, then convert to degrees
    slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
    slope = np.degrees(slope_rad)
    
    # Aspect in radians [0, 2π], 0 = North, clockwise
    aspect = np.arctan2(-dzdx, dzdy)
    aspect = np.where(aspect < 0, aspect + 2*np.pi, aspect)
    
    # Handle NaN values
    slope = np.nan_to_num(slope, nan=0.0)
    aspect = np.nan_to_num(aspect, nan=0.0)
    
    # Mask out invalid areas
    slope = np.where(valid_mask, slope, 0.0)
    aspect = np.where(valid_mask, aspect, 0.0)
    
    print(f"  Slope calculated: range {np.min(slope[valid_mask]):.1f} to {np.max(slope[valid_mask]):.1f} degrees")
    print(f"  Aspect calculated: range 0 to {np.max(aspect[valid_mask]):.2f} radians")
    
    return slope, aspect

# ============================================================================
# STEP 3: INGEST LAND USE (MAPBIOMAS)
# ============================================================================

def load_land_use(land_use_path):
    """Load MapBiomas land use raster (30m native resolution)."""
    with rasterio.open(land_use_path) as src:
        land_use = src.read(1).astype(np.int16)
        lu_meta = {
            'transform': src.transform,
            'crs': src.crs,
            'shape': land_use.shape
        }
    
    print(f"  Land use loaded: {land_use.shape}")
    print(f"  Unique classes: {len(np.unique(land_use))}")
    
    return land_use, lu_meta

# ============================================================================
# STEP 4: SNAP LAND USE TO TOPOGRAPHY GRID (IF NEEDED)
# ============================================================================

def snap_to_master_grid(array, src_transform, src_crs, 
                        dst_transform, dst_crs, dst_shape,
                        resampling_method=Resampling.nearest):
    """Reproject array to match master grid (elevation)."""
    reprojected = np.empty(dst_shape, dtype=array.dtype)
    
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

MAPBIOMAS_TO_FUEL_TYPE = {
    1: 1, 2: 1, 3: 1, 9: 1,
    4: 2, 45: 2, 49: 2, 6: 2,
    12: 3, 42: 3, 43: 3, 44: 3, 50: 3,
    14: 4, 15: 4, 18: 4, 19: 4, 20: 4, 21: 4, 
    35: 4, 36: 4, 39: 4, 40: 4, 41: 4, 46: 4, 
    47: 4, 48: 4, 57: 4, 58: 4, 62: 4,
    5: 5, 10: 5, 11: 5, 13: 5, 22: 5, 23: 5, 24: 5, 
    25: 5, 26: 5, 27: 5, 29: 5, 30: 5, 31: 5, 32: 5, 
    33: 5, 34: 5, 37: 5, 38: 5, 61: 5, 63: 5, 68: 5, 0: 5
}

FUEL_TYPE_TO_KS = {
    1: 0.40, # Test now
    2: 0.96,
    3: 1.00,
    4: 0.60,
    5: 0.00
}

def mapbiomas_to_fuel_array(land_use):
    """Convert MapBiomas codes to fuel types and Ks values."""
    fuel_type = np.zeros_like(land_use, dtype=np.int8)
    Ks = np.zeros_like(land_use, dtype=np.float32)
    
    for mapbiomas_code, fuel_id in MAPBIOMAS_TO_FUEL_TYPE.items():
        mask = (land_use == mapbiomas_code)
        fuel_type[mask] = fuel_id
        Ks[mask] = FUEL_TYPE_TO_KS[fuel_id]
    
    print(f"  Fuel type distribution:")
    for fuel_id in [1, 2, 3, 4, 5]:
        count = np.sum(fuel_type == fuel_id)
        pct = 100 * count / fuel_type.size
        ks_val = FUEL_TYPE_TO_KS[fuel_id]
        print(f"    Type {fuel_id} (Ks={ks_val:.2f}): {count:,} cells ({pct:.1f}%)")
    
    return fuel_type, Ks

# ============================================================================
# STEP 6: INGEST WEATHER TIME SERIES (ERA5)
# ============================================================================

def load_weather_timeseries(weather_csv_path):
    """Load ERA5 weather data for fire event."""
    weather = pd.read_csv(weather_csv_path, parse_dates=['timestamp'])
    
    required_cols = ['timestamp', 'temperature_c', 'relative_humidity', 
                    'wind_speed', 'wind_direction']
    missing = set(required_cols) - set(weather.columns)
    if missing:
        raise ValueError(f"Missing columns in weather CSV: {missing}")
    
    weather = weather.sort_values('timestamp').reset_index(drop=True)
    
    # Convert wind direction from degrees to radians if needed
    if weather['wind_direction'].max() > 2 * np.pi:
        print("  Converting wind direction from degrees to radians...")
        weather['wind_direction'] = np.radians(weather['wind_direction'])
        weather['wind_direction'] = weather['wind_direction'] % (2 * np.pi)
    
    print(f"  Weather data loaded: {len(weather)} time steps")
    print(f"  Time range: {weather['timestamp'].min()} to {weather['timestamp'].max()}")
    print(f"  Wind direction: {weather['wind_direction'].min():.3f} to {weather['wind_direction'].max():.3f} rad " +
          f"({np.degrees(weather['wind_direction'].min()):.1f}° to {np.degrees(weather['wind_direction'].max()):.1f}°)")
    
    return weather

# ============================================================================
# MAIN PREPARATION FUNCTION WITH EARLY CLIPPING
# ============================================================================

def prepare_ca_inputs(event_id, srtm_path, land_use_path, 
                     weather_csv_path, fire_points_gdf,
                     clip_to_fire=True, buffer_km=10):
    """
    Master function to prepare all CA model inputs.
    
    REVISED: Clips data EARLY (before slope calculation) to avoid memory errors.
    
    Args:
        event_id: Fire cluster ID
        srtm_path: Path to SRTM elevation raster
        land_use_path: Path to MapBiomas land use raster
        weather_csv_path: Path to ERA5 weather CSV
        fire_points_gdf: GeoDataFrame with FIRMS fire points
        clip_to_fire: If True, clip data to buffer around ignition (default: True)
        buffer_km: Buffer distance in km around ignition (default: 10)
    
    Returns:
        ca_data: Dictionary with all required arrays and metadata
    """
    print(f"\n{'='*70}")
    print(f"Preparing CA inputs for event {event_id}")
    print(f"{'='*70}\n")
    
    # ========================================================================
    # STEP 1: Load elevation (full extent)
    # ========================================================================
    print("1. Loading elevation...")
    elevation, master_meta = load_topography(srtm_path)
    
    # ========================================================================
    # STEP 2: Find ignition location and clip bounds (if enabled)
    # ========================================================================
    print("\n2. Finding ignition location...")
    
    # Filter to cluster and find earliest point
    cluster_points = fire_points_gdf[
        fire_points_gdf['CLUSTER_ID'] == event_id
    ].copy()
    
    if len(cluster_points) == 0:
        raise ValueError(f"No fire points found for cluster {event_id}")
    
    cluster_points = cluster_points.sort_values('ACQ_DATE')
    earliest_point = cluster_points.iloc[0]
    
    ignition_time = earliest_point['ACQ_DATE']
    ignition_geom = earliest_point['geometry']
    
    # Get coordinates
    x, y = ignition_geom.x, ignition_geom.y
    
    # Convert to array indices using FULL transform
    col, row = ~master_meta['transform'] * (x, y)
    ig_row, ig_col = int(row), int(col)
    
    # Check bounds
    rows, cols = master_meta['shape']
    if not (0 <= ig_row < rows and 0 <= ig_col < cols):
        raise ValueError(
            f"Ignition point ({ig_row}, {ig_col}) outside raster bounds {master_meta['shape']}"
        )
    
    print(f"  Ignition point (full grid): row={ig_row}, col={ig_col}")
    print(f"  Coordinates: x={x:.6f}, y={y:.6f}")
    print(f"  Ignition time: {ignition_time}")
    
    # ========================================================================
    # STEP 3: CLIP ELEVATION (if enabled) - BEFORE expensive operations!
    # ========================================================================
    if clip_to_fire:
        print(f"\n3. Clipping to {buffer_km} km buffer around ignition...")
        
        # Calculate buffer in cells
        buffer_cells = int((buffer_km * 1000) / 30)
        
        # Calculate clipping window
        row_min = max(0, ig_row - buffer_cells)
        row_max = min(rows, ig_row + buffer_cells + 1)
        col_min = max(0, ig_col - buffer_cells)
        col_max = min(cols, ig_col + buffer_cells + 1)
        
        # Clip elevation
        elevation = elevation[row_min:row_max, col_min:col_max]
        
        # Update transform for clipped extent
        original_transform = master_meta['transform']
        new_x_origin = original_transform.c + (col_min * original_transform.a)
        new_y_origin = original_transform.f + (row_min * original_transform.e)
        
        clipped_transform = Affine(
            original_transform.a, original_transform.b, new_x_origin,
            original_transform.d, original_transform.e, new_y_origin
        )
        
        # Update shape
        clipped_shape = (row_max - row_min, col_max - col_min)
        
        # Store clipping bounds for later use
        clip_bounds = {
            'row_min': row_min,
            'row_max': row_max,
            'col_min': col_min,
            'col_max': col_max
        }
        
        # Report clipping results
        original_cells = rows * cols
        clipped_cells = clipped_shape[0] * clipped_shape[1]
        reduction_pct = 100 * (1 - clipped_cells / original_cells)
        
        print(f"  Original grid: {rows:,} × {cols:,} = {original_cells:,} cells ({original_cells / 1e6:.1f} million)")
        print(f"  Clipped grid:  {clipped_shape[0]:,} × {clipped_shape[1]:,} = {clipped_cells:,} cells ({clipped_cells / 1e6:.2f} million)")
        print(f"  Buffer: {buffer_km} km ({buffer_cells} cells)")
        print(f"  Memory reduction: {reduction_pct:.1f}%")
        
        # Update metadata
        current_transform = clipped_transform
        current_shape = clipped_shape
        
        # Update ignition position relative to clipped grid
        ig_row_clipped = ig_row - row_min
        ig_col_clipped = ig_col - col_min
        print(f"  Ignition point (clipped grid): row={ig_row_clipped}, col={ig_col_clipped}")
        
    else:
        print("\n3. Skipping clipping (using full extent)")
        current_transform = master_meta['transform']
        current_shape = master_meta['shape']
        clip_bounds = None
        ig_row_clipped = ig_row
        ig_col_clipped = ig_col
    
    # ========================================================================
    # STEP 4: Calculate slope and aspect (on clipped or full elevation)
    # ========================================================================
    print("\n4. Calculating slope and aspect...")
    slope, aspect = calculate_slope_aspect(elevation, cell_size=30)
    
    # ========================================================================
    # STEP 5: Load land use (full extent)
    # ========================================================================
    print("\n5. Loading land use...")
    land_use, lu_meta = load_land_use(land_use_path)
    
    # ========================================================================
    # STEP 6: Clip land use (if clipping enabled)
    # ========================================================================
    if clip_to_fire:
        print("\n6. Clipping land use to same extent...")
        
        # Check if land use needs snapping first
        if (lu_meta['transform'] != master_meta['transform'] or 
            lu_meta['shape'] != master_meta['shape']):
            print("  Land use needs snapping before clipping...")
            
            # Snap to FULL master grid first
            land_use = snap_to_master_grid(
                land_use, 
                lu_meta['transform'], lu_meta['crs'],
                master_meta['transform'], master_meta['crs'], master_meta['shape'],
                resampling_method=Resampling.nearest
            )
        
        # Now clip using same bounds
        land_use = land_use[clip_bounds['row_min']:clip_bounds['row_max'], 
                           clip_bounds['col_min']:clip_bounds['col_max']]
        
    else:
        print("\n6. Snapping land use (if needed)...")
        # Snap land use to master grid (if needed)
        if (lu_meta['transform'] != master_meta['transform'] or 
            lu_meta['shape'] != master_meta['shape']):
            land_use = snap_to_master_grid(
                land_use, 
                lu_meta['transform'], lu_meta['crs'],
                master_meta['transform'], master_meta['crs'], master_meta['shape'],
                resampling_method=Resampling.nearest
            )
    
    # ========================================================================
    # STEP 7: Map to fuel types
    # ========================================================================
    print("\n7. Mapping to fuel types...")
    fuel_type, Ks = mapbiomas_to_fuel_array(land_use)
    
    # ========================================================================
    # STEP 8: Load weather
    # ========================================================================
    print("\n8. Loading weather time series...")
    weather = load_weather_timeseries(weather_csv_path)
    
    # ========================================================================
    # STEP 9: Create ignition raster (on clipped grid)
    # ========================================================================
    print("\n9. Creating ignition raster...")
    
    # Create binary ignition raster
    ignition = np.zeros(current_shape, dtype=np.uint8)
    
    # Set ignition cell (using clipped coordinates)
    if 0 <= ig_row_clipped < current_shape[0] and 0 <= ig_col_clipped < current_shape[1]:
        ignition[ig_row_clipped, ig_col_clipped] = 1
        print(f"  Ignition set at row={ig_row_clipped}, col={ig_col_clipped}")
    else:
        raise ValueError(
            f"Ignition point ({ig_row_clipped}, {ig_col_clipped}) outside clipped bounds {current_shape}"
        )
    
    # ========================================================================
    # STEP 10: Package everything
    # ========================================================================
    ca_data = {
        # Spatial grids (clipped or full)
        'elevation': elevation,
        'slope': slope,
        'aspect': aspect,
        'fuel_type': fuel_type,
        'Ks': Ks,
        'ignition': ignition,
        
        # Time series (always full)
        'weather': weather,
        'ignition_time': ignition_time,
        
        # Grid metadata (updated if clipped)
        'transform': current_transform,
        'crs': master_meta['crs'],
        'shape': current_shape,
        'cell_size': 30
    }
    
    print(f"\n{'='*70}")
    print(f"CA Data Preparation Complete")
    print(f"{'='*70}")
    print(f"Grid shape: {ca_data['shape']}")
    print(f"Grid CRS: {ca_data['crs']}")
    print(f"Ignition time: {ignition_time}")
    print(f"Weather time steps: {len(weather)}")
    print(f"{'='*70}\n")
    
    return ca_data

# ============================================================================
# UTILITY: EXPORT RASTER FOR VISUALIZATION
# ============================================================================

def export_raster(array, output_path, ca_data, dtype=rasterio.float32, nodata=None):
    """Export numpy array to GeoTIFF using ca_data metadata."""
    with rasterio.open(
        output_path,
        'w',
        driver='GTiff',
        height=ca_data['shape'][0],
        width=ca_data['shape'][1],
        count=1,
        dtype=dtype,
        crs=ca_data['crs'],
        transform=ca_data['transform'],
        compress='lzw',
        nodata=nodata
    ) as dst:
        dst.write(array, 1)
    
    print(f"  Exported: {output_path}")

def export_all_ca_layers(ca_data, output_dir='ca_debug_layers'):
    """Export all CA layers as GeoTIFFs for visualization."""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nExporting CA layers to {output_dir}/...")
    
    export_raster(ca_data['elevation'], 
                 f'{output_dir}/elevation.tif', 
                 ca_data, 
                 dtype=rasterio.float32,
                 nodata=-9999)
    
    export_raster(ca_data['slope'], 
                 f'{output_dir}/slope.tif', 
                 ca_data, 
                 dtype=rasterio.float32)
    
    export_raster(ca_data['aspect'], 
                 f'{output_dir}/aspect.tif', 
                 ca_data, 
                 dtype=rasterio.float32)
    
    export_raster(ca_data['fuel_type'], 
                 f'{output_dir}/fuel_type.tif', 
                 ca_data, 
                 dtype=rasterio.uint8)
    
    export_raster(ca_data['Ks'], 
                 f'{output_dir}/fuel_factor_Ks.tif', 
                 ca_data, 
                 dtype=rasterio.float32)
    
    export_raster(ca_data['ignition'], 
                 f'{output_dir}/ignition.tif', 
                 ca_data, 
                 dtype=rasterio.uint8)
    
    print(f"Done. All layers exported to {output_dir}/\n")

# ============================================================================
# UTILITY: DEBUG IGNITION POINT
# ============================================================================

def debug_ignition_point(ca_data, state=None):
    """Print detailed diagnostic info about ignition location and neighbors."""
    ignition_indices = np.argwhere(ca_data['ignition'] == 1)
    if len(ignition_indices) == 0:
        print("ERROR: No ignition point found!")
        return
    
    i, j = ignition_indices[0]
    rows, cols = ca_data['shape']
    
    print(f"\n{'='*80}")
    print(f"IGNITION POINT DIAGNOSTIC")
    print(f"{'='*80}")
    print(f"Location: row={i}, col={j}")
    print(f"Grid size: {rows} rows × {cols} cols")
    print(f"{'='*80}\n")
    
    print(f"Ignition Cell Values:")
    print(f"  Elevation:      {ca_data['elevation'][i,j]:>10.2f} m")
    print(f"  Slope:          {ca_data['slope'][i,j]:>10.2f} degrees")
    print(f"  Aspect:         {ca_data['aspect'][i,j]:>10.3f} radians")
    print(f"  Fuel Type:      {ca_data['fuel_type'][i,j]:>10}")
    print(f"  Fuel Factor Ks: {ca_data['Ks'][i,j]:>10.3f}")
    if state is not None:
        print(f"  State:          {state[i,j]:>10} (1=BURNING expected)")
    
    print(f"\nData Quality:")
    has_elev_nan = np.isnan(ca_data['elevation'][i,j])
    has_slope_nan = np.isnan(ca_data['slope'][i,j])
    has_ks_nan = np.isnan(ca_data['Ks'][i,j])
    is_nodata = (ca_data['elevation'][i,j] == -9999)
    
    print(f"  Elevation NaN:  {has_elev_nan}")
    print(f"  Slope NaN:      {has_slope_nan}")
    print(f"  Ks NaN:         {has_ks_nan}")
    print(f"  Is NoData:      {is_nodata}")
    
    if has_elev_nan or has_slope_nan or has_ks_nan or is_nodata:
        print(f"\n  ⚠️  WARNING: Ignition point has invalid data!")
    
    print(f"\n{'='*80}")
    print(f"8-NEIGHBOR ANALYSIS")
    print(f"{'='*80}")
    print(f"{'Dir':<8} {'Row':<6} {'Col':<6} {'InBounds':<10} {'Elev':<10} {'Slope':<10} {'Ks':<8} {'Valid':<10}")
    print("-" * 80)
    
    directions = {
        (-1, 0): "N", (-1, 1): "NE", (0, 1): "E", (1, 1): "SE",
        (1, 0): "S", (1, -1): "SW", (0, -1): "W", (-1, -1): "NW"
    }
    
    valid_spread_targets = 0
    
    for (di, dj), name in directions.items():
        ni, nj = i + di, j + dj
        in_bounds = (0 <= ni < rows and 0 <= nj < cols)
        
        if in_bounds:
            elev = ca_data['elevation'][ni, nj]
            slope = ca_data['slope'][ni, nj]
            ks = ca_data['Ks'][ni, nj]
            
            has_nan = np.isnan(elev) or np.isnan(slope) or np.isnan(ks)
            is_nodata_cell = (elev == -9999)
            has_no_fuel = (ks == 0)
            
            if state is not None:
                already_affected = (state[ni, nj] != 0)
            else:
                already_affected = False
            
            is_valid = (not has_nan and not is_nodata_cell and 
                       not has_no_fuel and not already_affected)
            
            if is_valid:
                valid_spread_targets += 1
                status = "✓ OK"
            else:
                reasons = []
                if has_nan: reasons.append("NaN")
                if is_nodata_cell: reasons.append("NoData")
                if has_no_fuel: reasons.append("NoFuel")
                if already_affected: reasons.append("Burned")
                status = "✗ " + ",".join(reasons)
            
            print(f"{name:<8} {ni:<6} {nj:<6} {'Yes':<10} {elev:<10.2f} {slope:<10.2f} {ks:<8.3f} {status:<10}")
        else:
            print(f"{name:<8} {ni:<6} {nj:<6} {'No':<10} {'---':<10} {'---':<10} {'---':<8} {'✗ OutOfBounds':<10}")
    
    print(f"{'='*80}")
    print(f"SUMMARY: {valid_spread_targets} valid neighbors for fire spread")
    print(f"{'='*80}\n")
    
    if valid_spread_targets == 0:
        print("⚠️  CRITICAL: No valid neighbors for spread! Fire will extinguish immediately.\n")
        print("Possible causes:")
        print("  1. Ignition point is surrounded by NoData cells")
        print("  2. Ignition point is surrounded by non-combustible cells (Ks=0)")
        print("  3. Ignition point is at edge/corner of valid data extent")
        print("  4. Grid alignment issues between ignition and environmental layers\n")
    
    return valid_spread_targets

# ============================================================================
# UTILITY: QUICK DATA QUALITY CHECK
# ============================================================================

def check_data_quality(ca_data):
    """Run comprehensive data quality checks on prepared CA inputs."""
    print(f"\n{'='*80}")
    print(f"DATA QUALITY REPORT")
    print(f"{'='*80}\n")
    
    print(f"Grid Information:")
    print(f"  Shape: {ca_data['shape']}")
    print(f"  Total cells: {ca_data['shape'][0] * ca_data['shape'][1]:,}")
    print(f"  Cell size: {ca_data['cell_size']} m")
    print(f"  CRS: {ca_data['crs']}\n")
    
    valid_elev = ca_data['elevation'][ca_data['elevation'] != -9999]
    print(f"Elevation:")
    print(f"  Valid cells: {len(valid_elev):,} ({100*len(valid_elev)/ca_data['elevation'].size:.1f}%)")
    print(f"  NoData cells: {np.sum(ca_data['elevation'] == -9999):,}")
    print(f"  Range: {np.min(valid_elev):.1f} to {np.max(valid_elev):.1f} m")
    print(f"  NaN count: {np.sum(np.isnan(ca_data['elevation']))}\n")
    
    valid_slope = ca_data['slope'][ca_data['elevation'] != -9999]
    print(f"Slope:")
    print(f"  Range: {np.min(valid_slope):.1f} to {np.max(valid_slope):.1f} degrees")
    print(f"  Mean: {np.mean(valid_slope):.1f} degrees")
    print(f"  NaN count: {np.sum(np.isnan(ca_data['slope']))}\n")
    
    print(f"Fuel Distribution:")
    for fuel_id in [1, 2, 3, 4, 5]:
        count = np.sum(ca_data['fuel_type'] == fuel_id)
        pct = 100 * count / ca_data['fuel_type'].size
        ks_val = FUEL_TYPE_TO_KS[fuel_id]
        print(f"  Type {fuel_id} (Ks={ks_val:.2f}): {count:,} cells ({pct:.1f}%)")
    
    combustible = np.sum(ca_data['Ks'] > 0)
    print(f"  Combustible cells (Ks > 0): {combustible:,} ({100*combustible/ca_data['Ks'].size:.1f}%)")
    print(f"  Ks NaN count: {np.sum(np.isnan(ca_data['Ks']))}\n")
    
    ignition_count = np.sum(ca_data['ignition'] == 1)
    print(f"Ignition:")
    print(f"  Ignition cells: {ignition_count}")
    print(f"  Ignition time: {ca_data['ignition_time']}\n")
    
    print(f"Weather:")
    print(f"  Time steps: {len(ca_data['weather'])}")
    print(f"  Time range: {ca_data['weather']['timestamp'].min()} to {ca_data['weather']['timestamp'].max()}")
    print(f"  Wind speed range: {ca_data['weather']['wind_speed'].min():.1f} to {ca_data['weather']['wind_speed'].max():.1f} m/s")
    
    print(f"\n{'='*80}\n")
    
# ============================================================================
# UTILITY: GET WEATHER DATA
# ============================================================================


def get_era5_data(gdf_init, id_column, lat, lon, start_date, end_date, delta_end, delta_start, ee_project, event_id):
    ee.Authenticate()
    ee.Initialize(project=ee_project)
    """
    Extract hourly ERA5 time series for each fire event.
    
    Returns: Dictionary with fire_id as keys, each containing hourly DataFrame
    """
    
    gdf = gdf_init[gdf_init[id_column] == event_id].copy()
    
    # CHECK: Ensure only one row per event (one representative point per cluster)
    if len(gdf) > 1:
        print(f"Warning: Event {event_id} has {len(gdf)} ignition points in cluster.")
        print("Taking the first ignition point as representative.")
        gdf = gdf.iloc[[0]]  # Take only the first row
    elif len(gdf) == 0:
        raise ValueError(f"No data found for event {event_id}")
    
    # Verify ERA5 band names
    era5_bands = {
        'temperature_2m',
        'dewpoint_temperature_2m',
        'u_component_of_wind_10m',
        'v_component_of_wind_10m'
    }
    
    results = {}
    
    # Process each fire event individually
    for idx, row in gdf.iterrows():
        event_id = row[id_column]
        
        # Get fire-specific date range (with buffer)
        start_dt = pd.to_datetime(row[start_date]) - timedelta(days=delta_start)
        end_dt = pd.to_datetime(row[end_date]) + timedelta(days=delta_end)
        
        # Create point geometry for fire centroid
        if 'geometry' in row.index and pd.notna(row['geometry']):
            point = ee.Geometry.Point(row['geometry'].centroid.x, row['geometry'].centroid.y)
        elif lat is not None and lon is not None:
            point = ee.Geometry.Point([row[lon], row[lat]])
        else:
            raise ValueError(f"Event {event_id}: No valid geometry or lat/lon columns provided")
        
        # Filter ERA5 for this fire's time window
        era5_collection = (ee.ImageCollection('ECMWF/ERA5/HOURLY')
            .filterDate(start_dt.strftime('%Y-%m-%d'), 
                       end_dt.strftime('%Y-%m-%d'))
            .select(list(era5_bands))
        )
        
        # Extract time series at point location
        def extract_hourly(image):
            values = image.reduceRegion(
                reducer=ee.Reducer.first(),
                geometry=point,
                scale=27830
            )
            return ee.Feature(None, values).set('system:time_start', image.get('system:time_start'))
        
        # Map over all images to get time series
        time_series = era5_collection.map(extract_hourly)
        
        # Convert to pandas DataFrame
        ts_list = time_series.getInfo()['features']
        
        hourly_data = []
        for feature in ts_list:
            props = feature['properties']
            hourly_data.append({
                'timestamp': datetime.fromtimestamp(props['system:time_start'] / 1000),
                'temperature_2m': props.get('temperature_2m'),
                'dewpoint_2m': props.get('dewpoint_temperature_2m'),
                'u_wind_10m': props.get('u_component_of_wind_10m'),
                'v_wind_10m': props.get('v_component_of_wind_10m')
            })
        
        df = pd.DataFrame(hourly_data).sort_values('timestamp')
        
        # Calculate derived variables
        df['temperature_c'] = df['temperature_2m'] - 273.15
        df['dewpoint_c'] = df['dewpoint_2m'] - 273.15
        
        # Calculate relative humidity from dewpoint
        df['relative_humidity'] = 100 * (
            np.exp((17.625 * df['dewpoint_c']) / (243.04 + df['dewpoint_c'])) /
            np.exp((17.625 * df['temperature_c']) / (243.04 + df['temperature_c']))
        )
        
        # Calculate wind speed and direction
        df['wind_speed'] = np.sqrt(df['u_wind_10m']**2 + df['v_wind_10m']**2)
        df['wind_direction'] = (np.arctan2(df['u_wind_10m'], df['v_wind_10m']) * 180 / np.pi + 360) % 360
        
        # Store processed time series
        results[event_id] = df[['timestamp', 'temperature_c', 'relative_humidity', 
                                'wind_speed', 'wind_direction']]
        
        print(f"Extracted {len(df)} hourly records for event {event_id}")
    
    return results