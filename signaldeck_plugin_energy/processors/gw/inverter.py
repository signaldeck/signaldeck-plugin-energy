import asyncio
import goodwe
import logging, datetime,json
from signaldeck_sdk import Processor
from pathlib import Path
from signaldeck_sdk import PersistData

i18n= {
    "date": "signaldeck_plugin_energy.GoodweInverter.label.date",
    "ppv1": "signaldeck_plugin_energy.GoodweInverter.label.ppv1",
    "ppv2": "signaldeck_plugin_energy.GoodweInverter.label.ppv2",
    "ipv1": "signaldeck_plugin_energy.GoodweInverter.label.ipv1",
    "ipv2": "signaldeck_plugin_energy.GoodweInverter.label.ipv2",
    "vpv1": "signaldeck_plugin_energy.GoodweInverter.label.vpv1",
    "vpv2": "signaldeck_plugin_energy.GoodweInverter.label.vpv2",
    "ppv": "signaldeck_plugin_energy.GoodweInverter.label.ppv",
    "e_day": "signaldeck_plugin_energy.GoodweInverter.label.e_day",
    "e_total": "signaldeck_plugin_energy.GoodweInverter.label.e_total"
}

fields=["date","ppv","vpv1","ipv1","ppv1","vpv2","ipv2","ppv2","e_day","e_total"]

def getStepFromData(inst,data):
    if "error" in data:
        return inst.interval_long #10 min
    return inst.interval_normal

async def getData(ip_address,keys):
    try:
        inverter = await goodwe.connect(ip_address)
        runtime_data = await inverter.read_runtime_data()
        res={}
        for field in keys:
            res[field]=runtime_data[field]
        if len(res)>0:
            res["date"]=datetime.datetime.now()
        return res
    except:
        return {"error": "Not available"}

class GoodweInverter(PersistData,Processor):

    def __init__(self,name,config,vP,collect_data):
        super().__init__(name,config,vP,collect_data)
        self.is_running = True 
        self.ip=config["ip"]
        self.interval_normal= 3 * 60
        self.interval_long= 10 * 60
        for fieldname in ["interval_long","interval_normal"]:
            if "persist" in self.config and fieldname in self.config["persist"]:
                setattr(self,fieldname,self.config["persist"][fieldname])
        self.state_cache=None
        if "state_cache" in config:
            self.state_cache=config["state_cache"]
        self.logger = logging.getLogger(__name__)
        self.makeDataAvailable()
         # Steuerflag für den Async-Logger

    def get_asyncio_tasks(self,collect_data):
        """
        Liefert die Liste von Async-Tasks für den Manager.
        """
        if collect_data:
            return [self._pvlogger_loop()]
        return []

    async def _pvlogger_loop(self):
        """
        Periodisches Polling der Inverterdaten und Persistenz.
        """
        self.logger.info(f'Start pv logger: {self.is_running}')
        while self.is_running:
            try:
                # Daten abfragen
                data = await getData(self.ip, fields[1:])  # date später hinzugefügt
                # Gesamtproduktion berechnen
                if "error" not in data:
                    if data.get("e_day") not in (None, "None"):
                        yest_val=self.hist("e_total", days=1, dropna=True, last=True)
                        if yest_val:
                            yesterday_total = float(yest_val)
                            data["e_total"] = yesterday_total + data["e_day"]
                    else:
                        self.logger.info("e_day is None, use previous values for e_day and e_total")
                        data["e_total"] = self.e_total if hasattr(self, "e_total") else None
                        data["e_day"] = self.e_day if hasattr(self, "e_day") else None
                    self.logger.info(f'New data: {data}, total from e_day and last day')
    
                    self.save_data(data)
                else:
                    self.logger.info("Inverter not online")

                # Nächstes Intervall
                timeStep = getStepFromData(self, data)
                self.logger.info(f'Next inverter update in {timeStep} seconds')
                await asyncio.sleep(timeStep)
            except Exception as e:
                self.logger.error("Error while processing data..", exc_info=True)

    def __del__(self):
        self.is_running=False

    def process(self,value,actionHash,file=None):
        fields=value.split(",")
        res= self.fetchData(fields)
        if not "error" in res:
            self.currVal=res
            self.makeDataAvailable()
        return {"html": self.renderResult(res)}



    def fetchData(self, fields, timeout: float = None):
        # Plane die Coroutine im bestehenden Loop ein
        coro = getData(self.ip, fields)
        future = asyncio.run_coroutine_threadsafe(coro, self.valueProvider.loop)

        try:
            res = future.result(timeout)  # blockiert bis Fertig oder Timeout
        except TimeoutError:
            raise RuntimeError("Modbus-Request timed out")
        
        # Offset-Handling wie gehabt
        if "error" not in res and self.config.get("totalOffset") is not None:
            if res.get("e_total") is not None:
                res["e_total"] += self.config["totalOffset"]

        return res


    def renderResult(self,res):
        data_to_display = dict(res)
        data_to_display["date"] = res["date"].strftime("%d.%m.%Y %H:%M:%S")
        return self.ctx.render("energy/inverter_state.html",values=data_to_display,i18n=i18n)

    def getCachedStateFromFile(self):
        if self.state_cache is None:
            return {}
        if not Path(self.state_cache).exists():
            return {}
        with open(self.state_cache,"r") as f:
            res = json.load(f)
            try:
                res["date"]=datetime.datetime.strptime(res["date"],"%d.%m.%Y %H:%M:%S")
                return res
            except:
                self.logger.warn("Unable to parse date")
                return res
    
    def getI18n(self):
        return {k: self.ctx.t(v) for k,v in i18n.items()}

    def getState(self,value,actionHash):
        data=self.currVal
        if data is None or len(data) == 0:
            return ""
        data= {k: data[k] for k in value[0].split(",")+["date"]}
        data["date"] = data["date"].strftime("%d.%m.%Y %H:%M:%S")
        return self.ctx.render("energy/inverter_state.html",values=data,i18n=self.getI18n())

