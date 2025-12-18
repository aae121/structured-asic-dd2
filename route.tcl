# Generic OpenROAD routing + parasitics script
# Expected environment variables:
#   DESIGN_NAME         : top module name
#   LEF_FILES           : space-separated list of LEF files
#   LIB_FILES           : space-separated list of liberty timing files
#   DEF_FILE            : DEF with fixed placement (e.g., <design>_fixed.def)
#   VERILOG_FILE        : gate-level netlist (e.g., <design>_renamed.v)
# Optional:
#   CONGESTION_REPORT   : output path for congestion reports (default: congestion.rpt)
#   PARASITICS_SPEF     : output SPEF path (default: <design>.spef)

proc require_env {name} {
  if {![info exists ::env($name)] || $::env($name) eq ""} {
    puts stderr "ERROR: env $name is required"
    exit 1
  }
}

foreach var {DESIGN_NAME LEF_FILES LIB_FILES DEF_FILE VERILOG_FILE} {
  require_env $var
}

set design $::env(DESIGN_NAME)
set cong_rpt [expr {[info exists ::env(CONGESTION_REPORT)] && $::env(CONGESTION_REPORT) ne "" ? $::env(CONGESTION_REPORT) : "congestion.rpt"}]
set spef_out [expr {[info exists ::env(PARASITICS_SPEF)] && $::env(PARASITICS_SPEF) ne "" ? $::env(PARASITICS_SPEF) : "$design.spef"}]

puts "==> Reading LEFs"
foreach lef [split $::env(LEF_FILES)] {
  if {$lef ne ""} { read_lef $lef }
}

puts "==> Reading Liberty files"
foreach lib [split $::env(LIB_FILES)] {
  if {$lib ne ""} { read_liberty $lib }
}

puts "==> Reading Verilog"
read_verilog $::env(VERILOG_FILE)
link_design $design

puts "==> Reading DEF"
read_def $::env(DEF_FILE)

puts "==> Global route"
global_route
report_congestion > $cong_rpt

puts "==> Detailed route"
detailed_route

puts "==> Parasitic extraction"
estimate_parasitics -global_routing
write_spef $spef_out

puts "==> Congestion report (post-route)"
report_congestion >> $cong_rpt

puts "==> Done"
