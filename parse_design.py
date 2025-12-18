"""
parse_design.py

Phase 1 - Step 2: Logical Design Netlist Parser for Structured ASIC Project

This module provides a single public function, `load_logical_db`, which parses
a mapped JSON design file and constructs a logical_db dictionary describing the
logical design: all instances and nets. This is the canonical source of logical
netlist information for all later project phases (validation, placement, etc).

logical_db structure:
- logical_db["instances"]: dict
    - key: inst_name (unique string from JSON)
    - value: {
        "type": <cell_type>,
        "connections": {port: net_name, ...}
      }
- logical_db["nets"]: dict
    - key: net_name (string)
    - value: {
        "drivers": ["inst.port", ...],
        "loads": ["inst.port", ...]
      }
- logical_db["cell_count_by_type"]: dict
    - key: cell_type (string)
    - value: count (int)

Author: [Your Name]
"""

import os
import sys
import json
from collections import defaultdict
from typing import Dict, Any

def load_logical_db(design_path: str) -> dict:
    """
    Parse a mapped JSON design file and build the logical_db structure.
    Args:
        design_path (str): Path to mapped JSON file.
    Returns:
        dict: logical_db as described above.
    Raises:
        Exception: On file or format errors.
    """
    if not os.path.isfile(design_path):
        raise FileNotFoundError(f"Design file not found: {design_path}")
    with open(design_path, 'r') as f:
        try:
            design = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to parse JSON: {e}")

    # Find the top module (first in 'modules' or with 'top' attribute)
    modules = design.get('modules', {})
    top_mod = None
    for name, mod in modules.items():
        if mod.get('attributes', {}).get('top', '0'*32)[-1] == '1':
            top_mod = mod
            break
    if top_mod is None and modules:
        top_mod = next(iter(modules.values()))
    if top_mod is None:
        raise ValueError("No modules found in design JSON.")

    # Build bit index to net name mapping
    netnames = top_mod.get('netnames', {})
    bit_to_net = {}
    for net, netinfo in netnames.items():
        for bit in netinfo.get('bits', []):
            bit_to_net[bit] = net

    # Parse instances
    instances = {}
    cell_count_by_type = defaultdict(int)
    cells = top_mod.get('cells', {})
    for inst_name, cell in cells.items():
        cell_type = cell.get('type', 'UNKNOWN')
        connections = {}
        for port, bits in cell.get('connections', {}).items():
            if not bits:
                continue
            # Only support single-bit ports for now
            bit = bits[0]
            net = bit_to_net.get(bit, str(bit))
            connections[port] = net
        instances[inst_name] = {
            'type': cell_type,
            'connections': connections
        }
        cell_count_by_type[cell_type] += 1

    # Parse nets: drivers and loads
    nets = defaultdict(lambda: {'drivers': [], 'loads': []})
    for inst_name, cell in cells.items():
        cell_type = cell.get('type', 'UNKNOWN')
        port_dirs = cell.get('port_directions', {})
        for port, bits in cell.get('connections', {}).items():
            if not bits:
                continue
            bit = bits[0]
            net = bit_to_net.get(bit, str(bit))
            direction = port_dirs.get(port, '').lower()
            if direction == 'output':
                nets[net]['drivers'].append(f"{inst_name}.{port}")
            elif direction == 'input':
                nets[net]['loads'].append(f"{inst_name}.{port}")
            else:
                # If direction unknown, treat as load (conservative)
                nets[net]['loads'].append(f"{inst_name}.{port}")

    # Add top-level ports as drivers/loads
    ports = top_mod.get('ports', {})
    for port, portinfo in ports.items():
        direction = portinfo.get('direction', '').lower()
        for bit in portinfo.get('bits', []):
            net = bit_to_net.get(bit, str(bit))
            if direction == 'input':
                nets[net]['drivers'].append(f"PORT.{port}")
            elif direction == 'output':
                nets[net]['loads'].append(f"PORT.{port}")
            elif direction == 'inout':
                nets[net]['drivers'].append(f"PORT.{port}")
                nets[net]['loads'].append(f"PORT.{port}")

    logical_db = {
        'instances': dict(instances),
        'nets': dict(nets),
        'cell_count_by_type': dict(cell_count_by_type)
    }
    return logical_db

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python src/parse_design.py <design_json>")
        sys.exit(1)
    design_path = sys.argv[1]
    try:
        logical_db = load_logical_db(design_path)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    print(f"Number of instances: {len(logical_db['instances'])}")
    print(f"Number of nets: {len(logical_db['nets'])}")
    print("Cell type distribution:")
    for cell_type, count in sorted(logical_db['cell_count_by_type'].items()):
        print(f"  {cell_type}: {count}")
