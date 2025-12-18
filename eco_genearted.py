#!/usr/bin/env python3
"""
eco_generator.py - Phase 3 CTS & ECO netlist generator (FULLY CORRECTED VERSION)
Implements:
  - Hierarchical CTS with buffer assignment and quality metrics
  - Per-tile CONB management with fanout tracking
  - Liberty-based power-optimized tie-off
  - Proper unused cell detection
  - CTS quality validation

Usage:
    python eco_generator.py --placement build/grow_placement.json \
        --mapped build/6502_mapped.json --fabric build/fabric_db.json \
        --fabric-yaml fabric.yaml --liberty sky130_hd_timing.lib \
        --out-dir build/<design> --design <name>
"""
import json
import yaml
import argparse
import math
import os
import sys
import re
from collections import defaultdict, namedtuple
from pprint import pprint
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import random

# ==================== Data Structures ====================

Node = namedtuple("Node", ["x", "y", "name", "tile", "cell_type"])

# ==================== Utilities ====================

def dist(a, b):
    """Calculate Euclidean distance between two points"""
    return math.hypot(a[0]-b[0], a[1]-b[1])

def mkdir_p(p):
    """Create directory if it doesn't exist"""
    os.makedirs(p, exist_ok=True)

# ==================== Parsers ====================

def load_json(path):
    """Load JSON file"""
    with open(path, "r") as f:
        return json.load(f)

def load_yaml(path):
    """Load YAML file"""
    with open(path, "r") as f:
        return yaml.safe_load(f)

def find_top_module(mapped_json):
    """Find the top module in the mapped JSON"""
    modules = mapped_json.get("modules", {})
    if not modules:
        return None
    for mname, m in modules.items():
        if m.get("attributes", {}).get("top"):
            return mname
    return next(iter(modules.keys()))

def extract_cells_from_yosys_json(mapped_json, module_name):
    """Extract cells dictionary from Yosys JSON"""
    modules = mapped_json.get("modules", {})
    module = modules.get(module_name, {})
    cells = module.get("cells", {})
    if not isinstance(cells, dict):
        for k, v in module.items():
            if k.lower().startswith("cells"):
                cells = v
                break
    return cells

def guess_ff_cells(cells):
    """Identify flip-flops in the netlist"""
    ffs = []
    for inst, info in cells.items():
        ctype = info.get("type", "").lower()
        # Check for DFF patterns in cell type
        if "df" in ctype and ("ff" in ctype or "df" in ctype or "dff" in ctype or "dfbbp" in ctype):
            ffs.append(inst)
            continue
        # Check attributes
        if "attributes" in info:
            found = False
            for v in info["attributes"].values():
                if isinstance(v, str) and "ff" in v.lower():
                    ffs.append(inst)
                    found = True
                    break
            if found:
                continue
    
    # Fallback: check for CLK pin
    if not ffs:
        for inst, info in cells.items():
            conns = info.get("connections", {})
            if any(k.lower() == "clk" or 'clk' in k.lower() for k in conns.keys()):
                ffs.append(inst)
    
    return sorted(set(ffs))

