"""
Drivers for qick_processor Peripherals.
2024-5-22
"""

import time

import numpy as np
from pynq.buffer import allocate

from qick.ip import SocIP


class QICK_Time_Tagger(SocIP):
    """
    QICK_Time_Tagger class
    """

    bindto = ["Fermi:user:qick_time_tagger:1.0", "QICK:QICK:qick_time_tagger:1.0"]

    def __init__(self, description):
        """
        Constructor method
        """
        super().__init__(description)

        # list of connected ADCs
        self.cfg["adcs"] = []

        # DMA block
        self.dma = None
        self.switch = None
        self.switch_ch = None

        # DMA buffer
        self.buff_rd = None

    def _init_config(self, description):
        self.REGISTERS = {
            "qtt_ctrl": 0,
            "qtt_cfg": 1,
            "dma_cfg": 2,
            "axi_dt1": 3,
            "proc_dt": 5,
            "proc_qty": 6,
            "tag0_qty": 7,
            "tag1_qty": 8,
            "tag2_qty": 9,
            "tag3_qty": 10,
            "smp_qty": 11,
            "arm_qty": 12,
            "thr_inh": 13,
            "qtt_status": 14,
            "qtt_debug": 15,
        }

        # state names
        self.DMA_STATES = ["ST_IDLE", "ST_TX", "ST_LAST", "ST_END"]

        # Parameters
        self.cfg["tag_mem_size"] = 2 ** int(description["parameters"]["TAG_FIFO_AW"])
        self.cfg["arm_mem_size"] = 2 ** int(description["parameters"]["ARM_FIFO_AW"])
        self.cfg["smp_mem_size"] = 2 ** int(description["parameters"]["SMP_FIFO_AW"])

        for param in ["adc_qty", "cmp_inter", "arm_store", "smp_store", "cmp_slope"]:
            self.cfg[param] = int(description["parameters"][param.upper()])
        self.cfg["debug"] = int(description["parameters"]["DEBUG"])

        # dict to map from memory names to IDs and counter names
        self.MEMS = {}
        for i in range(4):
            self.MEMS["TAG%d" % (i)] = (i, "tag%d_qty" % (i), self["tag_mem_size"])
        self.MEMS["ARM"] = (4, "arm_qty", self["arm_mem_size"])
        self.MEMS["SMP"] = (5, "smp_qty", self["smp_mem_size"])

    def _init_firmware(self):
        # Initial Values
        self.qtt_ctrl = 0
        self.qtt_cfg = 0
        self.dma_cfg = 0 + 16 * 1
        self.axi_dt1 = 0

    # Configure this driver with links to its memory and DMA.
    def configure_connections(self, soc):
        self.cfg["f_fabric"] = soc.metadata.get_fclk(self["fullpath"], "adc_clk")

        # which switch_avg port does this buffer drive?
        dma_path, switch_path, self.switch_ch = soc.metadata.trace_dma(
            "forward", self["fullpath"], "m_axis_dma"
        )
        self.dma = soc._get_block(dma_path)
        if switch_path is not None:
            self.switch = soc._get_block(switch_path)

        dma_maxlen = (
            2 ** int(self.dma.description["parameters"]["c_sg_length_width"]) // 4 - 1
        )
        buflen = max(self["tag_mem_size"], self["arm_mem_size"], self["smp_mem_size"])
        buflen = min(buflen, dma_maxlen)
        self.buff_rd = allocate(shape=buflen, dtype=np.int32)

        for iADC in range(self["adc_qty"]):
            try:
                block, port, _ = soc.metadata.trace_back(
                    self["fullpath"],
                    "s%d_axis_adc%d" % (iADC, iADC),
                    ["usp_rf_data_converter"],
                )
                # port names are of the form 'm02_axis' where the block number is always even
                adc = port[1:3]
                self.cfg["adcs"].append(adc)
            except:  # skip disconnected ADC Ports
                self.cfg["adcs"].append(None)

        try:
            trigcfg = {}
            trigcfg["type"], trigcfg["port"], trigcfg["bit"] = (
                soc.metadata.trace_trigger(self["fullpath"], "arm_i")
            )
            self.cfg["trigger"] = trigcfg
        except:
            self.cfg["trigger"] = None

        try:
            block, port, _ = soc.metadata.trace_back(
                self["fullpath"], "qick_peripheral", ["qick_processor"]
            )
            # port names are 'QPeriphA/B'
            self.cfg["peripheral"] = port[-1]
        except:
            self.cfg["peripheral"] = None

        # now that the DMA is connected, let's flush the memories
        self.flush_mems()

    def __str__(self):
        lines = []
        lines.append("---------------------------------------------")
        lines.append(" QICK Time Tagger INFO ")
        lines.append("---------------------------------------------")
        lines.append("Connections:")
        for i, (_, adcdesc) in enumerate(self["adcs"]):
            lines.append(" ADC%d : %s" % (i, adcdesc))
        lines.append("Configuration:")
        for param in [
            "adc_qty",
            "tag_mem_size",
            "cmp_slope",
            "cmp_inter",
            "arm_store",
            "arm_mem_size",
            "smp_store",
            "smp_mem_size",
        ]:
            lines.append(" %-14s: %d" % (param, self.cfg[param]))
        lines.append("----------\n")
        return "\n".join(lines)

    def read_mem(self, mem_sel: str, length=None, warn_full=True):
        """
        Read selected time-tagger memory using DMA.

        Parameters
        ----------
        mem_sel : str
            TAG0, TAG1, TAG2, TAG3, ARM, SMP
        length : int
            Number of values to read.
            If None, read all the values.
        """
        if mem_sel not in self.MEMS:
            raise RuntimeError(
                "Source Memory error. Options are TAG0, TAG1, TAG2, TAG3, ARM, SMP current Value : %s"
                % (mem_sel)
            )
        mem_id, mem_counter, mem_size = self.MEMS[mem_sel]

        if length is None:
            length = getattr(self, mem_counter)
            if warn_full and length >= mem_size - 1:
                self.logger.warning(
                    "Memory %s is at its max capacity of %d words. Some data was probably lost."
                    % (mem_sel, mem_size)
                )
        data = np.zeros(length, dtype=np.int32)

        already_read = 0
        while length > already_read:
            thislen = min(length - already_read, len(self.buff_rd))
            self.logger.info("reading %d words from %s" % (thislen, mem_sel))
            # Configure FIFO Read.
            self.dma_cfg = mem_id + 16 * thislen

            # Route switch to channel.
            if self.switch is not None:
                self.switch.sel(slv=self.switch_ch)
            # Start DMA Transfer
            self.qtt_ctrl = 32
            # DMA data.
            self.dma.recvchannel.transfer(self.buff_rd, nbytes=int(thislen * 4))
            self.dma.recvchannel.wait()
            # truncate, copy
            np.copyto(
                data[already_read : already_read + thislen], self.buff_rd[:thislen]
            )
            already_read += thislen

        return data

    def flush_mems(self, verbose=False):
        """Flush the time-tagger memories by reading them.
        This does not clear the tag queue to the tProc, only the memories readable by DMA.
        """
        for memname in self.MEMS:
            data = self.read_mem(memname, warn_full=False)

    def set_config(self, filt, slope, interp, wr_smp, invert):
        """
        QICK_Time_Tagger Configuration
        filt   : Filter ADC Inputs  > 0:No , 1:Yes
        slope  : Compare with Slope > 0:No , 1:Yes
        inter  : Number of bits for Interpolation (0 to 7)
        wr_smp : Number of group of 8 samples to store (1 to 32)
        invert : Invert Input       > 0:No , 1:Yes
        """
        # Check for Parameters
        if slope > self.cfg["cmp_slope"]:
            raise ValueError("Slope Comparator not implemented")
        if interp > self.cfg["cmp_inter"]:
            raise ValueError("Interpolation bits max Value ", self.cfg["cmp_inter"])
        if self.cfg["smp_store"] == 1:
            if wr_smp < 1 or wr_smp > 32:
                raise ValueError("wr_smp must be in range [1, 32]")
            if wr_smp == 32:
                wr_smp = 0
        self.qtt_cfg = (
            filt + (slope << 1) + (interp << 2) + (wr_smp << 5) + (invert << 10)
        )

    def get_config(self, print_cfg=False):
        cfg = self.qtt_cfg
        filt = cfg & 1
        slope = (cfg >> 1) & 1
        interp = (cfg >> 2) & 0x7
        wr_smp = (cfg >> 5) & 0x1F
        if wr_smp == 0:
            wr_smp = 32
        invert = (cfg >> 10) & 1
        if print_cfg:
            print("--- AXI Time Tagger CONFIG")
            print(" FILTER           : " + str(filt))
            print(" SLOPE            : " + str(slope))
            print(" INTERPOLATION    : " + str(interp))
            print(" WRITE SAMPLE QTY : " + str(wr_smp))
            print(" INVERT INPUT     : " + str(invert))
        return filt, slope, interp, wr_smp, invert

    def disarm(self):
        self.qtt_ctrl = 1 + 2 * 0

    def arm(self):
        self.qtt_ctrl = 1 + 2 * 1

    def pop_dt(self):
        self.qtt_ctrl = 1 + 2 * 2

    def set_threshold(self, value):
        valid = [-1 * 2**15, 2**15 - 1]
        if value < valid[0] or value > valid[1]:
            raise ValueError("Threshold must be in the range %s ADU." % (valid))
        self.axi_dt1 = value
        self.qtt_ctrl = 1 + 2 * 4

    def set_dead_time(self, value):
        valid = [5, 255]
        if value < valid[0] or value > valid[1]:
            raise ValueError("Dead time must be in the range %s clocks." % (valid))
        self.axi_dt1 = value
        self.qtt_ctrl = 1 + 2 * 5

    def reset(self):
        """Flush the time-tagger memories and reset the counters to 0.
        This flushes both the memories read by DMA and those read by the tProc.
        The configuration is not changed.

        This functionality is not reliable in current firmware.
        You should use flush_mems() instead.
        """
        self.qtt_ctrl = 1 + 2 * 7

    def info(self):
        print(self)

    def print_axi_regs(self):
        print("---------------------------------------------")
        print("--- AXI Registers")
        for xreg in self.REGISTERS.keys():
            reg_num = getattr(self, xreg)
            reg_bin = "{:039_b}".format(reg_num)
            print(f"{xreg:>10}", f"{reg_num:>11}" + " - " + f"{reg_bin:>33}")

    def print_status(self):
        print("---------------------------------------------")

    def print_debug(self):
        print("---------------------------------------------")
        print("--- AXI Time Tagger DEBUG")
        status_num = self.qtt_status
        status_bin = "{:032b}".format(status_num)
        trig_st = int(status_bin[24:32], 2)
        dma_st = int(status_bin[22:24], 2)
        print(" ST_TRIG  : " + str(trig_st))
        print(" ST_DMA   : " + str(dma_st))
        debug_num = self.qtt_debug
        debug_bin = "{:032b}".format(debug_num)
        dma_st = int(debug_bin[0:1], 2)
        len_cnt = int(debug_bin[10:16], 2)
        frd_cnt = int(debug_bin[6:10], 2)
        vld_cnt = int(debug_bin[2:6], 2)
        print(" -- FIFO --")
        print(" DMA_FULL   : " + str(debug_bin[31]))
        print(" DMA_EMPTY  : " + str(debug_bin[30]))
        print(" PROC_FULL  : " + str(debug_bin[29]))
        print(" PROC_EMPTY : " + str(debug_bin[28]))
        print(" -- DMA --")
        print(" DMA_ST     : " + str(dma_st) + " - " + self.DMA_STATES[dma_st])
        print(" DMA_REQ    : " + str(debug_bin[25]))
        print(" DMA_ACK    : " + str(debug_bin[24]))
        print(" POP_REQ    : " + str(debug_bin[23]))
        print(" POP_ACK    : " + str(debug_bin[22]))
        print(" FIFO_RD  : " + str(debug_bin[21]))
        print(" DT_TX    : " + str(debug_bin[20]))
        print(" DT_W     : " + str(debug_bin[19]))
        print(" DT_VLD   : " + str(debug_bin[18]))
        print(" DT_BF    : " + str(debug_bin[17]))
        print(" LP_CNT_EN: " + str(debug_bin[16]))
        print(" LEN_CNT    : " + str(len_cnt))
        print(" FIFO_RD_CNT: " + str(frd_cnt))
        print(" VLD_CNT    : " + str(vld_cnt))
        th_num = self.thr_inh
        th_bin = "{:032b}".format(th_num)
        thr = int(th_bin[16:32], 2)
        inh = int(th_bin[8:16], 2)
        cmd_cnt = int(th_bin[0:8], 2)
        print(" THRESHOLD  : " + str(thr))
        print(" INHIBIT    : " + str(inh))
        print(" CMD_CNT    : " + str(cmd_cnt))


