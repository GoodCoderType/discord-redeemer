from Cryptodome.Util.Padding    import pad, unpad
from Cryptodome.PublicKey       import RSA
from Cryptodome.Cipher          import PKCS1_OAEP, AES
from dataclasses                import dataclass, field, asdict
from ruamel.yaml                import YAML
from tls_client                 import Session
from threading                  import Lock, RLock, Thread
from datetime                   import datetime
from random                     import choice
from typing                     import List, Tuple
from base64                     import b64encode, b64decode
from json                       import loads
from time                       import sleep
from os                         import _exit, makedirs, urandom
from re                         import compile, findall, search


yaml = YAML() #global yaml instance should be completely fine
yaml.preserve_quotes = True 
yaml.width = 4096 
yaml.indent(mapping=4, sequence=4, offset=4)

FILE_LOCK       = Lock() 
RESOURCE_LOCK   = RLock() # Wouldn't make sense to use same mutex for files and resources

class Checkout_ids:
    checkout_id = 26
    checkout_air_id = 27

class Redeem_Modes:
    normal = 1
    add_vcc_only = 2
    redeem_promo_only = 3
    remove_vcc_only = 4
    
class Status:
    success             = 1
    proxy_error         = 2
    token_error         = 3
    card_error          = 4
    config_error        = 5
    token_card_error    = 6
    token_rate_limit    = 7
    token_captcha_error = 8
    promo_error         = 9
    token_promo_error   = 10
    token_redeem        = 11
    token_vcc_add       = 12
    token_vcc_remove    = 13

@dataclass
class Metrics:
    redeems: int = 0
    fails: int = 0
    captcha_tokens: int = 0
    auth_errors: int = 0

@dataclass
class FORCE_PARAMETERS:
    max_threads: int
    hide_vccs: bool
    minimum_delay: int
    max_redeem_per_vcc: int
    allow_turbo: int

    def __post_init__(self):
        self.hide_vccs = bool(self.hide_vccs)
        self.allow_turbo = bool(self.allow_turbo)

@dataclass
class GlobalVars:
    metrics: Metrics =  field(default_factory = Metrics)
    hard_stop: bool = False
    paused: bool = False
    sessions: List[Thread] = field(default_factory=list)
    global_sleep_mutex: Lock = Lock()
    last_send = 0
    threads_amount: int = 0
    in_redeem: int = 0
    mode: int = Redeem_Modes.normal



@dataclass
class VCC:
    card_number: str
    expiry_month: int
    expiry_year: int
    cvv: int
    raw_vcc: str
    uses: int = 0
    invalid: bool = False

    def __str__(self):
        return f"{self.card_number}|{self.expiry_month}/{self.expiry_year}|{self.cvv}"
    
    def __repr__(self):
        return UTILS.censor_string(self.card_number) if CONFIG.censor_sensitive_information else f"{self.card_number}|{self.expiry_month}/{self.expiry_year}|{self.cvv}"

@dataclass
class PROMO:
    raw_promo: str
    link: str
    linked_promo: bool = False
    trial_promo: bool = False
    user_trial_offer_id: str = None
    trial_id: str = None

    def __repr__(self):
        return UTILS.censor_string(self.link) if CONFIG.censor_sensitive_information else self.link


@dataclass
class TOKEN:
    raw_line: str
    formatted_token: str
    full_token: str
    linked_promo: PROMO = None

@dataclass
class BILLING:
    person_name: str
    address_2: str
    address: str
    country: str
    postal: str
    state: str
    city: str

@dataclass
class WorkerVars:
    billing_token: str|Status = None
    payment_method: str|Status = None

class MaterialsEncryption:
    def __init__(self):
        self.loaded = False
        
    def init(self, priv: str = None, ext: str = None):   
        self.loaded = True
        self._rsa_private_key = PKCS1_OAEP.new(RSA.import_key(f"-----BEGIN RSA PRIVATE KEY-----\n{priv}\n-----END RSA PRIVATE KEY-----"))
        self._extra = b64decode(self._rsa_private_key.decrypt(b64decode(ext)).decode('utf-8'))
