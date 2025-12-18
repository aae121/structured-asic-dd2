#!/usr/bin/env python3


import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple


def parse_setup_paths(path: Path, top: int) -> List[Tuple[str, str, float]]:
    
    lines = path.read_text(errors="ignore").splitlines()
    paths: List[Tuple[str, str, float]] = []
    start = end = None
    slack = None

    def commit():
        nonlocal start, end, slack
        if start and end and slack is not None:
            paths.append((start, end, slack))
        start = end = None
        slack = None

    for ln in lines:
        l = ln.strip()
        if l.lower().startswith("startpoint"):
            commit()
  
            parts = l.split()
            if len(parts) >= 2:
                start = parts[1].split("/")[0]
        elif l.lower().startswith("endpoint"):
            parts = l.split()
            if len(parts) >= 2:
                end = parts[1].split("/")[0]
        elif l.lower().startswith("slack"):
            try:
                slack = float(l.split()[-1])
            except Exception:
                slack = None
            commit()

    paths.sort(key=lambda x: x[2])
    return paths[:top]


def build_cell_to_nets(nets: Dict[str, List]) -> Dict[str, List[str]]:
    m: Dict[str, List[str]] = {}
    for net, members in nets.items():
        for mem in members:
            if isinstance(mem, str):
                m.setdefault(mem, []).append(net)
    return m


def compute_weights(paths: List[Tuple[str, str, float]], cell2nets: Dict[str, List[str]]) -> Dict[str, float]:
    weights: Dict[str, float] = {}
    if not paths:
        return weights

    worst_slack = min(p[2] for p in paths)
    for rank, (start, end, slack) in enumerate(paths, 1):
        cells = [start, end]
        severity = max(0.0, -slack)
        rank_bonus = max(0.0, (len(paths) - rank) / max(1, len(paths)))
        base = 1.0 + 5.0 * severity + 2.0 * rank_bonus
        cap = 20.0
        weight = min(cap, base)
        for c in cells:
            for net in cell2nets.get(c, []):
                weights[net] = max(weights.get(net, 1.0), weight)
    return weights


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--setup", dest="setup", required=True, help="setup report path")
    ap.add_argument("--logical", dest="logical", required=True, help="logical_db JSON path")
    ap.add_argument("--out", dest="out", required=True, help="output JSON for net weights")
    ap.add_argument("--top", dest="top", type=int, default=100, help="number of worst paths")
    args = ap.parse_args()

    setup_path = Path(args.setup)
    logical_path = Path(args.logical)
    out_path = Path(args.out)

    paths = parse_setup_paths(setup_path, args.top)
    if not logical_path.exists():
        raise FileNotFoundError(logical_path)
    logical = json.loads(logical_path.read_text())
    nets = logical.get("nets", {})
    cell2nets = build_cell_to_nets(nets)
    weights = compute_weights(paths, cell2nets)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(weights, indent=2))

    print(f"Computed weights for {len(weights)} nets from {len(paths)} worst paths")
    print(f"Worst slack observed: {min((p[2] for p in paths), default=0):.3f} ns")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
