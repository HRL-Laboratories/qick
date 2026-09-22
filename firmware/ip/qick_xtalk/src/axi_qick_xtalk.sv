///////////////////////////////////////////////////////////////////////////////
//  FERMI RESEARCH LAB
///////////////////////////////////////////////////////////////////////////////
//  Author         : Martin Di Federico
//  Date           : 2024_11_7
//  Version        : 1
///////////////////////////////////////////////////////////////////////////////
//  QICK PROCESSOR :  QIck Cross talk Compensation 
//////////////////////////////////////////////////////////////////////////////
   
module axi_qick_xtalk # (
   parameter CH_QTY       = 10  , // Number of Inputs
   parameter COEF_DW      = 18 , // Bits of the Coeff
   parameter SMP_DW       = 16 , // Samples Data WIDTH
   parameter SMP_CK       = 16   // Samples per Clock
) (
// Core and AXI CLK & RST
   input  wire                      a_clk          ,
   input  wire                      a_aresetn      ,
   input  wire                      ps_clk         ,
   input  wire                      ps_aresetn     ,
// AXI INTERFACE
   input  wire [5:0]                s_axi_awaddr   ,
   input  wire [2:0]                s_axi_awprot   ,
   input  wire                      s_axi_awvalid  ,
   output wire                      s_axi_awready  ,
   input  wire [31:0]               s_axi_wdata    ,
   input  wire [ 3:0]               s_axi_wstrb    ,
   input  wire                      s_axi_wvalid   ,
   output wire                      s_axi_wready   ,
   output wire [ 1:0]               s_axi_bresp    ,
   output wire                      s_axi_bvalid   ,
   input  wire                      s_axi_bready   ,
   input  wire [ 5:0]               s_axi_araddr   ,
   input  wire [ 2:0]               s_axi_arprot   ,
   input  wire                      s_axi_arvalid  ,
   output wire                      s_axi_arready  ,
   output wire [31:0]               s_axi_rdata    ,
   output wire [ 1:0]               s_axi_rresp    ,
   output wire                      s_axi_rvalid   ,
   input  wire                      s_axi_rready   ,
   ///// WAVE STREAM DATA
   input  wire                     w0_s_axis_tvalid_i ,
   input  wire [SMP_CK*SMP_DW-1:0] w0_s_axis_tdata_i  ,
   output wire                     w0_s_axis_tready_o ,
   input  wire                     w1_s_axis_tvalid_i ,
   input  wire [SMP_CK*SMP_DW-1:0] w1_s_axis_tdata_i  ,
   output wire                     w1_s_axis_tready_o ,
   input  wire                     w2_s_axis_tvalid_i ,
   input  wire [SMP_CK*SMP_DW-1:0] w2_s_axis_tdata_i  ,
   output wire                     w2_s_axis_tready_o ,
   input  wire                     w3_s_axis_tvalid_i ,
   input  wire [SMP_CK*SMP_DW-1:0] w3_s_axis_tdata_i  ,
   output wire                     w3_s_axis_tready_o ,
   input  wire                     w4_s_axis_tvalid_i ,
   input  wire [SMP_CK*SMP_DW-1:0] w4_s_axis_tdata_i  ,
   output wire                     w4_s_axis_tready_o ,
   input  wire                     w5_s_axis_tvalid_i ,
   input  wire [SMP_CK*SMP_DW-1:0] w5_s_axis_tdata_i  ,
   output wire                     w5_s_axis_tready_o ,
   input  wire                     w6_s_axis_tvalid_i ,
   input  wire [SMP_CK*SMP_DW-1:0] w6_s_axis_tdata_i  ,
   output wire                     w6_s_axis_tready_o ,
   input  wire                     w7_s_axis_tvalid_i ,
   input  wire [SMP_CK*SMP_DW-1:0] w7_s_axis_tdata_i  ,
   output wire                     w7_s_axis_tready_o ,
   input  wire                     w8_s_axis_tvalid_i ,
   input  wire [SMP_CK*SMP_DW-1:0] w8_s_axis_tdata_i  ,
   output wire                     w8_s_axis_tready_o ,
   input  wire                     w9_s_axis_tvalid_i ,
   input  wire [SMP_CK*SMP_DW-1:0] w9_s_axis_tdata_i  ,
   output wire                     w9_s_axis_tready_o ,
   input  wire                     w10_s_axis_tvalid_i,
   input  wire [SMP_CK*SMP_DW-1:0] w10_s_axis_tdata_i ,
   output wire                     w10_s_axis_tready_o,
   output wire                     m_axis_tvalid_o    ,
   output wire [SMP_CK*SMP_DW-1:0] m_axis_tdata_o     ,
   input  wire                     m_axis_tready_i    
   );