class QICK_Com(SocIP):
    """
    QICK_Comm class

    ####################
    QICK COM xREG
    ####################
    QCOM_CTRL        Write / Read 32-Bits
    QCOM_CFG         Write / Read 32-Bits
    AXI_DT1          Write / Read 32-Bits
    QCOM_FLAG        Read Only    32-Bits
    QCOM_DT1         Read Only    32-Bits
    QCOM_DT2         Read Only    32-Bits
    QCOM_STATUS      Read Only    32-Bits
    QCOM_TX_DT       Read Only    32-Bits
    QCOM_RX_DT       Read Only    32-Bits
    QCOM_DEBUG       Read Only    32-Bits
    """

    bindto = ["Fermi:user:qick_com:1.0", "QICK:QICK:qick_com:1.0"]

    def _init_config(self, description):
        self.REGISTERS = {
            "qcom_ctrl": 0,
            "qcom_cfg": 1,
            "axi_dt1": 2,
            "flag": 7,
            "dt1": 8,
            "dt2": 9,
            "status": 12,
            "tx_dt": 13,
            "rx_dt": 14,
            "debug": 15,
        }

    def _init_firmware(self):
        # Initial Values
        self.qcom_ctrl = 0
        self.qcom_cfg = 10
        self.raxi_dt1 = 0

    def __str__(self):
        lines = []
        lines.append("---------------------------------------------")
        lines.append(" QICK Com INFO ")
        lines.append("---------------------------------------------")
        lines.append("----------\n")
        return "\n".join(lines)

    def clr_flg(self):
        self.qcom_ctrl = 1

    def send_byte(self, data, dst):
        self.axi_dt1 = data
        if dst == 1:
            self.qcom_ctrl = 1 + 2 * 2
        elif dst == 2:
            self.qcom_ctrl = 1 + 2 * 3
        else:
            raise RuntimeError(
                "Destination Register error should be 1 or 2 current Value : %d" % (dst)
            )

    def send_half_word(self, data, dst):
        self.axi_dt1 = data
        if dst == 1:
            self.qcom_ctrl = 1 + 2 * 4
        elif dst == 2:
            self.qcom_ctrl = 1 + 2 * 5
        else:
            raise RuntimeError(
                "Destination Register error should be 1 or 2 current Value : %d" % (dst)
            )

    def send_word(self, data, dst):
        self.axi_dt1 = data
        if dst == 1:
            self.qcom_ctrl = 1 + 2 * 6
        elif dst == 2:
            self.qcom_ctrl = 1 + 2 * 7
        else:
            raise RuntimeError(
                "Destination Register error should be 1 or 2 current Value : %d" % (dst)
            )

    def set_flg(self):
        self.qcom_ctrl = 1 + 2 * 8

    def print_dt(self):
        print("FLAG:{}   DT1:{}   DT2:{}   ".format(self.flag, self.dt1, self.dt2))

    def print_axi_regs(self):
        print("---------------------------------------------")
        print("--- AXI Registers")
        for xreg in self.REGISTERS.keys():
            reg_num = getattr(self, xreg)
            reg_bin = "{:039_b}".format(reg_num)
            print(f"{xreg:>10}", f"{reg_num:>11}" + " - " + f"{reg_bin:>33}")

    def print_status(self):
        debug_num = self.status
        debug_bin = "{:032b}".format(debug_num)
        print("---------------------------------------------")
        print("--- AXI TNET Register RX_STATUS")
        print(" qcom_rx_st   : " + debug_bin[30:32])
        print(" rx_header    : " + debug_bin[27:30])
        print(" reg_sel      : " + debug_bin[25:27])
        print(" reg_wr_size  : " + debug_bin[23:25])
        print(" qcom_tx_st   : " + debug_bin[20:23])
        print(" tx_header    : " + debug_bin[17:20])

    def print_debug(self):
        debug_num = self.debug
        debug_bin = "{:032b}".format(debug_num)
        print("---------------------------------------------")
        print("--- AXI TNET Register RX_STATUS")
        print(" qcom_rx_st   : " + debug_bin[30:32])
        print(" rx_header    : " + debug_bin[27:30])
        print(" reg_sel      : " + debug_bin[25:27])
        print(" reg_wr_size  : " + debug_bin[23:25])
        print(" qcom_tx_st   : " + debug_bin[20:23])
        print(" tx_header    : " + debug_bin[17:20])


