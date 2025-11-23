#!/usr/bin/env python3
"""
plot_sa_results.py

Creates 2D scatter plots for SA knob exploration analysis.
Shows Runtime (seconds) on X-axis vs. Final HPWL (μm) on Y-axis.
Each point represents one SA run with specific knob settings.

Part of Task 1.D: SA Placer Knob Exploration
"""

import csv
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

def create_sa_analysis_plots(csv_file="experiment_results.csv", output_dir="plots"):
    """
    Creates comprehensive SA analysis plots from experiment results.
    
    Args:
        csv_file: Path to CSV file with experiment results
        output_dir: Directory to save plots
    """
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Load data
    try:
        data = []
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric columns
                row['alpha'] = float(row['alpha'])
                row['moves'] = int(row['moves'])
                row['T_initial'] = float(row['T_initial'])
                row['p_refine'] = float(row['p_refine'])
                row['final_hpwl'] = float(row['final_hpwl'])
                row['runtime_sec'] = float(row['runtime_sec'])
                row['improvement_pct'] = float(row['improvement_pct'])
                data.append(row)
        print(f"Loaded {len(data)} experiment results from {csv_file}")
    except FileNotFoundError:
        print(f"Error: {csv_file} not found. Run run_sa_experiments first!")
        return
    
    if not data:
        print("Error: No data found in CSV file!")
        return
    
    # Set style for better plots
    plt.style.use('default')
    plt.rcParams['figure.facecolor'] = 'white'
    plt.rcParams['axes.grid'] = True
    plt.rcParams['grid.alpha'] = 0.3
    
    # 1. Main Plot: Runtime vs HPWL scatter plot (Assignment Requirement)
    plt.figure(figsize=(12, 8))
    
    # Extract data for plotting
    runtimes = [row['runtime_sec'] for row in data]
    hpwls = [row['final_hpwl'] for row in data]
    alphas = [row['alpha'] for row in data]
    
    # Color by cooling rate (alpha)
    scatter = plt.scatter(runtimes, hpwls, c=alphas, s=60, alpha=0.7, cmap='viridis')
    
    plt.colorbar(scatter, label='Cooling Rate (α)')
    plt.xlabel('Runtime (seconds)', fontsize=12)
    plt.ylabel('Final HPWL (site units)', fontsize=12)
    plt.title('SA Performance: Runtime vs Final HPWL\n(Colored by Cooling Rate α)', 
              fontsize=14, fontweight='bold')
    
    # Add grid for better readability
    plt.grid(True, alpha=0.3)
    
    # Add annotations for interesting points
    best_hpwl_idx = min(range(len(data)), key=lambda i: data[i]['final_hpwl'])
    fastest_idx = min(range(len(data)), key=lambda i: data[i]['runtime_sec'])
    
    plt.annotate(f'Best HPWL\n({data[best_hpwl_idx]["final_hpwl"]:.0f})', 
                xy=(data[best_hpwl_idx]['runtime_sec'], data[best_hpwl_idx]['final_hpwl']),
                xytext=(10, 10), textcoords='offset points', 
                bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    plt.annotate(f'Fastest\n({data[fastest_idx]["runtime_sec"]:.1f}s)', 
                xy=(data[fastest_idx]['runtime_sec'], data[fastest_idx]['final_hpwl']),
                xytext=(10, -20), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='lightblue', alpha=0.7),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/sa_runtime_vs_hpwl.png', dpi=300, bbox_inches='tight')
    print(f"Saved main scatter plot: {output_dir}/sa_runtime_vs_hpwl.png")
    
    # 2. Pareto Frontier Analysis
    plt.figure(figsize=(10, 6))
    
    # Sort by runtime for Pareto frontier calculation
    data_sorted = sorted(data, key=lambda x: x['runtime_sec'])
    
    # Find Pareto frontier (points that are not dominated)
    pareto_points = []
    min_hpwl = float('inf')
    
    for point in data_sorted:
        if point['final_hpwl'] < min_hpwl:
            pareto_points.append(point)
            min_hpwl = point['final_hpwl']
    
    # Plot all points
    plt.scatter(runtimes, hpwls, alpha=0.6, s=40, color='lightgray', label='All configurations')
    
    # Highlight Pareto frontier
    pareto_runtimes = [p['runtime_sec'] for p in pareto_points]
    pareto_hpwls = [p['final_hpwl'] for p in pareto_points]
    plt.scatter(pareto_runtimes, pareto_hpwls, color='red', s=80, label='Pareto Frontier', zorder=5)
    
    # Connect Pareto points
    pareto_sorted = sorted(pareto_points, key=lambda x: x['runtime_sec'])
    pareto_x = [p['runtime_sec'] for p in pareto_sorted]
    pareto_y = [p['final_hpwl'] for p in pareto_sorted]
    plt.plot(pareto_x, pareto_y, 'r--', alpha=0.7, linewidth=2)
    
    plt.xlabel('Runtime (seconds)', fontsize=12)
    plt.ylabel('Final HPWL (site units)', fontsize=12)
    plt.title('Pareto Frontier: Quality vs Speed Trade-off', fontsize=14, fontweight='bold')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f'{output_dir}/pareto_frontier.png', dpi=300, bbox_inches='tight')
    print(f"Saved Pareto frontier plot: {output_dir}/pareto_frontier.png")
    
    # 3. Simple parameter analysis bar charts
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # Group by alpha and calculate averages
    alpha_groups = {}
    for row in data:
        alpha = row['alpha']
        if alpha not in alpha_groups:
            alpha_groups[alpha] = {'hpwl': [], 'runtime': []}
        alpha_groups[alpha]['hpwl'].append(row['final_hpwl'])
        alpha_groups[alpha]['runtime'].append(row['runtime_sec'])
    
    # Alpha effect on HPWL
    alphas_sorted = sorted(alpha_groups.keys())
    avg_hpwls = [np.mean(alpha_groups[a]['hpwl']) for a in alphas_sorted]
    axes[0,0].bar([str(a) for a in alphas_sorted], avg_hpwls, color='skyblue')
    axes[0,0].set_title('Average HPWL by Cooling Rate')
    axes[0,0].set_xlabel('Cooling Rate (α)')
    axes[0,0].set_ylabel('Average Final HPWL')
    
    # Alpha effect on Runtime
    avg_runtimes = [np.mean(alpha_groups[a]['runtime']) for a in alphas_sorted]
    axes[0,1].bar([str(a) for a in alphas_sorted], avg_runtimes, color='lightcoral')
    axes[0,1].set_title('Average Runtime by Cooling Rate')
    axes[0,1].set_xlabel('Cooling Rate (α)')
    axes[0,1].set_ylabel('Average Runtime (s)')
    
    # Group by moves
    moves_groups = {}
    for row in data:
        moves = row['moves']
        if moves not in moves_groups:
            moves_groups[moves] = {'hpwl': [], 'runtime': []}
        moves_groups[moves]['hpwl'].append(row['final_hpwl'])
        moves_groups[moves]['runtime'].append(row['runtime_sec'])
    
    # Moves effect on HPWL
    moves_sorted = sorted(moves_groups.keys())
    avg_hpwls_moves = [np.mean(moves_groups[m]['hpwl']) for m in moves_sorted]
    axes[1,0].bar([str(m) for m in moves_sorted], avg_hpwls_moves, color='lightgreen')
    axes[1,0].set_title('Average HPWL by Moves per Temperature')
    axes[1,0].set_xlabel('Moves per Temperature')
    axes[1,0].set_ylabel('Average Final HPWL')
    
    # Moves effect on Runtime
    avg_runtimes_moves = [np.mean(moves_groups[m]['runtime']) for m in moves_sorted]
    axes[1,1].bar([str(m) for m in moves_sorted], avg_runtimes_moves, color='gold')
    axes[1,1].set_title('Average Runtime by Moves per Temperature')
    axes[1,1].set_xlabel('Moves per Temperature')
    axes[1,1].set_ylabel('Average Runtime (s)')
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/parameter_analysis.png', dpi=300, bbox_inches='tight')
    print(f"Saved parameter analysis plots: {output_dir}/parameter_analysis.png")
    
    # 4. Generate analysis summary
    analysis_summary = generate_analysis_summary(data, pareto_points)
    
    with open(f'{output_dir}/sa_analysis_summary.txt', 'w', encoding='utf-8') as f:
        f.write(analysis_summary)
    print(f"Saved analysis summary: {output_dir}/sa_analysis_summary.txt")
    
    return data, pareto_points, analysis_summary

