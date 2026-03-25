"""
CA Model - CORRECTED VERSION WITH DIAGNOSTICS
Chaco Wildfire Spread Model - Paulo Medina

This version includes:
- All bug fixes (neighbor loop, spotting, etc.)
- Comprehensive diagnostics for debugging
- Weather validation
- Probability monitoring
"""

import numpy as np
import pandas as pd
import random
import math

# Cell state constants
UNBURNED = 0
BURNING = 1
BURNED = 2
NON_COMBUSTIBLE = -1

# Moore neighborhood (8 neighbors)
NEIGHBORS = [
    (-1, -1), (-1, 0), (-1, 1),  # Top row
    (0, -1),           (0, 1),   # Middle row (skip center)
    (1, -1),  (1, 0),  (1, 1)    # Bottom row
]


def initialize_state_grid(ignition, Ks):
    """Initialize cell state grid"""
    state = np.full(ignition.shape, UNBURNED, dtype=np.int8)
    state[ignition == 1] = BURNING
    state[Ks == 0] = NON_COMBUSTIBLE
    return state


def get_weather_values(weather_data, current_time):
    """Get weather values for current timestep"""
    current_hour = current_time.floor('h')
    current_weather_mask = weather_data['timestamp'] == current_hour
    current_weather = weather_data[current_weather_mask].iloc[0]
    return current_weather


def calculate_time_step(weather_values, ca_data, R0, m, Kr, c1, a_s, L):
    """
    Calculate adaptive time step based on REASONABLE maximum conditions.
    Uses 90th percentile wind and reasonable slope to avoid extreme outliers.
    """
    # Use 90th percentile wind speed instead of absolute max
    wind_p90 = np.percentile(weather_values['wind_speed'], 90)
    wind_factor = math.exp(wind_p90 * c1)
    
    # Use reasonable max slope (30 degrees) instead of data max
    reasonable_max_slope = np.radians(30)  
    max_K0 = np.exp(a_s * reasonable_max_slope)
    
    # max(Ks) = 1 (grassland)
    max_Ks = 1
    
    # Calculate Rmax        
    Rmax = R0 * wind_factor * max_K0 * max_Ks * Kr
    
    # Calculate delta_t
    delta_t = m * (L / Rmax)
    
    print(f"\n  Adaptive time step calculation:")
    print(f"    Wind (90th percentile): {wind_p90:.2f} m/s")
    print(f"    Wind factor: {wind_factor:.3f}")
    print(f"    Slope factor: {max_K0:.3f}")
    print(f"    Rmax: {Rmax:.3f} m/min")
    print(f"    Delta_t: {delta_t:.3f} minutes ({delta_t*60:.1f} seconds)\n")
    
    return delta_t


def calculate_spotting_distance(wind_speed, cell_size):
    """Calculate spotting distance based on wind speed"""
    spotting_threshold = 8.0  # m/s
    distance_coefficient = 50  # meters per m/s above threshold
    
    excess_wind = wind_speed - spotting_threshold
    if excess_wind <= 0:
        return 0
    
    spotting_distance_meters = distance_coefficient * excess_wind
    spotting_distance_cells = round(spotting_distance_meters / cell_size)
    
    max_spotting = 50  # cells
    spotting_distance_cells = min(spotting_distance_cells, max_spotting)
    
    return spotting_distance_cells


def trace_wind_vector(start, direction, distance, ca_data, state):
    """
    Trace path along wind direction and return cells to spot-ignite.
    FIXED: Proper loop iteration and return placement.
    """
    start_row, start_col = start
    rows, cols = ca_data['shape']
    
    spotted_cells = []
    
    if distance <= 0:
        return spotted_cells
    
    # Calculate wind vector components
    delta_row = distance * math.cos(direction)
    delta_col = distance * math.sin(direction)
    
    # Trace along the vector with small steps
    steps = distance * 2
    
    for step in range(steps):  # FIXED: Use range()
        
        # Calculate fractional progress along vector
        progress = step / steps
        
        # Calculate current position
        current_row = start_row + (delta_row * progress)
        current_col = start_col + (delta_col * progress)
        
        cell_row = round(current_row)
        cell_col = round(current_col)
        
        # Boundary check
        if cell_row < 0 or cell_row >= rows:
            continue
        if cell_col < 0 or cell_col >= cols:
            continue
        
        # Check if cell is valid for spotting
        current_state = state[cell_row, cell_col]
        current_fuel = ca_data['Ks'][cell_row, cell_col]
        
        if current_state != UNBURNED:
            continue
        if current_fuel == 0:
            continue
        
        # Add to spotted cells
        cell_tuple = (cell_row, cell_col)
        if cell_tuple not in spotted_cells:
            spotted_cells.append(cell_tuple)
    
    # FIXED: Return after loop completes, not inside
    return spotted_cells


