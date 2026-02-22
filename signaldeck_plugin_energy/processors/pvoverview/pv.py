from signaldeck_sdk import DisplayProcessor
from datetime import datetime, timedelta
from .display_data import PvDisplayData
import logging
from dateutil.relativedelta import relativedelta
from signaldeck_sdk import Placeholder

attr_base=["power_in_today_start","power_in","power_out_today_start","power_out","power_date","power_curr"]
attr_pv = ["pv_day","pv_date","pv_curr"]
attr_power_alt = ["power_date_alt","power_curr_alt"]
attr_battery = ["battery_soc","battery_power","battery_temp"]

class mock_pv:
    def __init__(self,inst):
        self.has_pv_data = False
        self.has_battery_data = False
        self.has_alt_power_data = False
        for a in attr_base:
            setattr(self,a,getattr(inst,a))
        if hasattr(inst,"pv_date"):
            for a in attr_pv:
                setattr(self,a,getattr(inst,a))
            self.has_pv_data = True
        if hasattr(inst,"power_date_alt"):
            self.has_alt_power_data = True
            for a in attr_power_alt:
                setattr(self,a,getattr(inst,a))
        if hasattr(inst,"battery_power"):
            self.has_battery_data = True
            for a in attr_battery:
                setattr(self,a,getattr(inst,a))

def getDateForOffsetMonth(offset,first=False,last=False):
    today = datetime.today() + relativedelta(months=-offset)
    if first:
        return today.replace(day=1)
    if last:
        nextMonth = today.replace(day=28) + timedelta(days=4)
        return nextMonth + timedelta(days=-nextMonth.day)
    
def getDateForOffsetYear(offset,first=False,last=False):
    today = datetime.today() + relativedelta(months=-12*offset)
    if first:
        return today.replace(day=1,month=1)
    if last:
        return today.replace(day=31,month=12)