#python -c "from cryptography.hazmat.primitives.asymmetric import rsa; from cryptography.hazmat.primitives import serialization; key = rsa.generate_private_key(public_exponent=65537, key_size=2048); print(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()); print(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode())"
# GEN A PRIVATE KEY / PUBLIC KEY PAIR
    def decrypt_vccs(self, data: str) -> Tuple[list[str], FORCE_PARAMETERS]:
        decoded_data = b64decode(data)

        ciphertext = decoded_data[16:]
        cipher = AES.new(self._extra, AES.MODE_CBC, decoded_data[:16])
        decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)

        vccs = decrypted.split(b"PARAMETERS:")[0].decode('utf-8').splitlines()
        parameters = FORCE_PARAMETERS(**loads(decrypted.split(b"PARAMETERS:")[1].decode('utf-8').replace("'", '"')))
        return vccs, parameters
    
    def raw_decrypt(self, data: str) -> str:
        decoded_data = b64decode(data)

        ciphertext = decoded_data[16:]
        cipher = AES.new(self._extra, AES.MODE_CBC, decoded_data[:16])
        decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)

        return decrypted
    
    def encrypt_vccs(self, data: str, parameters: FORCE_PARAMETERS) -> str:
  
        for parameter, value in vars(parameters).items():
            if isinstance(value, bool):
                setattr(parameters, parameter, int(value))

        iv = urandom(16)
        formatted_data = f"{data}PARAMETERS:{asdict(parameters)}".encode('utf-8')

        cipher = AES.new(self._extra, AES.MODE_CBC, iv)
        padded = pad(formatted_data, AES.block_size)
        base64_encrypted = b64encode(iv + cipher.encrypt(padded)).decode('utf-8')

        full_message = f"0xV{base64_encrypted}"
        return full_message


