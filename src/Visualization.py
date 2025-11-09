"""
fabric_viewer.py

Phase 1 Visualization: Structured ASIC Fabric Layout Renderer

Creates a visual map of the Structured ASIC layout:
• Draws die/core outlines (if defined)
• Displays all slot locations (color-coded by cell type)
• Marks and labels I/O pins in red
• Saves the image as build/fabric_view.png

Usage:
    python src/fabric_viewer.py ../fabric
"""

import os
import sys
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from parse_fabric import load_fabric_db


def render_fabric_layout(fabric_folder: str, output_file: str = "build/fabric_view.png"):
    # === Load layout data ===
    cells_file = os.path.join(fabric_folder, "fabric_cells.yaml")
    pins_file = os.path.join(fabric_folder, "pins.yaml")

    fabric_data = load_fabric_db(cells_file, pins_file)
    slots = fabric_data.get("slots", {})
    pins = fabric_data.get("pins", {})
    bounds = fabric_data.get("bounds")

    # === Setup plot ===
    cell_types = sorted({slot.get("type", "UNKNOWN") for slot in slots.values()})
    cmap = plt.colormaps.get_cmap("tab20", len(cell_types))
    color_map = {ctype: cmap(i) for i, ctype in enumerate(cell_types)}

    fig, ax = plt.subplots(figsize=(10, 10))

    # === Draw chip/core outline ===
    if bounds:
        ax.add_patch(Rectangle(
            (bounds["xmin"], bounds["ymin"]),
            bounds["xmax"] - bounds["xmin"],
            bounds["ymax"] - bounds["ymin"],
            fill=False, edgecolor="black", linewidth=2, label="Die/Core"
        ))

    # === Draw slot grid ===
    invalid_count = 0
    for name, slot in slots.items():
        x, y = slot.get("x"), slot.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            invalid_count += 1
            continue

        ctype = slot.get("type", "UNKNOWN")
        color = color_map.get(ctype, (0.5, 0.5, 0.5, 0.3))
        ax.add_patch(Rectangle((x - 0.5, y - 0.5), 1, 1, color=color, alpha=0.4))

    if invalid_count:
        print(f" Ignored {invalid_count} slots with invalid coordinates")

    # === Mark and label pins ===
    for pname, pin in pins.items():
        x, y = pin.get("x"), pin.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        ax.plot(x, y, "ro", markersize=5)
        ax.text(x, y, pname, fontsize=6, color="red",
                ha="center", va="center",
                bbox=dict(facecolor="white", alpha=0.6, edgecolor="none"))

    # === Final plot settings ===
    ax.set_aspect("equal")
    ax.set_xlabel("X Position")
    ax.set_ylabel("Y Position")
    ax.set_title("Structured ASIC Fabric Map")

    legend_handles = [
        Rectangle((0, 0), 1, 1, color=color_map[t], alpha=0.4)
        for t in cell_types
    ]
    ax.legend(legend_handles, cell_types, title="Cell Types",
              loc="upper right", bbox_to_anchor=(1.25, 1))

    # === Save image ===
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    plt.close()
    print(f" Fabric layout saved successfully at {output_file}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python src/fabric_viewer.py <fabric_folder>")
        sys.exit(1)

    folder = sys.argv[1]
    render_fabric_layout(folder)