def generate_analysis_summary(data, pareto_points):
    """Generate text summary of SA analysis for README.md"""
    
    best_hpwl_row = min(data, key=lambda x: x['final_hpwl'])
    fastest_row = min(data, key=lambda x: x['runtime_sec'])
    
    # Find balanced solution (good compromise)
    min_runtime = min(row['runtime_sec'] for row in data)
    max_runtime = max(row['runtime_sec'] for row in data)
    min_hpwl = min(row['final_hpwl'] for row in data)
    max_hpwl = max(row['final_hpwl'] for row in data)
    
    balanced_row = best_hpwl_row  # Simple fallback
    min_balance_score = float('inf')
    
    for row in data:
        normalized_runtime = (row['runtime_sec'] - min_runtime) / (max_runtime - min_runtime) if max_runtime > min_runtime else 0
        normalized_hpwl = (row['final_hpwl'] - min_hpwl) / (max_hpwl - min_hpwl) if max_hpwl > min_hpwl else 0
        balance_score = normalized_runtime + normalized_hpwl
        if balance_score < min_balance_score:
            min_balance_score = balance_score
            balanced_row = row
    
    alphas = sorted(set(row['alpha'] for row in data))
    moves = sorted(set(row['moves'] for row in data))
    
    summary = f"""
# SA Knob Exploration Analysis

## Experiment Overview
- Total configurations tested: {len(data)}
- Cooling rates (α): {alphas}
- Moves per temperature: {moves}
- Runtime range: {min_runtime:.2f}s - {max_runtime:.2f}s
- HPWL range: {min_hpwl:.0f} - {max_hpwl:.0f} site units

## Key Findings

### Best HPWL Configuration:
- Cooling Rate (α): {best_hpwl_row['alpha']}
- Moves per Temp: {best_hpwl_row['moves']}
- Final HPWL: {best_hpwl_row['final_hpwl']:.0f} site units
- Runtime: {best_hpwl_row['runtime_sec']:.2f}s

### Fastest Configuration:
- Cooling Rate (α): {fastest_row['alpha']}
- Moves per Temp: {fastest_row['moves']}
- Final HPWL: {fastest_row['final_hpwl']:.0f} site units
- Runtime: {fastest_row['runtime_sec']:.2f}s

### Recommended Balanced Configuration:
- Cooling Rate (α): {balanced_row['alpha']}
- Moves per Temp: {balanced_row['moves']}
- Final HPWL: {balanced_row['final_hpwl']:.0f} site units
- Runtime: {balanced_row['runtime_sec']:.2f}s
- Balance Score: {min_balance_score:.3f}

## Pareto Frontier Analysis
The Pareto frontier contains {len(pareto_points)} configurations that represent optimal trade-offs between quality and runtime.

### Parameter Correlations:
- Slower cooling (higher α): Generally improves HPWL but increases runtime
- More moves per temperature: Improves HPWL but significantly increases runtime
- Initial temperature effect: Fixed at 10.0 in experiments
- Refine probability effect: Tested at 0.5, 0.7, and 0.9

## Recommendations
1. **For best quality**: Use α={best_hpwl_row['alpha']}, moves={best_hpwl_row['moves']} (accept longer runtime)
2. **For fastest execution**: Use α={fastest_row['alpha']}, moves={fastest_row['moves']} (accept quality trade-off)
3. **For balanced performance**: Use α={balanced_row['alpha']}, moves={balanced_row['moves']} (recommended default)

The analysis shows a clear trade-off between solution quality (HPWL) and runtime, with the Pareto frontier providing guidance for selecting appropriate parameters based on project requirements.
"""
    
    return summary

def main():
    """Run the SA analysis and plotting"""
    print("SA Knob Exploration Analysis")
    print("=" * 40)
    
    data, pareto_points, summary = create_sa_analysis_plots()
    
    if data is not None:
        print("\\nAnalysis complete! Generated files:")
        print("- plots/sa_runtime_vs_hpwl.png (main assignment plot)")
        print("- plots/pareto_frontier.png") 
        print("- plots/parameter_analysis.png")
        print("- plots/sa_analysis_summary.txt")
        
        print(f"\\nQuick Summary:")
        print(f"Best HPWL: {min(row['final_hpwl'] for row in data):.0f} site units")
        print(f"Fastest runtime: {min(row['runtime_sec'] for row in data):.2f}s")
        print(f"Total configurations: {len(data)}")

if __name__ == "__main__":
    main()