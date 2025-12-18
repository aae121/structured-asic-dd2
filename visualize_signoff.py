#!/usr/bin/env python3
"""Signoff visualization utilities.

Features:
- Congestion heatmap from OpenROAD report_congestion output.
- Slack histogram from setup report.
- Critical path overlay (uses DEF placement to draw path nodes and a red polyline).

Usage (example):
    python src/visualize_signoff.py \
        --design 6502 \
        --def build/6502/6502_routed.def \
        --congestion build/6502/6502_congestion.rpt \
        --setup build/6502/6502.setup.rpt \
        --outdir build/6502

Notes:
- Congestion parser is heuristic; it expects lines with at least x, y, demand, capacity
  (optionally layer/overflow). Unknown formats are skipped with a warning count.
- Critical path extraction is heuristic for OpenSTA report_checks output. You may need
  to tweak regexes if your report format differs.
"""

import argparse
import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

import matplotlib.pyplot as plt
import numpy as np


# -------------------- DEF parsing --------------------
def parse_def(def_path: Path) -> Tuple[Dict[str, Tuple[float, float]], Optional[Tuple[float, float, float, float]]]:
    comps: Dict[str, Tuple[float, float]] = {}
    die = None
    comp_re = re.compile(r"^-\s+(?P<name>\S+)\s+\S+")
    placed_re = re.compile(r"\+\s+(?:FIXED|PLACED)\s+\(\s*(\d+)\s+(\d+)\s*\)\s+(\S+)")
    die_re = re.compile(r"DIEAREA\s+\(\s*(\d+)\s+(\d+)\s*\)\s+\(\s*(\d+)\s+(\d+)\s*\)")

    current = None
    with def_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            dm = die_re.search(line)
            if dm:
                die = (float(dm.group(1)), float(dm.group(2)), float(dm.group(3)), float(dm.group(4)))
            m = comp_re.match(line)
            if m:
                current = m.group("name")
                continue
            if current:
                pm = placed_re.search(line)
                if pm:
                    x, y = float(pm.group(1)), float(pm.group(2))
                    comps[current] = (x, y)
                    current = None
    return comps, die


# -------------------- Congestion parsing --------------------
def parse_congestion(rpt_path: Path):
    """Parse congestion report; returns list of (x, y, ratio)."""
    data = []
    skipped = 0

    # Pattern: x y demand capacity [overflow]
    pat1 = re.compile(r"^(?:layer\s+\S+\s+)?(?P<x>\d+)\s+(?P<y>\d+)\s+(?P<d>\d+\.?\d*)\s+(?P<c>\d+\.?\d*)\s+(?P<o>\d+\.?\d*)")
    # Pattern: "GCell (x y) overflow <val>"
    pat2 = re.compile(r"GCell\s*\(\s*(?P<x>\d+)\s+(?P<y>\d+)\s*\)\s*overflow\s*(?P<o>\d+\.?\d*)", re.IGNORECASE)

    with rpt_path.open() as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m1 = pat1.match(line)
            if m1:
                x = int(m1.group("x")); y = int(m1.group("y"))
                d = float(m1.group("d")); c = float(m1.group("c"))
                ratio = d / c if c else 0.0
                data.append((x, y, ratio))
                continue
            m2 = pat2.search(line)
            if m2:
                x = int(m2.group("x")); y = int(m2.group("y"))
                ratio = float(m2.group("o"))
                data.append((x, y, ratio))
                continue
            skipped += 1
    if skipped:
        print(f"[congestion] skipped {skipped} lines (unrecognized format)")
    return data


def plot_congestion(data, out_path: Path):
    if not data:
        print("[congestion] no data to plot")
        return
    xs, ys, ratios = zip(*data)
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    grid = defaultdict(lambda: np.nan)
    for x, y, r in data:
        grid[(x, y)] = r
    arr = np.full((maxy - miny + 1, maxx - minx + 1), np.nan)
    for (x, y), r in grid.items():
        arr[y - miny, x - minx] = r
    plt.figure(figsize=(10, 8))
    im = plt.imshow(arr, origin="lower", cmap="inferno")
    plt.colorbar(im, label="Congestion (demand/capacity or overflow)")
    plt.title("Congestion Heatmap")
    plt.xlabel("GCell X")
    plt.ylabel("GCell Y")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"[congestion] saved {out_path}")


