"""
validator.py

Fabric vs Logical Design Validator for Structured ASIC Project

This script validates whether a mapped logical design can fit on a given fabric.
It compares the required cell counts by type (from the design) to the available
slots by type (from the fabric), and generates a utilization report.

Usage:
    python src/validator.py <fabric_cells_yaml> <logical_db_json>

Arguments:
    fabric_cells_yaml: Path to fabric_cells.yaml with all available slots
    logical_db_json: Path to logical_db_*.json file (from parsers/logical_parser.py)

Outputs:
    - Prints a utilization report to stdout
    - Exits with code 1 if any cell type exceeds available slots (validation fails)
    - Exits with code 0 if design fits on fabric (validation passes)

Example:
    python src/validator.py fabric/fabric_cells.yaml parsed_outputs_all/logical_db_6502.json
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

def validate_fabric_vs_design(fabric_dir: str, design_path: str):
    """
    Validate if the logical design fits on the fabric.
    Returns: (report_string, fabric_db, logical_db)
    Raise SystemExit(1) if not enough slots for any cell type.
    """
    # Load databases
    fabric_db = load_fabric_db(os.path.join(fabric_dir, "fabric_cells.yaml"), os.path.join(fabric_dir, "pins.yaml"))
    logical_db = load_logical_db(design_path)

    # Gather available slots by type
    fabric_slots = {k: len(v) for k, v in fabric_db.get('cells_by_type', {}).items()}
    logical_cells_raw = logical_db.get('cell_count_by_type', {})
    # Normalize logical cell types to fabric cell types
    logical_cells = {}
    for cell_type, count in logical_cells_raw.items():
        norm_type = normalize_cell_type(cell_type)
        logical_cells[norm_type] = logical_cells.get(norm_type, 0) + count

    # Prepare report
    lines = []
    lines.append(f"Fabric Utilization Report for {os.path.basename(design_path)}")
    lines.append("")
    header = f"{'Cell Type':<12} {'Used':>8} / {'Available':<8} Utilization"
    lines.append(header)
    lines.append("-" * len(header))
    error_found = False
    for cell_type in sorted(set(fabric_slots) | set(logical_cells)):
        used = logical_cells.get(cell_type, 0)
        available = fabric_slots.get(cell_type, 0)
        utilization = (used / available * 100) if available else 0.0
        line = f"{cell_type:<12} {used:>8} / {available:<8} "
        if available:
            line += f"({utilization:.1f}%)"
        else:
            line += "(N/A)"
        lines.append(line)
        if used > available:
            lines.append(f"ERROR: Not enough slots for cell type '{cell_type}' (needed {used}, available {available})")
            error_found = True
    report = "\n".join(lines)
    if error_found:
        print(report)
        print("\nâŒ Validation failed: Design does not fit on fabric.")
        sys.exit(1)
    else:
        print(report)
        print("\nâœ Validation passed: Design is buildable on fabric.")
    return report, fabric_db, logical_db

def save_report_and_dbs(report: str, fabric_db: dict, logical_db: dict, design_path: str):
    """Save validation report and database files"""
    # Extract design name (remove _mapped suffix if present)
    design_base = os.path.splitext(os.path.basename(design_path))[0]
    design_name = design_base.replace("_mapped", "")
    
    # Create output directories
    build_root = "build"
    os.makedirs(build_root, exist_ok=True)
    design_dir = os.path.join(build_root, design_name)
    os.makedirs(design_dir, exist_ok=True)
    
    # Save validation report
    report_path = os.path.join(design_dir, "validation_report.txt")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"[validator] Saved report to {report_path}")
    
    # Save fabric DB (shared across all designs)
    fabric_db_path = os.path.join(build_root, "fabric.db")
    with open(fabric_db_path, "w") as f:
        json.dump(fabric_db, f, indent=2)
    print(f"[validator] Saved fabric DB to {fabric_db_path}")
    
    # Save logical DB (per design)
    logical_db_path = os.path.join(design_dir, "logical.db")
    with open(logical_db_path, "w") as f:
        json.dump(logical_db, f, indent=2)
    print(f"[validator] Saved logical DB to {logical_db_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python src/validator.py <fabric_dir> <design_json>")
        sys.exit(1)
    fabric_dir = sys.argv[1]
    design_path = sys.argv[2]
    report, fabric_db, logical_db = validate_fabric_vs_design(fabric_dir, design_path)
    save_report_and_dbs(report, fabric_db, logical_db, design_path)
