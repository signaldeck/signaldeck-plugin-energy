import logging, time, asyncio
from signaldeck_sdk import DisplayProcessor
from signaldeck_sdk import DisplayData
from .battery_control_display_data import BatteryControlDisplayData
from signaldeck_sdk import Cmd, Command
 


def getPowerEmuValue(power_curr,free_power,battery_load_remain_power):
    if free_power < battery_load_remain_power:
        return power_curr + free_power #no loading
    if free_power > 2000:
        return power_curr + battery_load_remain_power * 1.5
    return power_curr + battery_load_remain_power      

class SetOffset(Command):
    def __init__(self,processor):
        self.processor=processor
        super().__init__("battery_set_offset","Sets offset for battery meter simulator")

    async def run(self, offset,cmdRes=None,stopEvent=None):
        self.processor.setOffset(float(offset))
        if cmdRes is not None:
            cmdRes.appendState(self,msg=f'Set battery meter simulator offset to {self.processor.fix_offset}')

class UnsetOffset(Command):
    def __init__(self,processor):
        self.processor=processor
        super().__init__("battery_set_auto","Sets auto mode on for battery meter simulator")

    async def run(self,cmdRes=None,stopEvent=None):
        self.processor.setAuto()
        if cmdRes is not None:
            cmdRes.appendState(self,msg=f'Set battery meter simulator to auto mode')

class MeterSimulator(DisplayProcessor):


    def __init__(self,name,config,vP,collect_data):
        super().__init__(name,config,vP,collect_data)
        self.logger = logging.getLogger(__name__)
        self.big_pv_power = False
        self.fix_offset = None
        self.is_running = True 
        self.free_power_init = None
        self.fix_offset_start = None
        self.battery_unload_gap = config.get("battery_unload_gap",100)
        self.battery_load_remain_power = config.get("battery_load_remain_power",500)
        self.logger.info(f'Init Battery Meter Simulator with unload_gap={self.battery_unload_gap} and load_remain_power={self.battery_load_remain_power}')
        self._neg_since = None 

    def get_asyncio_tasks(self,collect_data):
        """
        Liefert die Liste von Async-Tasks für den Manager.
        """
        return [self._watchdog_loop()]

    async def _watchdog_loop(self):
        """
        Periodischer healtch check.
        """
        self.logger.info(f'Start bms watchdog: {self.is_running}')
        while self.is_running:
            try:
                # Daten abfragen
                if self.fix_offset_start:
                    if (time.monotonic() - self.fix_offset_start) > self.config.get("max_fix_offset_time",10*60):
                        self.logger.info(f'Fix offset active for more than {self.config.get("max_fix_offset_time",10*60) / 60} minutes, switching to auto mode')
                        self.setAuto()
                await asyncio.sleep(self.config.get("watchdog_interval",10*60))
            except Exception as e:
                self.logger.warning(e)

    def __del__(self):
        self.is_running=False

    def registerCommands(self, cmd: Cmd):
        cmd.registerCmd(SetOffset(self))
        cmd.registerCmd(UnsetOffset(self))

    def getTemplate(self, value):
        return "energy/battery_control.html"  

    def getDisplayData(self, value, actionHash, **kwargs) -> DisplayData:
        self.refresh()
        return BatteryControlDisplayData(self.ctx, actionHash).withValues(self)


    def getDateParams(self):
        return []

    def getBoolParams(self):
        return ["reset_offset"]

    def getIntParams(self):
        return []

    def getFloatParams(self):
        return ["fix_offset","change_unload_gap","change_load_gap"]

    def performActions(self,value,actionHash,**kwargs):
        if "fix_offset" in kwargs:
            self.setOffset(kwargs["fix_offset"])
        if "reset_offset" in kwargs:
            self.setAuto()
        if "change_unload_gap" in kwargs:
            self.battery_unload_gap += kwargs["change_unload_gap"]
        if "change_load_gap" in kwargs:
            self.battery_load_remain_power += kwargs["change_load_gap"]
        return

    def setOffset(self,offset):
        self.fix_offset = offset
        self.fix_offset_start = time.monotonic()
        self.free_power_init = self.free_power

    def setAuto(self):
        self.fix_offset = None
        self.fix_offset_start = None    

    def refresh(self):
        self.logger.debug("Start refreshing values")
        super().refresh()
        self.power_out_emu=self.power_out
        self.power_in_emu=self.power_in
        self.power_curr_emu=self.power_curr
        self.generateValues()
        self.logger.info(f'in=(power_curr={self.power_curr}, pv_curr={self.pv_curr}, batter_power={self.battery_power}, free_power={self.free_power}) -> out=(power_curr={self.power_curr_emu})')


    def generateValues(self):
        self.free_power = -self.power_curr + self.battery_power 
        if self.fix_offset:
            if self.free_power < 0 and (self.free_power_init - self.free_power) > 0.75 * self.fix_offset:
                now = time.monotonic()
                if self._neg_since is None:
                    # erstes Mal <0 in dieser Phase: Timestamp setzen
                    self._neg_since = now
                else:
                    # prüfen, ob 15 s durchgehend <0 vergangen sind
                    if (now - self._neg_since) >= 15:
                        self.fix_offset = None
                        self._neg_since = None  
            else:
                # jedes >0: Timestamp und Alarm zurücksetzen
                self._neg_since = None
                self._neg_alerted = False
            if self.fix_offset:
                self.power_curr_emu = self.power_curr + self.fix_offset
                return
        if self.free_power <= 0:
           self.power_curr_emu=self.power_curr - self.battery_unload_gap
           return
        self.power_curr_emu = getPowerEmuValue(self.power_curr,self.free_power,self.battery_load_remain_power)
          
