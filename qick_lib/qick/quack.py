from typing import List

import numpy as np

from qick import QickSoc


class QuackSoc(QickSoc):
    def __init__(self, bitfile, unipolar: bool = False, **kwargs):
        super().__init__(bitfile, **kwargs)
        self.unipolar = unipolar

    def init_DAC(self, channel: int = 0, debug: bool = False):
        if debug:
            print("initializing dac " + str(channel))
        if self.unipolar:
            self.axi_pvp_gen_v7_0.send_arbitrary_SPI(
                demux_int=channel, reg=0b0010, data_int=0b0000_0000_0000_0011_0010
            )
        else:
            self.axi_pvp_gen_v7_0.send_arbitrary_SPI(
                demux_int=channel, reg=0b0010, data_int=0b0000_0000_0000_0011_0000
            )

    def set_DAC(self, channel: int = 0, volts: float = 0.0, debug: bool = False):
        """set DAC to a static value

        :param channel: DAC slot.  DAC 0 is the closest DAC channel to the input ribbon cable.
        """
        if debug:
            print("setting dac " + str(channel) + " to " + str(volts))
        val = self.axi_pvp_gen_v7_0.volt2reg(
            volts, polarity="unipolar" if self.unipolar else "bipolar"
        )
        # 5 bits of demux, 4 bits of reg, 20 bits of data
        self.axi_pvp_gen_v7_0.send_arbitrary_SPI(channel, 0b0001, val)

    def setup_pvp(
        self,
        channels: List[int],
        start_vals: List[float],
        step_sizes: List[float],
        groups: List[int],
        directions: List[int],
        mode: int,
        steps: int,
    ):
        for v in [start_vals, step_sizes, groups]:
            if len(v) != len(channels):
                raise ValueError("check sweep input list lengths")
        cfg = {
            "startvals": start_vals,
            "stepsizes": step_sizes,
            "demuxvals": channels,
            "groups": groups,
            "mode": mode,
            "width": steps,
            "num_dims": max(groups) + 1,
            "direction": directions,
        }

        self.axi_pvp_gen_v7_0.setup_pvp(
            cfg, polarity="unipolar" if self.unipolar else "bipolar"
        )

    def setup_quack_sweep(
        self,
        loop_0_cfg,
        loop_1_cfg=None,
        loop_2_cfg=None,
        loop_3_cfg=None,
        dwell_cycles: int = 2150,
    ):
        """
        Sets up a standard quack sweep.
        :param loop_0_cfg: A dictionary defining the innermost loop.
                Keys:
                - 'start' (list[float]) :  start voltages of sweep
                - 'step' (list[float]) : voltage steps of sweep
                - 'channels' (list[int]) : quack box channel number (0-31)
                - 'loop_size' (int) : The number of points in loop.  This number currently needs to be identical for all loops.
        :param loop_1_cfg: A dictionary defining the second innermost loop. Has the same format as loop_0_cfg.
        :param loop_2_cfg: A dictionary defining the third loop. Has the same format as loop_0_cfg.
        :param loop_3_cfg: A dictionary defining the fourth loop. Has the same format as loop_0_cfg.
        :param dwell_cycles:  Number of axi clock cycles to wait after trigger before changing the voltage.
        """

        cfg_list = [loop_0_cfg, loop_1_cfg, loop_2_cfg, loop_3_cfg]
        num_dims = 0
        total_channels = 0
        axis_definitions = {}
        for i, cfg in enumerate(cfg_list):
            if cfg is not None:
                if i > 1 and cfg_list[i - 1] is None:
                    loop_missing = i - 1
                    raise ValueError("quack sweep loop %d is undefined" % loop_missing)
                else:
                    num_dims += 1
                    dacs = cfg["channels"]
                    for k, dac in enumerate(dacs):
                        total_channels += 1
                        dac_dict = {}
                        dac_dict["group"] = i
                        dac_dict["channel"] = dac
                        dac_dict["start_val"] = self.axi_pvp_gen_v7_0.volt2reg(
                            cfg["start"][k],
                            polarity="unipolar" if self.unipolar else "bipolar",
                        )
                        direction = 1 if cfg["step"][k] > 0 else 0
                        if self.unipolar:
                            step_size = self.axi_pvp_gen_v7_0.volt2reg(
                                np.abs(cfg["step"][k]), polarity="unipolar"
                            )
                        else:
                            ### if the polarity is bipolar, you need to set the step size differently because 0 register value starts at -5V
                            step_size = self.axi_pvp_gen_v7_0.volt2reg(
                                np.abs(cfg["step"][k]) - 5, polarity="bipolar"
                            )
                        dac_dict["step_val"] = step_size
                        dac_dict["direction"] = direction
                        dac_dict["loop_size"] = cfg["loop_size"]
                        axis_definitions[str(total_channels - 1)] = dac_dict
                    if total_channels > 4:
                        raise ValueError(
                            "total number of swept channels must be 4 or less"
                        )
        ## need to remap order of dacs to make it run correctly
        remapped = {}
        if num_dims == 2:
            if total_channels == 4:
                if (
                    axis_definitions["0"]["group"] == 0
                    and axis_definitions["1"]["group"] == 0
                ):
                    if (
                        axis_definitions["2"]["group"] == 1
                        and axis_definitions["3"]["group"] == 1
                    ):
                        remapped["0"] = axis_definitions["0"]
                        remapped["2"] = axis_definitions["1"]
                        remapped["1"] = axis_definitions["2"]
                        remapped["3"] = axis_definitions["3"]
                        axis_definitions = remapped

        for key, d in axis_definitions.items():
            self.axi_pvp_gen_v7_0.set_demux(axis=key, demux=d["channel"])
            self.axi_pvp_gen_v7_0.set_group(axis=key, group=d["group"])
            self.axi_pvp_gen_v7_0.set_direction(axis=key, direction=d["direction"])
            self.axi_pvp_gen_v7_0.set_start(axis=key, start_val=d["start_val"])
            self.axi_pvp_gen_v7_0.set_step_size(axis=key, step_size=d["step_val"])
            self.axi_pvp_gen_v7_0.set_pvp_width(axis=key, width=d["loop_size"])

        self.axi_pvp_gen_v7_0.set_mode(0)
        self.axi_pvp_gen_v7_0.set_num_dims(num_dims)
        self.axi_pvp_gen_v7_0.set_dwell_cycles(dwell_cycles)

    def send_spi(self, channel: int, register: int, data: int):
        self.axi_pvp_gen_v7_0.send_arbitrary_SPI(channel, register, data)

    def set_user_trigger(self, trigger_flag: bool):
        self.axi_pvp_gen_v7_0.set_user_trigger(trigger_flag)

    def set_trigger_source(self, trigger_source: str = "user"):
        self.axi_pvp_gen_v7_0.set_trigger_source(trigger_source)

    def clear_dac_regs(self):
        for axis in range(4):
            self.axi_pvp_gen_v7_0.set_group(axis=str(axis), group=axis)
            self.axi_pvp_gen_v7_0.set_step_size(axis=str(axis), step_size=0)
            self.axi_pvp_gen_v7_0.set_demux(axis=str(axis), demux=0)

    def quit_pvp(self):
        self.axi_pvp_gen_v7_0.quit_pvp()