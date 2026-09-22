module qick_xtalk #(
   parameter CH_QTY  = 4,  // Number of DAC Inputs
   parameter COEF_DW = 10, // Coefficient Width
   parameter SMP_DW  = 16, // Sample Width
   parameter SMP_CK  = 16  // Samples per Clock
) (
   // Core and AXI CLK & RST
   input  wire                            a_clk_i,
   input  wire                            a_rst_ni,
   // WAVE STREAM DATA
   input  wire signed [SMP_CK*SMP_DW-1:0] self_dt_i,
   input  wire signed [SMP_CK*SMP_DW-1:0] nei_dt_i  [CH_QTY],
   input  wire signed [COEF_DW-1:0]       k_param_i [CH_QTY],
   // DATA OUT   
   output wire signed [SMP_CK*SMP_DW-1:0] wave_o
);

// Intermediate Registers
logic signed [COEF_DW-1:0]       k_param_r [CH_QTY];
reg signed [SMP_DW+COEF_DW-1:0] wave [CH_QTY+1][SMP_CK];
logic signed [SMP_DW+COEF_DW-1:0] kw_mult [CH_QTY][SMP_CK];

reg signed [SMP_DW-1:0]         w_input [CH_QTY][SMP_CK];
reg signed [SMP_DW-1 :0]        nei_2_r [1][SMP_CK];
reg signed [SMP_DW-1 :0]        nei_3_r [2][SMP_CK];
reg signed [SMP_DW-1 :0]        nei_4_r [3][SMP_CK];
reg signed [SMP_DW-1 :0]        nei_5_r [4][SMP_CK];
reg signed [SMP_DW-1 :0]        nei_6_r [5][SMP_CK];
reg signed [SMP_DW-1 :0]        nei_7_r [6][SMP_CK];
reg signed [SMP_DW-1 :0]        nei_8_r [7][SMP_CK];
reg signed [SMP_DW-1 :0]        nei_9_r [8][SMP_CK];
reg signed [SMP_DW-1 :0]        nei_10_r [9][SMP_CK];

