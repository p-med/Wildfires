"""
Monte Carlo Simulation Framework for CA Fire Model
Runs multiple stochastic realizations and aggregates uncertainty

Paulo Medina - Chaco Fire Model
"""

import numpy as np
import rasterio
from tqdm import tqdm  # Progress bar (optional)

# ============================================================================
# MONTE CARLO SIMULATION RUNNER
# ============================================================================

def run_monte_carlo_simulation(ca_data, ca_model, n_runs=50, Kr=1.0, 
                               max_time_steps=1000, verbose=False, seed=None, R0=0.8, delta_t = None , m = 1):
    """
    Run multiple stochastic realizations of fire spread model.
    
    Args:
        ca_data: Dictionary with CA inputs (from prepare_ca_inputs)
        ca_model: Module with run_ca_simulation function
        n_runs: Number of stochastic realizations (default: 50)
        Kr: Time correction factor (default: 1.0)
        max_time_steps: Maximum timesteps per simulation
        verbose: Print detailed output for each run
        seed: Random seed for reproducibility (optional)
    
    Returns:
        monte_carlo_results: Dictionary with aggregated results
    """
    print(f"\n{'='*70}")
    print(f"Running Monte Carlo Simulation: {n_runs} realizations")
    print(f"Parameters: Kr={Kr}, max_time_steps={max_time_steps}")
    print(f"{'='*70}\n")
    
    # Set random seed if provided
    if seed is not None:
        np.random.seed(seed)
        import random
        random.seed(seed)
    
    # Initialize storage for all runs
    rows, cols = ca_data['shape']
    
    # Burn probability: accumulate binary burn/no-burn for each cell
    burn_count = np.zeros((rows, cols), dtype=np.int32)
    
    # Burn time accumulation: sum of burn times (for calculating mean)
    burn_time_sum = np.zeros((rows, cols), dtype=np.float64)
    burn_time_squared_sum = np.zeros((rows, cols), dtype=np.float64)
    
    # Store individual run results for detailed analysis
    all_burn_times = []
    all_burned_cells = []
    all_final_states = []
    
    # Track simulation statistics
    simulation_stats = {
        'total_burned_cells': [],
        'simulation_time_steps': [],
        'extinguished_early': 0,
        'reached_max_steps': 0
    }
    
    # ========================================================================
    # RUN SIMULATIONS
    # ========================================================================
    
    print("Running simulations...")
    for run_id in tqdm(range(n_runs), desc="Progress"):
        
        if verbose:
            print(f"\n{'='*50}")
            print(f"Run {run_id + 1}/{n_runs}")
            print(f"{'='*50}")

        # Run single simulation
        result = ca_model.run_ca_simulation(
            ca_data, 
            Kr=Kr, 
            max_time_steps=max_time_steps,
            R0 = R0,
            delta_t = delta_t,
            m = m
        )
        
        # Extract results
        burn_time = result['burn_time']
        final_state = result['final_state']
        total_burned = result['total_burned_cells']
        
        # Store run results
        all_burn_times.append(burn_time)
        all_burned_cells.append(total_burned)
        all_final_states.append(final_state)
        
        # Update burn probability (count cells that burned)
        burned_mask = (burn_time >= 0)  # Cells that burned (t >= 0)
        burn_count += burned_mask.astype(np.int32)
        
        # Update burn time statistics (only for cells that burned)
        burn_time_valid = np.where(burned_mask, burn_time, 0)
        burn_time_sum += burn_time_valid
        burn_time_squared_sum += burn_time_valid ** 2
        
        # Track simulation statistics
        simulation_stats['total_burned_cells'].append(total_burned)
        
        # Count time steps (find last burning timestep)
        max_burn_time = np.max(burn_time)
        simulation_stats['simulation_time_steps'].append(max_burn_time + 1)
        
        # Check termination reason
        if max_burn_time < max_time_steps - 1:
            simulation_stats['extinguished_early'] += 1
        else:
            simulation_stats['reached_max_steps'] += 1
        
        if not verbose:
            # Print summary for non-verbose mode
            if (run_id + 1) % 10 == 0 or run_id == 0:
                print(f"  Run {run_id + 1}: {total_burned} cells burned")
    
    # ========================================================================
    # AGGREGATE RESULTS
    # ========================================================================
    
    print(f"\n{'='*70}")
    print("Aggregating results...")
    print(f"{'='*70}\n")
    
    # Burn probability: fraction of runs where each cell burned
    burn_probability = burn_count / n_runs
    
    # Mean burn time (only for cells that burned at least once)
    mean_burn_time = np.where(
        burn_count > 0,
        burn_time_sum / burn_count,
        -1  # -1 = never burned
    )
    
    # Standard deviation of burn time
    # Var(X) = E[X²] - E[X]²
    variance_burn_time = np.where(
        burn_count > 0,
        (burn_time_squared_sum / burn_count) - (burn_time_sum / burn_count) ** 2,
        0
    )
    std_burn_time = np.sqrt(variance_burn_time)
    
    # Confidence intervals for burn probability (Wilson score interval)
    # For 95% CI: z = 1.96
    z = 1.96
    p = burn_probability
    n = n_runs
    
    # Wilson score interval
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denominator
    margin = z * np.sqrt((p * (1 - p) / n + z**2 / (4*n**2))) / denominator
    
    ci_lower = np.maximum(center - margin, 0)
    ci_upper = np.minimum(center + margin, 1)
    
    # ========================================================================
    # SIMULATION STATISTICS SUMMARY
    # ========================================================================
    
    burned_cells_array = np.array(simulation_stats['total_burned_cells'])
    
    summary_stats = {
        'n_runs': n_runs,
        'Kr': Kr,
        'mean_burned_cells': np.mean(burned_cells_array),
        'median_burned_cells': np.median(burned_cells_array),
        'std_burned_cells': np.std(burned_cells_array),
        'min_burned_cells': np.min(burned_cells_array),
        'max_burned_cells': np.max(burned_cells_array),
        'q25_burned_cells': np.percentile(burned_cells_array, 25),
        'q75_burned_cells': np.percentile(burned_cells_array, 75),
        'extinguished_early_pct': 100 * simulation_stats['extinguished_early'] / n_runs,
        'reached_max_steps_pct': 100 * simulation_stats['reached_max_steps'] / n_runs
    }
    
    # Print summary
    print(f"Monte Carlo Simulation Summary:")
    print(f"  Number of runs: {summary_stats['n_runs']}")
    print(f"  Kr parameter: {summary_stats['Kr']}")
    print(f"\nBurned Cells Statistics:")
    print(f"  Mean:   {summary_stats['mean_burned_cells']:.1f} cells")
    print(f"  Median: {summary_stats['median_burned_cells']:.0f} cells")
    print(f"  Std:    {summary_stats['std_burned_cells']:.1f} cells")
    print(f"  Min:    {summary_stats['min_burned_cells']} cells")
    print(f"  Max:    {summary_stats['max_burned_cells']} cells")
    print(f"  Q25:    {summary_stats['q25_burned_cells']:.0f} cells")
    print(f"  Q75:    {summary_stats['q75_burned_cells']:.0f} cells")
    print(f"\nSimulation Termination:")
    print(f"  Extinguished early: {summary_stats['extinguished_early_pct']:.1f}%")
    print(f"  Reached max steps:  {summary_stats['reached_max_steps_pct']:.1f}%")
    
    # Calculate total area statistics (hectares)
    cell_area_ha = (ca_data['cell_size'] ** 2) / 10000  # 30m x 30m = 0.09 ha
    
    summary_stats['mean_burned_area_ha'] = summary_stats['mean_burned_cells'] * cell_area_ha
    summary_stats['median_burned_area_ha'] = summary_stats['median_burned_cells'] * cell_area_ha
    summary_stats['std_burned_area_ha'] = summary_stats['std_burned_cells'] * cell_area_ha
    
    print(f"\nBurned Area Statistics (hectares):")
    print(f"  Mean:   {summary_stats['mean_burned_area_ha']:.2f} ha")
    print(f"  Median: {summary_stats['median_burned_area_ha']:.2f} ha")
    print(f"  Std:    {summary_stats['std_burned_area_ha']:.2f} ha")
    
    print(f"\n{'='*70}\n")
    
    # ========================================================================
    # PACKAGE RESULTS
    # ========================================================================
    
    monte_carlo_results = {
        # Aggregated rasters
        'burn_probability': burn_probability,
        'mean_burn_time': mean_burn_time,
        'std_burn_time': std_burn_time,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'burn_count': burn_count,
        
        # Individual run results
        'all_burn_times': all_burn_times,
        'all_burned_cells': all_burned_cells,
        'all_final_states': all_final_states,
        
        # Summary statistics
        'summary_stats': summary_stats,
        'simulation_stats': simulation_stats,
        
        # Metadata
        'ca_data': ca_data,
        'n_runs': n_runs,
        'Kr': Kr
    }
    
    return monte_carlo_results

