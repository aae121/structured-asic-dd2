# Generic OpenROAD routing + parasitics script
# Configured for test[1]/test directory structure
# Auto-fixes Sky130 LEF compatibility issues

# ============================================================================
# CONFIGURATION - Based on your uploaded files
# ============================================================================

set design_name "6502"

# LEF FILES - Found in tech/ directory
set lef_files [list \
    "./sky130_fd_sc_hd.tlef" \
    "./sky130_fd_sc_hd.lef" \
]

# LIBERTY FILES
set lib_files [list \
    "./sky130_fd_sc_hd__tt_025C_1v80.lib" \
]

# DEF FILE - Your placed design
set def_file "./build/6502/6502_placed.def"

# VERILOG FILE - Gate-level netlist
set verilog_file "./src/build/6502/6502_final.v"

# OPTIONAL OUTPUT PATHS
set congestion_report "./build/6502/congestion.rpt"
set parasitics_spef "./build/6502/${design_name}.spef"

# ============================================================================
# AUTO-FIX LEF FILES
# ============================================================================

proc fix_lef_file {filepath} {
    if {![file exists $filepath]} {
        return
    }
    
    # Read the file
    set fp [open $filepath r]
    set content [read $fp]
    close $fp
    
    # Check if it needs fixing
    if {[string match "*DISTANCE MICRONS 1 ;*" $content]} {
        puts "    Fixing LEF compatibility issue in: [file tail $filepath]"
        
        # Backup original
        set backup_path "${filepath}.backup"
        if {![file exists $backup_path]} {
            file copy -force $filepath $backup_path
        }
        
        # Remove problematic DISTANCE line
        regsub -all {[ \t]*DISTANCE MICRONS 1 ;[ \t]*\n} $content "" content
        
        # Write fixed version
        set fp [open $filepath w]
        puts -nonewline $fp $content
        close $fp
        
        puts "    ✓ Fixed and backed up to: [file tail $backup_path]"
    }
}

# Fix LEF files before using them
puts "==> Checking and fixing LEF files for OpenROAD compatibility..."
foreach lef $lef_files {
    if {$lef ne "" && [file exists $lef]} {
        fix_lef_file $lef
    }
}
puts ""

# ============================================================================
# ENVIRONMENT VARIABLE OVERRIDES
# ============================================================================

# Override with environment variables if they exist
if {[info exists ::env(DESIGN_NAME)] && $::env(DESIGN_NAME) ne ""} {
    set design_name $::env(DESIGN_NAME)
}
if {[info exists ::env(LEF_FILES)] && $::env(LEF_FILES) ne ""} {
    set lef_files [split $::env(LEF_FILES)]
}
if {[info exists ::env(LIB_FILES)] && $::env(LIB_FILES) ne ""} {
    set lib_files [split $::env(LIB_FILES)]
}
if {[info exists ::env(DEF_FILE)] && $::env(DEF_FILE) ne ""} {
    set def_file $::env(DEF_FILE)
}
if {[info exists ::env(VERILOG_FILE)] && $::env(VERILOG_FILE) ne ""} {
    set verilog_file $::env(VERILOG_FILE)
}
if {[info exists ::env(CONGESTION_REPORT)] && $::env(CONGESTION_REPORT) ne ""} {
    set congestion_report $::env(CONGESTION_REPORT)
}
if {[info exists ::env(PARASITICS_SPEF)] && $::env(PARASITICS_SPEF) ne ""} {
    set parasitics_spef $::env(PARASITICS_SPEF)
}

# ============================================================================
# FILE VALIDATION
# ============================================================================

proc check_file_exists {filepath varname} {
    if {![file exists $filepath]} {
        puts stderr "=========================================="
        puts stderr "ERROR: $varname file does not exist:"
        puts stderr "  Path: $filepath"
        puts stderr "=========================================="
        exit 1
    }
}

puts "==> Validating configuration..."
puts "    DESIGN_NAME: $design_name"
puts "    Working directory: [pwd]"
puts ""

foreach lef $lef_files {
    if {$lef ne ""} {
        check_file_exists $lef "LEF"
        puts "    LEF: $lef ✓"
    }
}

foreach lib $lib_files {
    if {$lib ne ""} {
        check_file_exists $lib "LIB"
        puts "    LIB: $lib ✓"
    }
}

check_file_exists $def_file "DEF"
puts "    DEF: $def_file ✓"

check_file_exists $verilog_file "VERILOG"
puts "    VERILOG: $verilog_file ✓"

puts ""
puts "    Output SPEF: $parasitics_spef"
puts "    Output congestion report: $congestion_report"
puts ""

# ============================================================================
# ROUTING FLOW
# ============================================================================

puts "==> Reading LEFs"
foreach lef $lef_files {
    if {$lef ne ""} { 
        puts "    Reading: $lef"
        read_lef $lef 
    }
}

puts "\n==> Reading Liberty files"
foreach lib $lib_files {
    if {$lib ne ""} { 
        puts "    Reading: $lib"
        read_liberty $lib 
    }
}

puts "\n==> Reading Verilog"
read_verilog $verilog_file
link_design $design_name

puts "\n==> Reading DEF"
read_def $def_file

puts "\n==> Global route"
global_route
report_congestion > $congestion_report

puts "\n==> Detailed route"
detailed_route

puts "\n==> Parasitic extraction"
estimate_parasitics -global_routing
write_spef $parasitics_spef

puts "\n==> Congestion report (post-route)"
report_congestion >> $congestion_report

puts "\n==> Done successfully!"
puts "    Output SPEF: $parasitics_spef"
puts "    Congestion report: $congestion_report"