class QICK_Net(SocIP):
    """
    QICK_Net class

    ####################
    AXIS T_CORE xREG
    ####################
    CORE_CTRL        Write / Read 32-Bits
    CORE_CFG         Write / Read 32-Bits
    RAXI_DT1         Write / Read 32-Bits
    RAXI_DT2         Write / Read 32-Bits
    CORE_R_DT1       Read Only    32-Bits
    CORE_R_DT2       Read Only    32-Bits
    PORT_LSW         Read Only    32-Bits
    PORT_MSW         Read Only    32-Bits
    RAND             Read Only    32-Bits
    CORE_W_DT1       Read Only    32-Bits
    CORE_W_DT2       Read Only    32-Bits
    CORE_STATUS      Read Only    32-Bits
    CORE_DEBUG       Read Only    32-Bits

    :param mem: memory address
    :type mem: int
    :param axi_dma: axi_dma address
    :type axi_dma: int
    """

    bindto = ["Fermi:user:qick_network:1.0", "QICK:QICK:qick_network:1.0"]

    main_list = [
        "M_NOT_READY",
        "M_IDLE",
        "M_LOC_CMD",
        "M_NET_CMD",
        "M_WRESP",
        "M_WACK",
        "M_NET_RESP",
        "M_NET_ANSW",
        "M_CMD_EXEC",
        "M_ERROR",
    ]
    task_list = [
        "T_NOT_READY",
        "T_IDLE",
        "T_LOC_CMD",
        "T_LOC_WSYNC",
        "T_LOC_SEND",
        "T_LOC_WnREQ",
        "T_NET_CMD",
        "T_NET_SEND",
    ]
    cmd_list = [
        "NOT_READY",
        "IDLE",
        "L_GNET",
        "L_SNET",
        "L_SYNC1",
        "L_UPDT_OFF",
        "L_SET_DT",
        "L_GET_DT",
        "L_RST_TIME",
        "L_START",
        "L_STOP",
        "N_GNET_P",
        "N_SNET_P",
        "N_SYNC1_P",
        "N_UPDT_OFF_P",
        "N_SET_DT_P",
        "N_GET_DT_P",
        "N_RST_TIME_P",
        "N_START_P",
        "N_STOP_P",
        "N_GNET_R",
        "N_SNET_R",
        "N_SYNC1_R",
        "N_UPDT_OFF_R",
        "N_DT_R",
        "N_TPROC_R",
        "N_GET_DT_A",
        "WAIT_TX_ACK",
        "WAIT_TX_nACK",
        "WAIT_CMD_nACK",
        "STATE",
        "ST_ERROR",
    ]
    link_list = [
        "NOT_READY",
        "IDLE",
        "RX",
        "PROCESS",
        "PROPAGATE",
        "TX_H",
        "TX_D",
        "WAIT_nREQ",
    ]
    ctrl_list = [
        "X",
        "IDLE",
        "CHECK_TIME1",
        "CHECK_TIME2",
        "WAIT_TIME",
        "WAIT_SYNC",
        "EXECUTE",
        "ERROR",
    ]

    def _init_config(self, description):
        self.REGISTERS = {
            "tnet_ctrl": 0,
            "tnet_cfg": 1,
            "tnet_addr": 2,
            "tnet_len": 3,
            "raxi_dt1": 4,
            "raxi_dt2": 5,
            "raxi_dt3": 6,
            "nn_id": 7,
            "rtd": 8,
            "tnet_w_dt1": 9,
            "tnet_w_dt2": 10,
            "rx_status": 11,
            "tx_status": 12,
            "status": 13,
            "debug": 14,
            "hist": 15,
        }

    def _init_firmware(self):
        # Initial Values
        self.tnet_ctrl = 0
        self.tnet_cfg = 0
        self.tnet_addr = 0
        self.mem_len = 100
        self.tnet_len = 0
        self.raxi_dt1 = 0
        self.raxi_dt2 = 0
        self.raxi_dt3 = 0

    # Configure this driver with links to its memory and DMA.
    def configure(self, mem, axi_dma):
        # Program memory.
        self.mem = mem
        # dma
        self.dma = axi_dma

    def clear_cond(self):
        self.logger.info("RESET")
        self.tproc_ctrl = 2048

    def print_axi_regs(self):
        print("---------------------------------------------")
        print("--- AXI Registers")
        for xreg in self.REGISTERS.keys():
            print(f"{xreg:>15}", getattr(self, xreg))

    def print_status(self):
        rx_status_num = self.rx_status
        rx_status_bin = "{:032b}".format(rx_status_num)
        tx_status_num = self.tx_status
        tx_status_bin = "{:032b}".format(tx_status_num)
        status_num = self.status
        status_bin = "{:032b}".format(status_num)
        print("---------------------------------------------")
        print("--- AXI TNET Register RX_STATUS")
        print(" RX_CNT    : " + rx_status_bin[26:32])
        print(" RX_CMD    : " + rx_status_bin[18:23])
        print(" RX_FLAGS  : " + rx_status_bin[23:26])
        print(" RX_DST    : " + rx_status_bin[14:18])
        print(" RX_SRC    : " + rx_status_bin[10:14])
        print(" RX_STEP   : " + rx_status_bin[4:10])
        print(" RX_H_DT   : " + rx_status_bin[0:4])

        print("--- AXI TNET Register TX_STATUS")
        print(" TX_CNT    : " + tx_status_bin[26:32])
        print(" TX_CMD    : " + tx_status_bin[18:23])
        print(" TX_FLAGS  : " + tx_status_bin[23:26])
        print(" TX_DST    : " + tx_status_bin[14:18])
        print(" TX_SRC    : " + tx_status_bin[10:14])
        print(" TX_STEP   : " + tx_status_bin[4:10])
        print(" TX_H_DT   : " + tx_status_bin[0:4])

        print("--- AXI TNET Register TNET_STATUS")
        print(" MMC_LOCKED   : " + status_bin[31])
        print(" GT_PLL_LOCK  : " + status_bin[30])
        print(" CH_A_RX_UP   : " + status_bin[29])
        print(" CH_A_TX_UP   : " + status_bin[28])
        print(" CH_B_RX_UP   : " + status_bin[27])
        print(" CH_B_TX_UP   : " + status_bin[26])
        print(" AURORA_RDY   : " + status_bin[25])
        print(" TX_REQ       : " + status_bin[24])
        print(" TX_ACK       : " + status_bin[23])
        print(" ERROR_ID     : " + status_bin[19:23])
        print("--------------------------------")
        print(" READY        : " + status_bin[15])
        print("--------------------------------")
        print(" GET_NET      : " + status_bin[14])
        print(" SET_NET      : " + status_bin[13])
        print(" SYNC1_NET    : " + status_bin[12])
        print(" SYNC2_NET    : " + status_bin[11])
        print(" GET_OFF      : " + status_bin[8])
        print(" UPDT_OFF     : " + status_bin[7])
        print(" SET_DT       : " + status_bin[6])
        print(" GET_DT       : " + status_bin[5])
        print(" RST_TIME     : " + status_bin[4])
        print(" START_CORE   : " + status_bin[3])
        print(" STOP_CORE    : " + status_bin[2])
        print(" GET_COND     : " + status_bin[1])
        print(" SET_COND     : " + status_bin[0])

    def print_debug(self):
        print("---------------------------------------------")

        print("--- AXI TNET Register DEBUG_0")
        self.tnet_cfg = 0
        debug_num = self.debug
        debug_bin = "{:032b}".format(debug_num)
        main_st = int(debug_bin[28:32], 2)
        task_st = int(debug_bin[24:28], 2)
        cmd_st = int(debug_bin[19:24], 2)
        ctrl_st = int(debug_bin[16:19], 2)
        link_st = int(debug_bin[13:16], 2)
        print(" MAIN_ST    : " + str(main_st) + " - " + self.main_list[main_st])
        print(" TASK_ST    : " + str(task_st) + " - " + self.task_list[task_st])
        print(" CMD_ST     : " + str(cmd_st) + " - " + self.cmd_list[cmd_st])
        print(" CTRL_ST    : " + str(ctrl_st) + " - " + self.ctrl_list[ctrl_st])
        print(" LINK_ST    : " + str(link_st) + " - " + self.link_list[link_st])

        print("---------------------------------------------")
        print("--- AXI TNET Register DEBUG_1")
        self.tnet_cfg = 1
        debug_num = self.debug
        debug_bin = "{:032b}".format(debug_num)
        print(" PY_CMD_CNT    : " + debug_bin[29:32])
        print(" tProc_CMD_CNT : " + debug_bin[26:29])
        print(" NET_CMD_CNT   : " + debug_bin[23:26])
        print(" ERROR_CNT     : " + debug_bin[15:23])
        print(" READY_CNT     : " + debug_bin[7:15])

        print("--- AXI TNET Register DEBUG_2")
        self.tnet_cfg = 2
        debug_num = self.debug
        debug_bin = "{:032b}".format(debug_num)
        print(" PR_CNT    : " + debug_bin[28:32])
        print(" PR_CMD    : " + debug_bin[23:28])
        print(" PR_SRC    : " + debug_bin[13:23])
        print(" PR_DST    : " + debug_bin[3:13])
        print(" net_dst_ones: " + debug_bin[2])
        print(" net_dst_own : " + debug_bin[1])
        print(" net_src_own : " + debug_bin[0])

        print("--- AXI TNET Register DEBUG_3")
        self.tnet_cfg = 3
        debug_num = self.debug
        debug_bin = "{:032b}".format(debug_num)
        print(" EX_CNT    : " + debug_bin[28:32])
        print(" EX_CMD    : " + debug_bin[23:28])
        print(" EX_SRC    : " + debug_bin[13:23])
        print(" EX_DST    : " + debug_bin[3:13])
        print(" net_dst_ones: " + debug_bin[2])
        print(" net_dst_own : " + debug_bin[1])
        print(" net_src_own : " + debug_bin[0])

        print("--- AXI TNET Register DEBUG_4")
        self.tnet_cfg = 4
        debug_num = self.debug
        debug_bin = "{:032b}".format(debug_num)
        print(" ERR_1    : " + debug_bin[28:32])
        print(" ERR_2    : " + debug_bin[24:28])
        print(" ERR_3    : " + debug_bin[20:24])
        print(" ERR_4    : " + debug_bin[16:20])
        print(" ERR_5    : " + debug_bin[12:16])
        print(" ERR_6    : " + debug_bin[8:12])
        print(" ERR_7    : " + debug_bin[4:8])
        print(" ERR_8    : " + debug_bin[0:4])

        print("--- AXI TNET Register HIST")
        hist_num = self.hist
        hist_bin = "{:032b}".format(hist_num)
        cmd1_st = int(hist_bin[27:32], 2)
        cmd2_st = int(hist_bin[22:27], 2)
        cmd3_st = int(hist_bin[17:22], 2)
        cmd4_st = int(hist_bin[12:17], 2)
        cmd5_st = int(hist_bin[7:12], 2)

        self.tnet_cfg = 5
        debug_num = self.debug
        debug_bin = "{:032b}".format(debug_num)
        cmd6_st = int(debug_bin[27:32], 2)
        cmd7_st = int(debug_bin[22:27], 2)
        cmd8_st = int(debug_bin[17:22], 2)
        cmd9_st = int(debug_bin[12:17], 2)
        cmd10_st = int(debug_bin[7:12], 2)
        self.tnet_cfg = 6
        debug_num = self.debug
        debug_bin = "{:032b}".format(debug_num)
        cmd11_st = int(debug_bin[27:32], 2)
        cmd12_st = int(debug_bin[22:27], 2)
        cmd13_st = int(debug_bin[17:22], 2)
        cmd14_st = int(debug_bin[12:17], 2)
        cmd15_st = int(debug_bin[7:12], 2)
        self.tnet_cfg = 7
        debug_num = self.debug
        debug_bin = "{:032b}".format(debug_num)
        cmd16_st = int(debug_bin[27:32], 2)
        cmd17_st = int(debug_bin[22:27], 2)
        cmd18_st = int(debug_bin[17:22], 2)
        cmd19_st = int(debug_bin[12:17], 2)
        cmd20_st = int(debug_bin[7:12], 2)

        print(" T1   : " + str(cmd1_st) + " - " + self.cmd_list[cmd1_st])
        print(" T2   : " + str(cmd2_st) + " - " + self.cmd_list[cmd2_st])
        print(" T3   : " + str(cmd3_st) + " - " + self.cmd_list[cmd3_st])
        print(" T4   : " + str(cmd4_st) + " - " + self.cmd_list[cmd4_st])
        print(" T5   : " + str(cmd5_st) + " - " + self.cmd_list[cmd5_st])
        print(" T6   : " + str(cmd6_st) + " - " + self.cmd_list[cmd6_st])
        print(" T7   : " + str(cmd7_st) + " - " + self.cmd_list[cmd7_st])
        print(" T8   : " + str(cmd8_st) + " - " + self.cmd_list[cmd8_st])
        print(" T9   : " + str(cmd9_st) + " - " + self.cmd_list[cmd9_st])
        print(" T10  : " + str(cmd10_st) + " - " + self.cmd_list[cmd10_st])
        print(" T11  : " + str(cmd11_st) + " - " + self.cmd_list[cmd11_st])
        print(" T12  : " + str(cmd12_st) + " - " + self.cmd_list[cmd12_st])
        print(" T13  : " + str(cmd13_st) + " - " + self.cmd_list[cmd13_st])
        print(" T14  : " + str(cmd14_st) + " - " + self.cmd_list[cmd14_st])
        print(" T15  : " + str(cmd15_st) + " - " + self.cmd_list[cmd15_st])
        print(" T16  : " + str(cmd16_st) + " - " + self.cmd_list[cmd16_st])
        print(" T17  : " + str(cmd17_st) + " - " + self.cmd_list[cmd17_st])
        print(" T18  : " + str(cmd18_st) + " - " + self.cmd_list[cmd18_st])
        print(" T19  : " + str(cmd19_st) + " - " + self.cmd_list[cmd19_st])
        print(" T20  : " + str(cmd19_st) + " - " + self.cmd_list[cmd20_st])

    def get_sth(self):
        debug_num = self.tnet_debug
        debug_bin = "{:032b}".format(debug_num)
        task_st = int(debug_bin[19:23], 2)
        ver_num = self.version
        ver_bin = "{:032b}".format(ver_num)
        cmd0_st = int(ver_bin[25:30], 2)
        cmd1_st = int(ver_bin[20:25], 2)
        cmd2_st = int(ver_bin[15:20], 2)
        cmd3_st = int(ver_bin[10:15], 2)
        cmd4_st = int(ver_bin[5:10], 2)
        cmd5_st = int(ver_bin[0:5], 2)
        print("---------------------------------------------")
        print(" AURORA_CNT  : " + debug_bin[27:32])
        print(" AURORA_OP   : " + debug_bin[23:27])
        print(" TASK_ST     : " + str(task_st) + " - " + task_list[task_st])
        print(" MAIN_ST     : " + debug_bin[15:19])
        print(" T0   : " + str(cmd0_st) + " - " + cmd_list[cmd0_st])
        print(" T1   : " + str(cmd1_st) + " - " + cmd_list[cmd1_st])
        print(" T2   : " + str(cmd2_st) + " - " + cmd_list[cmd2_st])
        print(" T3   : " + str(cmd3_st) + " - " + cmd_list[cmd3_st])
        print(" T4   : " + str(cmd4_st) + " - " + cmd_list[cmd4_st])
        print(" T5   : " + str(cmd5_st) + " - " + cmd_list[cmd5_st])