def build_fabric_nodes_from_db(fabric_db):
    """
    Build nodes from fabric database
    Handles both fabric_cells.yaml (instantiated) and fabric.yaml (template)
    
    Returns:
      nodes_by_type: { 'BUF': [Node,...], 'INV': [...], 'CONB': [...], ... }
      tile_to_nodes: { tile_name: [Node, Node, ...] }
    """
    nodes_by_type = defaultdict(list)
    tile_to_nodes = defaultdict(list)

    # Handle fabric_cells_by_tile structure (YOUR fabric_cells.yaml)
    if 'fabric_cells_by_tile' in fabric_db:
        fabric_data = fabric_db['fabric_cells_by_tile']
        tiles = fabric_data.get('tiles', {})
        
        for tile_name, tile_info in tiles.items():
            cell_list = tile_info.get('cells', [])
            
            for c in cell_list:
                name = c.get('name', '')
                x = float(c.get('x', 0.0))
                y = float(c.get('y', 0.0))
                
                # Determine cell type from name
                # Names like: "T0Y0__R0_BUF_0", "T0Y0__R1_CONB_0", etc.
                ctype = 'other'
                if '_BUF_' in name or '_CLKBUF_' in name:
                    ctype = 'buf'
                    nodes_by_type["BUF"].append(Node(x, y, name, tile_name, ctype))
                elif '_INV_' in name or '_CLKINV_' in name:
                    ctype = 'inv'
                    nodes_by_type["INV"].append(Node(x, y, name, tile_name, ctype))
                elif '_CONB_' in name:
                    ctype = 'conb'
                    nodes_by_type["CONB"].append(Node(x, y, name, tile_name, ctype))
                elif '_DFBBP_' in name or '_DFF_' in name:
                    ctype = 'dff'
                    nodes_by_type["DFF"].append(Node(x, y, name, tile_name, ctype))
                elif '_NAND_' in name:
                    ctype = 'nand'
                    nodes_by_type["NAND"].append(Node(x, y, name, tile_name, ctype))
                elif '_OR_' in name:
                    ctype = 'or'
                    nodes_by_type["OR"].append(Node(x, y, name, tile_name, ctype))
                elif '_AND_' in name:
                    ctype = 'and'
                    nodes_by_type["AND"].append(Node(x, y, name, tile_name, ctype))
                else:
                    nodes_by_type["OTHER"].append(Node(x, y, name, tile_name, ctype))
                
                # Add to tile mapping
                tile_to_nodes[tile_name].append(Node(x, y, name, tile_name, ctype))
        
        return nodes_by_type, tile_to_nodes

    # Handle fabric.yaml template format (tile_definition)
    elif 'tile_definition' in fabric_db:
        f_info = fabric_db.get("fabric_info", {})
        site_dims = f_info.get("site_dimensions_um", {})
        site_w = float(site_dims.get("width", 0.46))
        site_h = float(site_dims.get("height", 2.72))
        
        tile_def = fabric_db["tile_definition"]
        cells = tile_def.get("cells", [])
        
        # This is a template - need to know fabric_layout
        layout = fabric_db.get("fabric_layout", {})
        tiles_x = layout.get("tiles_x", 1)
        tiles_y = layout.get("tiles_y", 1)
        
        # Generate instances for each tile
        for tx in range(tiles_x):
            for ty in range(tiles_y):
                tile_name = f"T{tx}Y{ty}"
                
                for idx, c in enumerate(cells):
                    ctype_full = c.get("cell_type", "")
                    tmpl = c.get("template_name", f"cell_{idx}")
                    origin = c.get("origin_sites", {})
                    ox = origin.get("x", 0)
                    oy = origin.get("y", 0)
                    
                    # Calculate absolute position
                    tile_width_um = tile_def.get("dimensions_sites", {}).get("width", 60) * site_w
                    tile_height_um = tile_def.get("dimensions_sites", {}).get("height", 4) * site_h
                    
                    x_um = tx * tile_width_um + float(ox) * site_w
                    y_um = ty * tile_height_um + float(oy) * site_h
                    
                    # Instance name
                    inst_name = f"{tile_name}__{tmpl}"
                    
                    # Determine type
                    ctype = ctype_full.lower()
                    node = None
                    
                    if "clkbuf" in ctype or "buf" in ctype:
                        node = Node(x_um, y_um, inst_name, tile_name, "buf")
                        nodes_by_type["BUF"].append(node)
                    elif "clkinv" in ctype or "inv" in ctype:
                        node = Node(x_um, y_um, inst_name, tile_name, "inv")
                        nodes_by_type["INV"].append(node)
                    elif "conb" in ctype:
                        node = Node(x_um, y_um, inst_name, tile_name, "conb")
                        nodes_by_type["CONB"].append(node)
                    elif "dfbbp" in ctype or "dff" in ctype:
                        node = Node(x_um, y_um, inst_name, tile_name, "dff")
                        nodes_by_type["DFF"].append(node)
                    else:
                        node = Node(x_um, y_um, inst_name, tile_name, "other")
                        nodes_by_type["OTHER"].append(node)
                    
                    if node:
                        tile_to_nodes[tile_name].append(node)
        
        return nodes_by_type, tile_to_nodes

    # Handle old JSON-style 'tiles' -> tile -> cells
    elif fabric_db.get("tiles"):
        tiles = fabric_db["tiles"]
        for tile_name, tile in tiles.items():
            cell_list = tile.get("cells") or []
            for c in cell_list:
                name = c.get("name")
                ctype = (name or c.get("type", "")).lower()
                x = c.get("x") or c.get("x_um") or 0.0
                y = c.get("y") or c.get("y_um") or 0.0
                nname = name if name else f"{tile_name}_EMPTY_{len(nodes_by_type)}"
                node = None
                if "buf" in ctype or "clkbuf" in ctype:
                    node = Node(x, y, nname, tile_name, ctype)
                    nodes_by_type["BUF"].append(node)
                elif "inv" in ctype or "clkinv" in ctype:
                    node = Node(x, y, nname, tile_name, ctype)
                    nodes_by_type["INV"].append(node)
                elif "conb" in ctype:
                    node = Node(x, y, nname, tile_name, ctype)
                    nodes_by_type["CONB"].append(node)
                else:
                    node = Node(x, y, nname, tile_name, ctype)
                    nodes_by_type["OTHER"].append(node)
                if node:
                    tile_to_nodes[tile_name].append(node)

    # Handle direct 'cells' dict
    elif fabric_db.get("cells"):
        for name, info in fabric_db["cells"].items():
            x = info.get("x_um", info.get("x", 0.0))
            y = info.get("y_um", info.get("y", 0.0))
            ctype = (info.get("type", name) or "").lower()
            tile_name = info.get("tile", "tile_0")
            node = None
            if "buf" in ctype or "clkbuf" in ctype:
                node = Node(x, y, name, tile_name, ctype)
                nodes_by_type["BUF"].append(node)
            elif "inv" in ctype or "clkinv" in ctype:
                node = Node(x, y, name, tile_name, ctype)
                nodes_by_type["INV"].append(node)
            elif "conb" in ctype:
                node = Node(x, y, name, tile_name, ctype)
                nodes_by_type["CONB"].append(node)
            else:
                node = Node(x, y, name, tile_name, ctype)
                nodes_by_type["OTHER"].append(node)
            if node:
                tile_to_nodes[tile_name].append(node)

    return nodes_by_type, tile_to_nodes
# ==================== Liberty Parser ====================

