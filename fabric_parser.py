import yaml
import json
import sys
from pathlib import Path

# ----------------------------------------------------
# HARD-CODED PATHS (your exact Windows directories)
# ----------------------------------------------------
FABRIC_CELLS_PATH = "C:/Users/HP/structured_asic_project/fabric/fabric_cells.yaml"
PINS_PATH = "C:/Users/HP/structured_asic_project/fabric/pins.yaml"
OUTPUT_PATH = "fabric_db.json"


def load_yaml(path: str):
    path = Path(path)
    if not path.exists():
        print(f"ERROR: file not found: {path}")
        sys.exit(1)

    with open(path, "r") as f:
        return yaml.safe_load(f)


def build_fabric_db(fabric_cells_path, pins_path, output_path):
    print(f"Loading: {fabric_cells_path}")
    fabric_cells = load_yaml(fabric_cells_path)

    print(f"Loading: {pins_path}")
    pins = load_yaml(pins_path)

    # The fabric_cells.yaml file already contains tiles + cell types
    tiles = fabric_cells.get("tiles", {})
    cells = fabric_cells.get("cells", {})

    print(f"Loaded tiles: {len(tiles)}")
    print(f"Loaded cells: {len(cells)}")
    print(f"Loaded pins : {len(pins)}")

    # Build the master database
    fabric_db = {
        "tiles": tiles,
        "cells": cells,
        "pins": pins,
    }

    # Save as JSON
    with open(output_path, "w") as f:
        json.dump(fabric_db, f, indent=2)

    print(f"\nWrote master database → {output_path}")


if __name__ == "__main__":
    build_fabric_db(FABRIC_CELLS_PATH, PINS_PATH, OUTPUT_PATH)
