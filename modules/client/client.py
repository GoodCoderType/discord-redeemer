from tls_client.exceptions  import TLSClientExeption
from modules.utils.logger   import LOGGER
from modules.utils.utils    import FILES, CONFIG
from tls_client.response    import Response
from tls_client             import Session
from typing                 import Optional, Union

class TlsClient:
    timezone: str = None

    def __init__(self):
        self.client = Session(
            client_identifier = "chrome_120", 
            random_tls_extension_order = True
        )

        if not CONFIG.proxyless:
            proxy = FILES.get_proxy()

            self.client.proxies = {
                 "http" : f"http://{proxy}",
                 "https": f"http://{proxy}"
            }
            
        self.client.timeout_seconds = CONFIG.client_timeout

    def _change_proxy(self):
        if not CONFIG.proxyless and CONFIG.rotate_proxies:
            proxy = FILES.get_proxy()

            self.client.proxies = {
                 "http" : f"http://{proxy}",
                 "https": f"http://{proxy}"
            }

    def scrape_timezone(self):
        if CONFIG.static_timezone:
            return "America/New_York"
        
        if TlsClient.timezone and CONFIG.proxyless:
            return TlsClient.timezone

        old_headers: dict = self.client.headers.copy()

        response = self.do_request("https://api.ipify.org?format=json")

        if not response:
            return
        
        ip: str = response.json()["ip"]

        self.client.headers  = {
          "accept": "*/*",
          "accept-encoding": "gzip, deflate, br, zstd",
          "accept-language": "en-US,en;q=0.9",
          "connection": "keep-alive",
          "host": "demo.ip-api.com",
          "origin": "https://ip-api.com",
          "referer": "https://ip-api.com/",
          "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        }

        response = self.do_request("https://ip-api.com/")

        if not response:
            return
        
        auth_token: str = response.text.split("?fields=")[1].split("&lang=")[0]

        response = self.do_request(f"https://demo.ip-api.com/json/{ip}?fields={auth_token}&lang=en")

        if not response:
            return
        
        self.client.headers = old_headers
        
        TlsClient.timezone = response.json()["timezone"]

        return response.json()["timezone"]
    
    def do_request(self, 
        url: str, 
        method: str = "GET",
        headers: Optional[dict] = {},
        json: Optional[dict] = {}, 
        data: Optional[Union[str, dict]] = None, 
        **kwargs
    ) -> Response:
        """
        Do The Request. It Automatically Does Error Handling.

        Parameters:
        - url (str): The URL for the request.
        - method (str): (e.g., 'GET', 'POST').
        - data (Union[str, dict], optional): The request data. | -> Use Which You Need
        - json (dict, optional): The JSON payload.             /
        - kwargs: Additional keyword arguments for the request.
        """
        if not data:
            data = {} if method == "GET" else None # WTF DISCORD W H Y

        request = None
        error = None
        
        for _ in range(CONFIG.client_retries):
            try:
                request = self.client.execute_request(method=method, url=url, data=data, json=json, headers=headers, **kwargs)
                break
            except TLSClientExeption as e:
                error: TLSClientExeption = e
                self._change_proxy()
        
        if not request:
            LOGGER.error("Failed To Do Request", error)
            
        return request