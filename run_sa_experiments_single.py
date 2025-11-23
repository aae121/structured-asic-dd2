#!/usr/bin/env python3
"""
run_sa_experiments_single.py

Run SA experiments for a single design specified as command-line argument.
"""

import sys
import time
import csv
import json
import yaml
import copy
import traceback

from sa import run_sa, total_hpwl
from greedy_algorithm import run_seed, run_grow, build_adjacency

# Focused set of experiments as required by assignment (5-10 runs)
EXPERIMENT_CONFIGS = [
    # Vary cooling rate (alpha) - main parameter of interest
    {"alpha": 0.80, "moves": 200, "T_initial": 10.0, "p_refine": 0.7, "name": "Fast Cool"},
    {"alpha": 0.85, "moves": 200, "T_initial": 10.0, "p_refine": 0.7, "name": "Medium-Fast Cool"},
    {"alpha": 0.90, "moves": 200, "T_initial": 10.0, "p_refine": 0.7, "name": "Medium Cool"},
    {"alpha": 0.95, "moves": 200, "T_initial": 10.0, "p_refine": 0.7, "name": "Slow Cool"},
    {"alpha": 0.99, "moves": 200, "T_initial": 10.0, "p_refine": 0.7, "name": "Very Slow Cool"},
    
    # Vary moves per temperature
    {"alpha": 0.90, "moves": 100, "T_initial": 10.0, "p_refine": 0.7, "name": "Fewer Moves"},
    {"alpha": 0.90, "moves": 400, "T_initial": 10.0, "p_refine": 0.7, "name": "More Moves"},
    
    # Vary exploration vs refinement
    {"alpha": 0.90, "moves": 200, "T_initial": 10.0, "p_refine": 0.5, "name": "More Exploration"},
    {"alpha": 0.90, "moves": 200, "T_initial": 10.0, "p_refine": 0.9, "name": "More Refinement"},
]

def load_data(design_name):
    """Load fabric and logical database for a design"""
    with open("../fabric/fabric.yaml") as f:
        fabric = yaml.safe_load(f)
    
    with open("../fabric_db.json") as f:
        fabric_db = json.load(f)
    
    logical_path = f"../parsed_outputs/logical_db_{design_name}.json"
    with open(logical_path) as f:
        logical = json.load(f)
    
    return fabric, fabric_db, logical

def run_greedy(fabric, fabric_db, logical):
    """Run greedy placer (Seed + Grow)"""
    occupied = set()
    placements = {}
    pin_site_map = {}
    nets = logical["nets"]
    adj = build_adjacency(nets)
    
    sites_x, sites_y, site_w, site_h = run_seed(
        fabric, fabric_db, logical, occupied, placements, pin_site_map
    )
    
    placements = run_grow(
        logical, nets, adj, occupied, placements, sites_x, sites_y, site_w, site_h
    )
    
    return placements, nets, sites_x, sites_y

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_sa_experiments_single.py <design_name>")
        sys.exit(1)
    
    design_name = sys.argv[1]
    output_csv = f"experiment_results_{design_name}.csv"
    
    print(f"\n{'='*70}")
    print(f"SA EXPERIMENTS: {design_name}")
    print(f"{'='*70}")
    
    # Load data
    print(f"\nLoading design and fabric...")
    fabric, fabric_db, logical = load_data(design_name)
    print(f"  Cells: {len(logical.get('cells', {}))}")
    print(f"  Nets: {len(logical.get('nets', {}))}")
    
    # Run greedy placer
    print(f"\nRunning greedy placer...")
    placements, nets, sites_x, sites_y = run_greedy(fabric, fabric_db, logical)
    base_hpwl = total_hpwl(nets, placements)
    print(f"  Initial HPWL: {base_hpwl:.0f}")
    
    # Build adjacency
    adj = build_adjacency(nets)
    
    # Run experiments
    print(f"\nRunning {len(EXPERIMENT_CONFIGS)} SA experiments...")
    results_count = 0
    
    with open(output_csv, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["alpha", "moves", "T_initial", "p_refine", "final_hpwl", "runtime_sec", "improvement_pct"])
        
        total_experiments = len(EXPERIMENT_CONFIGS)
        
        for experiment_num, config in enumerate(EXPERIMENT_CONFIGS, 1):
            print(f"\n[{experiment_num}/{total_experiments}] {config['name']}...", end=" ", flush=True)
            
            trial = copy.deepcopy(placements)
            
            try:
                start = time.time()
                result = run_sa(
                    trial, nets, sites_x, sites_y,
                    T_initial=config['T_initial'],
                    alpha=config['alpha'],
                    moves_per_temp=config['moves'],
                    p_refine=config['p_refine'],
                    W_initial=max(sites_x, sites_y) * 0.5,
                    beta=config['alpha'],
                    T_min=0.01,
                    rng_seed=None,
                    verbose=False
                )
                sec = time.time() - start
                
                if result is None or not isinstance(result, tuple) or len(result) != 2:
                    print("ERROR")
                    continue
                
                _, final_hpwl = result
                improvement_pct = ((base_hpwl - final_hpwl) / base_hpwl) * 100 if base_hpwl > 0 else 0
                
                writer.writerow([config['alpha'], config['moves'], config['T_initial'], 
                               config['p_refine'], final_hpwl, sec, improvement_pct])
                csv_file.flush()
                
                print(f"HPWL={final_hpwl:.0f} ({improvement_pct:.1f}%), {sec:.1f}s")
                results_count += 1
                
            except Exception as e:
                print(f"FAILED: {e}")
                continue
    
    print(f"\n{'='*70}")
    print(f"✓ Experiments complete: {results_count}/{total_experiments}")
    print(f"✓ Results saved to: {output_csv}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
