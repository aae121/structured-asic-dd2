#!/usr/bin/env python3
import json
import math
import yaml
from collections import defaultdict
from pathlib import Path

from sa import run_sa, total_hpwl



def xy_to_site(x_um, y_um, site_w, site_h, sites_x, sites_y):
    sx = int(round(x_um / site_w))
    sy = int(round(y_um / site_h))
    return max(0, min(sites_x-1, sx)), max(0, min(sites_y-1, sy))

def site_to_xy(sx, sy, site_w, site_h):
    return sx * site_w, sy * site_h

def find_nearest_free(start_sx, start_sy, occupied, sites_x, sites_y, site_w, site_h):
 
    if (start_sx, start_sy) not in occupied:
        return start_sx, start_sy

    visited = set()
    from heapq import heappush, heappop
    heap = []
    radius = 1
    max_radius = max(sites_x, sites_y)

    while radius <= max_radius:
        ring_points = []

        for dx in range(-radius, radius+1):
            ring_points.append((start_sx+dx, start_sy+radius))
            ring_points.append((start_sx+dx, start_sy-radius))

        for dy in range(-radius+1, radius):
            ring_points.append((start_sx+radius, start_sy+dy))
            ring_points.append((start_sx-radius, start_sy+dy))

        for (nx, ny) in ring_points:
            if 0 <= nx < sites_x and 0 <= ny < sites_y:
                if (nx, ny) not in visited:
                    visited.add((nx, ny))
                    dist = math.hypot((nx-start_sx)*site_w, (ny-start_sy)*site_h)
                    heappush(heap, (dist, nx, ny))

        while heap:
            _, nx, ny = heappop(heap)
            if (nx, ny) not in occupied:
                return nx, ny

        radius += 1


    for sy in range(sites_y):
        for sx in range(sites_x):
            if (sx, sy) not in occupied:
                return sx, sy

    raise RuntimeError("No free site found")

def build_adjacency(nets):
    adj = defaultdict(set)
    for _, members in nets.items():
        cells = [m for m in members if isinstance(m, str)]
        for i in range(len(cells)):
            for j in range(i+1, len(cells)):
                a, b = cells[i], cells[j]
                adj[a].add(b)
                adj[b].add(a)
    return adj


def run_seed(fabric, fabric_db, logical, occupied, placements, pin_site_map):

    print("\n========== SEED STAGE ==========")

    site_w = float(fabric["fabric_info"]["site_dimensions_um"]["width"])
    site_h = float(fabric["fabric_info"]["site_dimensions_um"]["height"])
    tiles_x = int(fabric["fabric_layout"]["tiles_x"])
    tiles_y = int(fabric["fabric_layout"]["tiles_y"])
    tile_w = int(fabric["tile_definition"]["dimensions_sites"]["width"])
    tile_h = int(fabric["tile_definition"]["dimensions_sites"]["height"])

    sites_x = tiles_x * tile_w
    sites_y = tiles_y * tile_h

    nets = logical.get("nets", {})
    ports = logical.get("ports", {})

    port_to_cells = defaultdict(list)
    for pname, pinfo in ports.items():
        for bit in pinfo.get("bits", []):
            b = str(bit)
            if b in nets:
                for entry in nets[b]:
                    if isinstance(entry, str):
                        port_to_cells[pname].append(entry)

    pins = fabric_db["pins"]["pin_placement"]["pins"]

    fixed_pins = [p for p in pins if p["status"] == "FIXED"]
    print(f"Detected FIXED pins: {len(fixed_pins)}")

    seed_count = 0
    per_pin_seed = {}   
    for pin in fixed_pins:

        pname = pin["name"]
        connected = port_to_cells.get(pname, [])

        print(f"\nPin {pname}:")
        print(f"  Connected logical cells: {len(connected)}")

    
        sx, sy = xy_to_site(pin["x_um"], pin["y_um"], site_w, site_h, sites_x, sites_y)
        sx, sy = find_nearest_free(sx, sy, occupied, sites_x, sites_y, site_w, site_h)
        pin_site_map[pname] = (sx, sy)
        occupied.add((sx, sy))

        print(f"  Placed FIXED pin at site ({sx}, {sy})")

        placed_here = 0

        for cell in connected:
            if cell in placements:
                continue

            cx, cy = find_nearest_free(sx, sy, occupied, sites_x, sites_y, site_w, site_h)
            placements[cell] = {
                "site": [cx, cy],
                "site_um": [cx*site_w, cy*site_h],
                "via_pin": pname
            }
            occupied.add((cx, cy))
            seed_count += 1
            placed_here += 1

        per_pin_seed[pname] = placed_here
        print(f"  Seeded {placed_here} cells around pin {pname}")


    print(f"TOTAL SEED PLACEMENTS: {seed_count}")

    sorted_pins = sorted(per_pin_seed.items(), key=lambda x: -x[1])

    print("\nTop seeding pins:")
    for pname, cnt in sorted_pins[:10]:
        print(f"  {pname}: {cnt} cells")

    print(f"\nTotal occupied sites after seed: {len(occupied)}")


    return sites_x, sites_y, site_w, site_h



