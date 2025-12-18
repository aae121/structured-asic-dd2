#!/usr/bin/env python3
"""
eco_generator.py - CTS & ECO Netlist Generation
Usage: python eco_generator.py <design_name> <placement_json>
"""

import sys, json, math, yaml
from pathlib import Path

# Single data structure: {cell_name: {'type', 'site', 'assigned'}}
cells = {}

def get_cells(cell_type, assigned):
    return [n for n, c in cells.items() if c['type'] == cell_type and c['assigned'] == assigned]

def distance(site1, site2):
    return math.sqrt((site1[0]-site2[0])**2 + (site1[1]-site2[1])**2)

def find_nearest(target, candidates):
    return min((c for c in candidates if cells[c]['site']), 
               key=lambda c: distance(cells[c]['site'], target), default=None)

def center(cell_list):
    sites = [cells[c]['site'] for c in cell_list if cells[c]['site']]
    if not sites: return None
    return (sum(s[0] for s in sites)/len(sites), sum(s[1] for s in sites)/len(sites))


def load_data(design_name, placement_file):
    with open(f"parsed_outputs_all/logical_db_{design_name}.json") as f:
        logical = json.load(f)
    with open(f"fabric/fabric_cells.yaml") as f:
        fabric = yaml.safe_load(f)
    with open(placement_file) as f:
        data = json.load(f)
        placement = data.get("placements", data)
    
    # Build cell database from logical design cells
    for name, info in logical['cells'].items():
        cells[name] = {
            'type': info['type'],
            'site': placement.get(name, {}).get('site'),
            'assigned': True,  # All design cells are assigned
            'connections': info.get('connections', {})
        }
    
    # Add all fabric cells that are NOT in placement
    cell_type_map = {
        '_NAND_': 'sky130_fd_sc_hd__nand2_2',
        '_INV_': 'sky130_fd_sc_hd__clkinv_2',
        '_BUF_': 'sky130_fd_sc_hd__clkbuf_4',
        '_CONB_': 'sky130_fd_sc_hd__conb_1',
        '_DFF_': 'sky130_fd_sc_hd__dfbbp_1'
    }
    
    for tile_name, tile_data in fabric['fabric_cells_by_tile']['tiles'].items():
        for cell in tile_data['cells']:
            cell_name = cell['name']
            if cell_name not in cells:  # Not used in design
                # Determine cell type from name
                cell_type = None
                for pattern, ctype in cell_type_map.items():
                    if pattern in cell_name:
                        cell_type = ctype
                        break
                
                if cell_type in ['sky130_fd_sc_hd__clkbuf_4', 'sky130_fd_sc_hd__clkinv_2', 'sky130_fd_sc_hd__conb_1']:
                    cells[cell_name] = {
                        'type': cell_type,
                        'site': (cell.get('x', 0), cell.get('y', 0)),
                        'assigned': False,  # Available for CTS/ECO
                        'connections': {}
                    }
    
    return logical['nets'].copy(), logical.get('ports', {})


