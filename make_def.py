#!/usr/bin/env python3
"""
make_def.py - Generates a DEF file for structured ASIC designs

This script generates build/[design_name]/[design_name]_fixed.def containing:
- DIEAREA
- All PINS (+ FIXED)
- All COMPONENTS from fabric_cells.yaml (both used and unused) as + FIXED

Usage:
    python make_def.py <design_name>
    
Example:
    python make_def.py 6502
"""

import yaml
import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any


def load_yaml(path: str) -> Dict:
    """Load a YAML file and return its contents."""
    path = Path(path)
    if not path.exists():
        print(f"ERROR: file not found: {path}")
        sys.exit(1)
    
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_json(path: str) -> Dict:
    """Load a JSON file and return its contents."""
    path = Path(path)
    if not path.exists():
        print(f"ERROR: file not found: {path}")
        sys.exit(1)
    
    with open(path, "r") as f:
        return json.load(f)


def get_cell_type_from_name(cell_name: str) -> str:
    """
    Infer cell type from cell name.
    Cell names follow pattern: T{X}Y{Y}__R{row}_{TYPE}_{index}
    
    Examples:
        T0Y0__R0_NAND_0 -> sky130_fd_sc_hd__nand2_2
        T0Y0__R0_INV_0 -> sky130_fd_sc_hd__clkinv_2
        T0Y0__R0_BUF_0 -> sky130_fd_sc_hd__clkbuf_4
    """
    # Extract the type part from the cell name
    parts = cell_name.split('__')
    if len(parts) < 2:
        return "UNKNOWN"
    
    cell_part = parts[1]  # e.g., "R0_NAND_0"
    components = cell_part.split('_')
    if len(components) < 2:
        return "UNKNOWN"
    
    cell_type = components[1]  # e.g., "NAND", "INV", "BUF"
    
    # Map cell type to actual standard cell name
    type_map = {
        "NAND": "sky130_fd_sc_hd__nand2_2",
        "OR": "sky130_fd_sc_hd__or2_2",
        "AND": "sky130_fd_sc_hd__and2_2",
        "INV": "sky130_fd_sc_hd__clkinv_2",
        "BUF": "sky130_fd_sc_hd__clkbuf_4",
        "DFBBP": "sky130_fd_sc_hd__dfbbp_1",
        "TAP": "sky130_fd_sc_hd__tapvpwrvgnd_1",
        "DECAP": "sky130_fd_sc_hd__decap_4",
        "CONB": "sky130_fd_sc_hd__conb_1",
        "FILL": "sky130_fd_sc_hd__fill_1",
    }
    
    # Handle DECAP_3 case
    if cell_type == "DECAP":
        if "DECAP_0" in cell_name or "DECAP_1" in cell_name:
            # Check based on context - for now default to decap_4
            return "sky130_fd_sc_hd__decap_4"
        else:
            return "sky130_fd_sc_hd__decap_3"
    
    return type_map.get(cell_type, "UNKNOWN")


def build_template_map(fabric_data: Dict[str, Any]) -> Dict[str, str]:
    """Return mapping from template_name to cell_type using fabric.yaml."""
    tile_def = fabric_data.get("tile_definition", {})
    cells = tile_def.get("cells", [])
    mapping: Dict[str, str] = {}
    for entry in cells:
        tmpl = entry.get("template_name")
        ctype = entry.get("cell_type")
        if tmpl and ctype:
            mapping[tmpl] = ctype
    return mapping


