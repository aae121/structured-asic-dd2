#!/usr/bin/env python3
"""Rename Verilog instances to their physical slot names.

Usage:
    python rename.py <design_name> [--map MAP] [--netlist NETLIST] [--out OUT]

Defaults:
    MAP:       phase2_greedy/build/<design>/<design>.map (fallback: build/<design>/<design>.map)
    NETLIST:   src/build/<design>/<design>_final.v
    OUT:       build/<design>/<design>_renamed.v

The map file must contain lines of the form:
    logical_instance_name -> SLOT_X123_Y45 (x, y)

Every instance in the netlist whose name matches the left-hand side is renamed
to the slot name. Instances without a mapping are left untouched. A summary of
replaced and missing instances is printed to stdout.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Set


def parse_map(path: Path) -> Dict[str, str]:
    """Parse mapping file: logical -> slot name."""
    mapping: Dict[str, str] = {}
    with path.open() as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "->" not in line:
                continue
            left, right = line.split("->", 1)
            logical = left.strip()
            right_part = right.strip()
            slot = right_part.split()[0]
            mapping[logical] = slot
    return mapping


def rename_instances(lines: List[str], mapping: Dict[str, str]) -> (List[str], Set[str]):
    """Rename instance identifiers using the provided mapping."""
    used: Set[str] = set()
    out: List[str] = []

    skip_prefixes = (
        "module",
        "endmodule",
        "input",
        "output",
        "inout",
        "wire",
        "reg",
        "assign",
        "parameter",
        "localparam",
        "`",
    )

    inst_re = re.compile(r"^(?P<indent>\s*)(?P<cell>\S+)(?P<params>\s*#\s*\([^)]*\))?\s+(?P<inst>\S+)\s*(?P<rest>\(.*)")

    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith(skip_prefixes):
            out.append(line)
            continue

        m = inst_re.match(line)
        if not m:
            out.append(line)
            continue

        inst_name = m.group("inst")
        new_name = mapping.get(inst_name)
        if new_name:
            used.add(inst_name)
            suffix = "\n" if line.endswith("\n") else ""
            line = f"{m.group('indent')}{m.group('cell')}{m.group('params') or ''} {new_name} {m.group('rest')}{suffix}"
        out.append(line)

    return out, used


def pick_path(preferred: Path, fallback: Path) -> Path:
    """Return preferred if it exists, else fallback."""
    if preferred.exists():
        return preferred
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Neither {preferred} nor {fallback} exists")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("design", help="Design name, e.g., 6502")
    parser.add_argument("--map", dest="map_path", type=Path, help="Path to instance map file")
    parser.add_argument("--netlist", dest="netlist_path", type=Path, help="Path to <design>_final.v")
    parser.add_argument("--out", dest="out_path", type=Path, help="Output renamed netlist path")
    args = parser.parse_args()

    design = args.design

    default_map = Path(f"phase2_greedy/build/{design}/{design}.map")
    alt_map = Path(f"build/{design}/{design}.map")
    map_path = args.map_path if args.map_path else pick_path(default_map, alt_map)

    default_netlist = Path(f"src/build/{design}/{design}_final.v")
    alt_netlist = Path(f"build/{design}/{design}_final.v")
    netlist_path = args.netlist_path if args.netlist_path else pick_path(default_netlist, alt_netlist)

    out_path = args.out_path if args.out_path else Path(f"build/{design}/{design}_renamed.v")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Using map: {map_path}")
    print(f"Using netlist: {netlist_path}")
    print(f"Writing renamed netlist: {out_path}")

    mapping = parse_map(map_path)
    if not mapping:
        print("ERROR: mapping file is empty or invalid", file=sys.stderr)
        return 1

    lines = netlist_path.read_text().splitlines(keepends=True)
    renamed_lines, used = rename_instances(lines, mapping)

    missing = set(mapping.keys()) - used
    print(f"Instances renamed: {len(used)}/{len(mapping)}")
    if missing:
        print(f"Warning: {len(missing)} mapped instances not found in netlist", file=sys.stderr)

    out_path.write_text("".join(renamed_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