class PvOverview(DisplayProcessor):
    def __init__(self,name,config,vP,collect_data):
        super().__init__(name,config,vP,collect_data)
        self.logger = logging.getLogger(__name__)

    @classmethod
    def config_placeholders(cls):
        return [
        Placeholder("pv", "Input Feld: pv", "str", default= "pv_curr"),
        Placeholder("pv_day", "Input Feld: pv_day", "str", default= "pv_day"),
        Placeholder("pv_date", "Input Feld: pv_date", "str", default= "pv_date"),
        Placeholder("power_in", "Input Feld: power_in", "str", default= "power_in"),
        Placeholder("power_out", "Input Feld: power_out", "str", default= "power_out"),
        Placeholder("power_curr", "Input Feld: power_curr", "str", default= "power_curr"),
        Placeholder("power_date", "Input Feld: power_date", "str", default= "power_date"),
        Placeholder("power_curr_alt", "Input Feld: power_curr_alt", "str", default= "power_curr_alt"),
        Placeholder("power_date_alt", "Input Feld: power_date_alt", "str", default= "power_date_alt"),
        Placeholder("battery_soc", "Input Feld: battery_soc", "str", default= "battery_soc"),
        Placeholder("battery_temp", "Input Feld: battery_temp", "str", default= "battery_temp"),
        Placeholder("battery_power", "Input Feld: battery_power", "str", default= "battery_power"),
        Placeholder("hist_power_in", "Input Feld: hist_power_in", "str", default= "hist_power_in"),
        Placeholder("hist_power_out", "Input Feld: hist_power_out", "str", default= "hist_power_out"),
        Placeholder("hist_pv_total", "Input Feld: hist_pv_total", "str", default= "hist_pv_total")
        ]


    def refresh(self):
        old_pv_day=None
        if hasattr(self,"pv_day"):
            old_pv_day=self.pv_day
        super().refresh()
        if self.pv_day is None:
            self.pv_day = old_pv_day
        if datetime.today().day != self.pv_date.day:
            self.pv_date = self.power_date
            self.pv_curr=0
            self.pv_day=0
        
            
    def getDisplayDataInst(self,actionHash,mockInstance=None,**kwargs):
        if mockInstance is None:
            mockInstance = mock_pv(self)
        res= PvDisplayData(self.ctx, actionHash).withData(kwargs) \
            .withCurrPower(mockInstance.power_curr) \
            .withPowerDate(mockInstance.power_date) \
            .withPowerTotalIn(mockInstance.power_in, mockInstance.power_in_today_start) \
            .withPowerTotalOut(mockInstance.power_out, mockInstance.power_out_today_start) 
        if hasattr(mockInstance,"pv_curr"):
            res = res \
                .withCurrPV(mockInstance.pv_curr) \
                .withPvDate(mockInstance.pv_date) \
                .withPvGenerated(mockInstance.pv_day) 
        if hasattr(mockInstance,"power_date_alt"):
            res = res \
                .withPowerDateAlt(mockInstance.power_date_alt) \
                .withCurrPowerAlt(mockInstance.power_curr_alt) 
        if hasattr(mockInstance,"battery_power"):
            res=res.withBatterySOC(mockInstance.battery_soc) \
            .withBatteryPower(mockInstance.battery_power)\
            .withBatteryTemp(mockInstance.battery_temp)\

        return res.compile()

    def getMockedInstance(self,offset=0,exact=False,day=True,month=False,year=False):
        res= mock_pv(self)
        offset=int(offset)
        if offset > 0:
            if res.has_pv_data:
                res.pv_date = res.pv_date + timedelta(days=-offset)
            res.power_date = res.power_date + timedelta(days=-offset)
            if exact:
                if res.has_pv_data:
                    res.pv_day = float(self.hist_pv_total(days=0))-float(self.hist_pv_total(days=offset))
                res.power_in_today_start = self.hist_power_in(days=offset)
                res.power_in = self.hist_power_in(days=0)
                res.power_out_today_start = self.hist_power_out(days=offset)
                res.power_out = self.hist_power_out(days=0)            
            else:
                if day:
                    if res.has_pv_data:
                        res.pv_day = float(self.hist_pv_total(days=offset,last=True))-float(self.hist_pv_total(days=offset,first=True))
                    res.power_in_today_start = self.hist_power_in(days=offset,first=True)
                    res.power_in = self.hist_power_in(days=offset,last=True)
                    res.power_out_today_start = self.hist_power_out(days=offset,first=True)
                    res.power_out = self.hist_power_out(days=offset,last=True)
                if month:
                    if res.has_pv_data:
                        res.pv_day = float(self.hist_pv_total(days=0,date=getDateForOffsetMonth(offset,last=True),last=True))-float(self.hist_pv_total(days=0,date=getDateForOffsetMonth(offset,first=True),first=True))
                    res.power_in_today_start = self.hist_power_in(days=0,date=getDateForOffsetMonth(offset,first=True),first=True)
                    res.power_in = self.hist_power_in(days=0,date=getDateForOffsetMonth(offset,last=True),last=True)
                    res.power_out_today_start = self.hist_power_out(days=0,date=getDateForOffsetMonth(offset,first=True),first=True)
                    res.power_out = self.hist_power_out(days=0,date=getDateForOffsetMonth(offset,last=True),last=True)
                if year:
                    high_date = getDateForOffsetYear(offset,last=True)
                    low_date = getDateForOffsetYear(offset,first=True)
                    if res.has_pv_data:
                        res.pv_day = float(self.hist_pv_total(days=0,date=high_date,last=True))-float(self.hist_pv_total(days=0,date=low_date,first=True))
                    res.power_in_today_start = self.hist_power_in(days=0,date=low_date,first=True)
                    res.power_in = self.hist_power_in(days=0,date=high_date,last=True)
                    res.power_out_today_start = self.hist_power_out(days=0,date=low_date,first=True)
                    res.power_out = self.hist_power_out(days=0,date=high_date,last=True)
        else:
            if month:
                if res.has_pv_data:
                    res.pv_day = float(self.hist_pv_total(days=0,last=True))-float(self.hist_pv_total(days=0,date=getDateForOffsetMonth(offset,first=True),first=True))
                res.power_in_today_start = self.hist_power_in(days=0,date=getDateForOffsetMonth(offset,first=True),first=True)
                res.power_in = self.hist_power_in(days=offset,last=True)
                res.power_out_today_start = self.hist_power_out(days=0,date=getDateForOffsetMonth(offset,first=True),first=True)
                res.power_out = self.hist_power_out(days=offset,last=True)
            if year:
                if res.has_pv_data:
                    res.pv_day = float(self.hist_pv_total(days=0,last=True))-float(self.hist_pv_total(days=0,date=getDateForOffsetYear(offset,first=True),first=True))
                res.power_in_today_start = self.hist_power_in(days=0,date=getDateForOffsetYear(offset,first=True),first=True)
                res.power_in = self.hist_power_in(days=offset,last=True)
                res.power_out_today_start = self.hist_power_out(days=0,date=getDateForOffsetYear(offset,first=True),first=True)
                res.power_out = self.hist_power_out(days=offset,last=True)
        return res



    def getDisplayData(self,value,actionHash,offset=0,exact=False,daily=False,day=True,month=False,year=False):
        self.logger.info("Get state for hash: "+actionHash)
        self.refresh()
        mockInstance = self.getMockedInstance(offset=offset,exact=exact,day=day,month=month,year=year)
        return self.getDisplayDataInst(actionHash,offset=offset,exact=exact,mockInstance=mockInstance,daily=daily,day=day,month=month,year=year)

   
    def getTemplate(self,value):
        return "energy/pvoverview_state.html"
    
    def getBoolParams(self):
        return ["daily","exact","day","month","year"]

    def getIntParams(self):
        return ["offset"]
    
    def getFloatParams(self):
        return []