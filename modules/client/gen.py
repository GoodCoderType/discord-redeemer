from modules.utils.logger   import LOGGER
from modules.utils.utils    import CONFIG, GLOBAL_VARS, FILES, UTILS_DISCORD, PROMO, VCC, RESOURCE_LOCK, FORCE_PARAMETERS, loads
from tls_client             import Session
from threading              import Thread
from time                   import sleep, perf_counter

class PromoGenApiWrapperPersonal:
    def __init__(self):
        self.session: Session = Session(client_identifier = "chrome_120", random_tls_extension_order = True)
        self.session.timeout_seconds = CONFIG.gen_timeout

        self.session_id: str = None
        self.proxies: list[str] = FILES.get_proxies()
        self.last_update: int = perf_counter()
        self.used_promos: list[str] = []
        self.balance: int = -1 # Unused but to keep class consistency.

    def _start_session(self) -> str:
        try:
            if not self.proxies:
                raise Exception("No Proxies Available, Gen Needs Sticky Proxies!")

            response = self.session.post(
                "https://promo.eintim.dev/start_session", 
                json = {
                    "username": CONFIG.auth_username,
                    "password": CONFIG.auth_password,
                    "proxies":  self.proxies,
                    "threads":  GLOBAL_VARS.threads_amount * 2
                }
            )

            self.session_id = response.json()["session_id"]

        except Exception as e:
            LOGGER.error("Exception While Starting Session", e)
            return self._start_session()
        
        return self.session_id
    
    def _update_pool(self) -> str|bool:
        try:
            promo = None
            amount: int = len(FILES.promos)

            response = self.session.get(f"https://promo.eintim.dev/get_promo?sessionid={self.session_id}").json()

            if response["status"] == "error":
                self.session_id = None
                return False
            
            for raw_promo in response["data"]:
                
                if raw_promo in self.used_promos:
                    continue
                
                for promo in FILES.promos:
                    if promo and promo.raw_promo == raw_promo:
                        raw_promo = None
                        break

                if raw_promo:
                    formatted_promo: PROMO = UTILS_DISCORD.format_promo(raw_promo)
                    FILES.promos.append(formatted_promo)
                    self.used_promos.append(formatted_promo.raw_promo)

            if len(FILES.promos) > amount:
                LOGGER.success("Added Promos", len(FILES.promos) - amount, last_update = perf_counter() - self.last_update)
                self.last_update = perf_counter()
        
        except Exception as e:
            self.session_id = None
            return f"Unknown Exception While Updating Pool, Stopping Promo Gen! {e}"

        return True
    
    def _check_status(self) -> str|bool:
        try:
            response = self.session.get(f"https://promo.eintim.dev").json()

            if response["current_provider"] == None:
                return "No Provider Available!"
                
            return True
        
        except Exception as e:
            CONFIG.use_gen_promo = False
            return "Promo API Is Not Up At The Moment!"        

    def _gen_thread(self):
        while CONFIG.use_gen_promo:
            if not self.session_id and GLOBAL_VARS.sessions and (not FILES.linked_tokens and not FILES.promos):
                self._start_session()
                LOGGER.success("Started Gen", self.session_id)

            while self.session_id and GLOBAL_VARS.sessions:
                status = self._update_pool()

                if status != True:
                    LOGGER.error("Stopping Promo Gen", status)
                    return

                status = self._check_status()

                if status != True:
                    LOGGER.error("Stopping Promo Gen", status)
                    return
                
                sleep(25)

            sleep(5)

    def start_gen(self) -> str:
        status = self._check_status()
        
        if status != True:
            return status
        
        Thread(target = self._gen_thread, daemon=True).start()

        return