def generate_def(design_name: str):
    """Generate DEF file for the given design."""
    
    # Define paths
    fabric_cells_path = Path("fabric/fabric_cells.yaml")
    pins_path = Path("fabric/pins.yaml")
    fabric_path = Path("fabric/fabric.yaml")
    output_dir = Path(f"build/{design_name}")
    output_path = output_dir / f"{design_name}_fixed.def"
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Loading fabric cells from: {fabric_cells_path}")
    fabric_cells_data = load_yaml(fabric_cells_path)
    
    print(f"Loading pins from: {pins_path}")
    pins_data = load_yaml(pins_path)
    
    print(f"Loading fabric info from: {fabric_path}")
    fabric_data = load_yaml(fabric_path)
    template_map = build_template_map(fabric_data)
    
    # Extract die area information
    die_width = pins_data['pin_placement']['die']['width_um']
    die_height = pins_data['pin_placement']['die']['height_um']
    dbu_per_micron = pins_data['pin_placement']['units']['dbu_per_micron']
    
    # Convert to database units (DBU)
    die_width_dbu = int(die_width * dbu_per_micron)
    die_height_dbu = int(die_height * dbu_per_micron)
    
    print(f"Die area: {die_width} x {die_height} um ({die_width_dbu} x {die_height_dbu} DBU)")
    
    # Extract all cells from fabric_cells.yaml
    all_cells = []
    tiles = fabric_cells_data['fabric_cells_by_tile']['tiles']
    
    for tile_name, tile_data in tiles.items():
        for cell in tile_data['cells']:
            cell_name = cell['name']
            cell_x_um = cell['x']
            cell_y_um = cell['y']
            cell_orient = cell['orient']

            # Convert position to DBU
            cell_x_dbu = int(cell_x_um * dbu_per_micron)
            cell_y_dbu = int(cell_y_um * dbu_per_micron)

            # Prefer template-to-cell_type mapping, fall back to heuristic
            cell_template = cell_name.split('__', 1)[1] if '__' in cell_name else ""
            cell_type = template_map.get(cell_template, get_cell_type_from_name(cell_name))

            all_cells.append({
                'name': cell_name,
                'type': cell_type,
                'x': cell_x_dbu,
                'y': cell_y_dbu,
                'orient': cell_orient
            })
    
    print(f"Total cells: {len(all_cells)}")
    
    # Extract pins
    pins = pins_data['pin_placement']['pins']
    print(f"Total pins: {len(pins)}")
    
    # Write DEF file
    print(f"Writing DEF file to: {output_path}")
    
    with open(output_path, 'w') as f:
        # Header
        f.write(f"VERSION 5.8 ;\n")
        f.write(f"DIVIDERCHAR \"/\" ;\n")
        f.write(f"BUSBITCHARS \"[]\" ;\n")
        f.write(f"DESIGN {design_name} ;\n")
        f.write(f"UNITS DISTANCE MICRONS {dbu_per_micron} ;\n")
        f.write(f"\n")
        
        # DIEAREA
        f.write(f"DIEAREA ( 0 0 ) ( {die_width_dbu} {die_height_dbu} ) ;\n")
        f.write(f"\n")
        
        # PINS section
        f.write(f"PINS {len(pins)} ;\n")
        for pin in pins:
            pin_name = pin['name']
            pin_direction = pin['direction']
            pin_layer = pin['layer']
            pin_x_um = pin['x_um']
            pin_y_um = pin['y_um']
            
            # Convert to DBU
            pin_x_dbu = int(pin_x_um * dbu_per_micron)
            pin_y_dbu = int(pin_y_um * dbu_per_micron)
            
            # Determine pin placement based on side
            pin_side = pin.get('side', 'south')
            
            # For simplicity, create a small pin geometry
            # Typical pin is 0.17um wide in metal
            pin_width_dbu = int(0.17 * dbu_per_micron)
            pin_height_dbu = int(0.17 * dbu_per_micron)
            
            f.write(f"  - {pin_name} + NET {pin_name} + DIRECTION {pin_direction}\n")
            f.write(f"    + LAYER {pin_layer} ( {-pin_width_dbu//2} {-pin_height_dbu//2} ) ( {pin_width_dbu//2} {pin_height_dbu//2} )\n")
            f.write(f"    + FIXED ( {pin_x_dbu} {pin_y_dbu} ) N ;\n")
        
        f.write(f"END PINS\n")
        f.write(f"\n")
        
        # COMPONENTS section
        f.write(f"COMPONENTS {len(all_cells)} ;\n")
        for cell in all_cells:
            f.write(f"  - {cell['name']} {cell['type']}\n")
            f.write(f"    + FIXED ( {cell['x']} {cell['y']} ) {cell['orient']} ;\n")
        
        f.write(f"END COMPONENTS\n")
        f.write(f"\n")
        
        # End of design
        f.write(f"END DESIGN\n")
    
    print(f"Successfully generated: {output_path}")
    print(f"  - DIEAREA: ( 0 0 ) ( {die_width_dbu} {die_height_dbu} )")
    print(f"  - PINS: {len(pins)} (FIXED)")
    print(f"  - COMPONENTS: {len(all_cells)} (FIXED)")


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python make_def.py <design_name>")
        print("Example: python make_def.py 6502")
        sys.exit(1)
    
    design_name = sys.argv[1]
    print(f"Generating DEF file for design: {design_name}")
    print("=" * 60)
    
    generate_def(design_name)
    print("=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
