================================================================================
CELLULAR AUTOMATA FIRE SPREAD MODEL
Framework: Rui et al. (2018) with Freire & DaCamara (2019) enhancements
================================================================================

INPUT DATA STRUCTURE (from data_preparation_functions):
    ca_data = {
        'elevation': 2D array,
        'slope': 2D array (degrees),
        'aspect': 2D array (radians, 0=North),
        'Ks': 2D array (fuel coefficients),
        'ignition': 2D array (binary, initial fire cells),
        'weather': DataFrame (time, temp, RH, wind_speed, wind_direction),
        'ignition_time': datetime,
        'cell_size': 30 meters,
        'shape': (rows, cols)
    }

OUTPUT:
    - burn_time: 2D array (time step when each cell burned, -1=unburned)
    - fire_progression: List of 2D arrays (cell states at each time step)
    - burn_probability: 2D array (if ensemble mode, fraction of runs burned)

================================================================================
CELL STATES
================================================================================
    UNBURNED = 0
    BURNING = 1
    BURNED = 2
    NON_COMBUSTIBLE = -1  (water, urban, etc. - Ks = 0)

================================================================================
MODEL PARAMETERS (from Rui et al. 2018)
================================================================================
    R0 = 0.8 m/min          # Base spread rate (calibrate from literature/MCD64A1)
    m = 0.125               # Time step multiplier
    Δt = m × (L / Rmax)     # Adaptive time step (calculate dynamically)
    c1 = 0.045              # Wind coefficient 1 (from Freire 2019)
    c2 = 0.131              # Wind coefficient 2 (from Freire 2019)
    as = 0.078              # Slope coefficient (from Freire 2019)
    Kr = 1.0                # Time correction factor (will calibrate per event)
    
    SPOTTING_THRESHOLD = 8.0  # m/s, from Freire 2019
    SPOTTING_ANGLE = π/10     # radians, fire must spread within this angle of wind

================================================================================
NEIGHBORHOOD STRUCTURE (Moore 8-neighbors)
================================================================================
    NEIGHBORS = [
        (-1, -1), (-1, 0), (-1, 1),  # Top row
        ( 0, -1),          ( 0, 1),  # Middle row (skip center)
        ( 1, -1), ( 1, 0), ( 1, 1)   # Bottom row
    ]
    
    DISTANCES = {
        adjacent: L (30m),
        diagonal: L × √2 (42.43m)
    }
    
    ANGLES = {  # Direction from center to neighbor (radians, 0=North, clockwise)
        (-1,  0): 0,        # North
        (-1,  1): π/4,      # NE
        ( 0,  1): π/2,      # East
        ( 1,  1): 3π/4,     # SE
        ( 1,  0): π,        # South
        ( 1, -1): 5π/4,     # SW
        ( 0, -1): 3π/2,     # West
        (-1, -1): 7π/4      # NW
    }

================================================================================
MAIN SIMULATION LOOP (Single Run)
================================================================================

FUNCTION run_ca_simulation(ca_data, max_time_steps=1000, Kr=1.0):
    
    # -------------------------------------------------------------------
    # INITIALIZATION
    # -------------------------------------------------------------------
    rows, cols = ca_data['shape']
    
    # Cell state grid
    state = initialize_state_grid(ca_data['ignition'], ca_data['Ks'])
        # state[i,j] = BURNING where ignition[i,j] = 1
        # state[i,j] = NON_COMBUSTIBLE where Ks[i,j] = 0
        # state[i,j] = UNBURNED elsewhere
    
    # Burn time tracking (-1 = not burned yet)
    burn_time = np.full((rows, cols), -1, dtype=np.int32)
    burn_time[state == BURNING] = 0  # Ignition cells burned at t=0
    
    # Weather interpolation setup
    weather_interp = setup_weather_interpolator(ca_data['weather'], 
                                                 ca_data['ignition_time'])
    
    # Calculate adaptive time step
    Δt = calculate_time_step(ca_data, R0, m, Kr)
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
        current_time = ca_data['ignition_time'] + timedelta(minutes=t * Δt)
        weather_now = interpolate_weather(weather_interp, current_time)
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
                    R0=R0, Kr=Kr, c1=c1, c2=c2, as=as
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

================================================================================
ENSEMBLE MODE (Multiple Stochastic Runs)
================================================================================

FUNCTION run_ensemble_simulation(ca_data, n_runs=100, Kr=1.0):
    
    # Storage for ensemble results
    burn_count = np.zeros(ca_data['shape'], dtype=np.int32)
    burn_time_sum = np.zeros(ca_data['shape'], dtype=np.float32)
    
    for run in range(n_runs):
        
        # Run single simulation
        result = run_ca_simulation(ca_data, Kr=Kr)
        
        # Accumulate results
        burned_mask = (result['burn_time'] >= 0)
        burn_count[burned_mask] += 1
        
        # Sum burn times (for averaging)
        burn_time_sum += np.where(burned_mask, result['burn_time'], 0)
    
    # Calculate burn probability
    burn_probability = burn_count / n_runs
    
    # Calculate mean burn time (only for cells that burned in at least 1 run)
    mean_burn_time = np.where(
        burn_count > 0,
        burn_time_sum / burn_count,
        -1
    )
    
    return {
        'burn_probability': burn_probability,  # [0, 1]
        'mean_burn_time': mean_burn_time,      # Average time step burned
        'burn_count': burn_count,              # How many runs burned each cell
        'n_runs': n_runs
    }

================================================================================
KEY HELPER FUNCTIONS (Details for Next Phase)
================================================================================

1. calculate_spread_probability(from_cell, to_cell, direction, ca_data, weather, R0, Kr, ...)
   └─ Implements: R = R0 × Kφ × Kθ × Ks × Kr
   └─ Converts spread rate R to probability: p = f(R, Δt, distance)

2. calculate_time_step(ca_data, R0, m, Kr)
   └─ Adaptive: Δt = m × (L / Rmax)

3. interpolate_weather(weather_interp, current_time)
   └─ Linear interpolation between hourly ERA5 values

4. calculate_spotting_distance(wind_speed)
   └─ Empirical: e.g., cells = int(wind_speed / 2)

5. trace_wind_vector(start, direction, distance, ca_data)
   └─ Bresenham line algorithm to find cells along wind direction

6. calculate_angle(from_cell, to_cell)
   └─ Arctangent of dy/dx, convert to [0, 2π]

================================================================================
VALIDATION INTERFACE (Compare with Sentinel-2 / MCD64A1)
================================================================================

FUNCTION validate_simulation(ca_results, validation_raster):
    
    # Threshold probability (e.g., 0.5)
    predicted_burned = (ca_results['burn_probability'] > 0.5)
    
    # Load observed burn scar
    observed_burned = load_validation_raster(validation_raster)
    
    # Align grids (if needed)
    observed_burned_aligned = align_to_ca_grid(observed_burned, ca_data)
    
    # Calculate metrics
    metrics = {
        'kappa': calculate_kappa(predicted_burned, observed_burned_aligned),
        'accuracy': calculate_accuracy(predicted_burned, observed_burned_aligned),
        'omission': calculate_omission_error(predicted_burned, observed_burned_aligned),
        'commission': calculate_commission_error(predicted_burned, observed_burned_aligned),
        'rmse_burn_time': calculate_rmse_burn_time(
            ca_results['mean_burn_time'], 
            observed_burn_time_from_mcd64a1
        )
    }
    
    return metrics