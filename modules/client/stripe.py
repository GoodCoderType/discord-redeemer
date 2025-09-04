from modules.client.client  import TlsClient
from modules.utils.utils    import VCC, UTILS_DISCORD, CONFIG, Status
from modules.utils.logger   import LOGGER
from urllib.parse           import urlencode, quote
from dataclasses            import dataclass
from user_agents            import parse
from hashlib                import sha256, md5
from secrets                import token_bytes
from string                 import ascii_letters
from time                   import time
from random                 import randint, choice, sample, uniform, random
from base64                 import b64encode, urlsafe_b64encode, b64decode
from faker                  import Faker
from json                   import dumps
from time                   import perf_counter
from PIL                    import Image, ImageEnhance
from io                     import BytesIO
from os                     import urandom

fonts = [
    ["Andale Mono", "mono"],
    ["Arial Black", "sans"],
    ["Arial Hebrew", "sans"],
    ["Arial MT", "sans"],
    ["Arial Narrow", "sans"],
    ["Arial Rounded MT Bold", "sans"],
    ["Arial Unicode MS", "sans"],
    ["Arial", "sans"],
    ["Bitstream Vera Sans Mono", "mono"],
    ["Book Antiqua", "serif"],
    ["Bookman Old Style", "serif"],
    ["Calibri", "sans"],
    ["Cambria", "serif"],
    ["Century Gothic", "serif"],
    ["Century Schoolbook", "serif"],
    ["Century", "serif"],
    ["Comic Sans MS", "sans"],
    ["Comic Sans", "sans"],
    ["Consolas", "mono"],
    ["Courier New", "mono"],
    ["Courier", "mono"],
    ["Garamond", "serif"],
    ["Georgia", "serif"],
    ["Helvetica Neue", "sans"],
    ["Helvetica", "sans"],
    ["Impact", "sans"],
    ["Lucida Fax", "serif"],
    ["Lucida Handwriting", "script"],
    ["Lucida Sans Typewriter", "mono"],
    ["Lucida Sans Unicode", "sans"],
    ["Lucida Sans", "sans"],
    ["MS Gothic", "sans"],
    ["MS Outlook", "symbol"],
    ["MS PGothic", "sans"],
    ["MS Reference Sans Serif", "sans"],
    ["MS Serif", "serif"],
    ["MYRIAD PRO", "sans"],
    ["MYRIAD", "sans"],
    ["Microsoft Sans Serif", "sans"],
    ["Monaco", "sans"],
    ["Monotype Corsiva", "script"],
    ["Palatino Linotype", "serif"],
    ["Palatino", "serif"],
    ["Segoe Script", "script"],
    ["Segoe UI Semibold", "sans"],
    ["Segoe UI Symbol", "symbol"],
    ["Segoe UI", "sans"],
    ["Tahoma", "sans"],
    ["Times New Roman PS", "serif"],
    ["Times New Roman", "serif"],
    ["Times", "serif"],
    ["Trebuchet MS", "sans"],
    ["Verdana", "sans"],
    ["Wingdings 3", "symbol"],
    ["Wingdings", "symbol"]
] # Extracted From Stripe

class BillingSpooferFlags:
    street      = (1 << 0)
    postal      = (1 << 1)
    name        = (1 << 2)
    address_2   = (1 << 3)

@dataclass
class Features:
    pad_1: str
    pad_2: str
    language: str
    platform: str
    extensions: str
    screen: str
    pad_3: str
    pad_4: str
    storage: str
    fp_font: str
    pad_5: str
    user_agent: str
    pad_6: str
    pad_7: str
    pad_8: str

@dataclass
class FingerprintStripe:
    id: str
    features: Features
    title: str
    mm: list