def h_tree_cts(dffs, nets):
    print("\n========== CTS (H-Tree using ALL Fabric Buffers) ==========")
    
    # CTS Parameters
    MAX_FANOUT = 16           # Max fanout per buffer stage
    
    # Get ALL fabric buffers (both used and unused)
    all_buffers = [name for name, cell in cells.items() 
                   if cell['type'] == 'sky130_fd_sc_hd__clkbuf_4']
    
    # Separate available (unused) from already assigned buffers
    available_buffers = [b for b in all_buffers if not cells[b]['assigned']]
    
    print(f"Total fabric buffers: {len(all_buffers)}")
    print(f"Available buffers: {len(available_buffers)}")
    print(f"DFFs to connect: {len(dffs)}")
    
    if not dffs:
        print("No DFFs found - skipping CTS")
        return nets, []
    
    if not available_buffers:
        print("WARNING: No available buffers for CTS - direct clock connection")
        for dff in dffs:
            cells[dff].setdefault('connections', {})['CLK'] = 'clk'
        return nets, []
    
    # === STRATEGY: Use ALL buffers in H-tree ===
    # Level 0 (leaf): Each buffer drives DFFs or nothing
    # Upper levels: Each buffer drives up to MAX_FANOUT buffers below
    
    clock_buffers = []
    remaining_buffers = available_buffers.copy()
    
    # Sort buffers by position for better spatial distribution
    remaining_buffers.sort(key=lambda b: (cells[b]['site'][1], cells[b]['site'][0]) if cells[b]['site'] else (0, 0))
    
    # === Level 0: Connect DFFs to leaf buffers ===
    print(f"\n  Level 0: Assigning {len(dffs)} DFFs to leaf buffers")
    
    # Group DFFs by nearest buffer
    l0_buffers = {}  # buffer_name -> list of connected DFFs
    dff_assigned = set()
    
    for dff in dffs:
        dff_site = cells[dff]['site']
        if not dff_site:
            continue
        
        # Find nearest available buffer
        best_buf = None
        min_dist = float('inf')
        for buf in remaining_buffers:
            buf_site = cells[buf]['site']
            if buf_site:
                dist = distance(dff_site, buf_site)
                if dist < min_dist:
                    min_dist = dist
                    best_buf = buf
        
        if best_buf:
            if best_buf not in l0_buffers:
                l0_buffers[best_buf] = []
            l0_buffers[best_buf].append(dff)
            dff_assigned.add(dff)
            
            # If buffer reached MAX_FANOUT, remove from further DFF assignment
            if len(l0_buffers[best_buf]) >= MAX_FANOUT:
                remaining_buffers.remove(best_buf)
    
    # All remaining buffers are also L0 (with 0 DFFs) - they still need to be in tree
    for buf in remaining_buffers[:]:
        if buf not in l0_buffers:
            l0_buffers[buf] = []  # Empty leaf buffer
    
    # Assign L0 buffer connections
    l0_buf_list = list(l0_buffers.keys())
    for buf_idx, buf in enumerate(l0_buf_list):
        net_name = f"clk_L0_B{buf_idx}"
        dff_list = l0_buffers[buf]
        
        cells[buf]['assigned'] = True
        cells[buf]['connections'] = {'A': 'TBD', 'X': net_name}
        
        for dff in dff_list:
            cells[dff].setdefault('connections', {})['CLK'] = net_name
        
        clock_buffers.append(buf)
    
    # Remove all L0 buffers from remaining
    remaining_buffers = [b for b in available_buffers if b not in l0_buffers]
    
    print(f"    L0: {len(l0_buf_list)} buffers (driving {len(dff_assigned)} DFFs)")
    print(f"    Remaining buffers for upper levels: {len(remaining_buffers)}")
    
    # === Build upper levels ===
    current_level_bufs = l0_buf_list
    level = 1
    
    while len(current_level_bufs) > 1:
        # How many parent buffers needed?
        num_parents = (len(current_level_bufs) + MAX_FANOUT - 1) // MAX_FANOUT
        
        if remaining_buffers:
            # Use available buffers for this level
            num_parents = min(num_parents, len(remaining_buffers))
        
        if num_parents == 0:
            break
        
        print(f"\n  Level {level}: {len(current_level_bufs)} children -> {num_parents} parent buffers")
        
        next_level_bufs = []
        children_per_parent = (len(current_level_bufs) + num_parents - 1) // num_parents
        
        for parent_idx in range(num_parents):
            start = parent_idx * children_per_parent
            end = min(start + children_per_parent, len(current_level_bufs))
            child_bufs = current_level_bufs[start:end]
            
            if not child_bufs:
                continue
            
            # Find center of children
            child_center = center(child_bufs)
            
            # Get parent buffer
            if remaining_buffers:
                parent_buf = find_nearest(child_center, remaining_buffers) if child_center else remaining_buffers[0]
                remaining_buffers.remove(parent_buf)
            else:
                # No more buffers - use first child as parent (collapse)
                parent_buf = child_bufs[0]
                child_bufs = child_bufs[1:]
            
            parent_net = f"clk_L{level}_B{parent_idx}"
            
            cells[parent_buf]['assigned'] = True
            cells[parent_buf]['connections'] = {'A': 'TBD', 'X': parent_net}
            
            # Connect children to parent
            for child in child_bufs:
                cells[child]['connections']['A'] = parent_net
            
            next_level_bufs.append(parent_buf)
            if parent_buf not in clock_buffers:
                clock_buffers.append(parent_buf)
        
        current_level_bufs = next_level_bufs
        level += 1
        
        if len(current_level_bufs) <= 1:
            break
    
    # === Root: Connect top-level buffers to 'clk' ===
    print(f"\n  Root: {len(current_level_bufs)} buffers connect to clk port")
    for buf in current_level_bufs:
        cells[buf]['connections']['A'] = 'clk'
    
    total_levels = level
    
    print(f"\nCTS Complete:")
    print(f"  - {len(clock_buffers)} buffers used")
    print(f"  - {total_levels} tree levels")
    print(f"  - {len(dffs)} DFFs connected")
    print(f"  - Clock path: clk port -> L{total_levels-1} -> ... -> L0 -> DFFs")
    
    # Add all clock buffers to the clock net for tracking
    nets.setdefault('clk', []).extend(clock_buffers)
    
    return nets, clock_buffers

