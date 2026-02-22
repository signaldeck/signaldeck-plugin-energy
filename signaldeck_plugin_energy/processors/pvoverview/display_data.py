import datetime,json
from signaldeck_sdk.context import ApplicationContext
from signaldeck_sdk import DisplayData
import calendar
from dateutil.relativedelta import relativedelta


attr_base=["power_date","power_diff_in","power_diff_out","curr_power","total_power_usage"]
attr_pv = ["pv_date","pv_gen","curr_pv","pv_used","autarkie"]
attr_power_alt = ["power_date_alt","curr_power_alt"]
attr_battery = ["battery_power","battery_soc","battery_temp"]

def getMonthLength(offset):
    if offset == 0:
        d= datetime.datetime.today()
        val = d.day -1 + d.hour / 24 + d.minute / (24 * 60) 
        return val
    t = datetime.datetime.today()
    t= t.replace(day=15)
    t = t + relativedelta(months=-offset)
    return calendar.monthrange(t.year,t.month)[1]

def getYearLength(offset):
    year = datetime.datetime.today().year
    if offset == 0:
        d= datetime.datetime.today()
        val = d.timetuple().tm_yday + d.hour / 24 + d.minute / (24 * 60) 
        return val
    year += -offset
    return 365 + calendar.isleap(year)

def getMonthName(offset):
    t = datetime.datetime.today()
    t= t.replace(day=15)
    t = t + relativedelta(months=-offset)
    return calendar.month_name[t.month]

