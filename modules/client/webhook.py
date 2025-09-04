import requests
from json import dumps
from modules.utils.logger import LOGGER
from modules.utils.utils import FILES, CONFIG, GLOBAL_VARS
from dataclasses import dataclass
from time import time
from pathlib import Path

@dataclass
class WebhookFile:
    data: bytes
    name: str
    mimetype: str = "text/plain"

class WebhookClient:
    def __init__(self, webhook: str, message_id: str):
        self.webhook = webhook
        self.message_id = message_id
        self.upload_url = None

    def set_message_id(self, message_id: str):
        self.message_id = message_id

    def check_webhook(self) -> bool:
        try: # this can throw an exception if the url is invalid.
            response = requests.get(self.webhook)
            return response.status_code == 200
        except:
            return False 

    def check_message_id(self) -> bool:
        if not self.message_id:
            return False
        
        response = requests.get(f"{self.webhook}/messages/{self.message_id}")
        return response.status_code == 200

    def edit_message(self, embeds: dict, content: str = "", files_in: list[WebhookFile] = None):
        url = f"{self.webhook}/messages/{self.message_id}"
        data = {"content": content, "embeds": embeds, "attachments": []}
        files = {}

        try:
            if files_in:
                for file in files_in:
                    files[file.name] = (file.name, file.data, file.mimetype)

                requests.patch(url, data={"payload_json": dumps(data)}, files=files)
            else:
                requests.patch(url, json=data)
        except:
            LOGGER.error("Couldn't edit webhook message!")
        
    def send_message(self, embeds: dict, content: str = "") -> str:
        try:
            response = requests.post(f"{self.webhook}?wait=true", json={"content": content, "embeds": embeds})
            response_data = response.json()
            return response_data.get("id", "")
        except:
            LOGGER.error("Couldn't send initial webhook message!")

    def upload_image(self, image: bytes) -> str:
        try:
            if int(time()) - GLOBAL_VARS.last_send < 25:
                return self.upload_url
            
            GLOBAL_VARS.last_send = int(time())

            s = requests.session()
            
            response = s.get("https://imgbb.com/")

            auth_token = response.text.split("auth_token=\"")[1].split("\"")[0]
            files = {
                'source': ('console.png', image, 'image/png'),
                'type': (None, 'file'),
                'action': (None, 'upload'),
                'timestamp': (None, int(time())),
                'auth_token': (None, auth_token),
                'expiration': (None, 'PT15M'),
            }

            response = s.post("https://imgbb.com/json", files=files)

            self.upload_url = response.json()["image"]["url"]
            
            return response.json()["image"]["url"]
        except:
            LOGGER.error("Couldn't upload console preview!")

    def finalize(self):
        folder_path = Path(FILES.output_directory)
        files: list[WebhookFile] = []

        for file in folder_path.iterdir():
            if file.is_file():
                files.append(WebhookFile(file.open("rb").read(), file.name))
        
        self.edit_message(None, f"Checkout finished <t:{int(time())}:R> ", files)

WEBHOOK_CLIENT = WebhookClient(CONFIG.webhook_url, CONFIG.webhook_msg_id)