// Signal Declaration
//////////////////////////////////////////////////////////////////////////


// wire [ 7:0] axi_reg_CTRL;
// wire [10:0] axi_reg_CFG;
wire [17:0] axi_reg_K1, axi_reg_K2, axi_reg_K3, axi_reg_K4, axi_reg_K5,
            axi_reg_K6, axi_reg_K7, axi_reg_K8, axi_reg_K9, axi_reg_K10 ;
// wire [31:0] axi_reg_XT_STATUS, axi_reg_XT_DEBUG;

wire signed [SMP_CK*SMP_DW-1:0] neighbourhood [CH_QTY];
wire signed [COEF_DW-1:0] k_param [CH_QTY];

qick_xtalk # (
   .CH_QTY       ( CH_QTY  ), // Number of ADC Inputs
   .COEF_DW      ( COEF_DW ), // Number of ADC Inputs
   .SMP_DW       ( SMP_DW  ), // Samples WIDTH
   .SMP_CK       ( SMP_CK  ) // Samples per Clock
) XTALK (
// Core and AXI CLK & RST
   .a_clk_i        ( a_clk ),
   .a_rst_ni       ( a_aresetn ),
   .self_dt_i      ( w0_s_axis_tdata_i ),
   .nei_dt_i       ( neighbourhood ),
   .k_param_i      ( k_param ), 
   //.k_param_i       ( '{10'b01_1111_1111, 10'b10_0000_0001} ), // Casi 1 y -1
   //.k_param_i       ( '{10'b01_1111_1111, 10'b01_1111_1111} ), // Casi 1 y 1
   .wave_o         ( m_axis_tdata_o ) );



