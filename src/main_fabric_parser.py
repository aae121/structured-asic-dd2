"""
main_fabric_parser.py
Phase 1 Runner – Structured ASIC Project

This script loads the platform YAML files using `load_fabric_db` from src/parse_fabric.py,
summarizes the results, saves them to JSON, and shows a cell distribution plot.

Author: Ahmed Ayman Elkhodary
"""

from src.parse_fabric import load_fabric_db
import matplotlib.pyplot as plt
import json
import os

def main():
    # --- Locate YAML inputs ---
    fabric_cells = os.path.join("fabric", "fabric_cells.yaml")
    pins = os.path.join("fabric", "pins.yaml")

    # --- Load fabric database ---
    print("🔍 Loading fabric database...")
    db = load_fabric_db(fabric_cells, pins)

    # --- Print summary ---
    print("\n✅ Fabric Database Summary:")
    print(f"  Total Slots: {len(db['slots'])}")
    print(f"  Total Pins:  {len(db['pins'])}")
    print("\n  Cell Types and Counts:")
    for cell_type, names in db["cells_by_type"].items():
        print(f"    {cell_type}: {len(names)}")

   

    # --- Plot cell distribution ---
    cell_types = list(db["cells_by_type"].keys())
    counts = [len(v) for v in db["cells_by_type"].values()]
    plt.bar(cell_types, counts)
    plt.title("Fabric Cell Type Distribution")
    plt.xlabel("Cell Type")
    plt.ylabel("Number of Slots")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
