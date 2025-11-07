"""
visualize.py

Phase 1 Visualization: Structured ASIC Fabric Layout Plotter

This script visualizes the physical layout of the Structured ASIC fabric.
- Draws die/core boundaries (if available from pins.yaml)
- Plots all fabric slots as semi-transparent rectangles, color-coded by cell type
- Plots I/O pins as labeled points along the edges
- Saves the output image to build/fabric_layout.png

Usage:
    python src/visualize.py <fabric_dir>

Author: [Your Name]
"""

import os
import sys
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from parse_fabric import load_fabric_db
import numpy as np

def plot_fabric(fabric_dir: str, out_path: str = "build/fabric_layout.png"):
    fabric_cells_path = os.path.join(fabric_dir, "fabric_cells.yaml")
    pins_path = os.path.join(fabric_dir, "pins.yaml")
    fabric_db = load_fabric_db(fabric_cells_path, pins_path)

    slots = fabric_db["slots"]
    pins = fabric_db["pins"]
    bounds = fabric_db.get("bounds", None)

    # Assign a color to each cell type
    cell_types = sorted({slot["type"] for slot in slots.values()})
    colors = plt.cm.get_cmap("tab20", len(cell_types))
    type_to_color = {t: colors(i) for i, t in enumerate(cell_types)}

    fig, ax = plt.subplots(figsize=(10, 10))

    # Draw die/core boundaries if available
    if bounds:
        ax.add_patch(Rectangle((bounds["xmin"], bounds["ymin"]),
                              bounds["xmax"] - bounds["xmin"],
                              bounds["ymax"] - bounds["ymin"],
                              fill=False, edgecolor="black", linewidth=2, label="Die/Core Bounds"))

    # Plot all slots
    for slot_name, slot in slots.items():
        x = slot.get("x", 0)
        y = slot.get("y", 0)
        cell_type = slot.get("type", "UNKNOWN")
        color = type_to_color.get(cell_type, (0.5, 0.5, 0.5, 0.3))
        ax.add_patch(Rectangle((x-0.5, y-0.5), 1, 1, color=color, alpha=0.4, label=cell_type if slot_name == 0 else None))

    # Plot pins as labeled points
    for pin_name, pin in pins.items():
        x = pin.get("x", 0)
        y = pin.get("y", 0)
        ax.plot(x, y, marker="o", color="red", markersize=6)
        ax.text(x, y, pin_name, fontsize=8, ha="center", va="center", color="red", bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', boxstyle='round,pad=0.2'))

    # Legend for cell types
    handles = [Rectangle((0,0),1,1, color=type_to_color[t], alpha=0.4) for t in cell_types]
    ax.legend(handles, cell_types, title="Cell Types", loc="upper right", bbox_to_anchor=(1.15, 1))

    ax.set_aspect('equal')
    ax.set_xlabel("X (microns or site index)")
    ax.set_ylabel("Y (microns or site index)")
    ax.set_title("Structured ASIC Fabric Layout")
    plt.tight_layout()

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved fabric layout visualization to {out_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python src/visualize.py <fabric_dir>")
        sys.exit(1)
    fabric_dir = sys.argv[1]
    plot_fabric(fabric_dir)