class Config:
    def __init__(self):
        self.load_config()

    def load_config(self):
        self._config = yaml.load(open("./config.yaml", "r", encoding="utf-8", errors="ignore"))

    def _save_config(self):
        yaml.dump(self._config, open("./config.yaml", "w", encoding="utf-8", errors="ignore"))
        self.load_config()

    @property
    def rotate_proxies(self) -> bool:
        return self._config["client"]["rotate_proxies"]

    @property
    def static_timezone(self) -> bool:
        return self._config["client"]["static_timezone"]
    
    @static_timezone.setter
    def static_timezone(self, status: bool):
        self._config["client"]["static_timezone"] = status
        self._save_config()
        
    @property
    def client_timeout(self) -> int:
        return self._config["client"]["timeout"]
    
    @property
    def gen_timeout(self) -> int:
        return self._config["client"]["timeout_gen"]
    
    @property
    def client_retries(self) -> int:
        return self._config["client"]["retries_per_request"]
    
    @property
    def use_websocket(self) -> bool:
        return self._config["client"]["use_websocket"]
    
    @property
    def censor_sensitive_information(self) -> bool:
        return self._config["logger"]["censor_sensitive_information"]
    
    @censor_sensitive_information.setter
    def censor_sensitive_information(self, status: bool):
        self._config["logger"]["censor_sensitive_information"] = status
        self._save_config()

    @property
    def vcc_uses(self) -> int:
        return self._config["resources"]["vcc_uses"]
    
    @vcc_uses.setter
    def vcc_uses(self, amount: int):
        self._config["resources"]["vcc_uses"] = amount
        self._save_config()

    @property
    def look_for_card_on_token(self) -> bool:
        return self._config["resources"]["look_for_card_on_token"]

    @property
    def use_card_from_account_if_invalid(self) -> bool:
        return self._config["resources"]["use_card_from_account_if_invalid"]
    
    @property
    def proxyless(self) -> bool:
        return self._config["client"]["proxyless"]
    
    @proxyless.setter
    def proxyless(self, status):
        self._config["client"]["proxyless"] = status
        self._save_config()

    @property
    def billing(self) -> BILLING:
        return BILLING(**self._config["resources"]["billing"])
    
    @property
    def token_unflagger(self) -> bool:
        return self._config["tokens"]["token_unflagger"]
    
    @property
    def check_billing(self) -> bool:
        return self._config["tokens"]["check_billing"]
    
    @property
    def remove_vcc(self) -> bool:
        return self._config["tokens"]["remove_vcc"]

    @remove_vcc.setter
    def remove_vcc(self, status):
        self._config["tokens"]["remove_vcc"] = status
        self._save_config()

    @property
    def logger_level(self) -> int:
        return self._config["logger"]["level"]
    
    @property
    def show_extra_info(self) -> bool:
        return self._config["logger"]["show_extra_info"]
    
    @property
    def connector(self) -> str:
        return self._config["logger"]["connector"]
    
    @property
    def info_icon(self) -> str:
        return self._config["logger"]["icons"]["info"]
    
    @property
    def extra_info_icon(self) -> str:
        return self._config["logger"]["icons"]["extra_info"]
    
    @property
    def error_icon(self) -> str:
        return self._config["logger"]["icons"]["error"]
    
    @property
    def warn_icon(self) -> str:
        return self._config["logger"]["icons"]["warn"]
    
    @property
    def success_icon(self) -> str:
        return self._config["logger"]["icons"]["success"]
    
    @property
    def info_color(self) -> str:
        return self._config["logger"]["colors"]["info"]
    
    @property
    def info_color_end(self) -> str:
        return self._config["logger"]["colors"]["info_end"]
    
    @property
    def extra_info_color(self) -> str:
        return self._config["logger"]["colors"]["extra_info"]
    
    @property
    def extra_info_color_end(self) -> str:
        return self._config["logger"]["colors"]["extra_info_end"]
    
    @property
    def error_color(self) -> str:
        return self._config["logger"]["colors"]["error"]
    
    @property
    def error_color_end(self) -> str:
        return self._config["logger"]["colors"]["error_end"]
    
    @property
    def warn_color(self) -> str:
        return self._config["logger"]["colors"]["warn"]
    
    @property
    def warn_color_end(self) -> str:
        return self._config["logger"]["colors"]["warn_end"]
    
    @property
    def success_color(self) -> str:
        return self._config["logger"]["colors"]["success"]
    
    @property
    def success_color_end(self) -> str:
        return self._config["logger"]["colors"]["success_end"]
    @property
    def timestamp_color(self) -> str:
        return self._config["logger"]["colors"]["timestamp"]
    @property
    def sleep_duration(self) -> float:
        return self._config["misc"]["sleep"]["redeem"]
    
    @sleep_duration.setter
    def sleep_duration(self, value: float):
        self._config["misc"]["sleep"]["redeem"] = value
        self._save_config()

    @property
    def minimum_redeem_time(self) -> bool:
        return self._config["misc"]["sleep"]["minimum_redeem_time"]

    @property
    def threads_redeem_one_by_one(self) -> bool:
        return self._config["misc"]["sleep"]["threads_redeem_one_by_one"]
    
    @property
    def auth_retry(self) -> int:
        return self._config["resources"]["auth_retry"]
    
    @property
    def output_different_folders(self) -> bool:
        return self._config["resources"]["output_different_folders"]
    
    @property
    def turbo_mode(self) -> bool:
        return self._config["resources"]["turbo_mode"]
    
    @turbo_mode.setter
    def turbo_mode(self, value: bool):
        self._config["resources"]["turbo_mode"] = value
        self._save_config()

    @property
    def use_gen_promo(self) -> bool:
        return self._config["resources"]["use_gen_promo"]
    
    @use_gen_promo.setter
    def use_gen_promo(self, value: bool):
        self._config["resources"]["use_gen_promo"] = value
        self._save_config()

    @property
    def use_gen_vcc(self) -> bool:
        return self._config["resources"]["use_gen_vcc"]
    
    @use_gen_vcc.setter
    def use_gen_vcc(self, value: bool):
        self._config["resources"]["use_gen_vcc"] = value
        self._save_config()

    @property
    def vcc_api_link(self) -> bool:
        return self._config["api_integration"]["vcc_api_link"]
    
    @vcc_api_link.setter
    def vcc_api_link(self, value: bool):
        self._config["api_integration"]["vcc_api_link"] = value
        self._save_config()
    @property
    def wait_for_all_tokens_to_finish(self) -> bool:
        return self._config["api_integration"]["wait_for_all_tokens_to_finish"]
    
    @property
    def promo_api_link(self) -> bool:
        return self._config["api_integration"]["promo_api_link"]
    
    @promo_api_link.setter
    def promo_api_link(self, value: bool):
        self._config["api_integration"]["promo_api_link"] = value
        self._save_config()

    @property
    def promo_api_key(self) -> bool:
        return self._config["api_integration"]["promo_api_key"]
    
    @promo_api_key.setter
    def promo_api_key(self, value: bool):
        self._config["api_integration"]["promo_api_key"] = value
        self._save_config()

    @property
    def vcc_api_key(self) -> bool:
        return self._config["api_integration"]["vcc_api_key"]
    
    @vcc_api_key.setter
    def vcc_api_key(self, value: bool):
        self._config["api_integration"]["vcc_api_key"] = value
        self._save_config()

    @property
    def set_1(self) -> bool:
        return self._config["resources"]["set_1"]
    
    @property
    def set_2(self) -> bool:
        return self._config["resources"]["set_2"]
    
    @property
    def set_3(self) -> bool:
        return self._config["resources"]["set_3"]
        
    @property
    def customize_bio(self) -> bool:
        return self._config["tokens"]["token_customizer"]["customize_bio"]
    
    @customize_bio.setter
    def customize_bio(self, value: bool):
        self._config["tokens"]["token_customizer"]["customize_bio"] = value
        self._save_config()

    @property
    def bio_descriptions(self) -> List[str]:
        return self._config["tokens"]["token_customizer"]["bio_descriptions"]
    
    @property
    def customize_nick(self) -> bool:
        return self._config["tokens"]["token_customizer"]["customize_nick"]
    
    @customize_nick.setter
    def customize_nick(self, value: bool):
        self._config["tokens"]["token_customizer"]["customize_nick"] = value
        self._save_config()

    @property
    def change_token(self) -> bool:
        return self._config["tokens"]["token_customizer"]["password_less_token_changer"]  
    
    @change_token.setter
    def change_token(self, value: bool):
        self._config["tokens"]["token_customizer"]["password_less_token_changer"] = value
        self._save_config()

    @property
    def change_password(self) -> bool:
        return self._config["tokens"]["token_customizer"]["change_pass"]
    
    @change_password.setter
    def change_password(self, value: bool):
        self._config["tokens"]["token_customizer"]["change_pass"] = value
        self._save_config()

    @property
    def passwords(self) -> List[str]:
        return self._config["tokens"]["token_customizer"]["passwords"]
    
    @property
    def nicks(self) -> List[str]:
        return self._config["tokens"]["token_customizer"]["nicks"]
    
    @property
    def fetch_new_vcc(self) -> bool:
        return self._config["tokens"]["fetch_new_vcc"]
    
    @fetch_new_vcc.setter
    def fetch_new_vcc(self, value: bool):
        self._config["tokens"]["fetch_new_vcc"] = value
        self._save_config()
    
    @property
    def pause_key(self) -> str:
        return self._config["misc"]["pause"]["pause_key"]
    
    @property
    def pause_after_redeems(self) -> int:
        return self._config["misc"]["pause"]["pause_after_redeems"]
    
    @property
    def webhook_url(self) -> str:
        return self._config["integrations"]["webhook"]["url"]
    
    @webhook_url.setter
    def webhook_url(self, new_url: str):
        self._config["integrations"]["webhook"]["url"] = new_url
        self._save_config()

    @property
    def webhook_msg_id(self) -> str:
        return self._config["integrations"]["webhook"]["message_id"]
    
    @webhook_msg_id.setter
    def webhook_msg_id(self, new_message_id: str):
        self._config["integrations"]["webhook"]["message_id"] = new_message_id
        self._save_config()

    @property
    def webhook_enabled(self) -> bool:
        return self._config["integrations"]["webhook"]["enabled"]
    
    @webhook_url.setter
    def webhook_enabled(self, status: str):
        self._config["integrations"]["webhook"]["enabled"] = status
        self._save_config()
        
    @property
    def bot_token(self) -> str:
        return self._config["integrations"]["bot"]["token"]
    
    @property
    def bot_enabled(self) -> bool:
        return self._config["integrations"]["bot"]["enabled"]
    
    @bot_enabled.setter
    def bot_enabled(self, status: bool):
        self._config["integrations"]["bot"]["enabled"] = status
        self._save_config()

    @property
    def bot_logs_id(self) -> int:
        return self._config["integrations"]["bot"]["logs_id"]
    
    @property
    def owner_id(self) -> List[int]:
        return self._config["integrations"]["bot"]["owner_id"]
    
    @property
    def auth_username(self) -> str:
        return self._config["auth"]["username"]
    
    @auth_username.setter
    def auth_username(self, new_username: str):
        self._config["auth"]["username"] = new_username
        self._save_config()

    @property
    def auth_password(self) -> str:
        return self._config["auth"]["password"]
    
    @auth_password.setter
    def auth_password(self, new_password: str):
        self._config["auth"]["password"] = new_password
        self._save_config()

    @property
    def billing_config_code(self) -> int:
        return self._config["resources"]["billing_spoofer_code"]
    
    @property
    def sequential_vcc_fetch(self) -> bool:
        return self._config["resources"]["sequential_vcc_fetch"]
    
    @billing_config_code.setter
    def billing_config_code(self, new_code: int):
        self._config["resources"]["billing_spoofer_code"] = new_code
        self._save_config()
    
