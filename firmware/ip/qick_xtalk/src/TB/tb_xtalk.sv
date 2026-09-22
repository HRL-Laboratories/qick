///////////////////////////////////////////////////////////////////////////////
//  FERMI RESEARCH LAB
///////////////////////////////////////////////////////////////////////////////
//  Author         : mdife
///////////////////////////////////////////////////////////////////////////////

`timescale 1ns/10ps

import axi_vip_pkg::*;
import axi_mst_0_pkg::*;

`define T_C_CLK         2 // 1.66 // Half Clock Period for Simulation
`define T_ADC_CLK       25 // 1.66 // Half Clock Period for Simulation
`define T_PS_CLK        10  // Half Clock Period for Simulation

 
`define CH_QTY        1
`define COEF_DW       10
`define SMP_DW        16
`define SMP_CK        4  

`define DEBUG           1

module tb_xtalk();

///////////////////////////////////////////////////////////////////////////////

// VIP Agent
axi_mst_0_mst_t 	axi_mst_0_agent;
xil_axi_prot_t  prot        = 0;
xil_axi_resp_t  resp;

// Signals
reg c_clk, adc_clk, ps_clk;
reg rst_ni;
reg[31:0]       data_wr     = 32'h12345678;

integer t;
real           x0, x1, x2, x3,x4, x5, x6, x7 ;
reg [`SMP_DW-1:0] y0, y1, y2, y3,y4, y5, y6, y7, y8, y9 ;
reg signed [`SMP_DW*`SMP_CK-1:0] z_dt, r_dt, s_dt, f_dt ;
reg signed [`SMP_DW*`SMP_CK-1:0] adc_dt, nei_dt1, nei_dt2, nei_dt3, nei_dt4;

//AXI-LITE
wire [7:0]             s_axi_awaddr  ;
wire [2:0]             s_axi_awprot  ;
wire                   s_axi_awvalid ;
wire                   s_axi_awready ;
wire [31:0]            s_axi_wdata   ;
wire [3:0]             s_axi_wstrb   ;
wire                   s_axi_wvalid  ;
wire                   s_axi_wready  ;
wire  [1:0]            s_axi_bresp   ;
wire                   s_axi_bvalid  ;
wire                   s_axi_bready  ;
wire [7:0]             s_axi_araddr  ;
wire [2:0]             s_axi_arprot  ;
wire                   s_axi_arvalid ;
wire                   s_axi_arready ;
wire  [31:0]           s_axi_rdata   ;
wire  [1:0]            s_axi_rresp   ;
wire                   s_axi_rvalid  ;
wire                   s_axi_rready  ;


//////////////////////////////////////////////////////////////////////////
//  CLK Generation
initial begin
  c_clk = 1'b0;
  forever # (`T_C_CLK) c_clk = ~c_clk;
end
initial begin
  adc_clk = 1'b0;
  forever # (`T_ADC_CLK) adc_clk = ~adc_clk;
end
initial begin
  ps_clk = 1'b0;
  forever # (`T_PS_CLK) ps_clk = ~ps_clk;
end

// Register ADDRESS
parameter QXT_CTRL     = 0 * 4 ;
parameter QXT_CFG      = 1 * 4 ;
parameter K1           = 2 * 4 ;
parameter K2           = 3 * 4 ;
parameter K3           = 4 * 4 ;
parameter K4           = 5 * 4 ;


//////////////////////////////////////////////////////////////////////////
//  AXI AGENT
axi_mst_0 axi_mst_0_i (
   .aclk          ( ps_clk          ),
   .aresetn       ( rst_ni          ),
   .m_axi_araddr  ( s_axi_araddr    ),
   .m_axi_arprot  ( s_axi_arprot    ),
   .m_axi_arready ( s_axi_arready   ),
   .m_axi_arvalid ( s_axi_arvalid   ),
   .m_axi_awaddr  ( s_axi_awaddr    ),
   .m_axi_awprot  ( s_axi_awprot    ),
   .m_axi_awready ( s_axi_awready   ),
   .m_axi_awvalid ( s_axi_awvalid   ),
   .m_axi_bready  ( s_axi_bready    ),
   .m_axi_bresp   ( s_axi_bresp     ),
   .m_axi_bvalid  ( s_axi_bvalid    ),
   .m_axi_rdata   ( s_axi_rdata     ),
   .m_axi_rready  ( s_axi_rready    ),
   .m_axi_rresp   ( s_axi_rresp     ),
   .m_axi_rvalid  ( s_axi_rvalid    ),
   .m_axi_wdata   ( s_axi_wdata     ),
   .m_axi_wready  ( s_axi_wready    ),
   .m_axi_wstrb   ( s_axi_wstrb     ),
   .m_axi_wvalid  ( s_axi_wvalid    ));


   