# -------------------- Slack parsing --------------------
def parse_slacks(setup_rpt: Path) -> List[float]:
    slacks: List[float] = []
    # Matches: "slack (VIOLATED)   -0.123" or "slack 0.456"
    pat = re.compile(r"slack[^-+\d]*([+-]?\d+\.\d+|[+-]?\d+)")
    with setup_rpt.open() as f:
        for line in f:
            m = pat.search(line)
            if m:
                try:
                    slacks.append(float(m.group(1)))
                except ValueError:
                    continue
    return slacks


def plot_slack_hist(slacks: List[float], out_path: Path):
    if not slacks:
        print("[slack] no slacks found")
        return
    plt.figure(figsize=(10, 6))
    plt.hist(slacks, bins=60, color="steelblue", edgecolor="black", alpha=0.8)
    plt.axvline(0.0, color="red", linestyle="--", linewidth=1.5, label="0 slack")
    plt.xlabel("Endpoint slack (ns)")
    plt.ylabel("Count")
    plt.title("Setup Slack Histogram")
    plt.legend()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"[slack] saved {out_path}")


# -------------------- Critical path --------------------
def extract_first_path_instances(setup_rpt: Path) -> List[str]:
    """Grab the instance order of the first reported path (heuristic)."""
    instances: List[str] = []
    in_path = False
    point_re = re.compile(r"^(\s*\d+\.?|\s*)(?P<name>[A-Za-z0-9_$./]+)/(?:\S+)\s+")
    with setup_rpt.open() as f:
        for line in f:
            if "Startpoint" in line:
                in_path = True
                continue
            if in_path:
                if line.strip() == "" or line.startswith("data arrival") or line.startswith("slack"):
                    if instances:
                        break
                m = point_re.match(line)
                if m:
                    inst = m.group("name")
                    instances.append(inst)
    return instances


def plot_critical_path(instances: List[str], comp_locs: Dict[str, Tuple[float, float]], die, out_path: Path):
    coords = []
    missing = 0
    for inst in instances:
        loc = comp_locs.get(inst)
        if loc:
            coords.append(loc)
        else:
            missing += 1
    if not coords:
        print("[crit_path] no coordinates found for path; skipping plot")
        return

    plt.figure(figsize=(10, 8))
    xs, ys = zip(*coords)
    plt.scatter(xs, ys, c="red", s=20, label="Path nodes")
    plt.plot(xs, ys, "r-", linewidth=2, alpha=0.8, label="Critical path")

    if die:
        xmin, ymin, xmax, ymax = die
        plt.gca().add_patch(plt.Rectangle((xmin, ymin), xmax - xmin, ymax - ymin,
                                          fill=False, edgecolor="black", linewidth=1.5, label="Die"))
    plt.title("Critical Path Overlay (heuristic)")
    plt.xlabel("X (dbu)")
    plt.ylabel("Y (dbu)")
    plt.legend()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"[crit_path] saved {out_path} (missing {missing} nodes)")


# -------------------- CLI --------------------
def main():
    ap = argparse.ArgumentParser(description="Signoff visualization helper")
    ap.add_argument("--design", required=True)
    ap.add_argument("--def", dest="def_path", required=True, help="DEF file with component locations")
    ap.add_argument("--congestion", dest="congestion_rpt", help="congestion report (report_congestion)")
    ap.add_argument("--setup", dest="setup_rpt", help="setup report (report_checks max)")
    ap.add_argument("--outdir", default="build")
    args = ap.parse_args()

    def_path = Path(args.def_path)
    cong_rpt = Path(args.congestion_rpt) if args.congestion_rpt else None
    setup_rpt = Path(args.setup_rpt) if args.setup_rpt else None
    outdir = Path(args.outdir) / args.design

    comp_locs, die = parse_def(def_path)
    print(f"[def] components parsed: {len(comp_locs)}")

    if cong_rpt and cong_rpt.exists():
        cong = parse_congestion(cong_rpt)
        plot_congestion(cong, outdir / f"{args.design}_congestion.png")
    else:
        print("[congestion] report not provided or missing; skipping")

    if setup_rpt and setup_rpt.exists():
        slacks = parse_slacks(setup_rpt)
        plot_slack_hist(slacks, outdir / f"{args.design}_slack_hist.png")
        path_insts = extract_first_path_instances(setup_rpt)
        if path_insts:
            plot_critical_path(path_insts, comp_locs, die, outdir / f"{args.design}_critical_path.png")
        else:
            print("[crit_path] no path instances parsed; skipping overlay")
    else:
        print("[setup] report not provided or missing; skipping slack/path plots")


if __name__ == "__main__":
    sys.exit(main())