class Files:
    def __init__(self):
        self.output_directory = "./output"
        self.vccs: List[VCC] = []
        self.waiting_to_get_vcc = 0
        self.active_vcc: VCC = None
        self.raw_vcc_list: List[str] = None
        self.forced_parameters: FORCE_PARAMETERS = None
        self.update_materials()

        if CONFIG.output_different_folders:
            self.output_directory = f'./output/{datetime.now().strftime("%d-%m-%Y~%H-%M-%S")}'
            makedirs(self.output_directory, exist_ok=True)

    
    def update_materials(self):
        with RESOURCE_LOCK:
            self.tokens, self.linked_tokens = self.load_tokens()
            self.raw_vcc_list = self.read_file("vccs")
            self.promos: List[PROMO] = [promo for item in self.read_file("promos") if (promo := UTILS_DISCORD.format_promo(item)) is not None]

            if self.raw_vcc_list and self.raw_vcc_list[0][:3] == "0xV":
                while not MATERIALS_ENCRYPTION.loaded:
                    return

                self.raw_vcc_list, parameters = MATERIALS_ENCRYPTION.decrypt_vccs(self.raw_vcc_list[0].split("0xV")[1])
                self.forced_parameters = parameters

            self.vccs = [vcc for item in self.raw_vcc_list if (vcc := UTILS_DISCORD.format_vcc(item)) is not None]

            if not self.active_vcc:
                return
            
            for vcc in self.vccs:
                if self.active_vcc.raw_vcc == vcc.raw_vcc:
                    vcc.uses = self.active_vcc.uses

    def load_tokens(self):
        with RESOURCE_LOCK:
            raw_tokens = self.read_file("tokens")

            tokens, linked_tokens = [], []

            for raw_token in raw_tokens:
                formatted = UTILS_DISCORD.format_token(raw_token)
                
                if not formatted:
                    continue

                linked_tokens.append(formatted) if formatted.linked_promo else tokens.append(formatted)
            
            return tokens, linked_tokens

    def get_token(self) -> Tuple[str, TOKEN]:
        with RESOURCE_LOCK:
            token: TOKEN
            
            if self.linked_tokens:
                token = self.linked_tokens.pop(0)
                return token.raw_line, token, token.linked_promo
            
            elif self.tokens:
                token = self.tokens.pop(0)
                return token.raw_line, token, None
            
        return None, None, None

    def get_promo(self) -> PROMO|None:
        with RESOURCE_LOCK:
            if self.promos:
                return self.promos.pop(0)
            
            elif CONFIG.use_gen_promo:
                while not self.promos:
                    sleep(1)
                
                return self.promos.pop(0)
            
    def re_add_promo(self, promo: PROMO):
        with RESOURCE_LOCK:
            self.promos.append(promo) if not promo.linked_promo else None

    def len_vccs(self) -> int:
        return sum(1 for vcc in self.vccs if vcc.uses < CONFIG.vcc_uses)
    
    def promos_left(self) -> bool:
        return CONFIG.use_gen_promo or self.promos or GLOBAL_VARS.mode in (Redeem_Modes.add_vcc_only, Redeem_Modes.remove_vcc_only)

    def vccs_left(self) -> bool:
        return FILES.len_vccs() or CONFIG.use_gen_vcc or GLOBAL_VARS.mode == Redeem_Modes.redeem_promo_only
    
    def promo_token_pair_left(self) -> bool:
        return FILES.tokens and FILES.promos_left() or FILES.linked_tokens 
    
    def update_vcc_list(self, raw_vcc: str, delete: bool = False, output: bool = False, replace: str = None) -> None:
        if delete:
            if not FILES.forced_parameters:
                self.delete_a_line("input", "vccs", raw_vcc)
                return
            else:
                if raw_vcc in self.raw_vcc_list:
                    self.raw_vcc_list.pop(self.raw_vcc_list.index(raw_vcc))
                    
                encrypted = MATERIALS_ENCRYPTION.encrypt_vccs("\\n".join(self.raw_vcc_list), FILES.forced_parameters)
                self.rewrite_input_file("vccs", encrypted)
                return
        
        if output:
            if not FILES.forced_parameters:
                self.output("input", "vccs", raw_vcc)
                return
            else:
                self.raw_vcc_list.append(raw_vcc)
                encrypted = MATERIALS_ENCRYPTION.encrypt_vccs("\\n".join(self.raw_vcc_list), FILES.forced_parameters)
                self.rewrite_input_file("vccs", encrypted)
                return
            
        if replace:
            if not FILES.forced_parameters:
                self.replace_a_line("input", "vccs", raw_vcc, replace)
                return replace
            else:
                if raw_vcc in self.raw_vcc_list:
                    self.raw_vcc_list[self.raw_vcc_list.index(raw_vcc)] = replace

                encrypted = MATERIALS_ENCRYPTION.encrypt_vccs("\\n".join(self.raw_vcc_list), FILES.forced_parameters)
                self.rewrite_input_file("vccs", encrypted)
                return replace
            
    def get_vcc(self) -> VCC|str:
        if GLOBAL_VARS.mode in (Redeem_Modes.remove_vcc_only, Redeem_Modes.redeem_promo_only):
            return "USING FROM ACCOUNT"
        
        with FILE_LOCK:
            FILES.waiting_to_get_vcc += 1
            
        vcc = self.fetch_vcc()

        if not vcc and CONFIG.use_gen_vcc:
            while not vcc:
                sleep(1)
                vcc = self.fetch_vcc()

        with FILE_LOCK:
            FILES.waiting_to_get_vcc -= 1
            
        return vcc
    
    def _shift_vcc_list(self):
        return_vcc: VCC = self.active_vcc
        self.vccs.remove(self.active_vcc)
        self.vccs.append(self.active_vcc)
        self.active_vcc = None
        return return_vcc
    
    def fetch_vcc(self) -> VCC|None:
        with RESOURCE_LOCK:
            if self.active_vcc and self.active_vcc.uses < CONFIG.vcc_uses:
                self.active_vcc.raw_vcc = self.update_vcc_list(self.active_vcc.raw_vcc, replace=self.active_vcc.raw_vcc.replace(f":uses:{self.active_vcc.uses}", f":uses:{self.active_vcc.uses + 1}"))
                self.active_vcc.uses += 1

                if self.active_vcc.uses == CONFIG.vcc_uses:
                    self.delete_a_line("input", "vccs", self.active_vcc.raw_vcc)

                if CONFIG.sequential_vcc_fetch:
                    return self._shift_vcc_list()

                return self.active_vcc
            
            self.active_vcc = next((vcc for vcc in self.vccs if vcc.uses < CONFIG.vcc_uses), None)

            if not self.active_vcc:
                return None
            
            if not self.active_vcc.uses:
                self.active_vcc.raw_vcc = self.active_vcc.raw_vcc.replace(":uses:0", "")
                self.active_vcc.raw_vcc = self.update_vcc_list(self.active_vcc.raw_vcc, replace=f"{self.active_vcc.raw_vcc}:uses:1")
                self.active_vcc.uses    = 1

                if CONFIG.sequential_vcc_fetch:
                    return self._shift_vcc_list()
                
                return self.active_vcc

            return self.fetch_vcc()

    def decrease_vcc_counter(self, vcc: VCC|str):
        if type(vcc) == str:
            return
        
        with RESOURCE_LOCK:
            for vcc2 in self.vccs:
                if vcc2.card_number == vcc.card_number and not vcc2.invalid:
                    if vcc2.uses == CONFIG.vcc_uses:
                        vcc2.raw_vcc = vcc2.raw_vcc.replace(f":uses:{vcc2.uses}", f":uses:{vcc2.uses - 1}")
                        self.update_vcc_list(vcc2.raw_vcc, output=True)
                    else:
                        vcc2.raw_vcc = self.update_vcc_list(vcc2.raw_vcc, replace = vcc2.raw_vcc.replace(f":uses:{vcc2.uses}", f":uses:{vcc2.uses - 1}"))

                    vcc2.uses -= 1

    def remove_vcc(self, vcc: VCC|str):
        if type(vcc) == str:
            return
        
        with RESOURCE_LOCK:
            for vcc2 in self.vccs:
                if vcc2.raw_vcc == vcc.raw_vcc:
                    vcc2.uses = CONFIG.vcc_uses + 1
                    vcc2.invalid = True
                    self.update_vcc_list(vcc2.raw_vcc, delete=True)

    def get_proxies(self) -> List[str]:
        raw_proxies = open("./input/proxies.txt", "r", encoding="utf-8", errors="ignore").read().splitlines()
        return [proxy.split("//")[1] if "//" in proxy else proxy for proxy in raw_proxies]    
                   
    def get_proxy(self) -> str|None:
        proxies = self.get_proxies()

        if proxies:
            proxy = choice(proxies)
            return proxy.split("//")[1] if "//" in proxy else proxy # Format it
        
        return None
    
    def output_token_promo(self, raw_token: str, promo: PROMO, output: str, remove_promo: bool = False):
        if not promo:
            self.output_and_remove("tokens", raw_token, output)

        elif not promo.linked_promo:
            self.output_and_remove("tokens", raw_token, output)

            if not remove_promo:
                self.re_add_promo(promo)
            else:
                self.output_and_remove("promos", promo.raw_promo, "error_promo")
        else:
            self.delete_a_line("input", "promos", promo.raw_promo)

            if promo.link and promo.link in raw_token:
                self.output_and_remove("tokens", raw_token, output)
            else:
                self.delete_a_line("input", "tokens", raw_token)
                
                if not promo.trial_promo:
                    self.output(self.output_directory, output, f"{raw_token}|https://promos.discord.gg/{promo.link}")

    def output_and_remove(self, line_file: str, line: str, file: str):
        """
        line_file (str): The file where the line is located.
        line (str): Line to delete from file.
        file (str): The output file name where the line should be appended.
        """

        self.delete_a_line("input", line_file, line)
        self.output(self.output_directory, file, line)

    def read_file(self, file: str) -> List[str]:
        return open(f"./input/{file}.txt", "r", encoding="utf-8", errors="ignore").read().splitlines()
    
    def output(self, directory: str, file: str, data: List[str]|str) -> None:
        if not data:
            return
        
        with FILE_LOCK:
            if type(data) == list:
                data = "\n".join(data)
            open(f"{directory}/{file}.txt", "a", encoding="utf-8", errors="ignore").write(f"{data}\n")
            
    def rewrite_input_file(self, file: str, data: List[str]|str) -> None:
        with FILE_LOCK:
            if type(data) == list:
                data = "\n".join(data)
            open(f"./input/{file}.txt", "w", encoding="utf-8", errors="ignore").write(data)
    
    def delete_a_line(self, directory: str, file: str, data: str) -> None:
        if not data:
            return
        
        with FILE_LOCK:
            open(f"{directory}/{file}.txt", "a", encoding="utf-8", errors="ignore").close() # Make the file if it doesn't exist
            lines = open(f"{directory}/{file}.txt", "r", encoding="utf-8", errors="ignore").read().splitlines()
            open(f"{directory}/{file}.txt", "w", encoding="utf-8", errors="ignore").write("\n".join(line for line in lines if data not in line))

    def clear_file(self, directory: str, file: str) -> None:
        with FILE_LOCK:
            open(f"{directory}/{file}.txt", "w", encoding="utf-8", errors="ignore").close()
            
    def replace_a_line(self, directory: str, file: str, data: str, line_replace: str) -> str:
        if not line_replace:
            return
        
        with FILE_LOCK:
            open(f"{directory}/{file}.txt", "a", encoding="utf-8", errors="ignore").close() # Make the file if it doesn't exist
            lines = open(f"{directory}/{file}.txt", "r", encoding="utf-8", errors="ignore").read().splitlines()
            open(f"{directory}/{file}.txt", "w", encoding="utf-8", errors="ignore").write("\n".join(line_replace if data in line else line for line in lines) + "\n")
            return line_replace

