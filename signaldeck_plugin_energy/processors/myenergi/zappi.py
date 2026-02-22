import asyncio, requests
import logging, datetime,json,time
from signaldeck_sdk import DisplayProcessor, DisplayData
from requests.auth import HTTPDigestAuth
from signaldeck_sdk import PersistData
from .zappidisplaydata import ZappiDisplayData


                        

class Zappi(PersistData,DisplayProcessor):

    def __init__(self,name,config,vP,collect_data):
        super().__init__(name,config,vP,collect_data)
        self.is_running = True 
        self.logger = logging.getLogger(__name__)
        self.cache_ttl = self.config.get("cache_server",8 * 3600)
        self._cached_server = None
        self._cache_expiry = 0
        self.auto_mode=False
        self.min_bat_soc=30
        self.zmo=4
        self.pst="A"
        self.sta=7
        self.min_bat_soc_dyn=False

    # ----------------------------
    # interne Hilfsfunktionen
    # ----------------------------
    def _get_target_server_sync(self) -> str:
        """Fragt den Director ab, mit Caching."""
        now = time.time()
        if self._cached_server and now < self._cache_expiry:
            return self._cached_server

        self.logger.debug("Abfrage des Director-Servers")
        serial = self.config["serial_number"]
        api_key = self.config["api_key"]
        url = f'{self.config.get("base_url_dir")}{serial}'

        resp = requests.get(url, auth=HTTPDigestAuth(serial, api_key))
        target = resp.headers.get("X_MYENERGI-asn")
        if not target:
            raise RuntimeError("Konnte keinen Zielserver vom Director ermitteln.")

        self._cached_server = target
        self._cache_expiry = now + self.cache_ttl
        return target

    def _invalidate_cache(self):
        """Cache löschen (z. B. nach Fehler)."""
        self._cached_server = None
        self._cache_expiry = 0

    def _set_mode_sync(self, mode: int) -> dict:
        serial = self.config["serial_number"]
        api_key = self.config["api_key"]

        try:
            target_server = self._get_target_server_sync()
            url = f'{self.config.get("http_protocol","https")}://{target_server}/cgi-zappi-mode-Z{serial}-{mode}-0-0-0000'
            resp = requests.get(url, auth=HTTPDigestAuth(serial, api_key))
            resp.raise_for_status()
            return resp.json()
        except Exception:
            self._invalidate_cache()
            raise

    def _get_status_sync(self) -> dict:
        serial = self.config["serial_number"]
        api_key = self.config["api_key"]

        try:
            target_server = self._get_target_server_sync()
            self.logger.debug(f'Using target server {target_server}')
            url = f'{self.config.get("http_protocol","https")}://{target_server}/cgi-jstatus-Z{serial}'
            resp = requests.get(url, auth=HTTPDigestAuth(serial, api_key))
            resp.raise_for_status()
            data = resp.json()

            zappis = data.get("zappi", [])
            if len(zappis) == 0:
                self.logger.warning("Keine Zappi-Daten im Status gefunden.")
                return {}
            z=zappis[0]
            if str(z.get("sno")) == str(serial):
                mode = z.get("zmo")
                sta = z.get("sta")

                return {"zmo":mode, "sta": sta, "pst": z.get("pst"), "che": z.get("che"), "date": datetime.datetime.now()} #Date doesn't come from source -> We set it as date and don't care about parsing 
        except Exception:
            self._invalidate_cache()
        

    # ----------------------------
    # Sync-APIs
    # ----------------------------
    def set_mode_sync(self, mode: int) -> dict:
        """Setzt den Lade-Modus synchron (1=Fast, 2=Eco, 3=Eco+, 4=Stop)."""
        return self._set_mode_sync(mode)

    def get_status_sync(self) -> dict:
        """Gibt den aktuellen Modus und Status synchron zurück."""
        return self._get_status_sync()

    def get_mode_sync(self) -> str:
        """Nur den Modus zurückgeben (Kurzform)."""
        return self._get_status_sync()["mode"]

    # ----------------------------
    # Async-APIs
    # ----------------------------
    async def set_mode(self, mode: int) -> dict:
        return await asyncio.to_thread(self._set_mode_sync, mode)

    async def get_status(self) -> dict:
        return await asyncio.to_thread(self._get_status_sync)

    async def get_mode(self) -> str:
        status = await asyncio.to_thread(self._get_status_sync)
        return status["mode"]

        
    
    def get_asyncio_tasks(self,collect_data):
        """
        Liefert die Liste von Async-Tasks für den Manager.
        """
        if collect_data:
            return [self._zappi_status_loop(), self.watchdog_loop()]
        return [self.watchdog_loop()]

    async def watchdog_loop(self):
        """
        Periodischer healtch check.
        """
        self.logger.info(f'Start zappi watchdog: {self.is_running}')
        while self.is_running:
            try:
                if self.auto_mode:
                    if self.pst == "A": # Nicht verbunden
                        await asyncio.sleep(self.config.get("watchdog_interval",10*60))
                        continue
                    self.refresh()
                    if self.bat_soc is None:
                        self.logger.warning('No battery SOC available, cannot use watchdog')
                        await asyncio.sleep(self.config.get("watchdog_interval",10*60))
                        continue
                    if self.min_bat_soc_dyn:
                        if self.bat_soc > self.min_bat_soc + self.config.get("watchdog_bat_load_thr",5):
                            self.min_bat_soc=self.bat_soc - self.config.get("watchdog_bat_load_thr",5)
                            self.logger.info(f'Battery SOC {self.bat_soc} above min, setting min_bat_soc to {self.min_bat_soc}')
                    if self.zmo != 4: # Laden 
                        if self.bat_soc <= self.min_bat_soc:
                            self.logger.info(f'Battery SOC {self.bat_soc} below min {self.min_bat_soc}, setting mode to Stop')
                            await self.set_mode(4) # Stop
                            self.setZMOValue(4)
                    else:
                        if self.bat_soc >= self.min_bat_soc + self.config.get("watchdog_bat_load_thr",5):
                            self.logger.info(f'Battery SOC {self.bat_soc} above min { + self.config.get("watchdog_bat_load_thr",5)}, setting mode to Eco')
                            await self.set_mode(2) # Eco
                            self.setZMOValue(2)
                await asyncio.sleep(self.config.get("watchdog_interval",10*60))
            except Exception as e:
                self.logger.error("Error in watchdog..", exc_info=True)

    async def _zappi_status_loop(self):
        """
        Periodisches Polling Persistenz.
        """
        self.logger.info(f'Start Zappi logger: {self.is_running}')
        while self.is_running:
            try:
                # Daten abfragen
                data = await self.get_status() 
                self.logger.info(f'New data: {data}')
                if data:
                    self.save_data(data=data)
                await asyncio.sleep(self.config.get("poll_interval",5*60))
            except Exception as e:
                self.logger.error("Error while processing data..", exc_info=True)

    def __del__(self):
        self.is_running=False

    # Methods for DisplayProcessor
    def getTemplate(self, value):
        return "energy/zappi_control.html"  

    def getDisplayData(self, value, actionHash, **kwargs) -> DisplayData:
        self.refresh()
        return ZappiDisplayData(self.ctx, actionHash).withValues(self)


    def getDateParams(self):
        return []

    def getBoolParams(self):
        return ["auto_mode","min_bat_soc_dyn"]

    def getIntParams(self):
        return ["zmo"]

    def getFloatParams(self):
        return ["change_min_bat_soc"]
    

    def setZMOValue(self,mode):
        data = self.currVal
        data["zmo"]=mode
        data["date"]=datetime.datetime.now()
        self.save_data(data)

    def performActions(self,value,actionHash,**kwargs):
        if "zmo" in kwargs:
            if self.zmo != kwargs["zmo"]:
                self.set_mode_sync(kwargs["zmo"])
                self.setZMOValue(kwargs["zmo"])
        if "auto_mode" in kwargs:
            self.auto_mode=kwargs["auto_mode"]
        if "min_bat_soc_dyn" in kwargs:
            self.min_bat_soc_dyn=kwargs["min_bat_soc_dyn"]
        if "change_min_bat_soc" in kwargs:
            self.min_bat_soc+=kwargs["change_min_bat_soc"]
        return