class QICK_XTalk_Compensation(SocIP):
    """
    QICK_XTalk_Compensation class
    ####################
    QICK XTALK xREG
    ####################
    CTRL           Write / Read 4-Bits
    CFG            Write / Read 4-Bits
    K1             Write / Read 18-Bits
    K2             Write / Read 18-Bits
    K3             Write / Read 18-Bits
    K4             Write / Read 18-Bits
    K5             Write / Read 18-Bits
    K6             Write / Read 18-Bits
    K7             Write / Read 18-Bits
    K8             Write / Read 18-Bits
    K9             Write / Read 18-Bits
    K10            Write / Read 18-Bits
    XCOM_STATUS    Read Only    32-Bits
    XCOM_DEBUG     Read Only    32-Bits
    """

    bindto = ["Fermi:user:qick_xtalk:1.0", "QICK:QICK:qick_xtalk:1.0"]

    def _init_config(self, description):
        self.REGISTERS = {
            "xtalk_ctrl": 0,
            "xtalk_cfg": 1,
            "k1": 2,
            "k2": 3,
            "k3": 4,
            "k4": 5,
            "k5": 6,
            "k6": 7,
            "k7": 8,
            "k8": 9,
            "k9": 10,
            "k10": 11,
            "status": 14,
            "debug": 15,
        }

        # Parameters
        self.cfg["channels"] = int(description["parameters"]["CH_QTY"])
        self.cfg["coeff_dw"] = int(description["parameters"]["COEF_DW"])

    def _init_firmware(self):
        # Initial Values
        self.xtalk_ctrl = 0
        self.xtalk_cfg = 0
        self.k1 = 0
        self.k2 = 0
        self.k3 = 0
        self.k4 = 0
        self.k5 = 0
        self.k6 = 0
        self.k7 = 0
        self.k8 = 0
        self.k9 = 0
        self.k10 = 0

    def __str__(self):
        lines = []
        lines.append("---------------------------------------------")
        lines.append(" QICK XTalk INFO ")
        lines.append("---------------------------------------------")
        lines.append("----------\n")
        return "\n".join(lines)

    def bin_to_dec(self, binary, dw):
        fraction_multiplication = pow(2, (dw - 1))
        value = int(binary, 2)
        # Adjust for two's complement if necessary
        if value >= (1 << (dw - 1)):
            value -= 1 << dw
        value = value / fraction_multiplication
        return value

    def bin_to_dec_pad(self, binary, dw):
        fraction_multiplication = pow(2, (dw - 1))
        value = int(binary, 2)
        # Adjust for two's complement if necessary
        if value >= (1 << (dw - 1)):
            value = int(binary[32 - dw :], 2) - (1 << dw)
        value = value / fraction_multiplication
        return value

    def dec_to_bin(self, value, dw):
        fraction_multiplication = pow(2, (dw - 1))
        if value < 0:
            int_num = (1 << dw) + value
            int_num = int(int_num * fraction_multiplication)
        else:
            int_num = int(value * fraction_multiplication)
        # Calculates the binary representation with fixed width
        bin_num = format(int_num & ((1 << dw) - 1), f"0{dw}b")
        if bin_num[0] == "1":  # Negative number
            bin_pad = "1" * (32 - dw) + bin_num
        else:  # Positive number
            bin_pad = "0" * (32 - dw) + bin_num
        frac_num = self.bin_to_dec(bin_num, dw)
        print(
            "K parameter wanted:",
            "{:.8f}".format(value),
            "Stored :",
            "{:.8f}".format(frac_num),
        )
        return bin_pad

    def set_k1(self, dt):
        if (dt > 1) or (dt < -1):
            raise RuntimeError(
                "K parameter should be less than 1 (1, -1) current Value : %d" % (dt)
            )
        else:
            dw = self.cfg["coeff_dw"]
            dt_int_bin = self.dec_to_bin(dt, dw)
            dt_int_32 = int(dt_int_bin, 2)
            self.k1 = dt_int_32

    def set_k2(self, dt):
        if (dt > 1) or (dt < -1):
            raise RuntimeError(
                "K parameter should be less than 1 (1, -1) current Value : %d" % (dt)
            )
        else:
            dw = self.cfg["coeff_dw"]
            dt_int_bin = self.dec_to_bin(dt, dw)
            dt_int_32 = int(dt_int_bin, 2)
            self.k2 = dt_int_32

    def set_k3(self, dt):
        if (dt > 1) or (dt < -1):
            raise RuntimeError(
                "K parameter should be less than 1 (1, -1) current Value : %d" % (dt)
            )
        else:
            dw = self.cfg["coeff_dw"]
            dt_int_bin = self.dec_to_bin(dt, dw)
            dt_int_32 = int(dt_int_bin, 2)
            self.k3 = dt_int_32

    def set_k4(self, dt):
        if (dt > 1) or (dt < -1):
            raise RuntimeError(
                "K parameter should be less than 1 (1, -1) current Value : %d" % (dt)
            )
        else:
            dw = self.cfg["coeff_dw"]
            dt_int_bin = self.dec_to_bin(dt, dw)
            dt_int_32 = int(dt_int_bin, 2)
            self.k4 = dt_int_32

    def set_k5(self, dt):
        if (dt > 1) or (dt < -1):
            raise RuntimeError(
                "K parameter should be less than 1 (1, -1) current Value : %d" % (dt)
            )
        else:
            dw = self.cfg["coeff_dw"]
            dt_int_bin = self.dec_to_bin(dt, dw)
            dt_int_32 = int(dt_int_bin, 2)
            self.k5 = dt_int_32

    def set_k6(self, dt):
        if (dt > 1) or (dt < -1):
            raise RuntimeError(
                "K parameter should be less than 1 (1, -1) current Value : %d" % (dt)
            )
        else:
            dw = self.cfg["coeff_dw"]
            dt_int_bin = self.dec_to_bin(dt, dw)
            dt_int_32 = int(dt_int_bin, 2)
            self.k6 = dt_int_32

    def set_k7(self, dt):
        if (dt > 1) or (dt < -1):
            raise RuntimeError(
                "K parameter should be less than 1 (1, -1) current Value : %d" % (dt)
            )
        else:
            dw = self.cfg["coeff_dw"]
            dt_int_bin = self.dec_to_bin(dt, dw)
            dt_int_32 = int(dt_int_bin, 2)
            self.k7 = dt_int_32

    def set_k8(self, dt):
        if (dt > 1) or (dt < -1):
            raise RuntimeError(
                "K parameter should be less than 1 (1, -1) current Value : %d" % (dt)
            )
        else:
            dw = self.cfg["coeff_dw"]
            dt_int_bin = self.dec_to_bin(dt, dw)
            dt_int_32 = int(dt_int_bin, 2)
            self.k8 = dt_int_32

    def set_k9(self, dt):
        if (dt > 1) or (dt < -1):
            raise RuntimeError(
                "K parameter should be less than 1 (1, -1) current Value : %d" % (dt)
            )
        else:
            dw = self.cfg["coeff_dw"]
            dt_int_bin = self.dec_to_bin(dt, dw)
            dt_int_32 = int(dt_int_bin, 2)
            self.k9 = dt_int_32

    def set_k10(self, dt):
        if (dt > 1) or (dt < -1):
            raise RuntimeError(
                "K parameter should be less than 1 (1, -1) current Value : %d" % (dt)
            )
        else:
            dw = self.cfg["coeff_dw"]
            dt_int_bin = self.dec_to_bin(dt, dw)
            dt_int_32 = int(dt_int_bin, 2)
            self.k10 = dt_int_32

    def set_k(self, dt, k_val):
        if (dt > 1) or (dt < -1):
            raise RuntimeError(
                "K parameter should be less than 1 (1, -1) current Value : %d" % (dt)
            )
        else:
            dw = self.cfg["coeff_dw"]
            dt_int_bin = self.dec_to_bin(dt, dw)
            dt_int_32 = int(dt_int_bin, 2)
            setattr(self, k_val, dt_int_32)

    def axi_regs_dict(self):
        reg_dict = {}
        dw = self.cfg["coeff_dw"]
        for xreg in self.REGISTERS.keys():
            xreg_dict = {}
            reg_num = getattr(self, xreg)
            xreg_dict["reg_num"] = reg_num
            regbin = format(reg_num, f"0{dw}b")
            dec = self.bin_to_dec_pad(regbin, dw)
            xreg_dict["reg_dec"] = dec
            xreg_dict["reg_bin"] = "{:039_b}".format(reg_num)
            reg_dict[xreg] = xreg_dict
        return reg_dict

    def print_axi_regs(self):
        print("---------------------------------------------")
        print("--- AXI Registers")
        for xreg in self.REGISTERS.keys():
            reg_num = getattr(self, xreg)
            reg_bin = "{:039_b}".format(reg_num)
            print(f"{xreg:>10}", f"{reg_num:>11}" + " - " + f"{reg_bin:>33}")

    def print_status(self):
        status_num = self.status
        status_bin = "{:032b}".format(status_num)
        print("---------------------------------------------")
        print("--- AXI XTalk Register STATUS")
        print(" status_bin     : " + status_bin)

    def print_debug(self):
        debug_num = self.debug
        debug_bin = "{:032b}".format(debug_num)
        print("---------------------------------------------")
        print("--- AXI XTalk DEBUG")
        print(" debug_bin : " + debug_bin)


