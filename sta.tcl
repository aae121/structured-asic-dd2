# Generic STA script (OpenSTA-compatible)
# Required env vars:
#   DESIGN_NAME   : top module name
#   LIB_FILES     : space-separated liberty files
#   VERILOG_FILE  : gate-level netlist (renamed)
#   SPEF_FILE     : extracted parasitics
#   SDC_FILE      : timing constraints
# Optional env vars:
#   SETUP_RPT     : setup report path (default: <design>.setup.rpt)
#   HOLD_RPT      : hold report path (default: <design>.hold.rpt)
#   SKEW_RPT      : clock skew report path (default: <design>.skew.rpt)

proc require_env {name} {
  if {![info exists ::env($name)] || $::env($name) eq ""} {
    puts stderr "ERROR: env $name is required"
    exit 1
  }
}

foreach var {DESIGN_NAME LIB_FILES VERILOG_FILE SPEF_FILE SDC_FILE} {
  require_env $var
}

set design     $::env(DESIGN_NAME)
set setup_rpt  [expr {[info exists ::env(SETUP_RPT)] && $::env(SETUP_RPT) ne "" ? $::env(SETUP_RPT) : "$design.setup.rpt"}]
set hold_rpt   [expr {[info exists ::env(HOLD_RPT)]  && $::env(HOLD_RPT)  ne "" ? $::env(HOLD_RPT)  : "$design.hold.rpt"}]
set skew_rpt   [expr {[info exists ::env(SKEW_RPT)]  && $::env(SKEW_RPT)  ne "" ? $::env(SKEW_RPT)  : "$design.skew.rpt"}]

puts "==> Reading liberty"
foreach lib [split $::env(LIB_FILES)] {
  if {$lib ne ""} { read_liberty $lib }
}

puts "==> Reading netlist"
read_verilog $::env(VERILOG_FILE)
link_design $design

puts "==> Reading parasitics"
read_spef $::env(SPEF_FILE)

puts "==> Reading constraints"
read_sdc $::env(SDC_FILE)
set_propagated_clock [all_clocks]
update_timing

puts "==> Report setup"
report_checks -path_delay max -fields {slew cap input_pins nets} -digits 3 -nworst 100 > $setup_rpt

puts "==> Report hold"
report_checks -path_delay min -fields {slew cap input_pins nets} -digits 3 -nworst 100 > $hold_rpt

puts "==> Report clock skew"
report_clock_skew > $skew_rpt

puts "==> Done"
