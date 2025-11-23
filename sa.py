#!/usr/bin/env python3
"""
sa.py

Simulated Annealing helper functions for the Structured-ASIC placer.

Exports:
    - total_hpwl(nets, placements)
    - run_sa(placements, nets, sites_x, sites_y, ...)

Notes:
    - placements is a dict: { cell_name: { "site": [sx, sy], ... }, ... }
    - nets is the logical "nets" dict from your parsed logical DB
    - sites_x/sites_y are grid extents (integer number of sites)
"""

import math
import random
import copy
from typing import Tuple, Dict, Any

def total_hpwl(nets: dict, placements: dict) -> float:
    """
    Compute total Half-Perimeter Wire Length (HPWL) in site units.
    Expects placements[cell]["site"] = [sx, sy]
    Nets members may include pins or non-string entries; only cells that are strings and found in placements are used.
    """
    hpwl = 0.0
    for net, members in nets.items():
        xs = []
        ys = []
        for m in members:
            if isinstance(m, str) and m in placements:
                sx, sy = placements[m]["site"]
                xs.append(sx)
                ys.append(sy)
        if xs:
            hpwl += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return hpwl

def _swap_sites(placements: dict, c1: str, c2: str):
    """Swap 'site' fields for c1 and c2 in-place."""
    s1 = placements[c1]["site"]
    s2 = placements[c2]["site"]
    placements[c1]["site"], placements[c2]["site"] = s2, s1

def run_sa(
        placements: dict,
        nets: dict,
        sites_x: int,
        sites_y: int,
        T_initial: float = 10.0,
        alpha: float = 0.95,
        moves_per_temp: int = 2000,
        p_refine: float = 0.7,
        W_initial: float = None,
        beta: float = None,
        T_min: float = 0.01,
        rng_seed: int = None,
        verbose: bool = True
    ) -> Tuple[dict, float]:
    """
    Run a Simulated Annealing optimization on the given placements.

    Parameters:
    - placements: initial placement mapping (will be copied internally)
    - nets: nets dictionary for HPWL evaluation
    - sites_x, sites_y: grid size (for window scaling)
    - T_initial: starting temperature
    - alpha: temperature cooling multiplier (0 < alpha < 1)
    - moves_per_temp: inner loop size (N)
    - p_refine: probability to pick a 'refine' (local swap) vs 'explore' (windowed) move
    - W_initial: initial exploration window (in site units). If None, defaults to 0.5 * sites_x
    - beta: window cooling multiplier. If None, defaults to alpha.
    - T_min: stop when T <= T_min
    - rng_seed: if provided, seeds random for reproducibility
    - verbose: print progress

    Returns:
    - best_placements (deep copy)
    - best_hpwl (float)
    """
    if rng_seed is not None:
        random.seed(rng_seed)

    if W_initial is None:
        W_initial = max(1.0, 0.5 * max(sites_x, sites_y))
    if beta is None:
        beta = alpha

    # shallow copy of placements keys and mapping - we'll work in-place on a deep copy
    current = copy.deepcopy(placements)
    cells = list(current.keys())

    T = float(T_initial)
    W = float(W_initial)

    current_cost = total_hpwl(nets, current)
    best_cost = current_cost
    best_place = copy.deepcopy(current)

    if verbose:
        print(f"[SA] start HPWL = {current_cost:.3f}  T0={T_initial} alpha={alpha} N={moves_per_temp} p_refine={p_refine} W0={W_initial} beta={beta}")

    iteration = 0
    while T > T_min:
        iteration += 1
        for _ in range(moves_per_temp):
            # Choose move type
            if random.random() < p_refine:
                # refine: random swap between any two cells
                c1, c2 = random.sample(cells, 2)
            else:
                # explore: pick a cell and swap with another cell within the window W
                c1 = random.choice(cells)
                sx, sy = current[c1]["site"]

                # Build candidate list within window (quick scan)
                # If window is large it may be more efficient to sample, but we keep it simple
                candidates = []
                wx = max(0, int(round(W)))
                wy = max(0, int(round(W)))
                # gather candidate cells that are within WxW rectangle
                for c in cells:
                    sx2, sy2 = current[c]["site"]
                    if abs(sx2 - sx) <= wx and abs(sy2 - sy) <= wy and c != c1:
                        candidates.append(c)

                if not candidates:
                    # fallback to random pair
                    c2 = random.choice([c for c in cells if c != c1])
                else:
                    c2 = random.choice(candidates)

            # perform swap
            _swap_sites(current, c1, c2)
            new_cost = total_hpwl(nets, current)
            delta = new_cost - current_cost

            accept = False
            if delta <= 0:
                accept = True
            else:
                # Metropolis criterion
                # Protect against overflow: if T is tiny, exp(-delta/T) may underflow to 0
                try:
                    prob = math.exp(-delta / T)
                except OverflowError:
                    prob = 0.0
                if random.random() < prob:
                    accept = True

            if accept:
                current_cost = new_cost
                if current_cost < best_cost:
                    best_cost = current_cost
                    best_place = copy.deepcopy(current)
            else:
                # revert swap
                _swap_sites(current, c1, c2)

        # cool down
        T *= alpha
        W *= beta
        if verbose:
            print(f"[SA] iter={iteration:3d}  T={T:.4f}  W={W:.2f}  curr={current_cost:.3f}  best={best_cost:.3f}")

    if verbose:
        print(f"[SA] finished. best HPWL = {best_cost:.3f}")

    return best_place, best_cost


if __name__ == "__main__":
    # quick sanity test when executed directly (small synthetic)
    # This block won't run when imported
    print("sa.py quick test (no nets) ...")
    test_placements = {"a":{"site":[1,1]}, "b":{"site":[2,2]}, "c":{"site":[3,3]}}
    test_nets = {"n1": ["a","b"], "n2":["b","c"]}
    bp, cost = run_sa(test_placements, test_nets, sites_x=10, sites_y=10, moves_per_temp=100, rng_seed=1, verbose=True)
    print("Result cost:", cost)