// Input Register
genvar ind_dac, ind_nei;
generate
   for (ind_dac = 0; ind_dac < SMP_CK; ind_dac = ind_dac + 1) begin
      always @(posedge a_clk_i) begin
         if (!a_rst_ni)
            wave[0][ind_dac] <= 0;
         else
            wave[0][ind_dac] <= { self_dt_i[SMP_DW*(ind_dac+1)-1], self_dt_i[SMP_DW*ind_dac+:SMP_DW], {COEF_DW-1{1'b0}}};
      end
// TODO >> RESET PIPELINE
      for (ind_nei = 0; ind_nei < CH_QTY; ind_nei = ind_nei + 1) begin
         always @(posedge a_clk_i ) begin
            if      (ind_nei == 0) begin
               w_input[0][ind_dac] <= nei_dt_i[0] [SMP_DW*(ind_dac+1)-1:SMP_DW*ind_dac];
            end else if (ind_nei == 1) begin
               nei_2_r[0]   [ind_dac] <= nei_dt_i[1] [SMP_DW*(ind_dac+1)-1:SMP_DW*ind_dac];
               w_input[1][ind_dac]    <= nei_2_r[0]  [ind_dac];
            end else if (ind_nei == 2) begin
               nei_3_r[0] [ind_dac] <= nei_dt_i[2][SMP_DW*(ind_dac+1)-1:SMP_DW*ind_dac];
               nei_3_r[1] [ind_dac] <= nei_3_r [0] [ind_dac];
               w_input[2] [ind_dac] <= nei_3_r [1] [ind_dac];
            end else if (ind_nei == 3) begin
               nei_4_r[0] [ind_dac] <= nei_dt_i[3][SMP_DW*(ind_dac+1)-1:SMP_DW*ind_dac];
               nei_4_r[1] [ind_dac] <= nei_4_r [0] [ind_dac];
               nei_4_r[2] [ind_dac] <= nei_4_r [1] [ind_dac];
               w_input[3] [ind_dac] <= nei_4_r [2] [ind_dac];
            end else if (ind_nei == 4) begin
               nei_5_r[0] [ind_dac] <= nei_dt_i[4][SMP_DW*(ind_dac+1)-1:SMP_DW*ind_dac];
               nei_5_r[1] [ind_dac] <= nei_5_r [0] [ind_dac];
               nei_5_r[2] [ind_dac] <= nei_5_r [1] [ind_dac];
               nei_5_r[3] [ind_dac] <= nei_5_r [2] [ind_dac];
               w_input[4] [ind_dac] <= nei_5_r [3] [ind_dac];
            end else if (ind_nei == 5) begin
               nei_6_r[0] [ind_dac] <= nei_dt_i[5][SMP_DW*(ind_dac+1)-1:SMP_DW*ind_dac];
               nei_6_r[1] [ind_dac] <= nei_6_r [0] [ind_dac];
               nei_6_r[2] [ind_dac] <= nei_6_r [1] [ind_dac];
               nei_6_r[3] [ind_dac] <= nei_6_r [2] [ind_dac];
               nei_6_r[4] [ind_dac] <= nei_6_r [3] [ind_dac];
               w_input[5] [ind_dac] <= nei_6_r [4] [ind_dac];
            end else if (ind_nei == 6) begin
               nei_7_r[0] [ind_dac] <= nei_dt_i[6][SMP_DW*(ind_dac+1)-1:SMP_DW*ind_dac];
               nei_7_r[1] [ind_dac] <= nei_7_r [0] [ind_dac];
               nei_7_r[2] [ind_dac] <= nei_7_r [1] [ind_dac];
               nei_7_r[3] [ind_dac] <= nei_7_r [2] [ind_dac];
               nei_7_r[4] [ind_dac] <= nei_7_r [3] [ind_dac];
               nei_7_r[5] [ind_dac] <= nei_7_r [4] [ind_dac];
               w_input[6] [ind_dac] <= nei_7_r [5] [ind_dac];
            end else if (ind_nei == 7) begin
               nei_8_r[0] [ind_dac] <= nei_dt_i[7][SMP_DW*(ind_dac+1)-1:SMP_DW*ind_dac];
               nei_8_r[1] [ind_dac] <= nei_8_r [0] [ind_dac];
               nei_8_r[2] [ind_dac] <= nei_8_r [1] [ind_dac];
               nei_8_r[3] [ind_dac] <= nei_8_r [2] [ind_dac];
               nei_8_r[4] [ind_dac] <= nei_8_r [3] [ind_dac];
               nei_8_r[5] [ind_dac] <= nei_8_r [4] [ind_dac];
               nei_8_r[6] [ind_dac] <= nei_8_r [5] [ind_dac];
               w_input[7] [ind_dac] <= nei_8_r [6] [ind_dac];
            end else if (ind_nei == 8) begin
               nei_9_r[0] [ind_dac] <= nei_dt_i[8][SMP_DW*(ind_dac+1)-1:SMP_DW*ind_dac];
               nei_9_r[1] [ind_dac] <= nei_9_r [0] [ind_dac];
               nei_9_r[2] [ind_dac] <= nei_9_r [1] [ind_dac];
               nei_9_r[3] [ind_dac] <= nei_9_r [2] [ind_dac];
               nei_9_r[4] [ind_dac] <= nei_9_r [3] [ind_dac];
               nei_9_r[5] [ind_dac] <= nei_9_r [4] [ind_dac];
               nei_9_r[6] [ind_dac] <= nei_9_r [5] [ind_dac];
               nei_9_r[7] [ind_dac] <= nei_9_r [6] [ind_dac];
               w_input[8] [ind_dac] <= nei_9_r [7] [ind_dac];
            end else if (ind_nei == 9) begin
               nei_10_r[0] [ind_dac] <= nei_dt_i[9][SMP_DW*(ind_dac+1)-1:SMP_DW*ind_dac];
               nei_10_r[1] [ind_dac] <= nei_10_r [0] [ind_dac];
               nei_10_r[2] [ind_dac] <= nei_10_r [1] [ind_dac];
               nei_10_r[3] [ind_dac] <= nei_10_r [2] [ind_dac];
               nei_10_r[4] [ind_dac] <= nei_10_r [3] [ind_dac];
               nei_10_r[5] [ind_dac] <= nei_10_r [4] [ind_dac];
               nei_10_r[6] [ind_dac] <= nei_10_r [5] [ind_dac];
               nei_10_r[7] [ind_dac] <= nei_10_r [6] [ind_dac];
               nei_10_r[8] [ind_dac] <= nei_10_r [7] [ind_dac];
               w_input[9]  [ind_dac] <= nei_10_r [8] [ind_dac];
            end

         end
      end
   end
endgenerate

// Multiplier for Each Channel
generate
   for (ind_nei = 0; ind_nei < CH_QTY; ind_nei = ind_nei + 1) begin
      always @(posedge a_clk_i) begin
         k_param_r[ind_nei]   <= k_param_i[ind_nei];
      end
      for (ind_dac = 0; ind_dac < SMP_CK; ind_dac = ind_dac + 1) begin
         // assign kw_mult[ind_nei][ind_dac] = k_param_i[ind_nei] * w_input[ind_nei][ind_dac];
         always @(posedge a_clk_i) begin
            kw_mult[ind_nei][ind_dac] <= k_param_r[ind_nei] * w_input[ind_nei][ind_dac];
         end
      end
   end
endgenerate

// Pipelined Summation
generate
   for (ind_dac = 0; ind_dac < SMP_CK; ind_dac = ind_dac + 1) begin
      integer stage;
      always @(posedge a_clk_i) begin
         if (!a_rst_ni) begin
            for (stage = 1; stage <= CH_QTY; stage = stage + 1)
               wave[stage][ind_dac] <= 0;
         end else begin
            // wave[1][ind_dac] <= wave[0][ind_dac] + kw_mult[0][ind_dac];
            for (stage = 1; stage <= CH_QTY; stage = stage + 1) begin
               wave[stage][ind_dac] <= wave[stage-1][ind_dac] + kw_mult[stage-1][ind_dac];
            end
         end
      end
   end
endgenerate

// Output Assignment
reg  signed [SMP_DW-1:0] wave_s [SMP_CK];

///// CHECK
generate
   for (ind_dac=0; ind_dac<SMP_CK; ind_dac=ind_dac+1) begin
      always @(posedge a_clk_i) 
         wave_s[ind_dac] <= wave[CH_QTY][ind_dac][SMP_DW+COEF_DW-2:COEF_DW-1];
   end
endgenerate

///// OUT
generate
   for (ind_dac=0; ind_dac<SMP_CK; ind_dac=ind_dac+1) begin
      assign wave_o[SMP_DW*ind_dac+:SMP_DW] = wave_s[ind_dac];
   end
endgenerate


//generate
//   for (ind_dac = 0; ind_dac < SMP_CK; ind_dac = ind_dac + 1) begin
//      assign wave_o[SMP_DW*(ind_dac+1)-1:SMP_DW*ind_dac] = wave[CH_QTY][ind_dac][SMP_DW+COEF_DW-2:COEF_DW];
//   end
//endgenerate

endmodule