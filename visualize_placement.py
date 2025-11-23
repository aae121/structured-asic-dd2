#!/usr/bin/env python3
"""
visualize_placement.py

Creates required visualization deliverables:
1. Placement Density Heatmap (2D histogram showing cell density)
2. Net Length Histogram (1D histogram of all net HPWLs)

Usage: python visualize_placement.py <design_name> <placement_json>
"""

import json
import sys
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

def load_placement(placement_file):
    """Load placement from JSON file"""
    with open(placement_file, 'r') as f:
        data = json.load(f)
    
    # Handle both formats: direct placements dict or nested under "placements" key
    if "placements" in data:
        return data["placements"]
    else:
        return data

def load_logical_db(design_name):
    """Load logical database for the design"""
    logical_path = f"../parsed_outputs/logical_db_{design_name}.json"
    with open(logical_path, 'r') as f:
        logical = json.load(f)
    return logical

def calculate_hpwl(nets, placements):
    """Calculate HPWL for all nets"""
    net_hpwls = []
    for net_name, members in nets.items():
        xs = []
        ys = []
        for m in members:
            if isinstance(m, str) and m in placements:
                sx, sy = placements[m]["site"]
                xs.append(sx)
                ys.append(sy)
        if xs:
            hpwl = (max(xs) - min(xs)) + (max(ys) - min(ys))
            net_hpwls.append(hpwl)
    return net_hpwls

def create_density_heatmap(placements, design_name, output_dir="build"):
    """Create placement density heatmap"""
    
    # Extract all site coordinates
    sites = [cell["site"] for cell in placements.values() if "site" in cell]
    if not sites:
        print("ERROR: No placement sites found!")
        return
    
    xs = [s[0] for s in sites]
    ys = [s[1] for s in sites]
    
    # Determine grid bounds
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    print(f"Grid bounds: X=[{min_x}, {max_x}], Y=[{min_y}, {max_y}]")
    print(f"Total cells placed: {len(sites)}")
    
    # Create 2D histogram (density map)
    fig, ax = plt.subplots(figsize=(14, 10))
    
    # Use bins to create density map
    bins_x = min(100, (max_x - min_x) // 20 + 1)
    bins_y = min(100, (max_y - min_y) // 10 + 1)
    
    h, xedges, yedges, im = ax.hist2d(xs, ys, bins=[bins_x, bins_y], 
                                       cmap='hot', cmin=1)
    
    ax.set_xlabel('X (sites)', fontsize=12)
    ax.set_ylabel('Y (sites)', fontsize=12)
    ax.set_title(f'Placement Density Heatmap - {design_name}\n({len(sites)} cells placed)', 
                 fontsize=14, fontweight='bold')
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, label='Cell Density')
    
    # Add grid bounds as text
    ax.text(0.02, 0.98, f'Grid: {max_x-min_x} × {max_y-min_y} sites', 
            transform=ax.transAxes, fontsize=10,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    
    # Save to build directory
    output_path = Path(output_dir) / design_name
    output_path.mkdir(parents=True, exist_ok=True)
    
    filename = output_path / f"{design_name}_density.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"✓ Saved density heatmap: {filename}")
    plt.close()
    
    return filename

def create_net_length_histogram(net_hpwls, design_name, output_dir="build"):
    """Create net length histogram"""
    
    if not net_hpwls:
        print("ERROR: No net HPWLs found!")
        return
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Create histogram
    n, bins, patches = ax.hist(net_hpwls, bins=50, color='steelblue', 
                                edgecolor='black', alpha=0.7)
    
    ax.set_xlabel('Net HPWL (site units)', fontsize=12)
    ax.set_ylabel('Number of Nets', fontsize=12)
    ax.set_title(f'Net Length Distribution - {design_name}\n({len(net_hpwls)} nets)', 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Add statistics
    mean_hpwl = np.mean(net_hpwls)
    median_hpwl = np.median(net_hpwls)
    max_hpwl = np.max(net_hpwls)
    total_hpwl = np.sum(net_hpwls)
    
    stats_text = f'Total HPWL: {total_hpwl:.0f}\n'
    stats_text += f'Mean: {mean_hpwl:.1f}\n'
    stats_text += f'Median: {median_hpwl:.1f}\n'
    stats_text += f'Max: {max_hpwl:.0f}'
    
    ax.text(0.98, 0.98, stats_text,
            transform=ax.transAxes, fontsize=10,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))
    
    plt.tight_layout()
    
    # Save to build directory
    output_path = Path(output_dir) / design_name
    output_path.mkdir(parents=True, exist_ok=True)
    
    filename = output_path / f"{design_name}_net_length.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"✓ Saved net length histogram: {filename}")
    plt.close()
    
    return filename

def main():
    if len(sys.argv) < 2:
        print("Usage: python visualize_placement.py <design_name> [placement_json]")
        print("Example: python visualize_placement.py 6502 grow_placement.json")
        sys.exit(1)
    
    design_name = sys.argv[1]
    placement_file = sys.argv[2] if len(sys.argv) > 2 else "../grow_placement.json"
    
    print(f"\n{'='*60}")
    print(f"Creating Visualizations for {design_name}")
    print(f"{'='*60}")
    
    # Load data
    print(f"\nLoading placement from: {placement_file}")
    placements = load_placement(placement_file)
    
    print(f"Loading logical database...")
    logical = load_logical_db(design_name)
    nets = logical.get('nets', {})
    
    print(f"Loaded {len(placements)} placements, {len(nets)} nets")
    
    # Calculate net HPWLs
    print("\nCalculating net HPWLs...")
    net_hpwls = calculate_hpwl(nets, placements)
    total_hpwl = sum(net_hpwls)
    print(f"Total HPWL: {total_hpwl:.0f} site units")
    
    # Create visualizations
    print("\n" + "="*60)
    print("Generating Visualizations")
    print("="*60)
    
    density_file = create_density_heatmap(placements, design_name)
    histogram_file = create_net_length_histogram(net_hpwls, design_name)
    
    print("\n" + "="*60)
    print("✓ Visualizations Complete!")
    print("="*60)
    print(f"\nGenerated files:")
    print(f"  1. {density_file}")
    print(f"  2. {histogram_file}")
    print(f"\nTotal HPWL: {total_hpwl:.0f} site units")

if __name__ == "__main__":
    main()
