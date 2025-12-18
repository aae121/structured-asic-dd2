"""
validate_design.py

Fabric vs Logical Design Validator for Structured ASIC Project

This script validates whether a mapped logical design can fit on a given fabric.
It compares the required cell counts by type (from the design) to the available
slots by type (from the fabric), and generates a utilization report.

Usage:
    python src/validate_design.py <fabric_cells_yaml> <logical_db_json>

Arguments:
    fabric_cells_yaml: Path to fabric_cells.yaml with all available slots
    logical_db_json: Path to logical_db_*.json file (from parsers/logical_parser.py)

Outputs:
    - Prints a utilization report to stdout
    - Exits with code 1 if any cell type exceeds available slots (validation fails)
    - Exits with code 0 if design fits on fabric (validation passes)

Example:
    python src/validate_design.py fabric/fabric_cells.yaml parsed_outputs_all/logical_db_6502.json
"""

import os
import sys
import json
import yaml
from collections import defaultdict

# Cell type normalization mapping (full cell name -> short type)
CELL_TYPE_MAP = {
    'sky130_fd_sc_hd__nand2_2': 'NAND',
    'sky130_fd_sc_hd__clkinv_2': 'INV',
    'sky130_fd_sc_hd__clkbuf_4': 'BUF',
    'sky130_fd_sc_hd__conb_1': 'CONB',
    'sky130_fd_sc_hd__dfbbp_1': 'DFBBP',
    'sky130_fd_sc_hd__or2_2': 'OR',
    'sky130_fd_sc_hd__and2_2': 'AND',
    'sky130_fd_sc_hd__tapvpwrvgnd_1': 'TAP',
    'sky130_fd_sc_hd__decap_4': 'DECAP',
    'sky130_fd_sc_hd__decap_3': 'DECAP',
    'sky130_fd_sc_hd__fill_1': 'FILL',
}


def normalize_cell_type(cell_type):
    """Convert full Sky130 cell name to short type code"""
    return CELL_TYPE_MAP.get(cell_type, cell_type)


def load_fabric_cells(fabric_cells_path):
    """
    Load fabric_cells.yaml and count available slots by type.
    
    Returns:
        dict: {cell_type: count} e.g. {'NAND': 48600, 'INV': 12960, ...}
    """
    print(f"[validator] Loading fabric: {fabric_cells_path}")
    
    if not os.path.exists(fabric_cells_path):
        print(f"ERROR: Fabric file not found: {fabric_cells_path}")
        sys.exit(1)
    
    with open(fabric_cells_path, 'r') as f:
        fabric_data = yaml.safe_load(f)
    
    # Count cells by type from fabric_cells_by_tile structure
    fabric_slots = defaultdict(int)
    
    tiles = fabric_data.get('fabric_cells_by_tile', {}).get('tiles', {})
    
    for tile_name, tile_data in tiles.items():
        cells = tile_data.get('cells', [])
        for cell in cells:
            cell_name = cell.get('name', '')
            # Infer cell type from name: T0Y0__R0_NAND_0 -> NAND
            if '__' in cell_name:
                parts = cell_name.split('__')[1].split('_')
                if len(parts) >= 2:
                    # Skip row prefix (R0, R1, etc.)
                    if parts[0].startswith('R') and parts[0][1:].isdigit():
                        cell_type = parts[1]
                    else:
                        cell_type = parts[0]
                    fabric_slots[cell_type] += 1
    
    total_slots = sum(fabric_slots.values())
    print(f"[validator] Found {len(tiles)} tiles, {total_slots} total slots")
    
    return dict(fabric_slots)


def load_logical_db(logical_db_path):
    """
    Load logical_db_*.json and count required cells by type.
    
    Returns:
        dict: {cell_type: count} e.g. {'NAND': 1228, 'INV': 360, ...}
    """
    print(f"[validator] Loading design: {logical_db_path}")
    
    if not os.path.exists(logical_db_path):
        print(f"ERROR: Logical DB file not found: {logical_db_path}")
        sys.exit(1)
    
    with open(logical_db_path, 'r') as f:
        logical_data = json.load(f)
    
    # Count cells by type from logical_db structure
    logical_cells = defaultdict(int)
    
    cells = logical_data.get('cells', {})
    for cell_name, cell_data in cells.items():
        full_type = cell_data.get('type', 'UNKNOWN')
        # Normalize to short type
        short_type = normalize_cell_type(full_type)
        logical_cells[short_type] += 1
    
    total_cells = sum(logical_cells.values())
    print(f"[validator] Found {total_cells} cells in design")
    
    return dict(logical_cells)


def validate_design(fabric_slots, logical_cells, design_name):
    """
    Compare required cells vs available slots.
    Print utilization report and exit with error if validation fails.
    
    Returns:
        bool: True if validation passes, False otherwise
    """
    print(f"\n{'='*70}")
    print(f"Fabric Utilization Report for {design_name}")
    print(f"{'='*70}\n")
    
    # Combine all cell types from both fabric and design
    all_types = sorted(set(fabric_slots.keys()) | set(logical_cells.keys()))
    
    # Print header
    header = f"{'Cell Type':<15} {'Used':>10} / {'Available':<10} {'Utilization':>15}"
    print(header)
    print("-" * len(header))
    
    validation_passed = True
    errors = []
    
    for cell_type in all_types:
        used = logical_cells.get(cell_type, 0)
        available = fabric_slots.get(cell_type, 0)
        
        if available > 0:
            utilization = (used / available) * 100
            util_str = f"({utilization:.1f}%)"
        else:
            util_str = "(N/A)"
        
        # Print row
        print(f"{cell_type:<15} {used:>10} / {available:<10} {util_str:>15}")
        
        # Check if exceeds capacity
        if used > available:
            error_msg = f"  ❌ ERROR: Not enough slots for '{cell_type}' (needed {used}, available {available})"
            print(error_msg)
            errors.append(error_msg)
            validation_passed = False
    
    # Print summary
    print("-" * len(header))
    total_used = sum(logical_cells.values())
    total_available = sum(fabric_slots.values())
    overall_util = (total_used / total_available * 100) if total_available > 0 else 0
    print(f"{'TOTAL':<15} {total_used:>10} / {total_available:<10} ({overall_util:.1f}%)")
    
    print(f"\n{'='*70}")
    
    if validation_passed:
        print("✅ VALIDATION PASSED: Design fits on fabric")
        print(f"{'='*70}\n")
        return True
    else:
        print("❌ VALIDATION FAILED: Design does NOT fit on fabric")
        print(f"\nErrors found:")
        for error in errors:
            print(error)
        print(f"{'='*70}\n")
        return False


def main():
    if len(sys.argv) != 3:
        print("Usage: python src/validate_design.py <fabric_cells_yaml> <logical_db_json>")
        print("\nExample:")
        print("  python src/validate_design.py fabric/fabric_cells.yaml parsed_outputs_all/logical_db_6502.json")
        sys.exit(1)
    
    fabric_cells_path = sys.argv[1]
    logical_db_path = sys.argv[2]
    
    # Extract design name from logical_db filename
    design_name = os.path.basename(logical_db_path).replace('logical_db_', '').replace('.json', '')
    
    # Load data
    fabric_slots = load_fabric_cells(fabric_cells_path)
    logical_cells = load_logical_db(logical_db_path)
    
    # Validate
    validation_passed = validate_design(fabric_slots, logical_cells, design_name)
    
    # Exit with appropriate code
    if validation_passed:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