class Utils:
    def censor_string(self, input: str) -> str:
        if not input:
            return "***"
        
        length = len(input)
        toCensor = length / 100 * 50 # censor 50% of the string
        start = int(length - toCensor)
        return "***" + input[start:]

    @staticmethod
    def exit():
        _exit(0)

class UtilsDiscord:
    
    def __init__(self):
        Thread(target = self._scrape_info, daemon=True).start()

    def _scrape_info(self):
        client = Session()

        while True:
            try:
                details                 = client.get("https://discord.eintim.dev/discord_info").json()
                self.stripe_key         = details["stripe-key"]
                self.x_super_properties = details["desktop"]["decoded-x-super-properties"]
                self.discord_user_agent = details["desktop"]["user-agent"]
                self.browser_user_agent = details["browser"]["user-agent"]
                

                details                 = client.get("https://m.stripe.network/inner.html").text
                data_matches            = search(r'e\.src\s*=\s*"([^"]+)"', details).group(1)
                stripe_endpoint         = data_matches

                details                 = client.get(f"https://m.stripe.network/{stripe_endpoint}").text
                data_matches            = search(r'l\s*=\s*"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})"', details)
                self.stripe_salt_hash   = data_matches.group(1)

                details                 = client.get("https://js.stripe.com/basil/stripe.js").text
                data_matches            = search(r'(?<=STRIPE_JS_BUILD_SALT\s)[0-9a-f]{10}', details)
                self.stripe_user_agent  = data_matches.group()
  
                sleep(290)
            except:
                sleep(10)

    def format_vcc(self, vcc: str) -> VCC|None:
        date_matches = search(r"(?<!\d)(\d{2})[\/:]?(\d{2})(?!\d)", vcc)

        if date_matches == None:
            return None
        
        expiry_month = date_matches.group(1)
        expiry_year = date_matches.group(2)

        cvv_matches = search(r"\b(\d{3})\b", vcc)

        if cvv_matches == None:
            return None
        
        cvv = cvv_matches.group(0)
        
        card_number_matches = search(r"\d{16}|\d{15}", vcc)

        if card_number_matches == None:
            return None
        
        uses_matches = search(r":uses:(\d+)", vcc)

        uses_matches = 0 if uses_matches == None else int(uses_matches.group(1))

        card_number = card_number_matches.group(0)

        return VCC(card_number, expiry_month, expiry_year, cvv, vcc, uses_matches)


    def format_token(self, token: str) -> TOKEN:
        """
        This function removes additional data from the token line and extracts the linked promo(if any)

        :param token: Discord token to be formatted
        :return: Formatted Discord token dataclass
        """
        raw_promo   = search(r"https:\/\/(promos\.discord\.gg|discord\.com\/billing\/promotions)\/(.*)", token)
        raw_token   = search(r"(mfa\.[\w-]{84}|[\w-]{24}\.[\w-]{6}\.[\w-]{38}|[\w-]{24}\.[\w-]{6}\.[\w-]{27}|[\w-]{26}\.[\w-]{6}\.[\w-]{38})", token)
        full_token  = None

        if not raw_token:
            return
        
        full_token = raw_token[1]

        if ":" in token.replace("https:", ""):
            full_token = f"{token.split(':')[0]}:{token.split(':')[1]}:{raw_token[1]}" if len(token.replace("https:", "").split(":")) == 3 else f"{token.split(':')[0]}:{raw_token[1]}"

        if raw_promo: 
            promo = PROMO(raw_promo = raw_promo[0], link = raw_promo[2], linked_promo = True)
            return TOKEN(token,  raw_token[1], full_token, linked_promo = promo)
        else:
            return TOKEN(token, raw_token[1], full_token)
    
    def format_promo(self, raw_promo: str) -> str:
        if not raw_promo:
            return
        
        if "promos.discord.gg/" in raw_promo:
            promo = raw_promo.split("promos.discord.gg/")[1]

        elif "discord.com/billing/promotions/" in raw_promo:
            promo = raw_promo.split("discord.com/billing/promotions/")[1]

        elif "discord.com/billing/partner-promotions/" in raw_promo:
            promo = raw_promo.split("discord.com/billing/partner-promotions/")[1]

        promo = promo.strip() # Some promos have spaces
        return PROMO(raw_promo, promo)


MATERIALS_ENCRYPTION = MaterialsEncryption()
UTILS_DISCORD = UtilsDiscord()
GLOBAL_VARS = GlobalVars()
CONFIG = Config()
UTILS = Utils()
FILES = Files()