def run_grow(logical, nets, adj, occupied, placements, sites_x, sites_y, site_w, site_h):

    all_cells = set(logical.get("cells", {}).keys())
    unplaced = set(all_cells) - set(placements)

    total_deg = {c: len(adj.get(c, [])) for c in all_cells}

    placed_count = {}
    buckets = defaultdict(set)
    max_bucket = 0

    for c in unplaced:
        cnt = sum(1 for n in adj[c] if n in placements)
        placed_count[c] = cnt
        buckets[cnt].add(c)
        if cnt > max_bucket:
            max_bucket = cnt

    print("========= GROW STAGE =========")

    while unplaced:

        while max_bucket > 0 and len(buckets[max_bucket]) == 0:
            max_bucket -= 1

        if max_bucket > 0:
            group = buckets[max_bucket]
            cell = max(group, key=lambda c: total_deg[c])
            group.remove(cell)

            neigh = [n for n in adj[cell] if n in placements]
            xs, ys = [], []
            for n in neigh:
                sx, sy = placements[n]["site"]
                x, y = site_to_xy(sx, sy, site_w, site_h)
                xs.append(x); ys.append(y)
            bx, by = sum(xs)/len(xs), sum(ys)/len(ys)

            sx, sy = xy_to_site(bx, by, site_w, site_h, sites_x, sites_y)
            sx, sy = find_nearest_free(sx, sy, occupied, sites_x, sites_y, site_w, site_h)

            placements[cell] = {
                "site":[sx,sy],
                "site_um":[sx*site_w, sy*site_h],
                "via_grow": True
            }
            occupied.add((sx,sy))
            unplaced.remove(cell)

            for nb in adj[cell]:
                if nb in unplaced:
                    old = placed_count[nb]
                    buckets[old].discard(nb)
                    new = old + 1
                    placed_count[nb] = new
                    buckets[new].add(nb)
                    if new > max_bucket:
                        max_bucket = new

        else:

            cell = max(unplaced, key=lambda c: total_deg[c])
            cx, cy = sites_x//2, sites_y//2
            sx, sy = find_nearest_free(cx, cy, occupied, sites_x, sites_y, site_w, site_h)

            placements[cell] = {
                "site":[sx,sy],
                "site_um":[sx*site_w, sy*site_h],
                "via_grow":"fallback"
            }
            occupied.add((sx,sy))
            unplaced.remove(cell)

            for nb in adj[cell]:
                if nb in unplaced:
                    old = placed_count[nb]
                    buckets[old].discard(nb)
                    new = old + 1
                    placed_count[nb] = new
                    buckets[new].add(nb)
                    if new > max_bucket:
                        max_bucket = new

    print("Grow stage completed.\n")
    return placements



def load_net_weights(path: str | None):
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        with p.open() as f:
            return json.load(f)
    except Exception:
        return None


def main():

    
    fabric_yaml_path = "C:/Users/AUC/Downloads/structured_asic_project/fabric/fabric.yaml"
    fabric_db_path   = "C:/Users/AUC/Downloads/structured_asic_project/fabric_db.json"
    logical_db_path  = "C:/Users/AUC/Downloads/structured_asic_project/parsed_outputs/logical_db_6502.json"
    output_path      = "C:/Users/AUC/Downloads/structured_asic_project/grow_placement.json"
    net_weights_path = None  # e.g., "build/6502/critical_nets.json"

    with open(fabric_yaml_path) as f:
        fabric = yaml.safe_load(f)

    with open(fabric_db_path) as f:
        fabric_db = json.load(f)

    with open(logical_db_path) as f:
        logical = json.load(f)

    nets = logical.get("nets", {})
    adj = build_adjacency(nets)

    occupied = set()
    placements = {}
    pin_site_map = {}

    # SEED
    sites_x, sites_y, site_w, site_h = run_seed(
        fabric, fabric_db, logical,
        occupied, placements, pin_site_map
    )

    # GROW
    placements = run_grow(
        logical, nets, adj,
        occupied, placements,
        sites_x, sites_y, site_w, site_h
    )

    # timing-driven weights
    net_weights = load_net_weights(net_weights_path)

    # --- HPWL before SA (greedy result)
    pre_sa_hpwl = total_hpwl(nets, placements, net_weights)
    print(f"\nHPWL before SA (greedy): {pre_sa_hpwl:.3f}")

    # === Run Simulated Annealing (external module sa.py) ===
    placements_sa, best_hpwl = run_sa(
        placements,
        nets,
        sites_x,
        sites_y,
        T_initial=10.0,
        alpha=0.85,
        moves_per_temp=2000,
        p_refine=0.7,
        W_initial=sites_x * 0.5,
        beta=0.95,
        T_min=0.01,
        rng_seed=1,
        verbose=True,
        net_weights=net_weights
    )

   
    placements = placements_sa

    for cname, cinfo in placements.items():
        sx, sy = cinfo["site"]
        cinfo["site_um"] = [sx * site_w, sy * site_h]

    final_hpwl = total_hpwl(nets, placements, net_weights)
    print(f"\n✔ Final SA HPWL = {final_hpwl:.3f}\n")

    out = {
        "placements": placements,
        "pin_sites": pin_site_map,
        "grid": {
            "sites_x": sites_x,
            "sites_y": sites_y,
            "site_w_um": site_w,
            "site_h_um": site_h
        },
        "stats": {"placed_cells": len(placements)}
    }

    with open(output_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"✔ Grow+SA placement completed. {len(placements)} cells placed.")
    print(f"➡ Output saved to: {output_path}")


if __name__ == "__main__":
    main()