axi_qick_xtalk #( 
   .CH_QTY       ( `CH_QTY ) , // Number of Inputs
   .COEF_DW      ( `COEF_DW ) , // Bits of the Coeff
   .SMP_DW       ( `SMP_DW ) , // Samples WIDTH
   .SMP_CK       ( `SMP_CK ) , // Samples per Clock
   .DEBUG        ( 1 ) 
) axi_qick_xtalk (
// Core and AXI CLK & RST
   .a_clk               ( adc_clk            ),
   .a_aresetn           ( rst_ni        ),
   .ps_clk              ( ps_clk             ),
   .ps_aresetn          ( rst_ni         ),
   .s_axi_awaddr        ( s_axi_awaddr       ),
   .s_axi_awprot        ( s_axi_awprot       ),
   .s_axi_awvalid       ( s_axi_awvalid      ),
   .s_axi_awready       ( s_axi_awready      ),
   .s_axi_wdata         ( s_axi_wdata        ),
   .s_axi_wstrb         ( s_axi_wstrb        ),
   .s_axi_wvalid        ( s_axi_wvalid       ),
   .s_axi_wready        ( s_axi_wready       ),
   .s_axi_bresp         ( s_axi_bresp        ),
   .s_axi_bvalid        ( s_axi_bvalid       ),
   .s_axi_bready        ( s_axi_bready       ),
   .s_axi_araddr        ( s_axi_araddr       ),
   .s_axi_arprot        ( s_axi_arprot       ),
   .s_axi_arvalid       ( s_axi_arvalid      ),
   .s_axi_arready       ( s_axi_arready      ),
   .s_axi_rdata         ( s_axi_rdata        ),
   .s_axi_rresp         ( s_axi_rresp        ),
   .s_axi_rvalid        ( s_axi_rvalid       ),
   .s_axi_rready        ( s_axi_rready       ),
   .w0_s_axis_tvalid_i  ( 1 ),
   .w0_s_axis_tdata_i   ( adc_dt ),
   .w0_s_axis_tready_o  (  ),
   .w1_s_axis_tvalid_i  ( 1 ),
   .w1_s_axis_tdata_i   ( nei_dt1),
   .w1_s_axis_tready_o  (  ),
   .w2_s_axis_tvalid_i  ( 1 ),
   .w2_s_axis_tdata_i   ( nei_dt2 ),
   .w2_s_axis_tready_o  (  ),
   .w3_s_axis_tvalid_i  ( 1 ),
   .w3_s_axis_tdata_i   ( nei_dt3 ),
   .w3_s_axis_tready_o  (  ),
   .w4_s_axis_tvalid_i  ( 1 ),
   .w4_s_axis_tdata_i   ( nei_dt4 ),
   .w4_s_axis_tready_o  (  ),
   .m_axis_tvalid_o     (  ),
   .m_axis_tdata_o      (  ),
   .m_axis_tready_i     (  ) );


assign w0_s_axis_tvalid_i = 1'b1;
assign w1_s_axis_tvalid_i = 1'b1;
assign w2_s_axis_tvalid_i = 1'b1;

