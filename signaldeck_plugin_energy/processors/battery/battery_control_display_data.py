import json
from signaldeck_sdk import DisplayData


class BatteryControlDisplayData(DisplayData):

    def args_to_process(self):
        return ["power_curr","pv_curr","battery_power","free_power","power_curr_emu","battery_unload_gap","battery_load_remain_power","fix_offset"]
    
    def withValues(self,inst):
        for a in self.args_to_process():
            setattr(self,a,getattr(inst,a))
        return self

    
    def getStateChangeButtonData(self):
        buttons = self.buttons()
        return [buttons[name] for name in self.button_names_ordered()]
    
    def buttons(self):
        return {"offset_2000":  {"offsetvalue":2000,"name":"offset_2000","id":"bat_offset_2000","actionhash":self.hash,"get_params":json.dumps({"fix_offset":2000}),"text": self.t("signaldeck_plugin_energy.MeterSimulator.button.offset_2000")},
        "offset_1000":  {"offsetvalue":1000,"name":"offset_1000","id":"bat_offset_1000","actionhash":self.hash,"get_params":json.dumps({"fix_offset":1000}),"text":self.t("signaldeck_plugin_energy.MeterSimulator.button.offset_1000")},
        "offset_500":  {"offsetvalue":500,"name":"offset_500","id":"bat_offset_500","actionhash":self.hash,"get_params":json.dumps({"fix_offset":500}),"text":self.t("signaldeck_plugin_energy.MeterSimulator.button.offset_500")},
        "offset_off":  {"offsetvalue":None,"name":"offset_off","id":"bat_offset_off","actionhash":self.hash,"get_params":json.dumps({"reset_offset":True}),"text":self.t("signaldeck_plugin_energy.MeterSimulator.button.offset_auto")},
        "unload_gap_m10":  {"name":"unload_gap_m10","id":"bat_unload_gap_m10","actionhash":self.hash,"get_params":json.dumps({"change_unload_gap":-10}),"text":self.t("signaldeck_plugin_energy.MeterSimulator.button.unload_gap_minus_10")},
        "unload_gap_p10":  {"name":"unload_gap_p10","id":"bat_unload_gap_p10","actionhash":self.hash,"get_params":json.dumps({"change_unload_gap":+10}),"text":self.t("signaldeck_plugin_energy.MeterSimulator.button.unload_gap_plus_10")},
        "load_gap_m10":  {"name":"load_gap_m10","id":"bat_load_gap_m10","actionhash":self.hash,"get_params":json.dumps({"change_load_gap":-10}),"text":self.t("signaldeck_plugin_energy.MeterSimulator.button.load_gap_minus_10")},
        "load_gap_p10":  {"name":"load_gap_p10","id":"bat_load_gap_p10","actionhash":self.hash,"get_params":json.dumps({"change_load_gap":10}),"text":self.t("signaldeck_plugin_energy.MeterSimulator.button.load_gap_plus_10")},
        "unload_gap_m100":  {"name":"unload_gap_m100","id":"bat_unload_gap_m100","actionhash":self.hash,"get_params":json.dumps({"change_unload_gap":-100}),"text":self.t("signaldeck_plugin_energy.MeterSimulator.button.unload_gap_minus_100")},
        "unload_gap_p100":  {"name":"unload_gap_p100","id":"bat_unload_gap_p100","actionhash":self.hash,"get_params":json.dumps({"change_unload_gap":+100}),"text":self.t("signaldeck_plugin_energy.MeterSimulator.button.unload_gap_plus_100")},
        "load_gap_m100":  {"name":"load_gap_m100","id":"bat_load_gap_m100","actionhash":self.hash,"get_params":json.dumps({"change_load_gap":-100}),"text":self.t("signaldeck_plugin_energy.MeterSimulator.button.load_gap_minus_100")},
        "load_gap_p100":  {"name":"load_gap_p100","id":"bat_load_gap_p100","actionhash":self.hash,"get_params":json.dumps({"change_load_gap":100}),"text":self.t("signaldeck_plugin_energy.MeterSimulator.button.load_gap_plus_100")}}

    def getStateChangeButtonData(self):
        res = []
        for button in self.buttons().keys():
            res.append(self.buttons()[button])
        return res

    def getExportFields(self):
        return []
    

    def button_names_ordered(self):
        return ["offset_2000","offset_1000","offset_500","offset_off"]

    def buttonIsActive(self,button):
        if not self.fix_offset:
            return button["name"] == "offset_off"
        if "offsetvalue" in button:
            return self.fix_offset == button["offsetvalue"]
        return False


    def getCSSClass(self,buttonName):
        if self.buttonIsActive(self.buttons()[buttonName]):
            return " active"
        return ""