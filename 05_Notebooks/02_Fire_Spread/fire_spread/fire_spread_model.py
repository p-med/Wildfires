"""
CA Model
Chaco Wildfire Spread Model - Paulo Medina

"""

# ===============================================================================
# Cellular Automata (CA) model for wildfire spread
# ===============================================================================


# Cell States
# -------------------------------------------------------------------------------
# UNBURNED          =    0
# BURNING           =    1
# BURNED            =    2
# NON_COMBUSTIBLE   =   -1


# MODEL PARAMETERS (from Rui et al. 2018)
# -------------------------------------------------------------------------------
#     R0 = 0.8 m/min          # Base spread rate
#     m = 0.125               # Time step multiplier
#     Δt = m × (L / Rmax)     # Adaptive time step (calculate dynamically)
#     L = 10.0                # Cell size (m)
#     c1 = 0.045              # Wind coefficient 1 (from Freire 2019)
#     c2 = 0.131              # Wind coefficient 2 (from Freire 2019)
#     as = 0.078              # Slope coefficient (from Freire 2019)
#     Kr = 1.0                # Time correction factor (will calibrate per event)
    
#     SPOTTING_THRESHOLD = 8.0  # m/s, from Freire 2019
#     SPOTTING_ANGLE = π/10     # radians, fire must spread within this angle of wind


# NEIGHBORHOOD STRUCTURE (Moore 8-neighbors)
# -------------------------------------------------------------------------------
#     NEIGHBORS = [
#         (-1, -1), (-1, 0), (-1, 1),  # Top row
#         ( 0, -1),          ( 0, 1),  # Middle row (skip center)
#         ( 1, -1), ( 1, 0), ( 1, 1)   # Bottom row
#     ]
    
#     DISTANCES = {
#         adjacent: L (30m),
#         diagonal: L × √2 (42.43m)
#     }
    
#     ANGLES = {  # Direction from center to neighbor (radians, 0=North, clockwise)
#         (-1,  0): 0,        # North
#         (-1,  1): π/4,      # NE
#         ( 0,  1): π/2,      # East
#         ( 1,  1): 3π/4,     # SE
#         ( 1,  0): π,        # South
#         ( 1, -1): 5π/4,     # SW
#         ( 0, -1): 3π/2,     # West
#         (-1, -1): 7π/4      # NW
#     }

# ===============================================================================
# MAIN SIMULATION LOOP (Single Run)
# ===============================================================================

# Import modules
# -------------------------------------------------------------------------------
import numpy as np
import pandas as pd
import random
import math

# Initialize state grid
# -------------------------------------------------------------------------------
# Create an initial array of zeros and then set values based on ignition and Ks:
# state[i,j] = BURNING where ignition[i,j] = 1
# state[i,j] = NON_COMBUSTIBLE where Ks[i,j] = 0
# state[i,j] = UNBURNED elsewhere
def initialize_state_grid(ignition, Ks):
    state = np.full(ignition.shape, 0, dtype=np.int8) # Start with all UNBURNED
    state[ignition == 1] = 1  # BURNING
    state[Ks == 0] = -1  # NON_COMBUSTIBLE
    return state

# Get weather values at current time step (interpolation)
# -------------------------------------------------------------------------------
# Lookup the weather data for current time step
def get_weather_values(weather_data, current_time):
    # Flooring time to closest hour
    current_hour = current_time.floor('h')
        
    # Get corresponding row of data
    current_weather_mask = weather_data['timestamp'] == current_hour
    current_weather = weather_data[current_weather_mask].iloc[0]
    return current_weather

# Calculate adaptive time step based on current conditions
# -------------------------------------------------------------------------------
# def calculate_time_step(weather_values,ca_data, R0, m, Kr, c1, a_s, L):
#         # Δt = m × (L / Rmax)
#         # Rmax = max possible spread rate = R0 × max(Kφ) × max(Kθ) × max(Ks) × Kr
        
#         # max(Kφ)
#         wind_factor = math.exp(np.max(weather_values['wind_speed']) * c1)
        
#         # max(Kθ) = 1 (when spread direction perfectly aligned with wind)
#         max_slope = np.radians(np.max(ca_data['slope']))
#         max_K0 = np.exp(a_s * max_slope)  # max(Ks)
        
#         # max(Ks) = 1 max fuel type
#         max_Ks = 1
        
#         # Calculate Rmax        
#         Rmax = R0 * wind_factor * max_K0 * max_Ks * Kr
        
#         # Calculate delta T
#         delta_t = m * (L/Rmax)
#         return delta_t

