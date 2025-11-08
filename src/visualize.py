"""
visualize.py

Phase 1 Visualization: Structured ASIC Fabric Layout Plotter

Generates a clear, error-free plot of the Structured ASIC fabric:
- Draws die/core boundaries (if present)
- Plots all valid slots (color-coded by cell type)
- Plots I/O pins as labeled red dots
- Saves result to build/fabric_layout.png

Usage:
    python src/visualize.py ../fabric
"""

import os
import sys
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from parse_fabric import load_fabric_db


def plot_fabric(fabric_dir: str, out_path: str = "build/fabric_layout.png"):
    # ---- Load data ----
    fabric_cells_path = os.path.join(fabric_dir, "fabric_cells.yaml")
    pins_path = os.path.join(fabric_dir, "pins.yaml")

    fabric_db = load_fabric_db(fabric_cells_path, pins_path)
    slots = fabric_db.get("slots", {})
    pins = fabric_db.get("pins", {})
    bounds = fabric_db.get("bounds")

    # ---- Prepare plotting ----
    cell_types = sorted({slot.get("type", "UNKNOWN") for slot in slots.values()})
    cmap = plt.colormaps.get_cmap("tab20", len(cell_types))
    type_colors = {t: cmap(i) for i, t in enumerate(cell_types)}

    fig, ax = plt.subplots(figsize=(10, 10))

    # ---- Draw die/core boundary ----
    if bounds:
        ax.add_patch(Rectangle(
            (bounds["xmin"], bounds["ymin"]),
            bounds["xmax"] - bounds["xmin"],
            bounds["ymax"] - bounds["ymin"],
            fill=False, edgecolor="black", linewidth=2, label="Die/Core"
        ))

    # ---- Plot each slot ----
    skipped = 0
    for name, slot in slots.items():
        x, y = slot.get("x"), slot.get("y")

        # Ensure coordinates are numeric
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            skipped += 1
            continue

        ctype = slot.get("type", "UNKNOWN")
        color = type_colors.get(ctype, (0.5, 0.5, 0.5, 0.3))
        ax.add_patch(Rectangle((x - 0.5, y - 0.5), 1, 1, color=color, alpha=0.4))

    if skipped:
        print(f"⚠️ Skipped {skipped} invalid slots with missing coordinates")

    # ---- Plot pins ----
    for pname, pin in pins.items():
        x, y = pin.get("x"), pin.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        ax.plot(x, y, "ro", markersize=5)
        ax.text(x, y, pname, fontsize=6, color="red",
                ha="center", va="center",
                bbox=dict(facecolor="white", alpha=0.6, edgecolor="none"))

    # ---- Final layout setup ----
    ax.set_aspect("equal")
    ax.set_xlabel("X coordinate")
    ax.set_ylabel("Y coordinate")
    ax.set_title("Structured ASIC Fabric Layout")

    # Legend
    handles = [Rectangle((0, 0), 1, 1, color=type_colors[t], alpha=0.4)
               for t in cell_types]
    ax.legend(handles, cell_types, title="Cell Types", loc="upper right",
              bbox_to_anchor=(1.25, 1))

    # ---- Save output ----
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"✅ Saved fabric layout visualization to {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python src/visualize.py <fabric_dir>")
        sys.exit(1)

    fabric_dir = sys.argv[1]
    plot_fabric(fabric_dir)
