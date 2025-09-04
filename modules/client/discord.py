from modules.client.client  import TlsClient
from modules.utils.utils    import UTILS_DISCORD
from modules.utils.logger   import LOGGER
from base64                 import b64encode
from typing                 import Optional
from copy                   import deepcopy
from json                   import dumps
from uuid                   import uuid4
#To Do: Get Rid Of magic USER_AGENT, perhaps scrape it from somewhere

class DiscordWrapper:
    def __init__(
        self, 
        token: str, 
    ):
        """
        Initialize the DiscordWrapper class.

        Parameters:
            token (str): The authentication token for Discord.
            proxy (str, optional): A proxy server address. Defaults to None.

        Returns:
            Optional[TlsClient]: An initialized TlsClient instance if headers are set successfully, otherwise None.
        """

        self.token         = token
        self.tls           = TlsClient()
        self._super_prop   = None
        self._client_heartbeat_session_id = str(uuid4())
        self.client_launch_id = str(uuid4())
         
    def _set_cookies(self) -> bool:
        """
        Fetches The Cookies That Are Returned.

        Returns:
            bool: True if the Action is successfully completed, False otherwise.
        """
        response = self.tls.do_request("https://discord.com/api/v9/users/@me/affinities/guilds")

        if not response:
            LOGGER.warn("Could Not Fetch Cookies and Check Token")
            return
        
        self.tls.client.cookies = response.cookies
        return response.status_code
    
    def accept_tos(self) -> bool:
        """
        Discord Flags Aged Tokens If They Have Not Accepted Their T.O.S.
        This Request Just Uses The EndPoint That Does The Accept Action.

        Returns:
            bool: True if the Action is successfully completed, False otherwise.
        """

        response = self.tls.do_request(
            "https://discord.com/api/v9/users/@me/agreements", 
            "PATCH", 
            json = dumps({
                "terms"  : True, 
                "privacy": True
            })
        )

        if not response:
            return

        return True
    
    def set_headers(self) -> bool:
        timezone = self.tls.scrape_timezone()
        
        if not timezone:
            LOGGER.warn("Could Not Fetch Client Info")
            return
        
        self._super_prop = deepcopy(UTILS_DISCORD.x_super_properties)
        self._super_prop["client_app_state"] = "focused"
        self._super_prop["client_heartbeat_session_id"] = self._client_heartbeat_session_id
        self._super_prop["client_launch_id"] = self.client_launch_id

        self.tls.client.headers = {
            "accept": "*/*",
            "Accept-Encoding": "gzip, br",
            "accept-language": "en-US;q=0.9",
            "content-type": "application/json",
            "authorization": self.token,
            "priority": "u=1, i",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": UTILS_DISCORD.discord_user_agent,
            "x-debug-options": "bugReporterEnabled",
            "x-discord-locale": "en-US",
            "x-discord-timezone": timezone,
            "x-super-properties": b64encode(dumps(self._super_prop).encode('utf-8')).decode('utf-8'),
        }

        return self._set_cookies()