# ============================================================================
# EXPORT UNCERTAINTY RASTERS
# ============================================================================

def export_monte_carlo_results(mc_results, output_dir='monte_carlo_results', 
                               event_id=None, Kr=None):
    """
    Export Monte Carlo results as GeoTIFF rasters.
    
    Args:
        mc_results: Dictionary from run_monte_carlo_simulation
        output_dir: Directory to save rasters
        event_id: Optional event ID for filename
        Kr: Optional Kr value for filename
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    ca_data = mc_results['ca_data']
    
    # Create filename prefix
    prefix = f"event_{event_id}_Kr_{Kr}" if event_id and Kr else "mc_results"
    
    print(f"\nExporting Monte Carlo results to {output_dir}/...")
    
    # Define rasters to export
    rasters_to_export = {
        'burn_probability': {
            'data': mc_results['burn_probability'],
            'dtype': rasterio.float32,
            'description': 'Probability of burning (0-1)'
        },
        'mean_burn_time': {
            'data': mc_results['mean_burn_time'],
            'dtype': rasterio.float32,
            'description': 'Mean burn time (timesteps)',
            'nodata': -1
        },
        'std_burn_time': {
            'data': mc_results['std_burn_time'],
            'dtype': rasterio.float32,
            'description': 'Std dev of burn time'
        },
        'ci_lower_95': {
            'data': mc_results['ci_lower'],
            'dtype': rasterio.float32,
            'description': '95% CI lower bound'
        },
        'ci_upper_95': {
            'data': mc_results['ci_upper'],
            'dtype': rasterio.float32,
            'description': '95% CI upper bound'
        },
        'burn_count': {
            'data': mc_results['burn_count'],
            'dtype': rasterio.int32,
            'description': 'Number of runs where cell burned'
        }
    }
    
    # Export each raster
    for name, spec in rasters_to_export.items():
        output_path = f'{output_dir}/{prefix}_{name}.tif'
        
        with rasterio.open(
            output_path,
            'w',
            driver='GTiff',
            height=ca_data['shape'][0],
            width=ca_data['shape'][1],
            count=1,
            dtype=spec['dtype'],
            crs=ca_data['crs'],
            transform=ca_data['transform'],
            compress='lzw',
            nodata=spec.get('nodata', None)
        ) as dst:
            dst.write(spec['data'], 1)
            dst.set_band_description(1, spec['description'])
        
        print(f"  Exported: {output_path}")
    
    # Export summary statistics as text
    stats_path = f'{output_dir}/{prefix}_summary.txt'
    with open(stats_path, 'w') as f:
        f.write("Monte Carlo Simulation Summary\n")
        f.write("=" * 70 + "\n\n")
        
        summary = mc_results['summary_stats']
        for key, value in summary.items():
            f.write(f"{key}: {value}\n")
    
    print(f"  Exported: {stats_path}")
    print(f"\nDone. All results exported to {output_dir}/\n")

# ============================================================================
# CLASSIFY BURN PROBABILITY INTO RISK ZONES
# ============================================================================

def classify_burn_probability(burn_probability, thresholds=None):
    """
    Classify burn probability into discrete risk zones.
    
    Args:
        burn_probability: 2D array of burn probabilities (0-1)
        thresholds: List of thresholds (default: [0.1, 0.25, 0.5, 0.75])
    
    Returns:
        risk_zones: 2D array with integer classes
        class_labels: Dictionary mapping class to label
    """
    if thresholds is None:
        thresholds = [0.1, 0.25, 0.5, 0.75]
    
    # Create classified array
    risk_zones = np.zeros_like(burn_probability, dtype=np.uint8)
    
    # Assign classes
    risk_zones[burn_probability == 0] = 0  # No risk
    risk_zones[(burn_probability > 0) & (burn_probability <= thresholds[0])] = 1  # Very low
    risk_zones[(burn_probability > thresholds[0]) & (burn_probability <= thresholds[1])] = 2  # Low
    risk_zones[(burn_probability > thresholds[1]) & (burn_probability <= thresholds[2])] = 3  # Moderate
    risk_zones[(burn_probability > thresholds[2]) & (burn_probability <= thresholds[3])] = 4  # High
    risk_zones[burn_probability > thresholds[3]] = 5  # Very high
    
    class_labels = {
        0: f"No risk (p = 0)",
        1: f"Very low (0 < p ≤ {thresholds[0]})",
        2: f"Low ({thresholds[0]} < p ≤ {thresholds[1]})",
        3: f"Moderate ({thresholds[1]} < p ≤ {thresholds[2]})",
        4: f"High ({thresholds[2]} < p ≤ {thresholds[3]})",
        5: f"Very high (p > {thresholds[3]})"
    }
    
    # Print classification summary
    print("\nBurn Probability Classification:")
    for class_id, label in class_labels.items():
        count = np.sum(risk_zones == class_id)
        pct = 100 * count / risk_zones.size
        print(f"  Class {class_id} - {label}: {count:,} cells ({pct:.2f}%)")
    
    return risk_zones, class_labels

# ============================================================================
# COMPARE TO OBSERVED BURN SCAR
# ============================================================================

def compare_to_observed(mc_results, observed_burn_scar):
    """
    Compare Monte Carlo results to observed MODIS burn scar.
    
    Args:
        mc_results: Dictionary from run_monte_carlo_simulation
        observed_burn_scar: 2D binary array (1 = burned, 0 = not burned)
    
    Returns:
        comparison_metrics: Dictionary with accuracy metrics
    """
    burn_probability = mc_results['burn_probability']
    
    # Ensure arrays are same shape
    if burn_probability.shape != observed_burn_scar.shape:
        print("WARNING: Simulated and observed grids have different shapes!")
        print(f"  Simulated: {burn_probability.shape}")
        print(f"  Observed:  {observed_burn_scar.shape}")
        return None
    
    # Calculate metrics for different probability thresholds
    thresholds = [0.1, 0.25, 0.5, 0.75, 0.9]
    
    print("\n" + "="*70)
    print("Comparison to Observed Burn Scar")
    print("="*70 + "\n")
    
    results = {}
    
    for threshold in thresholds:
        # Binary prediction: burned if p > threshold
        predicted = (burn_probability > threshold).astype(int)
        
        # Confusion matrix
        true_positive = np.sum((predicted == 1) & (observed_burn_scar == 1))
        false_positive = np.sum((predicted == 1) & (observed_burn_scar == 0))
        true_negative = np.sum((predicted == 0) & (observed_burn_scar == 0))
        false_negative = np.sum((predicted == 0) & (observed_burn_scar == 1))
        
        # Metrics
        accuracy = (true_positive + true_negative) / predicted.size
        
        if (true_positive + false_positive) > 0:
            precision = true_positive / (true_positive + false_positive)
        else:
            precision = 0
        
        if (true_positive + false_negative) > 0:
            recall = true_positive / (true_positive + false_negative)
        else:
            recall = 0
        
        if (precision + recall) > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        else:
            f1 = 0
        
        results[threshold] = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'true_positive': true_positive,
            'false_positive': false_positive,
            'true_negative': true_negative,
            'false_negative': false_negative
        }
        
        print(f"Threshold p > {threshold}:")
        print(f"  Accuracy:  {accuracy:.3f}")
        print(f"  Precision: {precision:.3f}")
        print(f"  Recall:    {recall:.3f}")
        print(f"  F1 Score:  {f1:.3f}")
        print(f"  TP: {true_positive}, FP: {false_positive}, TN: {true_negative}, FN: {false_negative}")
        print()
    
    # Area comparison
    simulated_mean_area = mc_results['summary_stats']['mean_burned_cells']
    observed_area = np.sum(observed_burn_scar)
    area_error = abs(simulated_mean_area - observed_area) / observed_area * 100
    
    print(f"Area Comparison:")
    print(f"  Simulated (mean): {simulated_mean_area:.1f} cells")
    print(f"  Observed:         {observed_area} cells")
    print(f"  Relative error:   {area_error:.1f}%")
    print("="*70 + "\n")
    
    comparison_metrics = {
        'threshold_metrics': results,
        'simulated_area': simulated_mean_area,
        'observed_area': observed_area,
        'area_error_pct': area_error
    }
    
    return comparison_metrics