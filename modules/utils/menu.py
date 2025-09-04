from modules.utils.utils    import FILES, FORCE_PARAMETERS
from modules.utils.logger   import Col
from pystyle                import Colorate, Colors, Center
from time                   import strftime, sleep
from os                     import system

class Menu:
    def __init__(self):
        self._color_scheme = {
            "air": {
                "title" :   Colors.cyan_to_blue,
                "text"  :   Colors.cyan
            },
            "full": {
                "title" :   Colors.purple_to_blue,
                "text"  :   Colors.purple
            }
        }

        self._options = {
            "1": "Normal Session",
            "2": "VCC Adder",
            "3": "Promo Redeemer",
            "4": "VCC Remover",
            "6": "Billing Spoofing",
            "7": "Reload Config"
        }

        self.active_scheme = "full"

    def _print_gen_statuses(self, statuses: bool|list):
        if statuses == False:
            return
        
        for status in statuses:
            if status["status"] != None:
                print(f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}{status['type']}{Col.white}] [{Colors.red}!{Col.white}] Offline Due To: {status['status']}")
            else:
                balance_message: str = f"{Col.gray}- {Col.white}Balance: {Col.green}{status['balance']} " if status['balance'] > 0 else ""
                provider: str = f"{Col.gray}- {Col.white}Provider: {Col.green}{status['provider']}"
                print(f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}{status['type']}{Col.white}] [{Colors.green}+{Col.white}] Online {balance_message}{provider}")

        print() # Space For Formatting
    
    def _print_vcc_parameters(self, vcc_parameters: FORCE_PARAMETERS):
        if not vcc_parameters:
            return
        
        message = f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}${Col.white}] Using Custom VCCs - Amount: [{Colors.green}{FILES.len_vccs()}{Col.white}]"

        for parameter in vars(vcc_parameters).keys():
            if getattr(vcc_parameters, parameter):
                message += f" - {parameter}: [{Colors.green}{ getattr(vcc_parameters, parameter)}{Col.white}]"

        print(f"{message}\n")
                
                

    def print_menu(self, options: bool = False, statuses: bool|list = False, vcc_parameters: FORCE_PARAMETERS = None):
        self._print_logo()
        self._print_vcc_parameters(vcc_parameters)
        self._print_gen_statuses(statuses)

        if options:
            for option in self._options:
                print(f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}{option}{Col.white}] {self._options[option]}")

    def print_menu_billing_spoofer(self, billing_code: int) -> int:
        self._print_logo()

        if billing_code & (1 << 0):
            print(f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}Spoof Street{Col.white}] [{Colors.green}+{Col.white}]")
        else:
            print(f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}Spoof Street{Col.white}] [{Colors.red}X{Col.white}]")

        if billing_code & (1 << 1):
            print(f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}Spoof Postal{Col.white}] [{Colors.green}+{Col.white}]")  
        else:
            print(f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}Spoof Postal{Col.white}] [{Colors.red}X{Col.white}]")

        if billing_code & (1 << 2):
            print(f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}Spoof Naming{Col.white}] [{Colors.green}+{Col.white}]")
        else:
            print(f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}Spoof Naming{Col.white}] [{Colors.red}X{Col.white}]")

        if billing_code & (1 << 3):
            print(f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}Spoof Street{Col.white}] [{Colors.green}+{Col.white}]")
        else:
            print(f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}Spoof Street{Col.white}] [{Colors.red}X{Col.white}]")

        self.print_info("INPUT", "Select Which Option To Change (0-4) (4 To Exit)")
    
    def _print_logo(self):
        system("cls")
        print(Center.XCenter(Colorate.Vertical(self._color_scheme[self.active_scheme]['title'], self._logo)))
        
    def print_info(self, section: str, message: str):
        print(f"{Col.white}[{Col.gray}{strftime('%H:%M:%S')}{Col.white}] [{self._color_scheme[self.active_scheme]['text']}{section}{Col.white}]{Col.gray} - {Col.white}{message}")

    @property
    def _logo(self) -> str:
        return r"""


                           ________              __               __     _    _______
                          / ____/ /_  ___  _____/ /______  __  __/ /_   | |  / /__  /
                         / /   / __ \/ _ \/ ___/ //_/ __ \/ / / / __/   | | / / /_ < 
                        / /___/ / / /  __/ /__/ ,< / /_/ / /_/ / /_     | |/ /___/ / 
                        \____/_/ /_/\___/\___/_/|_|\____/\____/\__/     |___//____/                                                                                                        
                     
"""

MENU = Menu()