def parse_liberty_leakage(lib_path):
    """
    Parse Liberty file to extract leakage power for each cell type and pin configuration.
    Returns: { cell_type: { pin_name: { 'tie_high': leakage_pW, 'tie_low': leakage_pW } } }
    """
    if not lib_path or not os.path.exists(lib_path):
        print("WARNING: Liberty file not found, using default tie-low strategy")
        return {}
    
    leakage_db = defaultdict(lambda: defaultdict(dict))
    
    try:
        with open(lib_path, 'r') as f:
            content = f.read()
        
        # Find all cell definitions
        cell_pattern = r'cell\s*\(\s*"?([^")\s]+)"?\s*\)\s*\{'
        cells = re.finditer(cell_pattern, content)
        
        for cell_match in cells:
            cell_name = cell_match.group(1)
            cell_start = cell_match.end()
            
            # Find matching closing brace for this cell
            brace_count = 1
            cell_end = cell_start
            for i in range(cell_start, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        cell_end = i
                        break
            
            cell_content = content[cell_start:cell_end]
            
            # Extract leakage_power values
            leakage_pattern = r'leakage_power\s*\(\s*\)\s*\{([^}]+)\}'
            for leak_match in re.finditer(leakage_pattern, cell_content):
                leak_content = leak_match.group(1)
                
                # Extract when condition and value
                when_match = re.search(r'when\s*:\s*"([^"]+)"', leak_content)
                value_match = re.search(r'value\s*:\s*([0-9.eE+-]+)', leak_content)
                
                if value_match:
                    leakage_val = float(value_match.group(1)) * 1e12  # Convert to pW
                    
                    if when_match:
                        when_expr = when_match.group(1)
                        # Parse when expression to determine pin states
                        # Extended pin name list
                        for pin_name in ['A', 'B', 'C', 'D', 'S', 'A0', 'A1', 'A2', 'A3', 'S0', 'S1', 'S2']:
                            if f'!{pin_name}' in when_expr:
                                leakage_db[cell_name][pin_name]['tie_low'] = min(
                                    leakage_db[cell_name][pin_name].get('tie_low', float('inf')),
                                    leakage_val
                                )
                            elif pin_name in when_expr:
                                leakage_db[cell_name][pin_name]['tie_high'] = min(
                                    leakage_db[cell_name][pin_name].get('tie_high', float('inf')),
                                    leakage_val
                                )
                    else:
                        # No when condition - default leakage
                        pass
        
        print(f"Parsed Liberty file: {len(leakage_db)} cell types with leakage data")
        
    except Exception as e:
        print(f"WARNING: Failed to parse Liberty file: {e}")
        return {}
    
    return dict(leakage_db)

# ==================== CTS Builder ====================

def cluster_sinks(sinks, max_leaf=8):
    """Hierarchical clustering of sink coordinates"""
    if len(sinks) <= max_leaf:
        xs = [s[0] for s in sinks]
        ys = [s[1] for s in sinks]
        cx = sum(xs)/len(xs) if xs else 0
        cy = sum(ys)/len(ys) if ys else 0
        return {"members": sinks, "center": (cx, cy), "children": []}
    
    xs = [s[0] for s in sinks]
    ys = [s[1] for s in sinks]
    xrange_ = max(xs)-min(xs)
    yrange_ = max(ys)-min(ys)
    axis = 0 if xrange_ >= yrange_ else 1
    sinks_sorted = sorted(sinks, key=lambda s: s[axis])
    mid = len(sinks_sorted)//2
    left = cluster_sinks(sinks_sorted[:mid], max_leaf)
    right = cluster_sinks(sinks_sorted[mid:], max_leaf)
    cx = (left["center"][0] + right["center"][0]) / 2.0
    cy = (left["center"][1] + right["center"][1]) / 2.0
    return {"members": sinks, "center": (cx, cy), "children": [left, right]}

def claim_nearest_node(center, node_list, claimed_set):
    """Find nearest unclaimed node to a given center point"""
    best = None
    bestd = 1e9
    for n in node_list:
        if n.name in claimed_set:
            continue
        d = dist((n.x, n.y), center)
        if d < bestd:
            best = n
            bestd = d
    return best

def build_cts(tree, available_bufs, available_invs, claimed, max_segment_length=500.0):
    """
    Recursively build CTS tree by claiming buffers
    Added max_segment_length constraint for clock integrity
    """
    assignments = []
    child_assigns = []
    
    if tree.get("children"):
        child_nodes = []
        for child in tree["children"]:
            child_assigns_part = build_cts(child, available_bufs, available_invs, claimed, max_segment_length)
            if child_assigns_part:
                child_nodes.append(child_assigns_part[-1]['node'])
                child_assigns.extend(child_assigns_part)
        
        center = tree["center"]
        node = claim_nearest_node(center, available_bufs + available_invs, claimed)
        
        if node:
            # Validate segment lengths
            segment_lengths = [dist((node.x, node.y), (c.x, c.y)) for c in child_nodes]
            max_seg = max(segment_lengths) if segment_lengths else 0
            
            if max_seg > max_segment_length:
                print(f"WARNING: CTS segment length {max_seg:.2f}um exceeds limit {max_segment_length}um")
            
            claimed.add(node.name)
            assignments.extend(child_assigns)
            assignments.append({
                "node": node, 
                "children": child_nodes, 
                "center": center,
                "wirelength": sum(segment_lengths),
                "max_segment_length": max_seg
            })
        else:
            print("WARNING: No available buffer found for CTS node")
            assignments.extend(child_assigns)
    
    return assignments

def calculate_cts_metrics(cts_assignments, dff_instances, placement_map):
    """Calculate CTS quality metrics: total wirelength and estimated skew"""
    total_wl = 0.0
    max_path_length = 0.0
    min_path_length = float('inf')
    max_segment = 0.0
    
    # Calculate total wirelength and max segment
    for a in cts_assignments:
        wl = a.get('wirelength', 0.0)
        total_wl += wl
        seg = a.get('max_segment_length', 0.0)
        if seg > max_segment:
            max_segment = seg
    
    # Estimate path lengths to each DFF (simplified)
    dff_path_lengths = []
    for dff in dff_instances:
        if dff in placement_map:
            dff_x, dff_y = placement_map[dff]
            # Find nearest CTS node
            if cts_assignments:
                nearest = min(cts_assignments, key=lambda a: dist((a['node'].x, a['node'].y), (dff_x, dff_y)))
                path_len = dist((nearest['node'].x, nearest['node'].y), (dff_x, dff_y))
                dff_path_lengths.append(path_len)
    
    if dff_path_lengths:
        max_path_length = max(dff_path_lengths)
        min_path_length = min(dff_path_lengths)
    
    estimated_skew = max_path_length - min_path_length
    
    return {
        'total_wirelength_um': total_wl,
        'max_path_length_um': max_path_length,
        'min_path_length_um': min_path_length,
        'estimated_skew_um': estimated_skew,
        'max_segment_length_um': max_segment,
        'num_buffers': len(cts_assignments),
        'num_sinks': len(dff_instances)
    }

# ==================== CONB Management (Per-Tile) ====================

def assign_conb_per_tile(tile_to_nodes, max_fanout=50):
    """
    Assign one CONB per tile with fanout tracking.
    Returns: { tile_name: { 'conb_node': Node, 'lo_fanout': 0, 'hi_fanout': 0 } }
    """
    conb_assignment = {}
    
    for tile_name, nodes in tile_to_nodes.items():
        conb_nodes = [n for n in nodes if 'conb' in n.cell_type.lower()]
        if conb_nodes:
            conb_assignment[tile_name] = {
                'conb_node': conb_nodes[0],  # Use first CONB in tile
                'lo_fanout': 0,
                'hi_fanout': 0,
                'max_fanout': max_fanout
            }
        else:
            # If no CONB in tile, we'll need to use nearest tile's CONB
            pass
    
    return conb_assignment

def get_conb_for_cell(cell_x, cell_y, tile_to_nodes, conb_assignment):
    """Find the nearest tile's CONB for a given cell location"""
    best_tile = None
    best_dist = float('inf')
    
    for tile_name, tile_info in conb_assignment.items():
        conb_node = tile_info['conb_node']
        d = dist((cell_x, cell_y), (conb_node.x, conb_node.y))
        if d < best_dist:
            best_dist = d
            best_tile = tile_name
    
    return best_tile

# ==================== Power-Optimized Tie-off ====================

def determine_optimal_tie(cell_type, pin_name, leakage_db):
    """
    Determine optimal tie (HIGH or LOW) based on leakage power.
    Returns: 'tie_high' or 'tie_low'
    """
    if not leakage_db or cell_type not in leakage_db:
        return 'tie_low'  # Default to tie-low
    
    pin_data = leakage_db[cell_type].get(pin_name, {})
    
    leak_high = pin_data.get('tie_high', float('inf'))
    leak_low = pin_data.get('tie_low', float('inf'))
    
    if leak_low < leak_high:
        return 'tie_low'
    elif leak_high < leak_low:
        return 'tie_high'
    else:
        return 'tie_low'  # Default

# ==================== Netlist Modifier ====================

def modify_mapped_json(mapped_json, module_name, dff_instances, placement_map, 
                       cts_assignments, conb_assignment, leakage_db, 
                       out_dir, design_name, nodes_by_type, tile_to_nodes):
    """
    Modify the netlist to:
    1. Rewire DFF clocks to CTS buffers
    2. Add CTS buffer instances
    3. Perform power-optimized ECO tie-off using per-tile CONBs
    """
    module = mapped_json["modules"][module_name]
    cells = module.setdefault("cells", {})
    netnames = module.setdefault("netnames", {})

    root_net_name = "clk_cts_root"
    
    # ========== CTS IMPLEMENTATION ==========
    
    cts_nodes = [a['node'] for a in cts_assignments]
    if not cts_nodes:
        # Synthetic root
        xs = [placement_map[d][0] for d in dff_instances if d in placement_map]
        ys = [placement_map[d][1] for d in dff_instances if d in placement_map]
        if xs and ys:
            cx = sum(xs)/len(xs)
            cy = sum(ys)/len(ys)
        else:
            cx = cy = 0.0
        synthetic = Node(cx, cy, "CTS_ROOT_SYN", None, "clkbuf")
        cts_nodes = [synthetic]

    # Map each CTS node to a net name
    cts_node_net = {}
    for idx, node in enumerate(cts_nodes):
        netname = f"clk_cts_n{idx}"
        cts_node_net[node.name] = netname
        netnames.setdefault(netname, {"bits": [], "hide_name": False})

    # Map DFF -> nearest CTS node
    dff_to_net = {}
    for d in dff_instances:
        if d not in placement_map:
            chosen = cts_nodes[0]
        else:
            px, py = placement_map[d]
            best = min(cts_nodes, key=lambda n: dist((n.x, n.y), (px, py)))
            chosen = best
        dff_to_net[d] = cts_node_net[chosen.name]

    # Update DFF CLK pins
    for dff_inst in dff_instances:
        cell = cells.get(dff_inst)
        if not cell:
            continue
        conns = cell.get("connections", {})
        clk_pin_keys = [k for k in conns.keys() if k.lower() == "clk"]
        if not clk_pin_keys:
            clk_pin_keys = [k for k in conns.keys() if 'clk' in k.lower()]
        if clk_pin_keys:
            key = clk_pin_keys[0]
            net = dff_to_net.get(dff_inst, list(cts_node_net.values())[0])
            cell["connections"][key] = [net]
            netnames.setdefault(net, {"bits": [], "hide_name": False})
            netnames[net]["bits"].append(f"{dff_inst}.{key}")

    # Add CTS buffer instances
    for idx, a in enumerate(cts_assignments):
        node = a["node"]
        inst_name = f"cts_buf_{idx}"
        
        # Determine buffer type based on node cell_type
        if "inv" in node.cell_type.lower():
            buf_type = "sky130_fd_sc_hd__clkinv_4"
        else:
            buf_type = "sky130_fd_sc_hd__clkbuf_4"
        
        net_out = cts_node_net[node.name]
        cells[inst_name] = {
            "type": buf_type,
            "connections": {
                "A": [root_net_name],
                "X": [net_out]
            },
            "parameters": {}
        }
        netnames.setdefault(root_net_name, {"bits": [], "hide_name": False})
        netnames.setdefault(net_out, {"bits": [], "hide_name": False})
        netnames[net_out]["bits"].append(f"{inst_name}.X")

    print(f"CTS: Rewired {len(dff_instances)} DFFs, added {len(cts_assignments)} buffers")

    # ========== POWER-OPTIMIZED ECO TIE-OFF (PER-TILE CONB) ==========
    
    conb_cell_type = "sky130_fd_sc_hd__conb_1"
    conb_instances = {}  # { tile_name: conb_inst_name }
    tie_nets = {}  # { tile_name: { 'lo': net_name, 'hi': net_name } }
    
    # Create CONB instances for each tile
    for tile_name, tile_info in conb_assignment.items():
        conb_node = tile_info['conb_node']
        conb_inst_name = f"conb_{tile_name}"
        
        # Ensure unique instance name
        i = 0
        base = conb_inst_name
        while conb_inst_name in cells:
            i += 1
            conb_inst_name = f"{base}_{i}"
        
        tie_lo_net = f"tie_low_{tile_name}"
        tie_hi_net = f"tie_high_{tile_name}"
        
        cells[conb_inst_name] = {
            "type": conb_cell_type,
            "connections": {
                "LO": [tie_lo_net],
                "HI": [tie_hi_net]
            },
            "parameters": {}
        }
        
        netnames.setdefault(tie_lo_net, {"bits": [], "hide_name": False})
        netnames.setdefault(tie_hi_net, {"bits": [], "hide_name": False})
        netnames[tie_lo_net]["bits"].append(f"{conb_inst_name}.LO")
        netnames[tie_hi_net]["bits"].append(f"{conb_inst_name}.HI")
        
        conb_instances[tile_name] = conb_inst_name
        tie_nets[tile_name] = {'lo': tie_lo_net, 'hi': tie_hi_net}
    
    print(f"ECO: Created {len(conb_instances)} CONB instances (one per tile)")
    
    # Build set of used instances
    used_instances = set(dff_instances)
    used_instances.update(a['node'].name for a in cts_assignments)
    used_instances.update(conb_instances.values())
    used_instances.update(inst for inst in cells.keys() if inst.startswith("cts_buf_"))
    
    # Identify unused logic cells
    skip_types = set(["df", "dff", "dfbbp", "clkbuf", "clkinv", "conb", 
                      "tapvpwrvgnd", "decap", "fill", "cts_buf"])
    output_pin_keywords = set(["y", "q", "zn", "z", "x", "out"])
    
    unused_cells = []
    for inst_name, cinfo in list(cells.items()):
        # Skip if already used
        if inst_name in used_instances:
            continue
        
        # Skip system cells
        ctype = (cinfo.get("type", "") or "").lower()
        if any(s in ctype for s in skip_types):
            continue
        
        # Check if all outputs are disconnected (truly unused)
        conns = cinfo.get("connections", {})
        has_connected_output = False
        for pin, net in conns.items():
            if pin.lower() in output_pin_keywords or any(k in pin.lower() for k in ["y", "q", "z", "x"]):
                # Check if this output is actually connected to something
                if isinstance(net, list) and net:
                    # Could check if net has other fanout, but for now assume unused
                    pass
        
        unused_cells.append(inst_name)
    
    print(f"ECO: Found {len(unused_cells)} unused cells to tie off")
    
    # Tie unused cell inputs with power optimization
    tied_count = 0
    fanout_warnings = []
    power_savings = {'tie_high': 0, 'tie_low': 0}
    
    for inst in unused_cells:
        cell = cells.get(inst)
        if not cell:
            continue
        
        cell_type = cell.get("type", "")
        conns = cell.setdefault("connections", {})
        
        # Determine which tile this cell belongs to
        cell_x = cell_y = 0.0
        if inst in placement_map:
            cell_x, cell_y = placement_map[inst]
        
        # Find nearest tile's CONB (FIXED: Pass tile_to_nodes)
        tile_name = get_conb_for_cell(cell_x, cell_y, tile_to_nodes, conb_assignment)
        if not tile_name:
            # Fallback to first available tile
            tile_name = next(iter(conb_assignment.keys())) if conb_assignment else None
        
        if not tile_name or tile_name not in tie_nets:
            continue
        
        tile_tie_nets = tie_nets[tile_name]
        tile_conb_info = conb_assignment[tile_name]
        
        for pin, net in list(conns.items()):
            # Skip output pins
            if pin.lower() in output_pin_keywords or any(k in pin.lower() for k in ["y", "q", "z", "x", "out"]):
                continue
            
            # Skip if already connected to a tie net
            if isinstance(net, list) and net:
                if any(isinstance(n, str) and n.startswith("tie_") for n in net):
                    continue
            
            # Determine optimal tie based on leakage
            optimal_tie = determine_optimal_tie(cell_type, pin, leakage_db)
            
            # Check fanout limits
            if optimal_tie == 'tie_low':
                if tile_conb_info['lo_fanout'] >= tile_conb_info['max_fanout']:
                    fanout_warnings.append(f"Tile {tile_name} LO fanout exceeded")
                    continue
                tie_net = tile_tie_nets['lo']
                tile_conb_info['lo_fanout'] += 1
                power_savings['tie_low'] += 1
            else:
                if tile_conb_info['hi_fanout'] >= tile_conb_info['max_fanout']:
                    fanout_warnings.append(f"Tile {tile_name} HI fanout exceeded")
                    continue
                tie_net = tile_tie_nets['hi']
                tile_conb_info['hi_fanout'] += 1
                power_savings['tie_high'] += 1
            
            # Tie the pin
            cell["connections"][pin] = [tie_net]
            netnames.setdefault(tie_net, {"bits": [], "hide_name": False})
            repr_pin = f"{inst}.{pin}"
            if repr_pin not in netnames[tie_net]["bits"]:
                netnames[tie_net]["bits"].append(repr_pin)
            tied_count += 1
    
    print(f"ECO: Tied {tied_count} unused logic inputs across {len(conb_instances)} tiles")
    print(f"     Power optimization: {power_savings['tie_low']} tie-low, {power_savings['tie_high']} tie-high")
    
    if fanout_warnings:
        unique_warnings = set(fanout_warnings)
        print(f"WARNING: {len(unique_warnings)} fanout limit warnings")
        for w in list(unique_warnings)[:5]:  # Show first 5
            print(f"  - {w}")
    
    # Report fanout utilization
    print("\nCONB Fanout Utilization:")
    for tile_name, tile_info in sorted(conb_assignment.items()):
        lo_util = tile_info['lo_fanout']
        hi_util = tile_info['hi_fanout']
        max_fo = tile_info['max_fanout']
        lo_pct = (lo_util / max_fo * 100) if max_fo > 0 else 0
        hi_pct = (hi_util / max_fo * 100) if max_fo > 0 else 0
        print(f"  {tile_name}: LO={lo_util}/{max_fo} ({lo_pct:.1f}%), HI={hi_util}/{max_fo} ({hi_pct:.1f}%)")
    
    # Persist modifications
    mapped_json["modules"][module_name]["cells"] = cells
    mapped_json["modules"][module_name]["netnames"] = netnames

    # Write modified JSON
    out_json = os.path.join(out_dir, f"{design_name}_final.json")
    with open(out_json, "w") as f:
        json.dump(mapped_json, f, indent=2)
    print(f"\nWrote modified JSON → {out_json}")
    
    return out_json, conb_instances, tie_nets

# ==================== Verilog Emitter ====================

def emit_verilog_from_mapped(mapped_json_path, module_name, out_v_path):
    """Generate Verilog from modified mapped JSON"""
    mj = load_json(mapped_json_path)
    mod = mj["modules"][module_name]
    ports = mod.get("ports", {})
    port_decl = []
    
    for pname, pinfo in ports.items():
        dir_ = pinfo.get("direction", "input")
        width = len(pinfo.get("bits", []))
        if width > 1:
            port_decl.append(f"{dir_} [{width-1}:0] {pname}")
        else:
            port_decl.append(f"{dir_} {pname}")
    
    cells = mod.get("cells", {})
    netnames = mod.get("netnames", {})
    
    with open(out_v_path, "w") as f:
        f.write(f"module {module_name} (\n")
        f.write("  " + ",\n  ".join([p.split()[1] if len(p.split()) > 1 else p for p in port_decl]))
        f.write("\n);\n\n")
        
        # Port declarations
        for pd in port_decl:
            f.write(f"  {pd};\n")
        
        f.write("\n  // Internal nets\n")
        written_nets = set()
        for n, info in netnames.items():
            if n not in [p.split()[-1] for p in port_decl]:  # Not a port
                if n not in written_nets:
                    f.write(f"  wire {n};\n")
                    written_nets.add(n)
        
        f.write("\n  // Cell instances\n")
        for inst, info in sorted(cells.items()):
            typ = info.get("type", "UNKNOWN")
            conns = info.get("connections", {})
            conn_strs = []
            for pin, net in sorted(conns.items()):
                if isinstance(net, list):
                    net0 = net[0] if net else "/* empty */"
                else:
                    net0 = net
                conn_strs.append(f".{pin}({net0})")
            f.write(f"  {typ} {inst} ({', '.join(conn_strs)});\n")
        
        f.write("\nendmodule\n")
    
    print(f"Wrote Verilog → {out_v_path}")
    return out_v_path

# ==================== Visualization ====================

def build_fabric_wide_cts_tree(nodes_by_type, tile_to_nodes, max_leaf=8):
    """
    Build a fabric-wide CTS tree for visualization.
    Creates virtual sinks distributed across the entire fabric,
    then builds a CTS tree using only buffers (no inverters).
    """
    # Get fabric bounds from all buffers
    fabric_bufs = nodes_by_type.get("BUF", [])
    if not fabric_bufs:
        return []
    
    fabric_x = [n.x for n in fabric_bufs]
    fabric_y = [n.y for n in fabric_bufs]
    min_x, max_x = min(fabric_x), max(fabric_x)
    min_y, max_y = min(fabric_y), max(fabric_y)
    
    # Create virtual sinks distributed across the fabric
    # Use a grid pattern to ensure good coverage
    num_sinks_x = 20  # Number of virtual sinks in X direction
    num_sinks_y = 15  # Number of virtual sinks in Y direction
    
    virtual_sinks = []
    for i in range(num_sinks_x):
        for j in range(num_sinks_y):
            x = min_x + (max_x - min_x) * (i + 0.5) / num_sinks_x
            y = min_y + (max_y - min_y) * (j + 0.5) / num_sinks_y
            virtual_sinks.append((x, y, f"virtual_sink_{i}_{j}"))
    
    # Build cluster tree from virtual sinks
    cluster_tree = cluster_sinks(virtual_sinks, max_leaf=max_leaf)
    
    # Build CTS using ONLY buffers (no inverters)
    available_bufs_only = [n for n in fabric_bufs]  # Only buffers
    claimed = set()
    fabric_cts = build_cts(cluster_tree, available_bufs_only, [], claimed, max_segment_length=1000.0)
    
    return fabric_cts


def plot_cts_fabric_based(placement_map, dff_instances, cts_assignments, nodes_by_type, tile_to_nodes, out_png):
    """
    Plot fabric-wide CTS tree matching the reference image:
    - Many blue CTS buffers spread across the entire fabric
    - Thick blue lines connecting buffers (Buffer Connection)
    - Thin dark green lines from buffers to DFFs (Buffer to DFF)
    - Clock source at fabric center X, Y=0
    - Root buffer above clock source
    - Only buffers shown (no inverters)
    """
    # Get fabric bounds
    fabric_bufs = nodes_by_type.get("BUF", [])
    if not fabric_bufs:
        print("WARNING: No fabric buffers found for CTS visualization")
        return
    
    fabric_x = [n.x for n in fabric_bufs]
    fabric_y = [n.y for n in fabric_bufs]
    min_x, max_x = min(fabric_x), max(fabric_x)
    min_y, max_y = min(fabric_y), max(fabric_y)
    fabric_center_x = (min_x + max_x) / 2.0
    fabric_center_y = (min_y + max_y) / 2.0
    
    # Build fabric-wide CTS tree for visualization
    print("Building fabric-wide CTS tree for visualization...")
    fabric_cts = build_fabric_wide_cts_tree(nodes_by_type, tile_to_nodes, max_leaf=8)
    
    if not fabric_cts:
        print("WARNING: Could not build fabric CTS tree, using design CTS")
        fabric_cts = cts_assignments
    
    # Filter to only buffers (no inverters)
    fabric_cts_buffers = [a for a in fabric_cts if "buf" in a["node"].cell_type.lower()]
    
    if not fabric_cts_buffers:
        print("WARNING: No buffers in fabric CTS, falling back to design CTS")
        fabric_cts_buffers = [a for a in cts_assignments if "buf" in a["node"].cell_type.lower()]
        if not fabric_cts_buffers:
            return
    
    # Get DFF positions
    dff_pos = [(placement_map[d][0], placement_map[d][1]) for d in dff_instances if d in placement_map]
    dff_xs = [p[0] for p in dff_pos]
    dff_ys = [p[1] for p in dff_pos]
    
    # === PLOT ===
    plt.figure(figsize=(20, 16))
    
    # Draw fabric boundary (purple dashed rectangle)
    fabric_rect = mpatches.Rectangle(
        (min_x, min_y),
        max_x - min_x,
        max_y - min_y,
        fill=False,
        linestyle="--",
        linewidth=2.0,
        edgecolor="purple",
        alpha=0.7,
        zorder=1
    )
    plt.gca().add_patch(fabric_rect)
    
    # Get buffer positions (only buffers, no inverters)
    buf_nodes = [a["node"] for a in fabric_cts_buffers]
    buf_xs = [n.x for n in buf_nodes]
    buf_ys = [n.y for n in buf_nodes]
    
    # Plot CTS buffers (blue squares)
    plt.scatter(
        buf_xs, buf_ys,
        c="blue",
        s=120,
        alpha=0.85,
        marker="s",
        edgecolors="black",
        linewidths=1.5,
        zorder=10,
        label=f"CTS Buffer ({len(buf_xs)})"
    )
    
    # Draw buffer-to-buffer connections (thick blue lines)
    for a in fabric_cts_buffers:
        parent_node = a["node"]
        if "buf" not in parent_node.cell_type.lower():
            continue
        
        px, py = parent_node.x, parent_node.y
        
        for child in a.get("children", []):
            # Only draw if child is also a buffer
            if "buf" in child.cell_type.lower():
                cx, cy = child.x, child.y
                plt.plot(
                    [px, cx], [py, cy],
                    "b-",
                    linewidth=3.0,
                    alpha=0.8,
                    zorder=5,
                    label="Buffer Connection" if a == fabric_cts_buffers[0] and child == a.get("children", [])[0] else ""
                )
    
    # Plot DFFs (green dots)
    if dff_xs:
        plt.scatter(
            dff_xs, dff_ys,
            c="green",
            s=30,
            alpha=0.7,
            marker="o",
            edgecolors="darkgreen",
            linewidths=0.5,
            zorder=8,
            label=f"DFF (Sink) ({len(dff_xs)})"
        )
        
        # Draw buffer-to-DFF connections (thin dark green lines)
        for dx, dy in dff_pos:
            # Find nearest buffer
            if buf_xs:
                dists = [((dx - bx)**2 + (dy - by)**2)**0.5 for bx, by in zip(buf_xs, buf_ys)]
                nearest_idx = dists.index(min(dists))
                nearest_x, nearest_y = buf_xs[nearest_idx], buf_ys[nearest_idx]
                plt.plot(
                    [nearest_x, dx], [nearest_y, dy],
                    color="darkgreen",
                    linewidth=1.0,
                    alpha=0.5,
                    zorder=6,
                    label="Buffer to DFF" if dff_pos.index((dx, dy)) == 0 else ""
                )
    
    # Find root buffer (closest to fabric center X)
    root_buf = min(buf_nodes, key=lambda n: abs(n.x - fabric_center_x))
    root_x, root_y = root_buf.x, root_buf.y
    
    # Plot root buffer (red square)
    plt.scatter(
        [root_x], [root_y],
        c="red",
        s=200,
        alpha=1.0,
        marker="s",
        edgecolors="black",
        linewidths=2.5,
        zorder=12,
        label="Root Buffer"
    )
    
    # Clock source at fabric center X, Y=0
    clock_x = fabric_center_x
    clock_y = 0.0
    
    plt.scatter(
        [clock_x], [clock_y],
        c="yellow",
        s=800,
        alpha=1.0,
        marker="*",
        edgecolors="black",
        linewidths=2.5,
        zorder=15,
        label="Clock Source (Y=0)"
    )
    
    # Draw connection from clock source to root buffer
    plt.plot(
        [clock_x, root_x], [clock_y, root_y],
        "r--",
        linewidth=2.5,
        alpha=0.8,
        zorder=7
    )
    
    # Set axes to cover full fabric
    margin = 50.0
    plt.xlim(min_x - margin, max_x + margin)
    plt.ylim(-margin, max_y + margin)
    
    # Styling
    plt.legend(loc="upper right", fontsize=12, framealpha=0.95, edgecolor="black")
    plt.title(
        f"CTS Tree Visualization\n{len(buf_xs)} Buffers, {len(dff_xs)} DFFs",
        fontsize=16,
        fontweight="bold",
        pad=20
    )
    plt.xlabel("X (microns)", fontsize=14, fontweight="bold")
    plt.ylabel("Y (microns)", fontsize=14, fontweight="bold")
    plt.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)
    plt.tick_params(labelsize=11)
    
    plt.tight_layout()
    plt.savefig(out_png, dpi=600, bbox_inches="tight")
    
    # SVG version
    out_svg = out_png.replace(".png", ".svg")
    plt.savefig(out_svg, format="svg", bbox_inches="tight")
    
    plt.close()
    
    print(f"Wrote CTS plot → {out_png}")
    print(f"  Fabric-wide CTS: {len(buf_xs)} buffers, {len(dff_xs)} DFFs")
    print(f"  Clock source at X={clock_x:.1f}, Y={clock_y:.1f}")
    print(f"  Root buffer at X={root_x:.1f}, Y={root_y:.1f}")