///// Neighbourhood concatenation
///////////////////////////////////////////////////////////////////////////////
generate
   if      (CH_QTY == 1) begin : ONE_NEI
      assign neighbourhood = {w1_s_axis_tdata_i};
      assign k_param       = {axi_reg_K1[COEF_DW-1:0]} ;
   end else if (CH_QTY == 2) begin : TWO_NEI
      assign neighbourhood = {w1_s_axis_tdata_i, w2_s_axis_tdata_i} ;
      assign k_param       = {axi_reg_K1[COEF_DW-1:0], axi_reg_K2[COEF_DW-1:0] } ;
   end else if (CH_QTY == 3) begin : THREE_NEI
      assign neighbourhood = {w1_s_axis_tdata_i, w2_s_axis_tdata_i, w3_s_axis_tdata_i} ;
      assign k_param       = {axi_reg_K1[COEF_DW-1:0], axi_reg_K2[COEF_DW-1:0], axi_reg_K3[COEF_DW-1:0]} ;
   end else if (CH_QTY == 4) begin : FOUR_NEI
      assign neighbourhood = {w1_s_axis_tdata_i, w2_s_axis_tdata_i, w3_s_axis_tdata_i, w4_s_axis_tdata_i} ;
      assign k_param       = {axi_reg_K1[COEF_DW-1:0], axi_reg_K2[COEF_DW-1:0], axi_reg_K3[COEF_DW-1:0], axi_reg_K4[COEF_DW-1:0] } ;
   end else if (CH_QTY == 5) begin : FIVE_NEI
      assign neighbourhood = {w1_s_axis_tdata_i, w2_s_axis_tdata_i, w3_s_axis_tdata_i, w4_s_axis_tdata_i, w5_s_axis_tdata_i} ;
      assign k_param       = {axi_reg_K1[COEF_DW-1:0], axi_reg_K2[COEF_DW-1:0], axi_reg_K3[COEF_DW-1:0], axi_reg_K4[COEF_DW-1:0],
                              axi_reg_K5[COEF_DW-1:0] } ;
   end else if (CH_QTY == 6) begin : SIX_NEI
      assign neighbourhood = {w1_s_axis_tdata_i, w2_s_axis_tdata_i, w3_s_axis_tdata_i, w4_s_axis_tdata_i, w5_s_axis_tdata_i,
                              w6_s_axis_tdata_i} ;
      assign k_param       = {axi_reg_K1[COEF_DW-1:0], axi_reg_K2[COEF_DW-1:0], axi_reg_K3[COEF_DW-1:0], axi_reg_K4[COEF_DW-1:0],
                              axi_reg_K5[COEF_DW-1:0],axi_reg_K6[COEF_DW-1:0] } ;
   end else if (CH_QTY == 7) begin : SEVEN_NEI
      assign neighbourhood = {w1_s_axis_tdata_i, w2_s_axis_tdata_i, w3_s_axis_tdata_i, w4_s_axis_tdata_i, w5_s_axis_tdata_i,
                              w6_s_axis_tdata_i, w7_s_axis_tdata_i} ;
      assign k_param       = {axi_reg_K1[COEF_DW-1:0], axi_reg_K2[COEF_DW-1:0], axi_reg_K3[COEF_DW-1:0], axi_reg_K4[COEF_DW-1:0],
                              axi_reg_K5[COEF_DW-1:0], axi_reg_K6[COEF_DW-1:0], axi_reg_K7[COEF_DW-1:0]} ;
   end else if (CH_QTY == 8) begin : EIGHT_NEI
      assign neighbourhood = {w1_s_axis_tdata_i, w2_s_axis_tdata_i, w3_s_axis_tdata_i, w4_s_axis_tdata_i, w5_s_axis_tdata_i,
                              w6_s_axis_tdata_i, w7_s_axis_tdata_i, w8_s_axis_tdata_i} ;
      assign k_param       = {axi_reg_K1[COEF_DW-1:0], axi_reg_K2[COEF_DW-1:0], axi_reg_K3[COEF_DW-1:0], axi_reg_K4[COEF_DW-1:0],
                              axi_reg_K5[COEF_DW-1:0], axi_reg_K6[COEF_DW-1:0], axi_reg_K7[COEF_DW-1:0], axi_reg_K8[COEF_DW-1:0]} ;
   end else if (CH_QTY == 9) begin : NINE_NEI
      assign neighbourhood = {w1_s_axis_tdata_i, w2_s_axis_tdata_i, w3_s_axis_tdata_i, w4_s_axis_tdata_i, w5_s_axis_tdata_i,
                              w6_s_axis_tdata_i, w7_s_axis_tdata_i, w8_s_axis_tdata_i ,w9_s_axis_tdata_i} ;
      assign k_param       = {axi_reg_K1[COEF_DW-1:0], axi_reg_K2[COEF_DW-1:0], axi_reg_K3[COEF_DW-1:0], axi_reg_K4[COEF_DW-1:0],
                              axi_reg_K5[COEF_DW-1:0], axi_reg_K6[COEF_DW-1:0], axi_reg_K7[COEF_DW-1:0], axi_reg_K8[COEF_DW-1:0],
                              axi_reg_K9[COEF_DW-1:0]} ;
   end else if (CH_QTY == 10) begin : TEN_NEI
      assign neighbourhood = {w1_s_axis_tdata_i, w2_s_axis_tdata_i, w3_s_axis_tdata_i, w4_s_axis_tdata_i, w5_s_axis_tdata_i,
                              w6_s_axis_tdata_i, w7_s_axis_tdata_i, w8_s_axis_tdata_i ,w9_s_axis_tdata_i, w10_s_axis_tdata_i} ;
      assign k_param       = {axi_reg_K1[COEF_DW-1:0], axi_reg_K2[COEF_DW-1:0], axi_reg_K3[COEF_DW-1:0], axi_reg_K4[COEF_DW-1:0],
                              axi_reg_K5[COEF_DW-1:0], axi_reg_K6[COEF_DW-1:0], axi_reg_K7[COEF_DW-1:0], axi_reg_K8[COEF_DW-1:0],
                              axi_reg_K9[COEF_DW-1:0], axi_reg_K10[COEF_DW-1:0]} ;
   end