def get_burning_cell_indices(state):
    """Get list of (row, col) tuples where state == BURNING"""
    ignitions = np.argwhere(state == BURNING)
    return [tuple(idx) for idx in ignitions]


def calculate_spread_probability(from_cell, to_cell, direction, ca_data, weather, R0, Kr, c1, c2, a_s, delta_t):
    """Calculate spread probability from burning cell to neighbor"""
    i, j = from_cell
    ni, nj = to_cell
    di, dj = direction
    
    # Wind factor: Kφ = exp[V × (c1 + c2 × (cos(θ) - 1))]
    V = weather['wind_speed']
    spread_direction = np.atan2((nj-j), -(ni-i))
    wind_direction = weather['wind_direction']
    angle_diff = abs(spread_direction - wind_direction)
    
    # Handle angle wrap-around
    if angle_diff > math.pi:
        angle_diff = 2 * math.pi - angle_diff
    
    wind_factor = math.exp(V * (c1 + c2 * (math.cos(angle_diff) - 1)))
    
    # Slope factor: Kθ = exp[as × θs]
    elev_from = ca_data['elevation'][i, j]
    elev_to = ca_data['elevation'][ni, nj]
    delta_elevation = elev_to - elev_from
    
    # Calculate distance
    if abs(di) + abs(dj) == 1:  # Adjacent
        distance = ca_data['cell_size']
    else:  # Diagonal
        distance = ca_data['cell_size'] * math.sqrt(2)
    
    # Directional slope angle
    slope_angle = math.atan(delta_elevation / distance)
    slope_factor = math.exp(a_s * slope_angle)
    
    # Fuel factor
    fuel_factor = ca_data['Ks'][ni, nj]
    
    # Calculate spread rate
    base_prob = R0 * wind_factor * slope_factor * fuel_factor * Kr
    
    # Convert to probability [0, 1]
    p_spread = 1 - math.exp(-base_prob * delta_t / distance)
    
    return p_spread


