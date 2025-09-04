from cryptography.hazmat.primitives.asymmetric  import rsa, padding
from cryptography.hazmat.primitives             import serialization, hashes
from cryptography.hazmat.backends               import default_backend
from websocket                                  import create_connection
from json                                       import dumps, loads
from time                                       import sleep

from modules.utils.utils                        import UTILS_DISCORD, CONFIG
from modules.client.discord                     import DiscordWrapper
from user_agents                                import parse
from websocket                                  import create_connection
from threading                                  import Thread, Lock
from datetime                                   import datetime
from random                                     import randint
from time                                       import sleep, time, perf_counter
from json                                       import dumps, loads, JSONDecodeError
from uuid                                       import uuid4
from re                                         import findall
import base64
class WebSocket:
    def __init__(self):
        self.ws = None
        self.nonce_proof =  None
        self.fingerprint = None
        self.t_token = None
        self.started = False
        self.alive = True

    def open_ws(self):

        self.ws = create_connection("wss://remote-auth-gateway.discord.gg/?v=2", header={'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",'Accept-Encoding': 'gzip, deflate, br','Accept-Language': 'en-US,en;q=0.9','Cache-Control': 'no-cache','Origin': 'https://discord.com','Pragma': 'no-cache','Sec-Websocket-Extensions': 'permessage-deflate; client_max_window_bits',})
        self.started = True

        while self.alive:
            ws_data_recv = loads(self.ws.recv())

            match ws_data_recv['op']:
                case "nonce_proof":
                    self.nonce_proof = ws_data_recv['encrypted_nonce']

                case "pending_remote_init":
                    self.fingerprint = ws_data_recv['fingerprint']

                case "pending_login":
                    self.t_token = ws_data_recv['ticket']
                    self.ws.close()
                    return

            sleep(.5)

    def send_data(self, json):
        self.ws.send(dumps(json))

class DiscordEncryption:

    def make_url_safe(self, data):
        base64_str = base64.b64encode(bytes(data)).decode('utf-8')
        url_safe_base64 = base64_str.replace('/', '_').replace('+', '-').rstrip('=')
        return url_safe_base64
    
    def encode_base64(self, data):
        return base64.b64encode(data).decode('utf-8')

    def decode(self, encoded_data):
        decoded_data = base64.b64decode(encoded_data)
        return bytes(decoded_data)
    
    def decrypt_encrypted(self, private_key, encrypted_data):

        decrypted_data = private_key.decrypt(
            encrypted_data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted_data

    def generate_rsa_key(self):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        public_key = private_key.public_key()

        return private_key, public_key

    def export_public_key_spki(self, public_key):

        spki_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        return self.encode_base64(spki_bytes)
    
DISCORD_ENCRYPTION = DiscordEncryption()

class WebsocketDiscord: # Autifity Discord Filler WS (Couldn't be bothered to code another one)
    def __init__(self, 
        token: str,
        build_number: int,
        discord_wrapper: DiscordWrapper,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ):
        """
        Initialize the WebsocketDiscord class.

        Parameters:
            token (str): The authentication token for Discord.
            build_number (int): The build number of the Discord client.
            user_agent (str, optional): The user agent string for identifying the client. Defaults to a common user agent string for Chrome.

        Attributes:
            _heartbeat_thread (Thread): Thread for handling heartbeats.
            _ws_active (bool): Indicates if WebSocket should be active. This Specifies If The WebSocket Closes If It Should Be Open Again.
            _ws_online (bool): Indicates if WebSocket is online (connected).
            _setup (bool): Indicates if the WebSocket setup is complete.
            _lock (Lock): Lock for thread safety.
            _ws (WebSocket): WebSocket connection object.
            _build_number (int): Discord client build number.
            _user_agent (str): User agent for identifying the client.
            _token (str): Authentication token for Discord.
            _session_token (str): Token associated with the current session.
            session_id (str): Unique identifier for the current session.
        """

        self._heartbeat_thread  = None
        self._ws_active         = False
        self._ws_online         = False
        self._setup             = False

        self._lock              = Lock()
        self._ws                = None

        self._session_token     = None
        self._build_number      = build_number
        self._user_agent        = user_agent
        self._token             = token
        self._discord_wrapper   = discord_wrapper
        
        self.session_id         = None
        self.token_info         = {
            "token"         : token,
            "require_verify": None,
            "name"          : None,
            "guilds"        : [],
            "messages"      : {
                "sledge_hammer": []
            }
        }
        
    def close_websocket(self):
        """
        Close the WebSocket connection.

        This method sets the WebSocket and heartbeat thread to inactive and closes the WebSocket connection.
        """
        if not CONFIG.use_websocket:
            return
        
        try:
            self._close()
        except:
            pass
    def start_websocket(self) -> bool:
        """
        Start the WebSocket connection.

        This method initiates the WebSocket connection in a separate thread and waits until the WebSocket setup is complete.
        If the connection is not online after setup, it closes the WebSocket.

        Returns:
            bool: True if the WebSocket connection is successfully started, False otherwise.
        """
        if not CONFIG.use_websocket:
            return True
        
        Thread(target=self._websocket_manager, daemon=True).start()

        while not self._setup:
            sleep(.5)
        
        if not self._ws_online:
            self._close()
            return
        
        return True
    
    def _websocket_manager(self):
        self._ws_active = True

        while self._ws_active:

            if not self._open_websocket():
                self._ws_active = False
                return
            
            self._heartbeat_thread = Thread(target=self._heartbeat, daemon=True)
            self._heartbeat_thread.start()

            match self._read_messages():
                case "close":
                    self._heartbeat_thread.join()
                    break

                case "crash":
                    self._heartbeat_thread.join()


    
    def _read_messages(self) -> str:
        while self._ws_active:
            try:

                with self._lock:
                    loads(self._ws.recv())

            except:
                if not self._ws_active:
                    return "close"
                
                self._ws_online = False
                self._heartbeat_thread.join()
                return "crash"

        return "close"

    def _close(self):
        try:
            self._ws_active = False
            self._ws_online = False
            
            self._heartbeat_thread.join() if self._heartbeat_thread else None
            self._ws.close()
        except:
            pass
            
    def _open_websocket(self) -> bool:
        for _ in range(5):
            try:

                self._ws = create_connection(
                    "wss://gateway.discord.gg/?encoding=json&v=9", 
                    header = self._get_websocket_headers
                )
                
                self._ws.send(self._get_websocket_hello)

                while not self.session_id:
                    response = loads(self._ws.recv())

                    if response['op'] == 0 and response['t'] == "READY":
                        self._session_token  = response["d"]["analytics_token"]
                        self.session_id      = response["d"]["session_id"]
                        self._set_user_data(response["d"])

                self._ws_online = True
                break
            
            except:
                self._ws_online = False
        
        self._setup = True
        return self._ws_online
    
    def _heartbeat(self):
        while self._ws_online:
            try:
                with self._lock:      
                    self._ws.send(
                        dumps({
                            "op": 1, 
                            "d": None
                        })
                    )

                self._send_science(int(str(datetime.now().timestamp() * 1000000)[:13]))

                for _ in range(40):
                    sleep(0.5)
                    if not self._ws_online:
                        return
                       
            except:
                self._ws_online = False

    def _send_science(self, timestamp: int):
        payload = {
            "token": self._session_token,
            "events": [
                {
                   "type"                                       : "client_heartbeat",
                   "properties": {
                     "client_track_timestamp"                   : timestamp,
                     "client_heartbeat_session_id"              : str(uuid4()),
                     "client_heartbeat_initialization_timestamp": int(timestamp) - randint(30000,50000),
                     "client_heartbeat_version"                 : 17,
                     "client_performance_memory"                : 0,
                     "accessibility_features"                   : 256,
                     "rendered_locale"                          : "en-US",
                     "uptime_app"                               : 2,
                     "client_rtc_state"                         : "DISCONNECTED",
                     "client_app_state"                         : "unfocused",
                     "client_send_timestamp"                    : int(timestamp) - randint(30000,50000)
                   }
                 }
              ]
        }

        self._discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/science",
            "POST",
            json=dumps(payload), 
            timeout_seconds=10
        )
    
    def _set_user_data(self, data: dict):
        match data.get("required_action", "NO_VERIFY"):
            case "REQUIRE_VERIFIED_PHONE":
                self.token_info["require_verify"] = "phone"

            case "REQUIRE_VERIFIED_EMAIL":
                self.token_info["require_verify"] = "email"
                        
        self.token_info["name"] = data["user"]["username"]

    @property
    def _get_websocket_hello(self) -> dict:
        return dumps({
            "op": 2,
            "d": {
                "token": self._token,
                "capabilities": 16381,
                "properties": {
                    "os"                                        : "Windows",
                    "browser"                                   : UTILS_DISCORD.x_super_properties["browser"],
                    "device"                                    : "",
                    "system_locale"                             : "en-US",
                    "browser_user_agent"                        : self._user_agent,
                    "browser_version"                           : UTILS_DISCORD.x_super_properties["browser_version"],
                    "os_version"                                : UTILS_DISCORD.x_super_properties["os_version"],
                    "referrer"                                  : "https://discord.com/",
                    "referring_domain"                          : "discord.com",
                    "referrer_current"                          : "",
                    "referring_domain_current"                  : "",
                    "release_channel"                           : "stable",
                    "client_build_number"                       : UTILS_DISCORD.x_super_properties["client_build_number"],
                    "has_client_mods"                           : False,
                    "client_event_source"                       : None,
                    "is_fast_connect"                           : False,
                    "latest_headless_tasks"                     : [],
                    "latest_headless_task_run_seconds_before"   : None,
                    "gateway_connect_reasons"                   : "AppSkeleton",
                    "client_app_state"                          : "focused",
                    "client_launch_id"                          : self._discord_wrapper.client_launch_id
                },
                "presence": {
                    "status"    : "online",
                    "since"     : 0,
                    "activities": [],
                    "afk"       : False
                },
                "compress": False,
                "client_state": {
                    "guild_versions"    : {}
                }
            }
        })
    
    @property
    def _get_websocket_headers(self) -> dict:
        return {
            "User-Agent": self._user_agent,
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Origin": "https://discord.com",
            "Pragma": "no-cache",
            "Sec-Websocket-Extensions": "permessage-deflate; client_max_window_bits"
        }
    