# Auto-generated SDC for 6502 (25 MHz -> 40 ns period)
set_units -time ns

create_clock -name clk -period 40 [get_ports clk]
set_propagated_clock [get_clocks clk]

# Apply IO delays to all ports except the clock
set _in_ports  [remove_from_collection [all_inputs]  [get_ports {clk}]]
set _out_ports [all_outputs]

if {[sizeof_collection $_in_ports] > 0} {
  set_input_delay 5 -clock [get_clocks clk] $_in_ports
}
if {[sizeof_collection $_out_ports] > 0} {
  set_output_delay 5 -clock [get_clocks clk] $_out_ports
}
