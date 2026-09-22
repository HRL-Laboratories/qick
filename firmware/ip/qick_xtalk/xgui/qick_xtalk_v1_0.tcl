# Definitional proc to organize widgets for parameters.
proc init_gui { IPINST } {
  ipgui::add_param $IPINST -name "Component_Name"
  #Adding Page
  set Page_0 [ipgui::add_page $IPINST -name "Page 0"]
  ipgui::add_static_text $IPINST -name "TITLE" -parent ${Page_0} -text {QICK Cross Talk Compensation 1.0}
  ipgui::add_param $IPINST -name "CH_QTY" -parent ${Page_0}
  ipgui::add_param $IPINST -name "COEF_DW" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SMP_CK" -parent ${Page_0}


}

proc update_PARAM_VALUE.CH_QTY { PARAM_VALUE.CH_QTY } {
	# Procedure called to update CH_QTY when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CH_QTY { PARAM_VALUE.CH_QTY } {
	# Procedure called to validate CH_QTY
	return true
}

proc update_PARAM_VALUE.COEF_DW { PARAM_VALUE.COEF_DW } {
	# Procedure called to update COEF_DW when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.COEF_DW { PARAM_VALUE.COEF_DW } {
	# Procedure called to validate COEF_DW
	return true
}

proc update_PARAM_VALUE.SMP_CK { PARAM_VALUE.SMP_CK } {
	# Procedure called to update SMP_CK when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SMP_CK { PARAM_VALUE.SMP_CK } {
	# Procedure called to validate SMP_CK
	return true
}

proc update_PARAM_VALUE.SMP_DW { PARAM_VALUE.SMP_DW } {
	# Procedure called to update SMP_DW when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SMP_DW { PARAM_VALUE.SMP_DW } {
	# Procedure called to validate SMP_DW
	return true
}


proc update_MODELPARAM_VALUE.SMP_DW { MODELPARAM_VALUE.SMP_DW PARAM_VALUE.SMP_DW } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SMP_DW}] ${MODELPARAM_VALUE.SMP_DW}
}

proc update_MODELPARAM_VALUE.SMP_CK { MODELPARAM_VALUE.SMP_CK PARAM_VALUE.SMP_CK } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SMP_CK}] ${MODELPARAM_VALUE.SMP_CK}
}

proc update_MODELPARAM_VALUE.CH_QTY { MODELPARAM_VALUE.CH_QTY PARAM_VALUE.CH_QTY } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CH_QTY}] ${MODELPARAM_VALUE.CH_QTY}
}

proc update_MODELPARAM_VALUE.COEF_DW { MODELPARAM_VALUE.COEF_DW PARAM_VALUE.COEF_DW } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.COEF_DW}] ${MODELPARAM_VALUE.COEF_DW}
}

