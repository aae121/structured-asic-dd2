# 🧠 Structured ASIC DD2 Project  
**Supervised by Dr. Mohamed Shalan**  
**Team Members:** Ahmed Elkhodary · Habiba Seif · Laila Elsayed  

---

## 📘 Overview  
This project implements a complete **PnR (Place and Route)** and **STA (Static Timing Analysis)** flow for a **Structured ASIC platform**.  
The objective is to build a **reusable, automated, and visualizable physical design flow** that can process multiple designs (e.g., 6502 CPU) and analyze performance, congestion, and timing.

---

## 🎯 Objectives  
- Parse and validate platform and design data.  
- Perform placement as an **assignment problem** (Greedy + Simulated Annealing).  
- Implement **Clock Tree Synthesis (CTS)** using available buffer cells.  
- Generate **ECO netlists** for power optimization.  
- Integrate with **OpenROAD** for routing and static timing analysis.  
- Provide detailed **visualizations** for placement, congestion, and timing results.  

---

## 🧩 Project Phases  
| Phase | Deliverable | Description | Due Date |
|-------|--------------|--------------|----------|
| Week 0 | Setup | Group formation, GitHub repo & workflow setup | Nov 2 |
| Phase 1 | Database & Validation | Parse YAML/JSON and visualize fabric layout | Nov 9 |
| Phase 2 | Placement | Greedy + SA placer, HPWL minimization, analysis plots | Nov 23 |
| Phase 3 | CTS & ECO | Clock tree generation and power ECO | Nov 30 |
| Phases 4–5 | Routing & STA | Routing, parasitics, timing analysis | Dec 7 |
| Final | Report & Presentation | Full flow, dashboard, and analysis | Dec 10 |

---

## ⚙️ Tools & Technologies  
- **Languages:** Python, Tcl, Make  
- **EDA Tools:** OpenROAD, KLayout  
- **Libraries:** Matplotlib, NumPy, PyYAML, JSON  
- **Version Control:** Git & GitHub Project Board (Kanban)

---

## 🧭 Workflow  
- Protected **main** branch requiring PR reviews before merge.  
- Each feature implemented in a dedicated branch (`feature/<task>`).  
- **GitHub Issues** used for task tracking with clear ownership.  
- **Project Board** workflow: To Do → In Progress → Review → Done.  
- Frequent commits with descriptive messages referencing issue numbers.  

---

## 📊 Visualization Outputs  
- `fabric_layout.png` – Fabric map showing slots and pins.  
- `placement_density.png` – Cell density heatmap.  
- `net_length_histogram.png` – Distribution of net HPWLs.  
- `cts_tree.png` – Clock tree visualization.  
- `congestion.png`, `slack_histogram.png`, `critical_path.png` – Routing and STA analysis.  

---

## 🧠 Supervision  
This project is conducted under the supervision of **Dr. Mohamed Shalan**, focusing on algorithmic design automation, optimization, and structured ASIC physical design methodologies.