endgenerate
   

///////////////////////////////////////////////////////////////////////////////
// AXI Registers
///////////////////////////////////////////////////////////////////////////////
axi_slv_xtalk AXI_REG (
   .aclk       ( ps_clk             ), 
   .aresetn    ( ps_aresetn         ), 
   .awaddr     ( s_axi_awaddr[5:0]  ), 
   .awprot     ( s_axi_awprot       ), 
   .awvalid    ( s_axi_awvalid      ), 
   .awready    ( s_axi_awready      ), 
   .wdata      ( s_axi_wdata        ), 
   .wstrb      ( s_axi_wstrb        ), 
   .wvalid     ( s_axi_wvalid       ), 
   .wready     ( s_axi_wready       ), 
   .bresp      ( s_axi_bresp        ), 
   .bvalid     ( s_axi_bvalid       ), 
   .bready     ( s_axi_bready       ), 
   .araddr     ( s_axi_araddr       ), 
   .arprot     ( s_axi_arprot       ), 
   .arvalid    ( s_axi_arvalid      ), 
   .arready    ( s_axi_arready      ), 
   .rdata      ( s_axi_rdata        ), 
   .rresp      ( s_axi_rresp        ), 
   .rvalid     ( s_axi_rvalid       ), 
   .rready     ( s_axi_rready       ), 
// Registers
   .CTRL       (/*axi_reg_CTRL*/    ), // not used
   .CFG        (/*axi_reg_CFG*/     ), // not used
   .K1         (axi_reg_K1          ),
   .K2         (axi_reg_K2          ),
   .K3         (axi_reg_K3          ),
   .K4         (axi_reg_K4          ),
   .K5         (axi_reg_K5          ),
   .K6         (axi_reg_K6          ),
   .K7         (axi_reg_K7          ),
   .K8         (axi_reg_K8          ),
   .K9         (axi_reg_K9          ),
   .K10        (axi_reg_K10         ),
   .XT_STATUS  ('d0 /*axi_reg_XT_STATUS*/  ),   // not used
   .XT_DEBUG   ('d0 /*axi_reg_XT_DEBUG*/   )    // not used
);

///////////////////////////////////////////////////////////////////////////////
// OUT SIGNALS
///////////////////////////////////////////////////////////////////////////////
assign w0_s_axis_tready_o = 1'b1;
assign w1_s_axis_tready_o = 1'b1;
assign w2_s_axis_tready_o = 1'b1;
assign w3_s_axis_tready_o = 1'b1;
assign w4_s_axis_tready_o = 1'b1;
assign w5_s_axis_tready_o = 1'b1;
assign w6_s_axis_tready_o = 1'b1;
assign w7_s_axis_tready_o = 1'b1;
assign w8_s_axis_tready_o = 1'b1;
assign w9_s_axis_tready_o = 1'b1;
assign w10_s_axis_tready_o = 1'b1;


  
endmodule
