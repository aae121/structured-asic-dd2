"""
parse_fabric.py

Phase 1: Fabric Database Builder for Structured ASIC Project

This module provides a single public function, `load_fabric_db`, which parses
the platform YAML files (fabric_cells.yaml and pins.yaml) and constructs a
master `fabric_db` dictionary describing the physical fabric: all slots (cell
sites) and I/O pins. This is the canonical source of physical slot and pin
information for all later project phases (validation, placement, visualization).

fabric_db structure:
- fabric_db["slots"]: dict
    - key: slot_name (unique string from YAML)
    - value: {
        "type": <cell_type>,      # e.g. "NAND2", "INV_2", buffer, flop, etc.
        "x": <float or int>,      # coordinate or site index from YAML
        "y": <float or int>,
        ... (other physical attributes, e.g. orientation, tile, row, etc.)
      }
- fabric_db["cells_by_type"]: dict
    - key: cell_type (string)
    - value: list of slot_name
- fabric_db["pins"]: dict
    - key: pin_name (string)
    - value: {
        "x": <float or int>,
        "y": <float or int>,
        "direction": <"input"/"output"/"inout">,
        ... (other pin metadata from YAML)
      }
- fabric_db["bounds"]: dict (optional, if available in pins.yaml)
    - keys: xmin, xmax, ymin, ymax

Other modules should import and use only `load_fabric_db`.

Author: [Your Name]
"""

import os
import sys
from typing import Any, Dict
import yaml

def _load_yaml(path: str) -> Any:
    """Load a YAML file and return its contents."""
    with open(path, "r") as f:
        return yaml.safe_load(f)

def _infer_cell_type(slot_name: str) -> str:
    """
    Infer the cell type from the slot name.
    E.g. T0Y0__R0_NAND_0 → "NAND"
    """
    # Example: T0Y0__R0_NAND_0
    parts = slot_name.split("__")[-1].split("_")
    # Remove row prefix if present (e.g. R0_NAND_0)
    if len(parts) >= 2 and parts[0].startswith("R"):
        return parts[1]
    elif len(parts) >= 1:
        return parts[0]
    return slot_name

def _build_cells_by_type(slots: Dict[str, dict]) -> Dict[str, list]:
    """Build a mapping from cell_type to list of slot_names."""
    cells_by_type = {}
    for slot_name, slot in slots.items():
        cell_type = slot["type"]
        cells_by_type.setdefault(cell_type, []).append(slot_name)
    return cells_by_type

def load_fabric_db(
    fabric_cells_path: str,
    pins_path: str
) -> dict:
    """
    Parse the platform YAML files and return a fabric_db dictionary with all
    physical slot and pin information. This is the ONLY API other modules
    should depend on.
    """
    # --- Parse fabric_cells.yaml ---
    fc_yaml = _load_yaml(fabric_cells_path)
    slots = {}
    seen_slot_names = set()
    # The structure is: fabric_cells_by_tile: { tiles: { T0Y0: {cells: [...]}, ... } }
    tiles = fc_yaml.get("fabric_cells_by_tile", {}).get("tiles", {})
    for tile_name, tile in tiles.items():
        tile_x = tile.get("x")
        tile_y = tile.get("y")
        for cell in tile.get("cells", []):
            slot_name = cell.get("name")
            if slot_name is None:
                raise ValueError(f"Missing 'name' in cell entry in tile {tile_name}")
            if slot_name in seen_slot_names:
                raise ValueError(f"Duplicate slot name found: {slot_name}")
            seen_slot_names.add(slot_name)
            # Try to infer type from slot name, but allow override if present
            cell_type = _infer_cell_type(slot_name)
            slot = {
                "type": cell_type,
                "x": cell.get("x"),
                "y": cell.get("y"),
                "orient": cell.get("orient"),
                "tile": tile_name,
                "tile_x": tile_x,
                "tile_y": tile_y,
            }
            # Add any other fields present in the cell entry
            for k, v in cell.items():
                if k not in slot:
                    slot[k] = v
            slots[slot_name] = slot

    # --- Build cells_by_type ---
    cells_by_type = _build_cells_by_type(slots)

    # --- Parse pins.yaml ---
    pins_yaml = _load_yaml(pins_path)
    pins = {}
    seen_pin_names = set()
    for pin in pins_yaml.get("pins", pins_yaml.get("pin_placement", {}).get("pins", [])):
        pin_name = pin.get("name")
        if pin_name is None:
            raise ValueError("Missing 'name' in pin entry")
        if pin_name in seen_pin_names:
            raise ValueError(f"Duplicate pin name found: {pin_name}")
        seen_pin_names.add(pin_name)
        # Normalize direction to lowercase
        direction = pin.get("direction", "").lower()
        # Use x_um/y_um if present, else x/y
        x = pin.get("x_um", pin.get("x"))
        y = pin.get("y_um", pin.get("y"))
        pin_entry = {
            "x": x,
            "y": y,
            "direction": direction,
            "side": pin.get("side"),
            "layer": pin.get("layer"),
            "status": pin.get("status"),
        }
        # Add any other fields present in the pin entry
        for k, v in pin.items():
            if k not in pin_entry:
                pin_entry[k] = v
        pins[pin_name] = pin_entry

    # --- Optionally parse bounds ---
    bounds = None
    die = pins_yaml.get("die") or pins_yaml.get("pin_placement", {}).get("die")
    if die:
        bounds = {
            "xmin": 0.0,
            "xmax": die.get("width_um"),
            "ymin": 0.0,
            "ymax": die.get("height_um"),
        }

    fabric_db = {
        "slots": slots,
        "cells_by_type": cells_by_type,
        "pins": pins,
    }
    if bounds:
        fabric_db["bounds"] = bounds

    return fabric_db

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Parse fabric YAMLs and summarize fabric_db.")
    parser.add_argument("fabric_cells_path", help="Path to fabric_cells.yaml")
    parser.add_argument("pins_path", help="Path to pins.yaml")
    args = parser.parse_args()

    db = load_fabric_db(args.fabric_cells_path, args.pins_path)
    print(f"Loaded fabric_db:")
    print(f"  Number of slots: {len(db['slots'])}")
    print(f"  Number of pins: {len(db['pins'])}")
    print("  Cell types and counts:")
    cell_types = []
    counts = []
    for cell_type, slot_names in db["cells_by_type"].items():
        print(f"    {cell_type}: {len(slot_names)}")
        cell_types.append(cell_type)
        counts.append(len(slot_names))

    # Optional: visualize with matplotlib if available
    try:
        import matplotlib.pyplot as plt
        plt.bar(cell_types, counts)
        plt.title("Fabric Cell Type Distribution")
        plt.xlabel("Cell Type")
        plt.ylabel("Number of Slots")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
    except ImportError:
        print("matplotlib not installed; skipping plot.")