class PromoGenApiWrapper:
    def __init__(self):
        self.session: Session = Session(client_identifier = "chrome_120", random_tls_extension_order = True)
        self.session.timeout_seconds = CONFIG.gen_timeout

        self.used_promos: list[str] = []
        self.last_update: int = perf_counter()
        self.balance: int = 0
    
    def _update_pool(self) -> bool:
        try:
            promo = None
            amount: int = len(FILES.promos)
            post_json = {}

            if CONFIG.promo_api_key:
                post_json["key"] = CONFIG.promo_api_key

            post_json["amount"] = len(GLOBAL_VARS.sessions)
        
            response = self.session.get(
                f"{CONFIG.promo_api_link}/get_promo",
                json = post_json
            ).json()

            match response["status"]:
                case "success":
                    pass
                case "invalid_key":
                    return "Invalid Key"
                case "no_stock":
                    LOGGER.warn("Promo Api Returned No Stock, Waiting 5 Seconds...")
                    sleep(5)
                    return self._update_pool()
                case "no_balance":
                    return "No Balance"
                case _:
                    return f"Unknown Error! {response["status"]}"
            
            for raw_promo in response["promos"]:
                
                if raw_promo in self.used_promos:
                    continue
                
                for promo in FILES.promos:
                    if promo and promo.raw_promo == raw_promo:
                        raw_promo = None
                        break

                if raw_promo:
                    formatted_promo: PROMO = UTILS_DISCORD.format_promo(raw_promo)
                    FILES.promos.append(formatted_promo)
                    self.used_promos.append(formatted_promo.raw_promo)

            if len(FILES.promos) > amount:
                LOGGER.success("Added Promos", len(FILES.promos) - amount, last_update = perf_counter() - self.last_update)
                self.last_update = perf_counter()
        
        except Exception as e:
            return f"Unknown Exception While Updating Pool! {e}"

        return True
    
    def _check_status(self) -> str|bool:
        try:
            post_json = {}

            if CONFIG.promo_api_key:
                post_json["key"] = CONFIG.promo_api_key

            response: dict = self.session.post(
                CONFIG.promo_api_link,
                json = post_json
            ).json()

            if "status" in response.keys():
                match response["status"]:
                    case "success":
                        pass
                    case "invalid_key":
                        return "Invalid Key"
                    case "no_balance":
                        return "No Balance"
                    case _:
                        return f"Unknown Error! {response['status']}"
                
            return True
        
        except Exception as e:
            return "Promo API Is Not Up At The Moment!"
        

    def _gen_thread(self):
        while CONFIG.use_gen_promo:
            while GLOBAL_VARS.sessions and (not FILES.linked_tokens and not FILES.promos):
                status = self._update_pool()
                 
                if status != True:
                   CONFIG.use_gen_promo = False
                   LOGGER.error("Stopping Promo Gen", status)
                   return

                status = self._check_status()

                if status != True:
                   CONFIG.use_gen_promo = False
                   LOGGER.error("Stopping Promo Gen", status)
                   return
                
                sleep(5)

            sleep(5)

    def start_gen(self) -> str:
        status = self._check_status()

        if status != True:
            CONFIG.use_gen_promo = False
            return status
        
        Thread(target = self._gen_thread, daemon=True).start()
        return None


class VCCGenApiWrapper:
    def __init__(self):
        self.session: Session = Session(client_identifier = "chrome_120", random_tls_extension_order = True)
        self.session.timeout_seconds = CONFIG.gen_timeout

        self.used_vccs: list[str] = []
        self.last_update: int = perf_counter()
        self.balance: int = 0
    
    def _update_pool(self) -> bool:
        try:
            self.last_update = perf_counter()

            vcc = None
            amount: int = FILES.len_vccs()
            post_json = {}

            if CONFIG.vcc_api_key:
                post_json["key"] = CONFIG.vcc_api_key

            vcc_amount = 0

            if int(len(GLOBAL_VARS.sessions) / CONFIG.vcc_uses) == 0:
                vcc_amount = 1
            elif int(len(GLOBAL_VARS.sessions) % CONFIG.vcc_uses) == 0:
                vcc_amount = len(GLOBAL_VARS.sessions) / CONFIG.vcc_uses
            else:
                vcc_amount = int(len(GLOBAL_VARS.sessions) / CONFIG.vcc_uses) + 1

            post_json["amount"] = vcc_amount

            response = self.session.post(
                f"{CONFIG.vcc_api_link}/get_vcc",
                json = post_json
            ).json()

            match response["status"]:
                case "success":
                    pass
                case "invalid_key":
                    return "Invalid Key"
                case "no_stock":
                    LOGGER.warn("VCC Api Returned No Stock, Retrying in 5 Seconds...")
                    sleep(5)
                    return self._update_pool()
                case "no_balance":
                    return "No Balance"
                case _:
                    return f"Unknown Error {response['status']}"
            
            for raw_vcc in response["vccs"]:
                
                if raw_vcc in self.used_vccs:
                    continue
                
                for vcc in FILES.vccs:
                    if vcc.raw_vcc == raw_vcc:
                        raw_vcc = None
                        break
                
                if raw_vcc:
                    formatted_vcc: VCC = UTILS_DISCORD.format_vcc(raw_vcc)

                    if not formatted_vcc:
                        LOGGER.error("Unknown VCC Format From Gen!", raw_vcc)
                        continue

                    FILES.vccs.append(formatted_vcc)
                    self.used_vccs.append(raw_vcc)

            if FILES.len_vccs() > amount:
                LOGGER.success("Added VCCs", FILES.len_vccs() - amount, genned_in = perf_counter() - self.last_update)
                self.last_update = perf_counter()
        
        except Exception as e:
            return f"Unknown Exception While Updating VCC Pool! {e}"

        return True
    
    def _check_status(self) -> tuple[str|bool, dict]:
        try:
            post_json = {}

            if CONFIG.vcc_api_key:
                post_json["key"] = CONFIG.vcc_api_key

            response: dict = self.session.get(
                CONFIG.vcc_api_link,
                json = post_json
            ).json()

            if "status" in response.keys():
                match response["status"]:
                    case "success":
                        parameters = {}
                    case "invalid_key":
                        return "Invalid Key", {}
                    case "no_balance":
                        return "No Balance", {}
                    case _:
                        return f"Unknown Error! {response['status']}" , {}
                    
            if CONFIG.vcc_api_key and "balance" in response.keys():
                self.balance = response["balance"]

            if "parameters" in response.keys():
                parameters = response["parameters"]

            return True, parameters
        
        except:
            return "VCC API Is Not Up At The Moment!", {}
        

    def _gen_thread(self):
        while CONFIG.use_gen_vcc:
            while GLOBAL_VARS.sessions and (not FILES.len_vccs()):
                
                if CONFIG.wait_for_all_tokens_to_finish:
                    while len(GLOBAL_VARS.sessions) != FILES.waiting_to_get_vcc:
                        sleep(.1)

                status = self._update_pool()
                
                if status != True:
                   CONFIG.use_gen_vcc = False
                   LOGGER.error("Stopping VCC Gen", status)
                   FILES.forced_parameters = None
                   return

                status, _ = self._check_status()

                if status != True:
                   CONFIG.use_gen_vcc = False
                   LOGGER.error("Stopping VCC Gen", status)
                   FILES.forced_parameters = None
                   return
                
                sleep(10)

            sleep(5)

    def start_gen(self) -> str:
        status, parameters = self._check_status()

        if status != True:
            CONFIG.use_gen_vcc = False
            return status, None
        
        Thread(target = self._gen_thread, daemon=True).start()
        return None, parameters
    
