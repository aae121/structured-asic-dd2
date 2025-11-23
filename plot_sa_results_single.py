#!/usr/bin/env python3
"""
plot_sa_results_single.py

Generate SA analysis plots for a single design specified as command-line argument.
"""

import sys
import csv
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

def create_plots(design_name, csv_file):
    """Create SA analysis plots for a design"""
    
    # Load data
    data = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['alpha'] = float(row['alpha'])
            row['moves'] = int(row['moves'])
            row['T_initial'] = float(row['T_initial'])
            row['p_refine'] = float(row['p_refine'])
            row['final_hpwl'] = float(row['final_hpwl'])
            row['runtime_sec'] = float(row['runtime_sec'])
            row['improvement_pct'] = float(row['improvement_pct'])
            data.append(row)
    
    if not data:
        print("ERROR: No data found!")
        return False
    
    # Create output directory
    output_dir = Path(f"plots_{design_name}")
    output_dir.mkdir(exist_ok=True)
    
    # Extract values
    runtimes = [row['runtime_sec'] for row in data]
    hpwls = [row['final_hpwl'] for row in data]
    alphas = [row['alpha'] for row in data]
    
    # Main scatter plot: Runtime vs HPWL
    plt.figure(figsize=(12, 8))
    scatter = plt.scatter(runtimes, hpwls, c=alphas, s=60, alpha=0.7, cmap='viridis')
    plt.colorbar(scatter, label='Cooling Rate (α)')
    plt.xlabel('Runtime (seconds)', fontsize=12)
    plt.ylabel('Final HPWL (site units)', fontsize=12)
    plt.title(f'SA Performance: Runtime vs Final HPWL - {design_name}\\n(Colored by Cooling Rate α)', 
              fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    
    # Annotations
    best_idx = min(range(len(data)), key=lambda i: data[i]['final_hpwl'])
    fastest_idx = min(range(len(data)), key=lambda i: data[i]['runtime_sec'])
    
    plt.annotate(f'Best HPWL\\n({data[best_idx]["final_hpwl"]:.0f})', 
                xy=(data[best_idx]['runtime_sec'], data[best_idx]['final_hpwl']),
                xytext=(10, 10), textcoords='offset points', 
                bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    plt.annotate(f'Fastest\\n({data[fastest_idx]["runtime_sec"]:.1f}s)', 
                xy=(data[fastest_idx]['runtime_sec'], data[fastest_idx]['final_hpwl']),
                xytext=(10, -20), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='lightblue', alpha=0.7),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    plt.tight_layout()
    plt.savefig(output_dir / f"sa_runtime_vs_hpwl_{design_name}.png", dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_dir}/sa_runtime_vs_hpwl_{design_name}.png")
    plt.close()
    
    # Pareto frontier
    data_sorted = sorted(data, key=lambda x: x['runtime_sec'])
    pareto_points = []
    min_hpwl = float('inf')
    
    for point in data_sorted:
        if point['final_hpwl'] < min_hpwl:
            pareto_points.append(point)
            min_hpwl = point['final_hpwl']
    
    plt.figure(figsize=(10, 6))
    plt.scatter(runtimes, hpwls, alpha=0.6, s=40, color='lightgray', label='All configurations')
    
    pareto_runtimes = [p['runtime_sec'] for p in pareto_points]
    pareto_hpwls = [p['final_hpwl'] for p in pareto_points]
    plt.scatter(pareto_runtimes, pareto_hpwls, color='red', s=80, label='Pareto Frontier', zorder=5)
    
    pareto_sorted = sorted(pareto_points, key=lambda x: x['runtime_sec'])
    pareto_x = [p['runtime_sec'] for p in pareto_sorted]
    pareto_y = [p['final_hpwl'] for p in pareto_sorted]
    plt.plot(pareto_x, pareto_y, 'r--', alpha=0.7, linewidth=2)
    
    plt.xlabel('Runtime (seconds)', fontsize=12)
    plt.ylabel('Final HPWL (site units)', fontsize=12)
    plt.title(f'Pareto Frontier - {design_name}', fontsize=14, fontweight='bold')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / f"pareto_frontier_{design_name}.png", dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_dir}/pareto_frontier_{design_name}.png")
    plt.close()
    
    # Generate summary
    best_hpwl_row = min(data, key=lambda x: x['final_hpwl'])
    fastest_row = min(data, key=lambda x: x['runtime_sec'])
    
    summary = f"""
# SA Knob Exploration Analysis - {design_name}

## Experiment Overview
- Total configurations tested: {len(data)}
- Runtime range: {min(runtimes):.2f}s - {max(runtimes):.2f}s
- HPWL range: {min(hpwls):.0f} - {max(hpwls):.0f} site units

## Key Findings

### Best HPWL Configuration:
- Cooling Rate (α): {best_hpwl_row['alpha']}
- Moves per Temp: {best_hpwl_row['moves']}
- Final HPWL: {best_hpwl_row['final_hpwl']:.0f} site units
- Runtime: {best_hpwl_row['runtime_sec']:.2f}s
- Improvement: {best_hpwl_row['improvement_pct']:.1f}%

### Fastest Configuration:
- Cooling Rate (α): {fastest_row['alpha']}
- Moves per Temp: {fastest_row['moves']}
- Final HPWL: {fastest_row['final_hpwl']:.0f} site units
- Runtime: {fastest_row['runtime_sec']:.2f}s
- Improvement: {fastest_row['improvement_pct']:.1f}%

## Pareto Frontier
The Pareto frontier contains {len(pareto_points)} configurations.

## Recommendations
1. For best quality: Use α={best_hpwl_row['alpha']}, moves={best_hpwl_row['moves']}
2. For fastest execution: Use α={fastest_row['alpha']}, moves={fastest_row['moves']}
"""
    
    with open(output_dir / f"sa_analysis_summary_{design_name}.txt", 'w', encoding='utf-8') as f:
        f.write(summary)
    print(f"✓ Saved: {output_dir}/sa_analysis_summary_{design_name}.txt")
    
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python plot_sa_results_single.py <design_name>")
        sys.exit(1)
    
    design_name = sys.argv[1]
    csv_file = f"experiment_results_{design_name}.csv"
    
    print(f"\n{'='*70}")
    print(f"PLOTTING SA RESULTS: {design_name}")
    print(f"{'='*70}")
    
    if not Path(csv_file).exists():
        print(f"ERROR: {csv_file} not found!")
        sys.exit(1)
    
    success = create_plots(design_name, csv_file)
    
    if success:
        print(f"\n{'='*70}")
        print(f"✓ Plots complete for {design_name}")
        print(f"{'='*70}")
    else:
        print(f"\n✗ Failed to create plots for {design_name}")
        sys.exit(1)

if __name__ == "__main__":
    main()