class StripeWrapper:
    def __init__(
        self, 
        vcc: VCC|str = None, 
    ):
        self.card_token     = None  
        self.vcc            = vcc
        self.tls            = TlsClient()
        self.faker          = Faker()

        self.street         = CONFIG.billing.address
        self.postal         = CONFIG.billing.postal
        self.name           = CONFIG.billing.person_name
        self.address_2      = CONFIG.billing.address_2
        self.fp            = self.create_fp()

        if CONFIG.billing_config_code & BillingSpooferFlags.street:
            self.street = self.faker.street_address()
             
        if CONFIG.billing_config_code & BillingSpooferFlags.postal:
            self.postal = self.faker.postalcode()

        if CONFIG.billing_config_code & BillingSpooferFlags.name:
            self.name = self.faker.name()

        if CONFIG.billing_config_code & BillingSpooferFlags.address_2:
            self.address_2 = self.faker.street_address()
        
        self._muid = self._sid = self._guid = None

    def _sha256(self, string: str) -> str:
        hash_bytes = sha256(string.encode('utf-8')).digest()
        return urlsafe_b64encode(hash_bytes).rstrip(b'=').decode('ascii')
    
    def _sha256_salt(self, string: str) -> str:
        return self._sha256(string + UTILS_DISCORD.stripe_salt_hash)
    
    def _detect_fonts_from_fp(self):
        detected_fonts: list = []
        chrome_font_fp: str = "0100100101111101100111101100010101110010110111110111111"

        for bit, (font_name, _) in zip(chrome_font_fp, fonts):
            if bit == '1':
                detected_fonts.append(font_name)

        return detected_fonts
    
    def _font_fp_gen(self, detected_fonts) -> str:
        detection_bits: list = []

        for font_name, _ in fonts:
            if font_name in detected_fonts:
                prob = 0.7 + uniform(0, 0.1)
            else:
                prob = 0.05 + uniform(0, 0.35)

            detection_bits.append('1' if random() < prob else '0')

        fp = "".join(detection_bits)

        return fp
    
    def _spoof_canvas(self) -> str:
        pre_rendered = "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"
        buffered = BytesIO()

        img = Image.open(BytesIO(b64decode(pre_rendered)))
        ImageEnhance.Brightness(img).enhance(uniform(1, 1.25))
        ImageEnhance.Sharpness(img).enhance(uniform(1, 2))

        img.save(buffered, format="PNG")
        spoofed_b64 = f"data:image/png;base64,{b64encode(buffered.getvalue()).decode()}"
        return md5(spoofed_b64.encode()).hexdigest()
    
    def create_fp(self) -> FingerprintStripe:
        color_depth = choice((
            24,
            30
        ))
        device_pixel_ratio = randint(1,2)

        resolutions = (
            "1920x1080",
            "2560x1440"
        )

        screen_size = choice(resolutions)
        screen_width, screen_height = screen_size.split("x")

        screen_data = f"{screen_width}w_{screen_height}h_{color_depth}d_{device_pixel_ratio}r"   
        fp_font = self._font_fp_gen(self._detect_fonts_from_fp())

        random_ping_value = randint(0, 20)

        title = self._sha256_salt(f"({random_ping_value}) Discord | Billing | User Settings")
        canvas_data = self._spoof_canvas()

        features = Features(
            "true",
            "false",
            "en-US,en",
            "Win32",
            "Chrome PDF Viewer,internal-pdf-viewer,application/pdf,pdf++text/pdf,pdf, Chromium PDF Viewer,internal-pdf-viewer,application/pdf,pdf++text/pdf,pdf, Microsoft Edge PDF Viewer,internal-pdf-viewer,application/pdf,pdf++text/pdf,pdf, WebKit built-in PDF,internal-pdf-viewer,application/pdf,pdf++text/pdf,pdf",
            screen_data,
            "3",
            "false",
            "sessionStorage-enabled, localStorage-enabled",
            fp_font,
            "",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "",
            "false",
            canvas_data
        )

        rand_mm = []

        for _ in range(randint(7,9)):
            rand_mm.append(randint(1,6))

        return FingerprintStripe(
            md5(" ".join(str(getattr(features, attr)) for attr in features.__dict__).encode()).hexdigest(),
            features,
            title,
            rand_mm
        )
    
    def setup_intents(self, client_secret: str) -> str|Status:
        for attempt in range(3):
            setup_data = urlencode({
                "payment_method_data[type]": "card",
                "payment_method_data[card][token]": self.card_token,
                "payment_method_data[billing_details][name]": self.name,
                "payment_method_data[billing_details][address][line1]": self.street,
                "payment_method_data[billing_details][address][line2]": self.address_2,
                "payment_method_data[billing_details][address][city]": CONFIG.billing.city,
                "payment_method_data[billing_details][address][state]": CONFIG.billing.state,
                "payment_method_data[billing_details][address][postal_code]": self.postal,
                "payment_method_data[billing_details][address][country]": CONFIG.billing.country,
                "payment_method_data[billing_details][phone]": "",
                "payment_method_data[allow_redisplay]": "unspecified",
                "payment_method_data[pasted_fields]": "number,exp,cvc",
                "payment_method_data[client_attribution_metadata][merchant_integration_version]": "2021",
                "payment_method_data[client_attribution_metadata][payment_intent_creation_flow]": "standard",
                "payment_method_data[client_attribution_metadata][payment_method_selection_flow]": "merchant_specified",
                "payment_method_data[client_attribution_metadata][merchant_integration_source]": "elements",
                "payment_method_data[client_attribution_metadata][merchant_integration_subtype]": "payment-element",
                "payment_method_data[guid]": self._guid,
                "payment_method_data[muid]": self._muid,
                "payment_method_data[sid]": self._sid,
                "payment_method_data[payment_user_agent]": f"stripe.js/{UTILS_DISCORD.stripe_user_agent}; stripe-js-v3/{UTILS_DISCORD.stripe_user_agent}; payment-element",
                "payment_method_data[referrer]": "https://discord.com",
                "payment_method_data[time_on_page]": str(randint(60000, 120000)),
                "expected_payment_method_type": "card",
                "use_stripe_sdk": "true",
                "key": UTILS_DISCORD.stripe_key,
                "_stripe_version": "2025-03-31.basil",
                "client_secret": client_secret
            }, quote_via = quote)
           
            request = self.tls.do_request(
                f"https://api.stripe.com/v1/setup_intents/{client_secret[:29]}/confirm", 
                "POST", 
                data = setup_data
            )

            if not request:
                return Status.success

            if "error" in request.json().keys():
                if attempt < 2:
                    if not self._set_cookies():
                        return Status.proxy_error
                    
                    status = self._get_token()

                    if status != Status.success:
                        return status
                
                    continue

                return Status.card_error

            return request.json()["payment_method"]
    
    def authenticate_vcc(self, client_secret: str) -> Status:
        payment_intent_data = urlencode({
            "expected_payment_method_type": "card",
            "use_stripe_sdk": "true",
            "key": UTILS_DISCORD.stripe_key,
            "client_secret": client_secret,
        })

        payment_intent_confirm = self.tls.do_request(
            f"https://api.stripe.com/v1/payment_intents/{client_secret[:27]}/confirm",  #stripe_payment_intent_client_secret from setup_intents
            "POST", 
            data = payment_intent_data
        )
        
        if not payment_intent_confirm:
            return Status.proxy_error
        
        if not "next_action" in payment_intent_confirm.json().keys():
            return Status.card_error
        
        authenticate_data = urlencode({
            "source": payment_intent_confirm.json()["next_action"]["use_stripe_sdk"]["three_d_secure_2_source"],
            "browser": dumps({
                "fingerprintAttempted": False,
                "fingerprintData": None,
                "challengeWindowSize": None,
                "threeDSCompInd": "Y",
                "browserJavaEnabled": False,
                "browserJavascriptEnabled": True,
                "browserLanguage": "en-US",
                "browserColorDepth": "24",
                "browserScreenHeight": "1080",
                "browserScreenWidth": "1920",
                "browserTZ": "-180",
                "browserUserAgent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/138.0.0.0 Safari/537.36"
                )
            }),
            "one_click_authn_device_support[hosted]": False,
            "one_click_authn_device_support[same_origin_frame]": False,
            "one_click_authn_device_support[spc_eligible]": False,
            "one_click_authn_device_support[webauthn_eligible]": False,
            "one_click_authn_device_support[publickey_credentials_get_allowed]": True,
            "key": UTILS_DISCORD.stripe_key
        }, quote_via = quote)


        request = self.tls.do_request(
            f"https://api.stripe.com/v1/3ds2/authenticate", 
            "POST", 
            data = authenticate_data
        )

        if not request:
            return Status.proxy_error
        
        return Status.success
    
    def _get_token(self) -> Status:
        if type(self.vcc) == str:
            return Status.success
        
        stripe_token_payload = urlencode({
            "card[number]": self.vcc.card_number,
            "card[cvc]": self.vcc.cvv,
            "card[exp_month]": self.vcc.expiry_month,
            "card[exp_year]": self.vcc.expiry_year,
            "guid": self._guid,
            "muid": self._muid,
            "sid": self._sid,
            "payment_user_agent": f"stripe.js/{UTILS_DISCORD.stripe_user_agent}; stripe-js-v3/{UTILS_DISCORD.stripe_user_agent}; split-card-element",
            "time_on_page": randint(60000, 120000),
            "key": UTILS_DISCORD.stripe_key,
            "pasted_fields": "number,exp,cvc",
            "_stripe_version": "2025-03-31.basil",
            "referrer": "https://discord.com",
        })

        request = self.tls.do_request(
            "https://api.stripe.com/v1/tokens", 
            "POST",
            data = stripe_token_payload
        )

        if not request:
            return "Proxy_err"
 
        if "error" in request.json().keys():
            match request.json()["error"]["type"]:
                case "card_error":
                    LOGGER.error("Failed To Get Card Token, Invalid Card!", repr(self.vcc), error = request.json()["error"]["message"])
                    return Status.card_error
                
                case "invalid_request_error":
                    if not self._set_cookies():
                        return Status.proxy_error
                    
                    LOGGER.error("Invalid Request Error", repr(self.vcc), error = request.json()["error"]["message"])
                    return Status.card_error
                
                case _:
                    LOGGER.error("Unknown Error, Send Us A Photo", request.json()["error"], "CODE_PART_0")
                    return Status.card_error

        self.card_token = request.json()["id"]

        return Status.success
    
    def _get_random_value(self) -> str:
        try:
            random_bytes = urandom(10)  # 10 bytes = 80 bits
            return "".join(f"{b:02x}" for b in random_bytes)
        except:
            return "".join(f"{randint(0,255):02x}" for _ in range(10))
        
    def _set_cookies(self) -> bool:
        for part in range(1, 4):
            response = self.tls.do_request(
                "https://m.stripe.com/6",
                "POST",
                data = self._get_cookies_data(part)
            )

            if not response:
                LOGGER.warn("Could Not Fetch Cookies, Stripe!")
                return

            for cookie_name, cookie_value in response.json().items(): # Yes the cookies are in a dict.
                match cookie_name:
                    case "muid":
                        self._muid = cookie_value
                    case "guid":
                        self._guid = cookie_value
                        self.tls.client.cookies.set("m", cookie_value)
                    case "sid":
                        self._sid = cookie_value

        return True 

    def setup_client(self) -> Status:
        self.tls.client.headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
            "connection": "keep-alive",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9",
            "host": "api.stripe.com",
            "origin": "https://js.stripe.com",
            "referer": "https://js.stripe.com/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "sec-ch-ua": f"\"Not A(Brand\";v=\"8\", \"Google Chrome\";v=\"{parse(UTILS_DISCORD.browser_user_agent).browser.version_string.split('.')[0]}\", \"Chromium\";v=\"{parse(UTILS_DISCORD.browser_user_agent).browser.version_string.split('.')[0]}\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
  
        if not self._set_cookies():
            return Status.proxy_error
        
        return self._get_token()
    
    def _get_cookies_data(self, part: int = 1) -> str:
        random_value = self._get_random_value()

        match part: #https://m.stripe.network/out-4.5.44.js
            case 1:
                return b64encode(quote(dumps({
                   "v2":1,
                   "id":self.fp.id,
                   "t": round(uniform(300, 400), 1),
                   "tag":"$npm_package_version",
                   "src":"js",
                   "a": {
                      "a":{
                         "v":self.fp.features.pad_1,
                         "t":0
                      },
                      "b":{
                         "v":self.fp.features.pad_2,
                         "t":0
                      },
                      "c":{
                         "v":self.fp.features.language,
                         "t":round(uniform(0, 0.2), 1)
                      },
                      "d":{
                         "v":self.fp.features.platform,
                         "t":0
                      },
                      "e":{
                         "v":self.fp.features.extensions,
                         "t":0
                      },
                      "f":{
                         "v":self.fp.features.screen,
                         "t":0
                      },
                      "g":{
                         "v":self.fp.features.pad_3,
                         "t":round(uniform(0, 0.1), 1)
                      },
                      "h":{
                         "v":self.fp.features.pad_4,
                         "t":0
                      },
                      "i":{
                         "v":self.fp.features.storage,
                         "t":round(uniform(0.1, 1.0), 1)
                      },
                      "j":{
                         "v": self.fp.features.fp_font,
                         "t": round(uniform(100,150), 1),
                         "at" :round(uniform(100.0,110.0), 1)
                      },
                      "k":{
                         "v":self.fp.features.pad_5,
                         "t":0
                      },
                      "l":{
                         "v":self.fp.features.user_agent,
                         "t":0
                      },
                      "m":{
                         "v":self.fp.features.pad_6,
                         "t":round(uniform(0.0, 0.3), 1)
                      },
                      "n":{
                         "v":self.fp.features.pad_7,
                         "t": round(uniform(90.0, 100.0), 1),
                         "at": round(uniform(1.0, 1.5), 1)
                      },
                      "o":{
                         "v":self.fp.features.pad_8,
                         "t": round(uniform(10.0, 20.0), 1)
                      }
                   },
                   "b":{
                      "a":"https://GS7hqnkZBRpP_7Wn9-CGFhzq4kr2X3JC4A3k6BDBvpE.g2u9-hqZvGIqYJcPlPfwJAf-v3RgyK_x1NppzAlA12M/", # referer Static Anyway
                      "b":"https://GS7hqnkZBRpP_7Wn9-CGFhzq4kr2X3JC4A3k6BDBvpE.g2u9-hqZvGIqYJcPlPfwJAf-v3RgyK_x1NppzAlA12M/s9xIad8ADhleZhudjNphiB9AqrMO4FmdfLKVlLJU1_A/VUxgUze3mDpTw4tfmKSknXeDXJIbHyM-Ht24VfhOXuM", # url
                      "c": self.fp.title,
                      "d":"NA", #muid
                      "e":"NA", #sid
                      "f":False,
                      "g":True,
                      "h":True,
                      "i":["location"],
                      "j":[],
                      "n":uniform(300,400),
                      "u":"discord.com",
                      "v":"discord.com",
                      "w": f"{int(time() * 1000)}:{sha256(f"{random_value}{int(time() * 1000) + 1}".encode()).hexdigest()}" #return t + ":" + B("sha256Hex")(e + (t + 1))
                   },
                   "h": random_value # random_value
                })).encode()).decode()
            case 2:
                return b64encode(quote(dumps({
                   "v2":2,
                   "id":self.fp.id,
                   "t":round(uniform(4, 12), 1),
                   "tag":"$npm_package_version",
                   "src":"js",
                   "a":{
                      "a":{
                         "v":self.fp.features.pad_1,
                         "t":0
                      },
                      "b":{
                         "v":self.fp.features.pad_2,
                         "t":0
                      },
                      "c":{
                         "v":self.fp.features.language,
                         "t":round(uniform(0, 0.2), 1)
                      },
                      "d":{
                         "v":self.fp.features.platform,
                         "t":0
                      },
                      "e":{
                         "v":self.fp.features.extensions,
                         "t":0
                      },
                      "f":{
                         "v":self.fp.features.screen,
                         "t":0
                      },
                      "g":{
                         "v":self.fp.features.pad_3,
                         "t":round(uniform(0, 0.1), 1)
                      },
                      "h":{
                         "v":self.fp.features.pad_4,
                         "t":0
                      },
                      "i":{
                         "v":self.fp.features.storage,
                         "t":round(uniform(0.1, 1.0), 1)
                      },
                      "j":{
                         "v": self.fp.features.fp_font,
                         "t": round(uniform(100,150), 1),
                         "at" :round(uniform(100.0,110.0), 1)
                      },
                      "k":{
                         "v":self.fp.features.pad_5,
                         "t":0
                      },
                      "l":{
                         "v":self.fp.features.user_agent,
                         "t":0
                      },
                      "m":{
                         "v":self.fp.features.pad_6,
                         "t":round(uniform(0.0, 0.3), 1)
                      },
                      "n":{
                         "v":self.fp.features.pad_7,
                         "t": round(uniform(90.0, 100.0), 1),
                         "at": round(uniform(1.0, 1.5), 1)
                      },
                      "o":{
                         "v":self.fp.features.pad_8,
                         "t": round(uniform(10.0, 20.0), 1)
                      }
                   },
                   "b":{
                      "a":"https://GS7hqnkZBRpP_7Wn9-CGFhzq4kr2X3JC4A3k6BDBvpE.g2u9-hqZvGIqYJcPlPfwJAf-v3RgyK_x1NppzAlA12M/", # Static Anyway
                      "b":"https://GS7hqnkZBRpP_7Wn9-CGFhzq4kr2X3JC4A3k6BDBvpE.g2u9-hqZvGIqYJcPlPfwJAf-v3RgyK_x1NppzAlA12M/s9xIad8ADhleZhudjNphiB9AqrMO4FmdfLKVlLJU1_A/VUxgUze3mDpTw4tfmKSknXeDXJIbHyM-Ht24VfhOXuM",
                      "c": self.fp.title,
                      "d": self._muid,
                      "e": self._sid,
                      "f":False,
                      "g":True,
                      "h":True,
                      "i":[
                         "location"
                      ],
                      "j":[

                      ],
                      "n":uniform(300,400),
                      "u":"discord.com",
                      "v":"discord.com",
                      "w":f"{int(time() * 1000)}:{sha256(f"{random_value}{int(time() * 1000) + 1}".encode()).hexdigest()}"
                   },
                   "h": random_value
                })).encode()).decode()
            case 3:
                return b64encode(quote(dumps({
                   "muid": self._muid,
                   "sid": self._sid,
                   "url":"https://GS7hqnkZBRpP_7Wn9-CGFhzq4kr2X3JC4A3k6BDBvpE.g2u9-hqZvGIqYJcPlPfwJAf-v3RgyK_x1NppzAlA12M/s9xIad8ADhleZhudjNphiB9AqrMO4FmdfLKVlLJU1_A/VUxgUze3mDpTw4tfmKSknXeDXJIbHyM-Ht24VfhOXuM",
                   "source":"mouse-timings-10-v2",
                   "data":self.fp.mm})).encode()).decode()
            case 4:
                return b64encode(quote(dumps({
                   "muid": self._muid,
                   "sid": self._sid,
                   "url":"https://GS7hqnkZBRpP_7Wn9-CGFhzq4kr2X3JC4A3k6BDBvpE.g2u9-hqZvGIqYJcPlPfwJAf-v3RgyK_x1NppzAlA12M/s9xIad8ADhleZhudjNphiB9AqrMO4FmdfLKVlLJU1_A/VUxgUze3mDpTw4tfmKSknXeDXJIbHyM-Ht24VfhOXuM",
                   "source":"mouse-timings-10",
                   "data": self.fp.mm
                })).encode()).decode()