def calculate_time_step(weather_values, ca_data, R0, m, Kr, c1, a_s, L):
    """
    Calculate adaptive time step based on REASONABLE maximum conditions.
    
    FIXED: Uses 90th percentile instead of absolute maximum to avoid
    extreme outliers from distant parts of the study area.
    """
    # Use 90th percentile wind speed instead of absolute max
    wind_p90 = np.percentile(weather_values['wind_speed'], 90)
    wind_factor = math.exp(wind_p90 * c1)
    
    # Use reasonable max slope (30 degrees) instead of data max
    # 30 degrees is already quite steep for fire spread
    reasonable_max_slope = np.radians(30)  
    max_K0 = np.exp(a_s * reasonable_max_slope)
    
    # max(Ks) = 1 (grassland)
    max_Ks = 1
    
    # Calculate Rmax        
    Rmax = R0 * wind_factor * max_K0 * max_Ks * Kr
    
    # Calculate delta_t
    delta_t = m * (L / Rmax)
    
    print(f"  Adaptive time step calculation:")
    print(f"    Wind (90th percentile): {wind_p90:.2f} m/s")
    print(f"    Wind factor: {wind_factor:.3f}")
    print(f"    Slope factor: {max_K0:.3f}")
    print(f"    Rmax: {Rmax:.3f} m/min")
    print(f"    Delta_t: {delta_t:.3f} minutes ({delta_t*60:.1f} seconds)")
    
    return delta_t

# Calculate spotting distance
# -------------------------------------------------------------------------------
def calculate_spotting_distance(wind_speed, cell_size):
    # Constants
    spotting_threshold = 8.0 #m/s
    distance_coefficient = 50 # meters per m/s above threshold
    
    # Excess wind speed above threshold
    excess_wind = wind_speed - spotting_threshold
    if excess_wind <= 0:
        return 0
    
    # Linear relationship
    spotting_distance_meters = distance_coefficient * excess_wind
    
    # Convert to number of cells
    spotting_distance_cells = round(spotting_distance_meters / cell_size)
    
    # Safety cap
    max_spotting = 50 # cells
    spotting_distance_cells = min(spotting_distance_cells, max_spotting)
    
    return spotting_distance_cells

# Calculate cells ignited along wind vector (Freire)
# -------------------------------------------------------------------------------
def trace_wind_vector(start, direction, distance, ca_data, state):
    """
    Traces a path along the wind direction and returns cells to ignite
    
    Parameters:
        start: (row, col) - starting burning cell
        direction: wind direction in radians (0=North, clockwise)
        distance: how far to trace (in number of cells)
        ca_data: dictionary with 'state', 'Ks', 'shape', etc.
    
    Returns:
        List of (row, col) tuples representing cells to spot-ignite
    """
    # Unpacl parameters
    start_row, start_col = start # Starting cell
    rows, cols = ca_data['shape'] # Grid dimensions
    
    # Initialize list of spotted cells
    spotted_cells = []
    
    # If no trace found
    if distance <= 0:
        return spotted_cells
    
    # ---------------------------------------------------------------
    # Calculate wind vector components
    # ---------------------------------------------------------------
    # Convert wind direction to movement in grid space
    # Remember: row increases downward (South), col increases rightward (East)
    # Wind direction: 0 = North, π/2 = East, π = South, 3π/2 = West
    
    delta_row = distance * math.cos(direction)
    delta_col = distance * math.sin(direction)
    
    # ---------------------------------------------------------------
    # Trace along the vector with small steps
    # ---------------------------------------------------------------
    
    steps = distance * 2
    
    for step in range(steps):
        
        # Calculate fractional profess along vector
        progress = step / steps
        
        # Calculate current position along the vector
        current_row = start_row + (delta_row * progress)
        current_col = start_col + (delta_col * progress)
        
        # Convert to cell indices (round to nearest integer)
        cell_row = round(current_row)
        cell_col = round(current_col)
        
        # ---------------------------------------------------------------
        # Boundary check
        # --------------------------------------------------------------- 
        if cell_row < 0 or cell_row >= rows:
            continue
        if cell_col < 0 or cell_col >= cols:
            continue
                
        # --------------------------------------------------------------
        # Check if cell is valid for spotting
        # ---------------------------------------------------------------
        
        current_state = state[cell_row, cell_col]
        current_fuel = ca_data['Ks'][cell_row, cell_col]
        
        # Skip if already burned, burning, or non-combustible
        if current_state != 0: # Not UNBURNED
            continue
        # Skip if no fuel
        if current_fuel == 0:
            continue
        
        # If valid, add to spotted cells
        cell_tuple = (cell_row, cell_col)
        if cell_tuple not in spotted_cells:
            spotted_cells.append(cell_tuple)
            
    return spotted_cells
        
        

