create_clock -period 10.000 -name ps_clk -waveform {0.000 5.000} [get_ports ps_clk]
create_clock -period 1.600 -name a_clk -waveform {0.000 0.800} [get_ports a_clk]