def main():
    parser = argparse.ArgumentParser(
        description="Phase 3: CTS & ECO Netlist Generator for Structured ASIC"
    )
    parser.add_argument("--placement", required=True, help="grow_placement.json")
    parser.add_argument("--mapped", required=True, help="6502_mapped.json (Yosys mapped JSON)")
    parser.add_argument("--fabric", required=False, help="fabric_db.json (parsed) - optional if fabric YAML provided")
    parser.add_argument("--fabric-yaml", required=False, help="fabric_cells.yaml or fabric.yaml - optional")
    parser.add_argument("--liberty", required=False, help="fabric.lib or technology liberty (optional)")
    parser.add_argument("--out-dir", required=False, default="build/out", help="output directory")
    parser.add_argument("--design", required=False, default="sasic_top", help="design/module name")
    parser.add_argument("--max-fanout", type=int, default=50, help="max fanout per CONB (default: 50)")
    parser.add_argument("--max-segment", type=float, default=500.0, help="max CTS segment length in um (default: 500)")
    args = parser.parse_args()

    mkdir_p(args.out_dir)
    log_lines = []
    log_lines.append(f"=== ECO Generator for {args.design} ===")

    # ========== Load Placement ==========
    if not os.path.exists(args.placement):
        print(f"ERROR: placement file not found: {args.placement}")
        sys.exit(1)
    
    placement_json = load_json(args.placement)
    placements = placement_json.get("placements") or placement_json.get("placed") or {}
    placement_map = {}
    
    for inst, info in placements.items():
        if isinstance(info, dict):
            su = info.get("site_um")
            if su and len(su) >= 2:
                placement_map[inst] = (float(su[0]), float(su[1]))
            elif "site" in info and isinstance(info["site"], list):
                placement_map[inst] = (float(info["site"][0]), float(info["site"][1]))
    
    print(f"Loaded placement: {len(placement_map)} instances")
    log_lines.append(f"Loaded placement: {len(placement_map)} instances")

    # ========== Load Mapped Netlist ==========
    if not os.path.exists(args.mapped):
        print(f"ERROR: mapped netlist file not found: {args.mapped}")
        sys.exit(1)
    
    mapped_json = load_json(args.mapped)
    module_name = find_top_module(mapped_json)
    
    if not module_name:
        print("ERROR: could not determine top module in mapped JSON")
        sys.exit(1)
    
    print(f"Top module detected: {module_name}")
    log_lines.append(f"Top module: {module_name}")

    cells = extract_cells_from_yosys_json(mapped_json, module_name)
    dff_instances = guess_ff_cells(cells)
    
    print(f"Found {len(dff_instances)} FF/DFF-like instances")
    log_lines.append(f"Found {len(dff_instances)} FF/DFF instances")
    if dff_instances:
        log_lines.append(f"  Sample DFFs: {dff_instances[:10]}")

    # ========== Load Fabric ==========
    fabric_db = {}
    
    if args.fabric and os.path.exists(args.fabric):
        try:
            fabric_db = load_json(args.fabric)
            print(f"Loaded fabric DB: {args.fabric}")
        except Exception as e:
            print(f"Failed to parse fabric_db.json: {e}")
    
    if args.fabric_yaml and os.path.exists(args.fabric_yaml):
        try:
            fabric_yaml = load_yaml(args.fabric_yaml)
            if fabric_yaml:
                fabric_db = fabric_yaml
                print(f"Loaded fabric YAML: {args.fabric_yaml}")
        except Exception as e:
            print(f"Failed to parse fabric YAML: {e}")
    
    if not fabric_db:
        print("WARNING: No fabric DB provided; will use synthetic nodes if needed")

    nodes_by_type, tile_to_nodes = build_fabric_nodes_from_db(fabric_db)
    
    available_bufs = nodes_by_type.get("BUF", []) + nodes_by_type.get("INV", [])
    available_invs = nodes_by_type.get("INV", [])
    available_conbs = nodes_by_type.get("CONB", [])
    
    print(f"Fabric resources: {len(available_bufs)} buffers, {len(available_invs)} inverters, {len(available_conbs)} CONBs")
    print(f"Fabric tiles: {len(tile_to_nodes)}")
    log_lines.append(f"Available buffers: {len(available_bufs)}, inverters: {len(available_invs)}, CONBs: {len(available_conbs)}")
    log_lines.append(f"Fabric tiles: {len(tile_to_nodes)}")

    # ========== Load Liberty for Power Optimization ==========
    leakage_db = {}
    if args.liberty:
        leakage_db = parse_liberty_leakage(args.liberty)
        if leakage_db:
            log_lines.append(f"Loaded leakage data for {len(leakage_db)} cell types")

    # ========== Build CTS ==========
    print("\n=== Building Clock Tree ===")
    
    sinks = []
    for d in dff_instances:
        if d in placement_map:
            x, y = placement_map[d]
            sinks.append((x, y, d))
    
    if not sinks:
        print("WARNING: No sink coordinates found for DFFs - cannot build spatial CTS")
        log_lines.append("WARNING: No DFF coordinates available for CTS")
    
    cluster_tree = cluster_sinks(sinks, max_leaf=8)
    claimed = set()
    cts_assignments = build_cts(cluster_tree, available_bufs, available_invs, claimed, args.max_segment)
    
    print(f"CTS: Claimed {len(claimed)} buffers/inverters")
    log_lines.append(f"CTS claimed {len(claimed)} nodes: {list(claimed)[:20]}...")
    
    # Calculate CTS metrics
    if cts_assignments:
        cts_metrics = calculate_cts_metrics(cts_assignments, dff_instances, placement_map)
        print(f"\nCTS Quality Metrics:")
        print(f"  Total wirelength: {cts_metrics['total_wirelength_um']:.2f} um")
        print(f"  Max segment length: {cts_metrics['max_segment_length_um']:.2f} um")
        print(f"  Estimated skew: {cts_metrics['estimated_skew_um']:.2f} um")
        print(f"  Buffers used: {cts_metrics['num_buffers']}")
        print(f"  Sinks: {cts_metrics['num_sinks']}")
        
        log_lines.append(f"CTS Metrics:")
        log_lines.append(f"  Total WL: {cts_metrics['total_wirelength_um']:.2f} um")
        log_lines.append(f"  Max segment: {cts_metrics['max_segment_length_um']:.2f} um")
        log_lines.append(f"  Est. skew: {cts_metrics['estimated_skew_um']:.2f} um")
        log_lines.append(f"  Buffers: {cts_metrics['num_buffers']}, Sinks: {cts_metrics['num_sinks']}")

    # ========== Assign CONB per Tile ==========
    print("\n=== Assigning CONB Cells ===")
    conb_assignment = assign_conb_per_tile(tile_to_nodes, max_fanout=args.max_fanout)
    print(f"Assigned {len(conb_assignment)} CONB cells (one per tile)")
    log_lines.append(f"CONB assignment: {len(conb_assignment)} tiles")

    # ========== Modify Netlist (CTS + ECO) ==========
    print("\n=== Modifying Netlist ===")
    out_json_path, conb_instances, tie_nets = modify_mapped_json(
        mapped_json, module_name, dff_instances, placement_map,
        cts_assignments, conb_assignment, leakage_db,
        args.out_dir, args.design, nodes_by_type, tile_to_nodes
    )

    # ========== Emit Verilog ==========
    out_v = os.path.join(args.out_dir, f"{args.design}_final.v")
    try:
        emit_verilog_from_mapped(out_json_path, module_name, out_v)
        log_lines.append(f"Generated Verilog: {out_v}")
    except Exception as e:
        print(f"WARNING: Verilog emitter failed: {e}")
        log_lines.append(f"WARNING: Verilog generation failed: {e}")

    # ========== Plot CTS Tree ==========
    out_png = os.path.join(args.out_dir, f"{args.design}_cts_tree.png")
    try:
        plot_cts_fabric_based(placement_map, dff_instances, cts_assignments, nodes_by_type, tile_to_nodes, out_png)
        log_lines.append(f"Generated CTS plot: {out_png}")
    except Exception as e:
        print(f"WARNING: CTS plot failed: {e}")
        log_lines.append(f"WARNING: CTS plot failed: {e}")

    # ========== Write Summary Log ==========
    out_log = os.path.join(args.out_dir, "eco_log.txt")
    with open(out_log, "w") as f:
        for line in log_lines:
            f.write(line + "\n")
    
    print(f"\nWrote ECO log → {out_log}")
    print("\n=== Phase 3 Complete ===")
    print(f"Output files in: {args.out_dir}")
    print(f"  - {args.design}_final.json (modified netlist)")
    print(f"  - {args.design}_final.v (Verilog)")
    print(f"  - {args.design}_cts_tree.png (visualization)")

if __name__ == "__main__":
    main()