class PvDisplayData(DisplayData):

    def __init__(self,ctx: ApplicationContext,hash):
        super().__init__(ctx,hash)
        self.has_pv_data = False
        self.has_battery_data = False
        self.has_alt_power_data = False

    def getStatefullFields(self):
        return ["offset", "exact", "daily", "day", "month", "year"]


    def withPowerDate(self,date: datetime.datetime):
        self.power_date=date
        return self

    def withPowerDateAlt(self,date: datetime.datetime):
        self.power_date_alt=date
        self.has_alt_power_data = True
        return self

    def withPvDate(self,date: datetime.datetime):
        self.pv_date=date
        return self

    def withBatteryTemp(self,temp):
        self.battery_temp=temp
        return self

    def correctDailyValueIfNeeded(self,value):
        if self.daily and self.exact and self.offset > 0:
            return value / self.offset
        if self.daily and self.month:
            return value / getMonthLength(self.offset) 
        if self.daily and self.year:
            return value / getYearLength(self.offset) 
        return value

    def withPowerTotalIn(self,powerInEnd,powerInStart):
        if powerInEnd is None or powerInStart is None:
            self.power_diff_in=0
            return self
        self.power_diff_in=self.correctDailyValueIfNeeded(powerInEnd-powerInStart)
        return self

    def withPowerTotalOut(self,powerOutEnd,powerOutStart):
        if powerOutEnd is None or powerOutStart is None:
            self.power_diff_out=0
            return self
        self.power_diff_out=self.correctDailyValueIfNeeded(powerOutEnd - powerOutStart)
        return self

    def withPvGenerated(self,pvGen):
        self.pv_gen=self.correctDailyValueIfNeeded(pvGen)
        return self

    def withCurrPower(self,currPower):
        self.curr_power=currPower
        return self

    def withCurrPowerAlt(self,currPower):
        self.curr_power_alt=currPower
        return self

    def withBatteryPower(self, batPower):
        self.battery_power = batPower
        return self
    
    def withBatterySOC(self, batSoc):
        self.battery_soc = batSoc
        self.has_battery_data = True
        return self

    def withCurrPV(self,currPV):
        self.has_pv_data = True
        self.curr_pv=currPV
        return self        

    def numberOfResultVals(self):
        count = 1
        if self.has_pv_data:
            count += 1
        if self.has_battery_data:
            count += 1
        return str(int(count))

    def compile(self):
        self.total_power_usage= self.power_diff_in
        self.autarkie=0
        if self.has_pv_data:
            self.pv_used=0
            if self.pv_gen:
                self.pv_used= self.pv_gen - self.power_diff_out
            else:
                self.pv_gen=0
            self.total_power_usage= self.power_diff_in + self.pv_used
            if self.total_power_usage:
                self.autarkie= 100 * self.pv_used / self.total_power_usage
        if self.has_battery_data:
            if self.battery_power is None:
                self.battery_power=0
            if self.battery_soc is None:
                self.battery_soc=0
            if self.battery_temp is None:
                self.battery_temp=0
        self.title=self.getTitle()
        return self

    def getTitle(self):
        if self.exact:
            hours=self.offset * 24
            return f'{hours}h von {datetime.datetime.now()+datetime.timedelta(days=-self.offset)}'
        if self.offset == 0 and self.day:
            return f'{self.pv_date.year}-{self.pv_date.month}-{self.pv_date.day} {self.pv_date.time().strftime("%H:%M:%S")}/{self.power_date.time().strftime("%H:%M:%S")} ({self.power_date_alt.time().strftime("%H:%M:%S")})'
        else:
            if self.day:
                return f'{self.pv_date.date()}'
            if self.month:
                return f'{getMonthName(self.offset)}'
            if self.year:
                year= self.pv_date.date().year
                year = year - self.offset
                return f'{year}'
        

    def isButtonActive(self,buttonName):
        if self.exact:
            if self.day:
                if self.offset == 1:
                    return buttonName == "24h"
                if self.offset == 3:
                    return buttonName == "72h"
                if self.offset == 7:
                    return buttonName == "7d"
                if self.offset == 30:
                    return buttonName == "30d"
        return False

    def getCSSClass(self,buttonName):
        if hasattr(self,buttonName) and getattr(self,buttonName):
            return " active"
        if self.isButtonActive(buttonName):
            return " active"
        return ""

    def buttons(self):
        return {
            "day": {"name":"day",
                    "params":{"day": True,"month":False,"year":False,"offset":0,"exact":False},
                    "text":self.t("signaldeck_plugin_energy.pv.button.day")
            },
            "month": {"name":"month",
                      "params":{"day": False,"month":True,"year":False,"offset":0,"exact":False},
                      "text":self.t("signaldeck_plugin_energy.pv.button.month")
            },
            "year": {"name":"year",
                     "params":{"day": False,"month":False,"year":True,"offset":0,"exact":False},
                     "text":self.t("signaldeck_plugin_energy.pv.button.year")
            },
            "prev": {"name":"prev",
                     "params":{"exact":False,"offset": self.offset+1},
                     "text":self.t("signaldeck_plugin_energy.pv.button.prev")
            },
            "next":{"name":"next",
                    "params":{"exact":False,"offset": self.offset-1},
                    "text":self.t("signaldeck_plugin_energy.pv.button.next")
            },
            "24h":{"name":"24h",
                   "params":{"exact":True,"day": True,"month":False,"year":False,"offset": 1},
                   "text":self.t("signaldeck_plugin_energy.pv.button.24h")
            },
            "72h":{"name":"72h",
                   "params":{"exact":True,"day": True,"month":False,"year":False,"offset": 3},
                   "text":self.t("signaldeck_plugin_energy.pv.button.72h")
            },
            "7d":{"name":"7d",
                  "params":{"exact":True,"day": True,"month":False,"year":False,"offset": 7},
                  "text":self.t("signaldeck_plugin_energy.pv.button.7d")
            },
            "30d":{"name":"30d",
                   "params":{"exact":True,"day": True,"month":False,"year":False,"offset": 30},
                   "text":self.t("signaldeck_plugin_energy.pv.button.30d")},
            "daily":{"name":"daily",
                     "params":{"daily": not self.daily},
                     "text":self.t("signaldeck_plugin_energy.pv.button.daily")}}


    def getExportFields(self):
        res = attr_base
        if self.has_pv_data:
            res = res + attr_pv
        if self.has_alt_power_data:
            res = res + attr_power_alt
        if self.has_battery_data:
            res = res + attr_battery
        return res