# Get burning cells
# -------------------------------------------------------------------------------
# Returns list of (row, col) tuples where state == BURNING
def get_burning_cell_indices(state):
    ignitions = np.argwhere(state == 1)
    return [tuple(idx) for idx in ignitions] # Return a list of tuples of the indices
    
# Calculate spread probability from burning cell to neighbor
# -------------------------------------------------------------------------------
def calculate_spread_probability(from_cell, to_cell, direction, ca_data, weather, R0, Kr, c1, c2, a_s, delta_t):
    # R = R0 × Kφ × Kθ × Ks × Kr
    # p_spread = f(R, distance, Δt)
    # Unpack parameters
    i, j = from_cell
    ni, nj = to_cell
    di, dj = direction
    
    # -------------------------------------------------------------
    # Wind factor
    # Kφ = exp[V × (c1 + c2 × (cos(θ) - 1))]
    # - V = wind speed at current time step (m/s)
    # - θ = angle between wind direction and fire spread direction
    # - c1 = 0.045
    # - c2 = 0.131
    V = weather['wind_speed']
    spread_direction = np.atan2((nj-j), -(ni-i))
    wind_direction = weather['wind_direction']
    angle_diff = abs(spread_direction - wind_direction)
    # Handle angle wrap-around (0 to 2π)
    if angle_diff > math.pi:
        angle_diff = 2 * math.pi - angle_diff
    # Calculate wind factor
    wind_factor = math.exp(V * ( c1 + c2 * (math.cos(angle_diff) - 1)))
    
    # -------------------------------------------------------------
    # Slope factor
    # Kθ = exp[as × θs]
    # - as = 0.078
    # - θs = slope angle in direction of fire spread (math.radians)
    elev_from = ca_data['elevation'][i, j]      # Burning cell
    elev_to = ca_data['elevation'][ni, nj]      # Neighbor cell
    # Elevation difference
    delta_elevation = elev_to - elev_from
    # Distance (already calculated in your code)
    if abs(di) + abs(dj) == 1:  # Adjacent
        distance = ca_data['cell_size']
    else:  # Diagonal
        distance = ca_data['cell_size'] * math.sqrt(2)

    # Directional slope angle (radians)
    slope_angle = math.atan(delta_elevation / distance)

    # Slope factor
    slope_factor = math.exp(a_s * slope_angle)
    
    # -------------------------------------------------------------
    # Fuel factor (from fuel type)
    fuel_factor = ca_data['Ks'][ni, nj]  # Assuming Ks is normalized [0-1]
        
    # --------------------------------------------------------------
    # Local R calculation  
    # Base spread probability (normalized by distance)
    base_prob = R0 * wind_factor * slope_factor * fuel_factor * Kr
    
    # Convert to a probability between 0 and 1 (using a logistic function)
    p_spread = 1 - math.exp(-base_prob * delta_t / distance)
    
    return p_spread


# ====================================================================
# SIMULATION FUNCTION
# ====================================================================
        