class AxiPvpGen(SocIP):
    """
    Control the axi_pvp_gen_v7_x IP
    This version binds to the newest ip block in the firmware folder
    """

    # PVP Gen Control Registers

    # START_VAL_0_REG : 20 bit
    # START_VAL_1_REG : 20 bit
    # START_VAL_2_REG : 20 bit
    # START_VAL_3_REG : 20 bit

    # STEP_SIZE_0_REG : 20 bit
    # STEP_SIZE_1_REG : 20 bit
    # STEP_SIZE_2_REG : 20 bit
    # STEP_SIZE_3_REG : 20 bit

    # DEMUX_0_REG : 5 bit
    # DEMUX_1_REG : 5 bit
    # DEMUX_2_REG : 5 bit
    # DEMUX_3_REG : 5 bit

    # DAC_0_GROUP_REG: 2 bit
    # DAC_1_GROUP_REG: 2 bit
    # DAC_2_GROUP_REG: 2 bit
    # DAC_3_GROUP_REG: 2 bit

    # DAC_0_PVP_WIDTH_REG: 10 bit
    # DAC_1_PVP_WIDTH_REG: 10 bit
    # DAC_2_PVP_WIDTH_REG: 10 bit
    # DAC_3_PVP_WIDTH_REG: 10 bit

    # CTRL_REG: 4 bit
    # CONFIG_REG: 29 bit

    # DWELL_CYCLES_REG = 32 bit
    # CYCLES_TILL_READOUT_REG = 16 bit
    # NUM_DIMS_REG: 3 bit
    # TRIG_SRC_REG: 1 bit

    bindto = ["xilinx.com:module_ref:axi_pvp_gen_v7:1.0"]

    def __init__(self, description, **kwargs):
        super().__init__(description)

        # map register names to offsets
        self.REGISTERS = {
            "START_VAL_0_REG": 0,
            "START_VAL_1_REG": 1,
            "START_VAL_2_REG": 2,
            "START_VAL_3_REG": 3,
            "STEP_SIZE_0_REG": 4,
            "STEP_SIZE_1_REG": 5,
            "STEP_SIZE_2_REG": 6,
            "STEP_SIZE_3_REG": 7,
            "DEMUX_0_REG": 8,
            "DEMUX_1_REG": 9,
            "DEMUX_2_REG": 10,
            "DEMUX_3_REG": 11,
            "DAC_0_GROUP_REG": 12,
            "DAC_1_GROUP_REG": 13,
            "DAC_2_GROUP_REG": 14,
            "DAC_3_GROUP_REG": 15,
            "DAC_0_DIRECTION_REG": 16,
            "DAC_1_DIRECTION_REG": 17,
            "DAC_2_DIRECTION_REG": 18,
            "DAC_3_DIRECTION_REG": 19,
            "DAC_0_PVP_WIDTH_REG": 20,
            "DAC_1_PVP_WIDTH_REG": 21,
            "DAC_2_PVP_WIDTH_REG": 22,
            "DAC_3_PVP_WIDTH_REG": 23,
            "CTRL_REG": 24,
            "CONFIG_REG": 25,
            "DWELL_CYCLES_REG": 26,
            "CYCLES_TILL_READOUT_REG": 27,
            "NUM_DIMS_REG": 28,
            "USER_TRIGGER_REG": 30,
            "QUIT_PVP_REG": 31,
        }

        # default register values

        self.START_VAL_0_REG = 0
        self.START_VAL_1_REG = 0
        self.START_VAL_2_REG = 0
        self.START_VAL_3_REG = 0

        self.STEP_SIZE_0_REG = 0
        self.STEP_SIZE_1_REG = 0
        self.STEP_SIZE_2_REG = 0
        self.STEP_SIZE_3_REG = 0

        self.DEMUX_0_REG = 0  # if we don't set these, expect weird behavior on dac 0 when it tries to do it all
        self.DEMUX_1_REG = 0
        self.DEMUX_2_REG = 0
        self.DEMUX_3_REG = 0

        self.DAC_0_GROUP_REG = 0  # by default, assign one DAC per group
        self.DAC_1_GROUP_REG = 1
        self.DAC_2_GROUP_REG = 2
        self.DAC_3_GROUP_REG = 3

        self.DAC_0_DIRECTION_REG = 0
        self.DAC_1_DIRECTION_REG = 0
        self.DAC_2_DIRECTION_REG = 0
        self.DAC_3_DIRECTION_REG = 0

        self.DAC_0_PVP_WIDTH_REG = 256
        self.DAC_1_PVP_WIDTH_REG = 256
        self.DAC_2_PVP_WIDTH_REG = 256
        self.DAC_3_PVP_WIDTH_REG = 256

        self.CONFIG_REG = 0
        self.CTRL_REG = 14
        self.DWELL_CYCLES_REG = 2150
        self.CYCLES_TILL_READOUT = 10
        self.NUM_DIMS_REG = 0

        self.USER_TRIGGER_REG = (
            0  # if we're in user mode, a rising edge here means go to the next step
        )
        self.QUIT_PVP_REG = 0

    # ################################
    # Methods
    # ################################
    def volt2reg(self, volt: float = 0.0, debug: bool = False, polarity="bipolar"):
        """Calculates 20 bit representation of voltage based on DAC rails"""
        if polarity == "unipolar":
            VREFN = 0.0
            VREFP = 5.0
            bit_res = 20

            if volt < VREFN:
                if debug:
                    print("volt out of range, volt < VREFN")
                return -1
            elif volt > VREFP:
                if debug:
                    print("volt out of range, volt > VREFP")
                return -1
            else:
                Df = (2**bit_res - 1) * (volt - VREFN) / (VREFP - VREFN)
                if debug:
                    print("Df is " + str(bin(int(Df))))
        if polarity == "bipolar":
            VREFN = -5.0
            VREFP = 5.0
            bit_res = 20

            if volt < VREFN:
                if debug:
                    print("volt out of range, volt < VREFN")
                return -1
            elif volt > VREFP:
                if debug:
                    print("volt out of range, volt > VREFP")
                return -1
            else:
                Df = (2**bit_res - 1) * (volt - VREFN) / (VREFP - VREFN)
                if debug:
                    print("Df is " + str(bin(int(Df))))
        return int(Df)

    def check_lock(self, registerName="<name of locked register>"):
        if self.CTRL_REG & 0b1 == 1:
            raise RuntimeError(
                registerName + " cannot be changed while pvp plot is running."
            )

    def set_any_axis(self, axis="", axis_reg_dict={}, val=0):
        """helper method for any method that has four available axes"""

        if axis in axis_reg_dict:
            reg_str = axis_reg_dict[axis]
            setattr(self, reg_str, val)

        else:
            raise ValueError(
                "No valid axis was specified. Valid axis arguments are '0', '1', '2', '3'"
            )

    def set_start(self, axis="", start_val=0b00):
        """method to set start val
        (note that we want a method for this because we don't want to worry about registers outside this class)"""
        start_regs = {
            "0": "START_VAL_0_REG",
            "1": "START_VAL_1_REG",
            "2": "START_VAL_2_REG",
            "3": "START_VAL_3_REG",
        }
        self.set_any_axis(axis=axis, axis_reg_dict=start_regs, val=start_val)

    def set_step_size(self, axis="", step_size=0):
        """sets size of step (in Volts)"""
        step_size_regs = {
            "0": "STEP_SIZE_0_REG",
            "1": "STEP_SIZE_1_REG",
            "2": "STEP_SIZE_2_REG",
            "3": "STEP_SIZE_3_REG",
        }
        self.set_any_axis(axis=axis, axis_reg_dict=step_size_regs, val=step_size)

    def set_demux(self, axis="", demux=0):
        """Set dac channel value for a given axis"""

        demux_regs = {
            "0": "DEMUX_0_REG",
            "1": "DEMUX_1_REG",
            "2": "DEMUX_2_REG",
            "3": "DEMUX_3_REG",
        }

        if demux >= 0 and demux < 32:
            self.set_any_axis(axis=axis, axis_reg_dict=demux_regs, val=demux)
        else:
            raise ValueError("Demux value must be in the range 0-31 inclusive")

    def set_group(self, axis="", group=0):
        """Set with which group a particular DAC should update"""
        group_regs = {
            "0": "DAC_0_GROUP_REG",
            "1": "DAC_1_GROUP_REG",
            "2": "DAC_2_GROUP_REG",
            "3": "DAC_3_GROUP_REG",
        }
        self.set_any_axis(axis=axis, axis_reg_dict=group_regs, val=group)

    def set_pvp_width(self, axis="", width=256):
        """Set with which group a particular DAC should update"""
        group_regs = {
            "0": "DAC_0_PVP_WIDTH_REG",
            "1": "DAC_1_PVP_WIDTH_REG",
            "2": "DAC_2_PVP_WIDTH_REG",
            "3": "DAC_3_PVP_WIDTH_REG",
        }
        self.set_any_axis(axis=axis, axis_reg_dict=group_regs, val=width)

    def set_direction(self, axis="", direction=0):
        group_regs = {
            "0": "DAC_0_DIRECTION_REG",
            "1": "DAC_1_DIRECTION_REG",
            "2": "DAC_2_DIRECTION_REG",
            "3": "DAC_3_DIRECTION_REG",
        }
        self.set_any_axis(axis=axis, axis_reg_dict=group_regs, val=direction)

    def set_clr(self, clr=1):
        """Clear all DACs via CLRN pin, if in mode 3"""
        # WARNING THIS WILL  NOT STOP YOU FROM CLEARING EVEN IN THE MIDDLE OF A PVP PLOT
        if self.MODE_REG == 3:
            self.CTRL_REG &= 0b1011
            self.CTRL_REG |= clr << 2
        else:
            print("wrong mode (need to be in mode 3 to change clrn manually)")

    def set_reset(self, resetn=1):
        """Reset all DACs via RSTN pin, if in mode 3"""
        # WARNING THIS WILL  NOT STOP YOU FROM RESETTING EVEN IN THE MIDDLE OF A PVP PLOT
        if self.MODE_REG == 3:
            self.CTRL_REG &= 0b1101
            self.CTRL_REG |= resetn << 1
        else:
            print("wrong mode (need to be in mode 3 to change resetn manually)")

    def set_ldac(self, ldac=1, debug=0):
        """Toggle the value of the LDAC pin, if in mode 3"""
        # check if mode allows for manual control
        if self.MODE_REG == 3:
            # clear bit and set it
            self.CTRL_REG &= 0b0111
            self.CTRL_REG |= ldac << 3
            if debug:
                print("ctrl reg: ", self.CTRL_REG)
        else:
            print("wrong mode (need to be in mode 3 to change ldac manually)")

    def set_trigger_source(self, src="qick"):
        """set to qick for triggering with trigger pin 7, and to user for triggering in code"""
        if src == "qick":
            self.CTRL_REG &= 0b1110  # set to 0
        elif src == "user":
            self.CTRL_REG |= 0b1  # set to 1
        else:
            raise ValueError("Trigger source must be either 'qick' or 'user'")

    def set_dwell_cycles(self, dwell_cycles=38400):
        """Set number of clock cycles in between each step"""

        dc_min = 400 * self.NUM_DIMS_REG + 100
        if dwell_cycles < dc_min:
            raise ValueError(
                "Dwell cycles must be at least %d so that all SPI messages can send"
                % dc_min
            )
        self.DWELL_CYCLES_REG = dwell_cycles

    def set_readout_cycles(self, cycles_till=400):
        """Set number of cycles during which the measurement may be read out"""

        self.CYCLES_TILL_READOUT = cycles_till

    def set_num_dims(self, num_dims=0):
        """Set the number of groups looped through in the pvp plot"""

        self.NUM_DIMS_REG = num_dims

    def set_mode(self, m=0):
        """Set operation mode of the pvp gen block. This feature is currently hardcoded to mode 0."""
        pass

    def set_user_trigger(self, user_trig=0):
        """Set the user's trigger (only read if the user is in control of triggering the pvp)"""
        self.USER_TRIGGER_REG &= 0
        self.USER_TRIGGER_REG |= user_trig

    ## Compound methods

    def report_settings(self):
        """Report all pvp gen registers' current value"""
        print("Start of DAC 0: ", hex(self.START_VAL_0_REG))
        print("Start of DAC 1: ", hex(self.START_VAL_1_REG))
        print("Start of DAC 2: ", hex(self.START_VAL_2_REG))
        print("Start of DAC 3: ", hex(self.START_VAL_3_REG))

        print("Step Size DAC 0: ", hex(self.STEP_SIZE_0_REG))

        print("DEMUX 0: ", hex(self.DEMUX_0_REG))
        print("DEMUX 1: ", hex(self.DEMUX_1_REG))
        print("DEMUX 2: ", hex(self.DEMUX_2_REG))
        print("DEMUX 3: ", hex(self.DEMUX_3_REG))

        print("Control Reg: ", hex(self.CTRL_REG))
        print("Arbitrary 24 bits of SPI: ", hex(self.CONFIG_REG))

        print("Number of Dwell Cycles: ", hex(self.DWELL_CYCLES_REG))
        print("Cycles till Trigger AWGs: ", hex(self.CYCLES_TILL_READOUT))
        print("Size of PVP plot (square): ", hex(self.PVP_WIDTH_REG))
        print("Number of DACs Running: ", hex(self.NUM_DIMS_REG))
        print(
            "Trigger source: ", "user" if (self.USER_TRIGGER_REG) else "qick_processor"
        )

    def send_arbitrary_SPI(
        self, demux_int=0b00000, reg=0b0000, data_int=0x00000, debug=0
    ):
        """Allow the user to specify an arbitrary dac (demux_int) and send it an arbitrary 24 bit message (data_int)
        Raises the done flag when finished and cannot be run again until pvp trigger reg is cleared"""

        demux_shift = demux_int << 24
        reg_shift = reg << 20
        out = demux_shift + reg_shift + data_int
        if debug:
            print("Writing config reg to " + str(bin(out)))
        self.CONFIG_REG = out
        time.sleep(0.1)
        self.CONFIG_REG = 0

    def run_pvp_demo(self):
        """Create the correct number of rising edges to sweep out an entire pvp plot, if in user trigger mode"""
        width_regs = [
            self.DAC_0_PVP_WIDTH_REG,
            self.DAC_1_PVP_WIDTH_REG,
            self.DAC_2_PVP_WIDTH_REG,
            self.DAC_3_PVP_WIDTH_REG,
        ]
        dims = []
        for n in range(4):
            if n > self.NUM_DIMS_REG - 1:
                dims.append(1)
            else:
                dims.append(width_regs[n])
        total_trigs = dims[0] * dims[1] * dims[2] * dims[3]
        for i in range(total_trigs):
            self.one_pvp_step()

    def one_pvp_step(self):
        """Create one rising edge for the trigger to read out, if in user trigger mode"""
        self.set_user_trigger(1)
        time.sleep(
            0.01
        )  # this is an arbitrary testing value, but we read the edge so we gotta flip back and forth
        self.set_user_trigger(0)
        time.sleep(0.05)

    def quit_pvp(self):
        self.QUIT_PVP_REG = 1
        time.sleep(0.05)
        self.QUIT_PVP_REG = 0