def power_down_eco(nets):
    print("\n========== POWER-DOWN ECO ==========")
    MAX_FANOUT = 100  # Realistic fanout limit per tie cell
    SEARCH_RADIUS = 200  # Search within this distance (in sites) for CONB
    
    conb_cells = get_cells('sky130_fd_sc_hd__conb_1', False)
    if not conb_cells:
        print("No CONB cells")
        return nets
    
    # Get all unused logic cells
    logic_types = ['sky130_fd_sc_hd__nand2_2', 'sky130_fd_sc_hd__nor2_2', 
                   'sky130_fd_sc_hd__clkinv_2', 'sky130_fd_sc_hd__clkbuf_4']
    unused = [c for t in logic_types for c in get_cells(t, False)]
    
    print(f"Unused cells: {len(unused)}")
    print(f"Available CONB: {len(conb_cells)}")
    
    # Leakage power optimization: which pin (HI or LO) is best per cell type
    leakage_config = {
        'nand': 'LO',  # NAND with all inputs = 0 has lowest leakage
        'nor': 'HI',   # NOR with all inputs = 1 has lowest leakage
        'inv': 'LO',   # INV with input = 0 (output = 1) has lower leakage
        'buf': 'LO',   # BUF with input = 0 has lower leakage
    }
    
    # Track CONB usage: {conb_name: {'lo_count', 'hi_count', 'lo_net', 'hi_net'}}
    conb_usage = {}
    
    # Process each unused cell individually
    cells_tied = 0
    
    for cell in unused:
        if not cells[cell]['site']:
            continue
        
        cell_site = cells[cell]['site']
        cell_type = cells[cell]['type'].lower()
        
        # Determine optimal tie pin for this cell
        optimal_tie = 'LO'  # default
        for key, tie_pin in leakage_config.items():
            if key in cell_type:
                optimal_tie = tie_pin
                break
        
        # Find closest CONB within search radius
        candidates = []
        for conb in conb_cells:
            if not cells[conb]['site']:
                continue
            
            dist = distance(cell_site, cells[conb]['site'])
            if dist <= SEARCH_RADIUS:
                # Check if this CONB has capacity
                usage = conb_usage.get(conb, {'lo_count': 0, 'hi_count': 0})
                total = usage['lo_count'] + usage['hi_count']
                
                if total < MAX_FANOUT:
                    candidates.append((dist, conb))
        
        if not candidates:
            continue  # No nearby CONB with capacity
        
        # Pick closest CONB
        candidates.sort()
        best_conb = candidates[0][1]
        
        # Initialize CONB usage if first time
        if best_conb not in conb_usage:
            conb_usage[best_conb] = {
                'lo_count': 0,
                'hi_count': 0,
                'lo_net': f"tie_lo_{best_conb}",
                'hi_net': f"tie_hi_{best_conb}"
            }
        
        # Assign cell to CONB with optimal pin
        usage = conb_usage[best_conb]
        
        if optimal_tie == 'LO':
            # Tie cell input to LO net
            net_lo = usage['lo_net']
            
            if net_lo not in nets:
                nets[net_lo] = [best_conb]
            
            nets[net_lo].append(cell)
            cells[cell]['assigned'] = True
            usage['lo_count'] += 1
            
            # Connect cell inputs to LO net
            if 'nand' in cell_type or 'nor' in cell_type:
                cells[cell]['connections'] = {'A': net_lo, 'B': net_lo}
            else:  # inv or buf
                cells[cell]['connections'] = {'A': net_lo}
        
        else:  # HI
            # Tie cell input to HI net
            net_hi = usage['hi_net']
            
            if net_hi not in nets:
                nets[net_hi] = [best_conb]
            
            nets[net_hi].append(cell)
            cells[cell]['assigned'] = True
            usage['hi_count'] += 1
            
            # Connect cell inputs to HI net
            if 'nand' in cell_type or 'nor' in cell_type:
                cells[cell]['connections'] = {'A': net_hi, 'B': net_hi}
            else:  # inv or buf
                cells[cell]['connections'] = {'A': net_hi}
        
        cells_tied += 1
    
    # Assign all used CONB cells and configure their connections
    conbs_used = 0
    for conb, usage in conb_usage.items():
        if usage['lo_count'] > 0 or usage['hi_count'] > 0:
            cells[conb]['assigned'] = True
            conbs_used += 1
            
            # Configure CONB pins based on what's used
            if usage['lo_count'] > 0 and usage['hi_count'] > 0:
                # Both pins used
                cells[conb]['connections'] = {'HI': usage['hi_net'], 'LO': usage['lo_net']}
            elif usage['lo_count'] > 0:
                # Only LO used
                cells[conb]['connections'] = {'HI': 'vdd_unused', 'LO': usage['lo_net']}
            else:
                # Only HI used
                cells[conb]['connections'] = {'HI': usage['hi_net'], 'LO': 'gnd_unused'}
            
            print(f"  CONB {conb}: {usage['lo_count']} LO ties, {usage['hi_count']} HI ties")
    
    print(f"Total tied: {cells_tied} cells using {conbs_used} CONB (search radius: {SEARCH_RADIUS} sites)")
    return nets

