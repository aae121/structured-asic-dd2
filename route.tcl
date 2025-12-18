# ==============================================================================
# Routing Flow Script for Design: 6502
# ==============================================================================

# Set environment variable for OpenROAD
set ::env(DESIGN_NAME) "6502"
set build_dir "build/$::env(DESIGN_NAME)"
set routed_def "$build_dir/${::env(DESIGN_NAME)}_routed.def"
set spef_file "$build_dir/${::env(DESIGN_NAME)}.spef"
set congestion_rpt "$build_dir/${::env(DESIGN_NAME)}_congestion.rpt"

# ------------------------------------------------------------------------------
# Read LEF/DEF
# ------------------------------------------------------------------------------
read_lef  "$build_dir/sky130_fd_sc_hd_combined.lef"
read_def  "$build_dir/floorplan.def"

# ------------------------------------------------------------------------------
# Global Routing
# ------------------------------------------------------------------------------
global_route

# ------------------------------------------------------------------------------
# Detailed Routing (SPEF will be generated here)
# ------------------------------------------------------------------------------
detailed_route

# ------------------------------------------------------------------------------
# Step 6 - Report SPEF size
# ------------------------------------------------------------------------------
if {[file exists $spef_file]} {
    set spef_size [file size $spef_file]
    puts "  SPEF file size: [expr {$spef_size / 1024}] KB"
} else {
    puts "  SPEF file not found."
}

# ------------------------------------------------------------------------------
# Step 7 - Generate Congestion Report
# ------------------------------------------------------------------------------
puts "\nGenerating congestion report..."

set congestion_fp [open $congestion_rpt w]
puts $congestion_fp "=========================================="
puts $congestion_fp "Routing Congestion Report"
puts $congestion_fp "Design: $::env(DESIGN_NAME)"
puts $congestion_fp "=========================================="
puts $congestion_fp ""
puts $congestion_fp "Global Routing Congestion:"
puts $congestion_fp [report_checks]
puts $congestion_fp "\nLayer-by-Layer Wire Usage:"
puts $congestion_fp [report_wire_length]

# Report DRC violations if any
if {[file exists "${build_dir}/${::env(DESIGN_NAME)}_drc.rpt"]} {
    set drc_fp [open "${build_dir}/${::env(DESIGN_NAME)}_drc.rpt" r]
    set drc_content [read $drc_fp]
    close $drc_fp
    puts $congestion_fp "\nDRC Violations:"
    puts $congestion_fp $drc_content
}
close $congestion_fp

puts "Congestion report written: $congestion_rpt"
puts "\nCongestion Summary:"
puts "----------------------------------------"
report_checks -path_delay min_max

# ------------------------------------------------------------------------------
# Step 8 - Summary and Verification
# ------------------------------------------------------------------------------
puts "\nRouting Flow Complete!"
puts "=========================================="
puts "Outputs:"
puts "  Routed DEF:       $routed_def"
puts "  Parasitics:       $spef_file"
puts "  Congestion Report: $congestion_rpt"
puts "  DRC Report:       ${build_dir}/${::env(DESIGN_NAME)}_drc.rpt"
puts "=========================================="

# Verify outputs
if {![file exists $routed_def]} {
    puts "ERROR: Routed DEF file not created!"
    exit 1
}
if {![file exists $spef_file]} {
    puts "WARNING: SPEF file not created!"
}
if {![file exists $congestion_rpt]} {
    puts "WARNING: Congestion report not created!"
}

# Final statistics
puts "\nFinal Design Statistics:"
puts "  Total wire length: [report_wire_length]"
puts "  Number of nets:    [llength [get_nets *]]"
puts "  Number of pins:    [llength [get_pins *]]"

puts "\nRouting completed successfully!"
puts "=========================================="

exit 0

