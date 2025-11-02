# Structured ASIC DD2 Project

**Supervised by:** Dr. Mohamed Shalan  
**Team Members:** Ahmed · Habiba · Laila  
**Course:** Digital Design II  
**Duration:** Fall 2025 (6.5 Weeks)

---

## 🧠 Project Overview
This project develops a **complete Physical Design (PnR + STA) flow** for a **Structured ASIC platform** — a semi-custom architecture bridging FPGAs and Standard-Cell ASICs.  
Our flow reads mapped netlists, validates them against a fixed fabric, performs placement, clock-tree synthesis, routing, and timing analysis — all within a unified, automated, and visualized environment.

---

## 🎯 Objectives
- Build a **reusable and generic** structured-ASIC flow capable of handling multiple designs.  
- Implement core physical-design stages:
  - Database creation and validation  
  - Placement (Greedy + Simulated Annealing)  
  - Clock Tree Synthesis (CTS) and ECO generation  
  - Routing and post-route Static Timing Analysis (STA)  
- Automate the flow via **Makefile** or Python scripts.  
- Visualize intermediate results (heatmaps, histograms, timing plots).  

---

## 🧩 Repository Structure