def generate_verilog(design_name, nets, ports):
    output = Path(f"build/{design_name}")
    output.mkdir(parents=True, exist_ok=True)
    
    # Statistics
    assigned = sum(1 for c in cells.values() if c['assigned'])
    design_cells = sum(1 for c in cells.values() if c['assigned'] and c.get('connections'))
    eco_cells = assigned - design_cells
    
    with open(output / f"{design_name}_final.v", 'w') as f:
        # Header comment
        f.write(f"// {design_name} Final Netlist with CTS and ECO\n")
        f.write(f"// Design cells: {design_cells}\n")
        f.write(f"// CTS/ECO cells: {eco_cells}\n")
        f.write(f"// Total: {assigned}\n\n")
        
        # Module declaration with ports
        port_list = ', '.join(ports.keys()) if ports else ''
        f.write(f"module {design_name}_final ({port_list});\n\n")
        
        # Port declarations
        for port_name, port_info in ports.items():
            direction = port_info.get('direction', 'input')
            f.write(f"  {direction} {port_name};\n")
        f.write("\n")
        
        # Wire declarations for nets
        f.write("  // Internal nets\n")
        for net_name in sorted(nets.keys()):
            if net_name not in ports:  # Don't redeclare ports
                f.write(f"  wire {net_name};\n")
        f.write("\n")
        
        # Cell instantiations with connections
        f.write("  // Cell instantiations\n")
        for cell_name, cell_data in sorted(cells.items()):
            if cell_data['assigned']:  # Only instantiate assigned cells
                cell_type = cell_data['type']
                connections = cell_data.get('connections', {})
                
                f.write(f"  {cell_type} {cell_name} (")
                if connections:
                    conn_list = [f".{pin}({net})" for pin, net in sorted(connections.items())]
                    f.write(', '.join(conn_list))
                f.write(f");\n")
        
        f.write("\nendmodule\n")
    
    print(f"\nVerilog: build/{design_name}/{design_name}_final.v")
    print(f"  Design cells: {design_cells}")
    print(f"  CTS/ECO cells: {eco_cells}")
    print(f"  Total cells: {assigned}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python eco_generator.py <design_name> <placement_json>")
        sys.exit(1)
    
    design, placement = sys.argv[1], sys.argv[2]
    print(f"ECO GENERATOR: {design}")
    
    nets, ports = load_data(design, placement)
    dffs = get_cells('sky130_fd_sc_hd__dfbbp_1', True)
    
    nets, clock_buffers = h_tree_cts(dffs, nets)
    nets = power_down_eco(nets)
    generate_verilog(design, nets, ports)
    
    # Save CTS data for visualization
    output_dir = Path(f"build/{design}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cts_data = {
        'clock_buffers': [
            {
                'name': buf,
                'site': cells[buf]['site'],
                'connections': cells[buf]['connections']
            }
            for buf in clock_buffers
        ],
        'dffs': [
            {
                'name': dff,
                'site': cells[dff]['site'],
                'connections': cells[dff]['connections']
            }
            for dff in dffs
        ]
    }
    
    with open(output_dir / f"{design}_cts_data.json", 'w') as f:
        json.dump(cts_data, f, indent=2)
    
    print("COMPLETE")
