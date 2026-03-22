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

# Initialize state grid
# -------------------------------------------------------------------------------
# Create an initial array of zeros and then set values based on ignition and Ks:
# state[i,j] = BURNING where ignition[i,j] = 1
# state[i,j] = NON_COMBUSTIBLE where Ks[i,j] = 0
# state[i,j] = UNBURNED elsewhere
def initialize_state_grid(ignition, Ks):
    state = np.full(ignition.shape, 0, dtype=np.int8)
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
    
def run_ca_simulation(ca_data, max_time_steps=1000, Kr=1.0):
    
    # -------------------------------------------------------------------
    # INITIALIZATION
    # -------------------------------------------------------------------
    
    # Set constants (from Rui et al. 2018 and Freire 2019)
    R0 = 0.8 #m/min          # Base spread rate
    m = 0.125               # Time step multiplier
    # Δt = m * (L / Rmax)     # Adaptive time step (calculate dynamically)
    L = 30.0                # Cell size (m)
    c1 = 0.045              # Wind coefficient 1 (from Freire 2019)
    c2 = 0.131              # Wind coefficient 2 (from Freire 2019)
    a_s = 0.078              # Slope coefficient (from Freire 2019)
    Kr = 1.0                # Time correction factor (will calibrate per event)

    
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
    delta_t = calculate_time_step(ca_data, R0, m, Kr)
        # Δt = m × (L / Rmax)
        # Rmax = max possible spread rate = R0 × max(Kφ) × max(Kθ) × max(Ks) × Kr
        # Typically Δt ≈ 2-4 minutes
    
    # Fire progression history (optional, for visualization)
    fire_progression = []
    
    # -------------------------------------------------------------------
    # TIME STEPPING LOOP
    # -------------------------------------------------------------------
    for t in range(max_time_steps):
        
        # Record current state
        fire_progression.append(state.copy())
        
        # Get current weather conditions
        current_time = ignition_time + pd.Timedelta(minutes=t * delta_t)
        weather_now = get_weather_values(weather_values, current_time)
            # Returns: {wind_speed, wind_direction, temperature, RH}
        
        # Find all currently burning cells
        burning_cells = get_burning_cell_indices(state)
            # Returns list of (row, col) tuples where state == BURNING
            
        # If no burning cells, fire is extinguished → STOP
        if len(burning_cells) == 0:
            print(f"Fire extinguished at time step {t}")
            break
        
        # -------------------------------------------------------------------
        # SPREAD TO NEIGHBORS (Standard CA Rule)
        # -------------------------------------------------------------------
        new_ignitions = []  # Track new cells that will ignite
        
        for (i, j) in burning_cells:
            
            # Check all 8 neighbors
            for (di, dj) in NEIGHBORS:
                ni, nj = i + di, j + dj
                
                # Boundary check
                if not (0 <= ni < rows and 0 <= nj < cols):
                    continue
                
                # Skip if neighbor already burned or burning
                if state[ni, nj] != UNBURNED:
                    continue
                
                # Calculate spread probability
                p_spread = calculate_spread_probability(
                    from_cell=(i, j),
                    to_cell=(ni, nj),
                    direction=(di, dj),
                    ca_data=ca_data,
                    weather=weather_now,
                    R0=R0, Kr=Kr, c1=c1, c2=c2, as=a_s
                )
                
                # Stochastic ignition
                if random.uniform(0, 1) < p_spread:
                    new_ignitions.append((ni, nj))
        
        # -------------------------------------------------------------------
        # WIND-DRIVEN SPOTTING (Freire Enhancement)
        # -------------------------------------------------------------------
        if weather_now['wind_speed'] > SPOTTING_THRESHOLD:
            
            for (i, j) in burning_cells:
                
                # Check each neighbor that just ignited
                for (ni, nj) in new_ignitions:
                    
                    # Calculate spread direction
                    spread_direction = calculate_angle(from_cell=(i,j), to_cell=(ni,nj))
                    
                    # Check if spread is aligned with wind
                    angle_diff = abs(spread_direction - weather_now['wind_direction'])
                    angle_diff = min(angle_diff, 2π - angle_diff)  # Wrap around
                    
                    if angle_diff < SPOTTING_ANGLE:
                        
                        # Calculate spotting distance
                        spot_distance = calculate_spotting_distance(weather_now['wind_speed'])
                            # e.g., spot_distance = int(wind_speed / 2)  [cells]
                        
                        # Ignite cells along wind vector
                        spotted_cells = trace_wind_vector(
                            start=(i, j),
                            direction=weather_now['wind_direction'],
                            distance=spot_distance,
                            ca_data=ca_data
                        )
                        
                        new_ignitions.extend(spotted_cells)
        
        # -------------------------------------------------------------------
        # UPDATE CELL STATES
        # -------------------------------------------------------------------
        # Burning → Burned
        state[state == BURNING] = BURNED
        
        # New ignitions → Burning
        for (ni, nj) in set(new_ignitions):  # Use set to remove duplicates
            if state[ni, nj] == UNBURNED:
                state[ni, nj] = BURNING
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
        'fire_progression': fire_progression,  # State at each time step
        'time_step_minutes': Δt,
        'total_burned_cells': np.sum(state == BURNED)
    }