def run_ca_simulation(ca_data, max_time_steps=1000, Kr=1.0):
    
    # ----------------------------------------------------------------
    # INITIALIZATION
    # ----------------------------------------------------------------
    
    # Set constants (from Rui et al. 2018 and Freire 2019)
    R0 = 0.8 #m/min             # Base spread rate
    m = 0.5 #0.125                   # Time step multiplier
    # Δt = m * (L / Rmax)       # Adaptive time step (calculate dynamically)
    L = ca_data['cell_size']    # Cell size (m)
    c1 = 0.045                  # Wind coefficient 1 (from Freire 2019)
    c2 = 0.131                  # Wind coefficient 2 (from Freire 2019)
    a_s = 0.078                 # Slope coefficient (from Freire 2019)
    neighbors = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1)
    ] # Moore neighborhood (8 neighbors)


    
    # Set variables from ca_data
    rows, cols = ca_data['shape'] # Get grid dimensions
    ignition_time = ca_data['ignition_time'] # Ignition time (datetime object)
    weather_values = ca_data['weather'] # Weather DataFrame (timestamp, wind_speed, wind_direction, temperature, RH)
    
    # Cell state grid
    state = initialize_state_grid(ca_data['ignition'], ca_data['Ks'])

    # Burn time tracking (-1 = not burned yet)
    burn_time = np.full((rows, cols), -1, dtype=np.int32)
    burn_time[state == 1] = 0  # Ignition cells burned at t=0
    
    # Calculate adaptive time step
    #delta_t = calculate_time_step(weather_values,ca_data, R0, m, Kr, c1, a_s, L)
    delta_t = 2.0 # Typically Δt ≈ 2-4 minutes
    
    # Fire progression history (optional, for visualization)
    # fire_progression = []
    
    # -------------------------------------------------------------------
    # TIME STEPPING LOOP
    # -------------------------------------------------------------------
    for t in range(max_time_steps):
        
        # Record current state
        # fire_progression.append(state.copy())
        
        # Get current weather conditions
        current_time = ignition_time + pd.Timedelta(minutes=t * delta_t)
        weather_now = get_weather_values(weather_values, current_time)
            # Returns: {wind_speed, wind_direction, temperature, RH}
        
        # Find all currently burning cells
        burning_cells = get_burning_cell_indices(state)
            # Returns list of (row, col) tuples where state == BURNING
        print(f"t={t}: Burning cells: {len(burning_cells)}, Time: {current_time}")

        # If no burning cells, fire is extinguished → STOP
        if len(burning_cells) == 0:
            print(f"Fire extinguished at time step {t}")
            break
        
        # -------------------------------------------------------------------
        # SPREAD TO NEIGHBORS (Standard CA Rule)
        # -------------------------------------------------------------------
        new_ignitions = []  # Track new cells that will ignite
        
        for (i, j) in burning_cells:
            #neighbors = state[i-1:i+2, j-1:j+2]  # Get 8 neighbors (including diagonals)
            # Check all 8 neighbors
            for (di, dj) in neighbors:
                ni, nj = i + di, j + dj
                
                # Boundary check
                if not (0 <= ni < rows and 0 <= nj < cols):
                    continue
                
                # Skip if neighbor already burned or burning
                if state[ni, nj] != 0:  # Not UNBURNED
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
                    
        if t < 10:  # Monitor first 10 timesteps
            print(f"  → New ignitions this timestep: {len(new_ignitions)}")
        
        # -------------------------------------------------------------------
        # WIND-DRIVEN SPOTTING (Freire Enhancement)
        # -------------------------------------------------------------------
        if weather_now['wind_speed'] > 8.0: # Spotting threshold (m/s) based on Freire 2019
            
            for (i, j) in burning_cells:
                
                # Check each neighbor that just ignited
                for (ni, nj) in new_ignitions:
                    
                    # Calculate spread direction
                    spread_direction = np.atan2((nj-j), -(ni-i))
                    
                    # Check if spread is aligned with wind
                    angle_diff = abs(spread_direction - weather_now['wind_direction'])
                    angle_diff = min(angle_diff, 2*np.pi - angle_diff)  # Wrap around
                    
                    if angle_diff < math.pi / 10: # Within spotting angle (π/10 radians) based on Freire 2019
                        
                        # Calculate spotting distance
                        spot_distance = calculate_spotting_distance(weather_now['wind_speed'], ca_data['cell_size'])
                            # e.g., spot_distance = int(wind_speed / 2)  [cells]
                        
                        # Ignite cells along wind vector
                        spotted_cells = trace_wind_vector(
                            start=(i, j),
                            direction=weather_now['wind_direction'],
                            distance=spot_distance,
                            ca_data=ca_data,
                            state=state
                        )
                        
                        new_ignitions.extend(spotted_cells)
        
        # -------------------------------------------------------------------
        # UPDATE CELL STATES
        # -------------------------------------------------------------------
        # Burning → Burned
        state[state == 1] = 2  # All currently burning cells become burned
        
        # New ignitions → Burning
        for (ni, nj) in set(new_ignitions):  # Use set to remove duplicates
            if state[ni, nj] == 0:
                state[ni, nj] = 1  # Ignite new cell
                burn_time[ni, nj] = t + 1
        
        # Check for maximum time (safety break)
        if t == max_time_steps - 1:
            print(f"WARNING: Reached max time steps ({max_time_steps})")
            break
    
    # -------------------------------------------------------------------
    # RETURN RESULTS
    # -------------------------------------------------------------------
    return {
        'burn_time': burn_time,        # When each cell burned (-1 = unburned)
        'final_state': state,          # Final cell states
        # 'fire_progression': fire_progression,  # State at each time step
        'time_step_minutes': delta_t,
        'total_burned_cells': np.sum(state == 2)
    }
