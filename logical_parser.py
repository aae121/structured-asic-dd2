import json
import os
from collections import defaultdict


BASE_PATH = r"C:/Users/HP/structured_asic_project/designs/"
OUTPUT_PATH = r"C:/Users/HP/structured_asic_project/parsed_outputs/"    # <--- You can change this


def ensure_output_dir():
    if not os.path.exists(OUTPUT_PATH):
        os.makedirs(OUTPUT_PATH)


def parse_design(design_name):
    """
    Loads <design_name>_mapped.json and returns:
        logical_db
        netlist_graph
    Also writes them to JSON files.
    """

    json_path = os.path.join(BASE_PATH, f"{design_name}_mapped.json")
    print(f"→ Reading mapped JSON: {json_path}")

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Mapped JSON not found: {json_path}")

    with open(json_path, "r") as f:
        data = json.load(f)

    top_module = next(iter(data["modules"]))
    module = data["modules"][top_module]

    # -----------------------------
    # Build logical_db
    # -----------------------------
    logical_db = {
        "ports": module["ports"],
        "cells": {},
        "nets": defaultdict(list)
    }

    for cell_name, cell in module["cells"].items():
        logical_db["cells"][cell_name] = {
            "type": cell["type"],
            "connections": cell["connections"],
            "port_directions": cell["port_directions"],
        }

        # Build net list
        for _, net_list in cell["connections"].items():
            for net in net_list:
                logical_db["nets"][net].append(cell_name)

    # -----------------------------
    # Build netlist_graph
    # -----------------------------
    netlist_graph = defaultdict(set)

    for net, cell_list in logical_db["nets"].items():
        for i in range(len(cell_list)):
            for j in range(i + 1, len(cell_list)):
                a, b = cell_list[i], cell_list[j]
                netlist_graph[a].add(b)
                netlist_graph[b].add(a)

    # -----------------------------------
    # Write outputs to JSON files
    # -----------------------------------
    ensure_output_dir()

    logical_db_path = os.path.join(OUTPUT_PATH, f"logical_db_{design_name}.json")
    netlist_graph_path = os.path.join(OUTPUT_PATH, f"netlist_graph_{design_name}.json")

    # Convert sets → lists for JSON
    serializable_graph = {k: list(v) for k, v in netlist_graph.items()}

    with open(logical_db_path, "w") as f:
        json.dump(logical_db, f, indent=2)

    with open(netlist_graph_path, "w") as f:
        json.dump(serializable_graph, f, indent=2)

    print("\n✔ Output files written:")
    print(f"  Logical DB → {logical_db_path}")
    print(f"  Netlist Graph → {netlist_graph_path}\n")

    return logical_db, netlist_graph


# -----------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------
if __name__ == "__main__":
    design = "6502"

    logical_db, netlist_graph = parse_design(design)

    print(f"Cells: {len(logical_db['cells'])}")
    print(f"Nets:  {len(logical_db['nets'])}")
    print(f"Graph Nodes: {len(netlist_graph)}")