def run_ca_simulation(ca_data, max_time_steps=1000, Kr=1.0, verbose=True):
    """
    Run CA wildfire simulation.
    
    Args:
        ca_data: Dictionary with all input data
        max_time_steps: Maximum simulation steps
        Kr: Calibration factor for spread rate
        verbose: Print diagnostic information
    
    Returns:
        Dictionary with simulation results
    """
    
    # ----------------------------------------------------------------
    # INITIALIZATION
    # ----------------------------------------------------------------
    
    # Constants (from Rui et al. 2018 and Freire 2019)
    R0 = 0.8      # Base spread rate (m/min)
    m = 0.5       # Time step multiplier
    L = ca_data['cell_size']  # Cell size (m)
    c1 = 0.045    # Wind coefficient 1
    c2 = 0.131    # Wind coefficient 2
    a_s = 0.078   # Slope coefficient
    
    # Extract variables from ca_data
    rows, cols = ca_data['shape']
    ignition_time = ca_data['ignition_time']
    weather_values = ca_data['weather']
    
    # ----------------------------------------------------------------
    # PRE-SIMULATION WEATHER CHECK
    # ----------------------------------------------------------------
    if verbose:
        print(f"\n{'='*80}")
        print(f"WEATHER DATA VALIDATION")
        print(f"{'='*80}")
        print(f"Weather time range: {weather_values['timestamp'].min()} to {weather_values['timestamp'].max()}")
        print(f"Ignition time: {ignition_time}")
        print(f"\nWind speed statistics:")
        print(f"  Min: {weather_values['wind_speed'].min():.2f} m/s")
        print(f"  Max: {weather_values['wind_speed'].max():.2f} m/s")
        print(f"  Mean: {weather_values['wind_speed'].mean():.2f} m/s")
        print(f"  Median: {weather_values['wind_speed'].median():.2f} m/s")
        
        # Check first few hours after ignition
        ignition_idx = weather_values['timestamp'] == ignition_time.floor('h')
        if ignition_idx.any():
            row_idx = weather_values[ignition_idx].index[0]
            print(f"\nWeather at ignition time (first 5 hours):")
            for i in range(min(5, len(weather_values) - row_idx)):
                row = weather_values.iloc[row_idx + i]
                print(f"  {row['timestamp']}: Wind={row['wind_speed']:.2f} m/s, " +
                      f"Dir={np.degrees(row['wind_direction']):.1f}°, " +
                      f"Temp={row['temperature_c']:.1f}°C, RH={row['relative_humidity']:.1f}%")
        print(f"{'='*80}\n")
    
    # Initialize state grid
    state = initialize_state_grid(ca_data['ignition'], ca_data['Ks'])
    
    # Burn time tracking
    burn_time = np.full((rows, cols), -1, dtype=np.int32)
    burn_time[state == BURNING] = 0
    
    # Calculate adaptive time step
    # delta_t = calculate_time_step(weather_values, ca_data, R0, m, Kr, c1, a_s, L)
    delta_t = 2.0
    
    # Fire progression history
    fire_progression = []
    
    if verbose:
        print(f"{'='*80}")
        print(f"STARTING SIMULATION")
        print(f"{'='*80}")
        print(f"  Grid: {rows} × {cols} cells")
        print(f"  Delta_t: {delta_t:.2f} minutes")
        print(f"  Kr: {Kr}")
        print(f"  Initial burning cells: {np.sum(state == BURNING)}")
        print(f"{'='*80}\n")
    
    # ----------------------------------------------------------------
    # TIME STEPPING LOOP
    # ----------------------------------------------------------------
    for t in range(max_time_steps):
        
        # Record current state
        fire_progression.append(state.copy())
        
        # Get current weather
        current_time = ignition_time + pd.Timedelta(minutes=t * delta_t)
        weather_now = get_weather_values(weather_values, current_time)
        
        # Find burning cells
        burning_cells = get_burning_cell_indices(state)
        
        # Monitor progress
        if verbose and t < 10:
            print(f"t={t}: Burning={len(burning_cells)}, Time={current_time}")
        
        # Check if fire extinguished
        if len(burning_cells) == 0:
            if verbose:
                print(f"\nFire extinguished at time step {t}")
            break
        
        # ---------------------------------------------------------------
        # SPREAD TO NEIGHBORS (Standard CA Rule)
        # ---------------------------------------------------------------
        new_ignitions = []
        
        for (i, j) in burning_cells:
            # Check all 8 neighbors
            for (di, dj) in NEIGHBORS:
                ni, nj = i + di, j + dj
                
                # Boundary check
                if not (0 <= ni < rows and 0 <= nj < cols):
                    continue
                
                # Skip if not unburned
                if state[ni, nj] != UNBURNED:
                    continue
                
                # Calculate spread probability
                p_spread = calculate_spread_probability(
                    from_cell=(i, j),
                    to_cell=(ni, nj),
                    direction=(di, dj),
                    ca_data=ca_data,
                    weather=weather_now,
                    R0=R0, Kr=Kr, c1=c1, c2=c2, a_s=a_s, delta_t=delta_t
                )
                
                # Stochastic ignition
                if random.uniform(0, 1) < p_spread:
                    new_ignitions.append((ni, nj))
        
        # Monitor new ignitions
        if verbose and t < 10:
            print(f"  → New ignitions: {len(new_ignitions)}")
        
        # ---------------------------------------------------------------
        # DETAILED DIAGNOSTIC (First timestep only)
        # ---------------------------------------------------------------
        if verbose and t == 0 and len(burning_cells) > 0:
            i, j = burning_cells[0]
            
            print(f"\n{'='*80}")
            print(f"DETAILED PROBABILITY DIAGNOSTIC - TIMESTEP 0")
            print(f"{'='*80}")
            print(f"Burning cell: ({i}, {j})")
            print(f"  Elevation: {ca_data['elevation'][i,j]:.2f} m")
            print(f"  Slope: {ca_data['slope'][i,j]:.2f} degrees")
            print(f"  Fuel (Ks): {ca_data['Ks'][i,j]:.3f}")
            print(f"  Fuel type: {ca_data['fuel_type'][i,j]}")
            
            print(f"\nWeather at ignition:")
            print(f"  Wind speed: {weather_now['wind_speed']:.2f} m/s")
            print(f"  Wind direction: {weather_now['wind_direction']:.3f} rad ({np.degrees(weather_now['wind_direction']):.1f}°)")
            print(f"  Temperature: {weather_now['temperature_c']:.1f} °C")
            print(f"  RH: {weather_now['relative_humidity']:.1f} %")
            
            print(f"\nNeighbor spread analysis:")
            print(f"{'Dir':<6} {'Coords':<12} {'State':<10} {'FType':<6} {'Ks':<8} {'ΔElev':<8} {'Prob':<12} {'%':<10}")
            print("-" * 90)
            
            dir_names = {
                (-1, 0): "N", (-1, 1): "NE", (0, 1): "E", (1, 1): "SE",
                (1, 0): "S", (1, -1): "SW", (0, -1): "W", (-1, -1): "NW"
            }
            
            for (di, dj) in NEIGHBORS:
                ni, nj = i + di, j + dj
                dir_name = dir_names.get((di, dj), "?")
                
                if not (0 <= ni < rows and 0 <= nj < cols):
                    print(f"{dir_name:<6} OUT-OF-BOUNDS")
                    continue
                
                neighbor_state = state[ni, nj]
                state_names = {0: "UNBURNED", 1: "BURNING", 2: "BURNED", -1: "NON-COMB"}
                state_name = state_names.get(neighbor_state, "?")
                
                if neighbor_state != UNBURNED:
                    print(f"{dir_name:<6} ({ni},{nj})  {state_name:<10} {'---':<6} {'---':<8} {'---':<8} {'SKIPPED':<12}")
                    continue
                
                neighbor_ks = ca_data['Ks'][ni, nj]
                neighbor_ftype = ca_data['fuel_type'][ni, nj]
                delta_elev = ca_data['elevation'][ni, nj] - ca_data['elevation'][i, j]
                
                # Calculate probability
                p_spread = calculate_spread_probability(
                    from_cell=(i, j),
                    to_cell=(ni, nj),
                    direction=(di, dj),
                    ca_data=ca_data,
                    weather=weather_now,
                    R0=R0, Kr=Kr, c1=c1, c2=c2, a_s=a_s, delta_t=delta_t
                )
                
                print(f"{dir_name:<6} ({ni},{nj})  {state_name:<10} {neighbor_ftype:<6} {neighbor_ks:<8.3f} " +
                      f"{delta_elev:<8.2f} {p_spread:<12.6f} {p_spread*100:<10.4f}")
            
            print(f"{'='*80}\n")
        
        # ---------------------------------------------------------------
        # WIND-DRIVEN SPOTTING
        # ---------------------------------------------------------------
        if weather_now['wind_speed'] > 8.0:
            for (i, j) in burning_cells:
                for (ni, nj) in new_ignitions:
                    spread_direction = np.atan2((nj-j), -(ni-i))
                    angle_diff = abs(spread_direction - weather_now['wind_direction'])
                    angle_diff = min(angle_diff, 2*np.pi - angle_diff)
                    
                    if angle_diff < math.pi / 10:
                        spot_distance = calculate_spotting_distance(
                            weather_now['wind_speed'], 
                            ca_data['cell_size']
                        )
                        
                        spotted_cells = trace_wind_vector(
                            start=(i, j),
                            direction=weather_now['wind_direction'],
                            distance=spot_distance,
                            ca_data=ca_data,
                            state=state
                        )
                        
                        new_ignitions.extend(spotted_cells)
        
        # ---------------------------------------------------------------
        # UPDATE CELL STATES
        # ---------------------------------------------------------------
        # Burning → Burned
        state[state == BURNING] = BURNED
        
        # New ignitions → Burning
        for (ni, nj) in set(new_ignitions):
            if state[ni, nj] == UNBURNED:
                state[ni, nj] = BURNING
                burn_time[ni, nj] = t + 1
        
        # Safety check
        if t == max_time_steps - 1:
            if verbose:
                print(f"\nWARNING: Reached max time steps ({max_time_steps})")
            break
    
    # ----------------------------------------------------------------
    # RETURN RESULTS
    # ----------------------------------------------------------------
    if verbose:
        print(f"\n{'='*80}")
        print(f"SIMULATION COMPLETE")
        print(f"{'='*80}")
        print(f"  Total timesteps: {len(fire_progression)}")
        print(f"  Total burned cells: {np.sum(state == BURNED)}")
        print(f"  Burned area: {np.sum(state == BURNED) * 30 * 30 / 10000:.2f} hectares")
        print(f"  Duration: {len(fire_progression) * delta_t:.1f} minutes")
        print(f"{'='*80}\n")
    
    return {
        'burn_time': burn_time,
        'final_state': state,
        'fire_progression': fire_progression,
        'time_step_minutes': delta_t,
        'total_burned_cells': np.sum(state == BURNED)
    }