def START_GENS() -> list[dict]|bool:
    statuses = []
    promo_gen = None
    vcc_gen = None

    if CONFIG.use_gen_promo:
        if not CONFIG.promo_api_link:
            promo_gen = PromoGenApiWrapperPersonal()
            statuses.append({
                "status": promo_gen.start_gen(),
                "type": "Promo Gen",
                "balance": promo_gen.balance,
                "provider": "EinTim Gen"
            })
        else:
            promo_gen = PromoGenApiWrapper()
            statuses.append({
                "status": promo_gen.start_gen(),
                "type": "Promo Gen",
                "balance": promo_gen.balance,
                "provider": CONFIG.promo_api_link
            })

    if CONFIG.use_gen_vcc and CONFIG.vcc_api_link:
        vcc_gen = VCCGenApiWrapper()
        status, parameters = vcc_gen.start_gen()

        FILES.forced_parameters = FORCE_PARAMETERS(**parameters) if parameters else None

        statuses.append({
            "status": status,
            "type": "VCC Gen",
            "balance": vcc_gen.balance,
            "provider": CONFIG.vcc_api_link,
        })

    if promo_gen or vcc_gen:
        return statuses
    
    return False


"""
API DOCS:

Check GEN:
    /
    GET
    json = {
    "key": "API_KEY" # optional
    }

    Return, Json:
    {
    "status": "success",
    "balance": "BALANCE", # Optional
    "parameters": { # Optional
        "max_threads": int # 0 Means No Limit Set
        "hide_vccs": bool 
        "minimum_delay": int # 0 Means No Limit Set
        "max_redeem_per_vcc": int # 0 Means No Limit Set
        "allow_turbo": bool
      } # ALL PARAMETERS must be present if used
    }

    {
    "status": "invalid_key",
    }
    
    {
    "status": "no_balance",
    }
Fetch VCC:
    /get_vcc
    POST
    json = {
    "key": "API_KEY" # optional
    "amount": "AMOUNT" # The required amount
    }

    Return, Json:
    {
    "status": "success",
    "vccs": []
    }

    {
    "status": "no_stock",
    }

    {
    "status": "invalid_key",
    }

    {
    "status": "no_balance",
    }
    #Other statuses are considered unknown, will cause the gen to shutdown

Fetch Promo:
    /get_promo
    POST
    json = {
    "key": "API_KEY" # optional
    "amount": "AMOUNT" # The required amount
    }

    Return, Json:
    {
    "status": "success",
    "promos": []
    }

    {
    "status": "no_stock",
    }

    {
    "status": "invalid_key",
    }

    {
    "status": "no_balance",
    }
    #Other statuses are considered unknown, will cause the gen to shutdown

"""