initial begin
   START_SIMULATION ();
   TEST_AXI ();
   AMP = 3;

   WRITE_AXI( K1       ,  0);
   WRITE_AXI( K2       ,  0);
   WRITE_AXI( K3       ,  0);
   WRITE_AXI( K4       ,  0);
   SIM_RAMP () ;
   
   WRITE_AXI( K1         ,  10'b01_0000_0000); // 0.5
   //WRITE_AXI( K1       ,  18'b01_0000_0000_0000_0000); // 0.5
   //WRITE_AXI( K2       ,  18'b01_0000_0000_0000_0000); // 0.5
   //WRITE_AXI( K3       ,  18'b01_0000_0000_0000_0000); // 0.5
   //WRITE_AXI( K4       ,  0);
   SIM_RAMP () ;

   WRITE_AXI( K1         ,  10'b01__1111_1111); // 0.5
   //WRITE_AXI( K1       ,  18'b01_0000_0000_0000_0000); // 0.5
   //WRITE_AXI( K2       ,  18'b01_0000_0000_0000_0000); // 0.5
   //WRITE_AXI( K3       ,  0);
   //WRITE_AXI( K4       ,  18'b01_0000_0000_0000_0000); // 0.5
   SIM_RAMP () ;

   WRITE_AXI( K1       ,  10'b10_1111_1111); // Casi 1 -- OK
   //WRITE_AXI( K1       ,  18'b01_1111_11111111_1111); // Casi 1 -- OK
   //WRITE_AXI( K2       ,  18'b01_1111_11111111_1111); // Casi 1 -- OK
   //WRITE_AXI( K3       ,  18'b01_1111_11111111_1111); // Casi 1 -- OK
   //WRITE_AXI( K4       ,  18'b01_1111_11111111_1111); // Casi 1 -- OK
   SIM_RAMP () ;

   WRITE_AXI( K1       ,  18'b10_0000_0000_0000_0001); //Casi -1 -- OK
   WRITE_AXI( K2       ,  18'b10_0000_0000_0000_0001); //Casi -1 -- OK
   WRITE_AXI( K3       ,  18'b10_0000_0000_0000_0001); //Casi -1 -- OK
   WRITE_AXI( K4       ,  18'b10_0000_0000_0000_0001); //Casi -1 -- OK
   SIM_RAMP () ;

   SIM_SINE ();
end


task START_SIMULATION (); begin
   $display("START SIMULATION");
   // Create agents.
   axi_mst_0_agent 	= new("axi_mst_0 VIP Agent",tb_xtalk.axi_mst_0_i.inst.IF);
   // Set tag for agents.
   axi_mst_0_agent.set_agent_tag	("axi_mst_0 VIP");
   // Start agents.
   axi_mst_0_agent.start_master();
   rst_ni  = 1'b0;
   adc_dt  = 0;
   nei_dt1 = 0;
   nei_dt2 = 0;
   nei_dt3 = 0;
   nei_dt4 = 0;
   @ (posedge ps_clk); #0.1;
   rst_ni            = 1'b1;
   end
endtask

task WRITE_AXI(integer PORT_AXI, DATA_AXI); begin
   @ (posedge ps_clk); #0.1;
   axi_mst_0_agent.AXI4LITE_WRITE_BURST(PORT_AXI, prot, DATA_AXI, resp);
   end
endtask


task TEST_AXI (); begin
   $display("-----Writting AXI ");
   WRITE_AXI( QXT_CTRL ,  1);
   WRITE_AXI( QXT_CFG  ,  2);
   WRITE_AXI( K1       ,  3);
   WRITE_AXI( K2       ,  4);
   WRITE_AXI( K3       ,  5);
   WRITE_AXI( K4       ,  6);
end
endtask



task SIM_RAMP(); begin
   $display("SIM TAGGER");
   for (t=-3; t<=3; t=t+1) begin
      @ (posedge adc_clk); #0.1;
      y0 = t[`SMP_DW-1:0]; // ( (8*t)+0 );
      y1 = ( (10*t)+1 );
      y2 = ( (8*t)+2 );
      y3 = ( (8*t)+3 );
      y4 = ( (8*t)+4 );
      y5 = ( (8*t)+5 );
      y6 = ( (8*t)+6 );
      y7 = ( (8*t)+7 );
      y8 = ( (8*t)+8 );
      y9 = ( (8*t)+9 );
      z_dt    = {0, 0, 0, 0, 0, 0, 0, 0 };   
      r_dt    = {y7, y6, y5, y4, y3, y2, y1, y0 };   
      adc_dt  = r_dt ;
      nei_dt1 = r_dt *20;   
      nei_dt2 = r_dt *200;   
      nei_dt3 = r_dt *2000;   
      nei_dt4 = r_dt *2000;   
   
   end
end
endtask

integer AMP;

task SIM_SINE(); begin
   for (t=0; t<100; t=t+1) begin
      @ (posedge adc_clk); #0.1;
      //x = (t)* (22.0/7.0)/20;
      //y = $sin(x) ;
      //yd = y *1000*AMP+($random %100);
      x0 =   t * (22.0/7.0)/20 ;
      x1 =   t * (22.0/7.0)/20 ;
      x2 =   t * (22.0/7.0)/20 ;
      x3 =   t * (22.0/7.0)/20 ;
      x4 = ( (8*t)+0 ) * (22.0/7.0) / 5;
      x5 = ( (8*t)+1 ) * (22.0/7.0) / 5;
      x6 = ( (8*t)+2 ) * (22.0/7.0) / 5;
      x7 = ( (8*t)+3 ) * (22.0/7.0) / 5;
      y0 = $sin(x0)*1000*AMP;
      y1 = $sin(x1)*1000*AMP;
      y2 = $sin(x2)*1000*AMP;
      y3 = $sin(x3)*1000*AMP;
      y4 = $sin(x4)*1000*AMP;
      y5 = $sin(x5)*1000*AMP;
      y6 = $sin(x6)*1000*AMP;
      y7 = $sin(x7)*1000*AMP;
      z_dt    = {0, 0, 0, 0, 0, 0, 0, 0 };   
      s_dt    = {0, 0, 0, 0, y3, y2, y1, y0 };   
      f_dt    = {0, 0, 0, 0, y7, y6, y5, y4 };   
      adc_dt  = s_dt;
      nei_dt1 = s_dt ;   
      nei_dt2 = z_dt  ;   

   end

      adc_dt = 0;
end
endtask




endmodule




