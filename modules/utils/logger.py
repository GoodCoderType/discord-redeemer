from modules.utils.utils    import CONFIG, GLOBAL_VARS, FILES
from threading              import Lock, Thread
from pystyle                import Colors
from time                   import strftime, sleep
from os                     import system

LOGGER_LOCK                 = Lock()

class Col:
    green           = Colors.light_green
    red             = Colors.red
    gray            = Colors.gray
    yellow          = Colors.yellow
    lyellow         = Colors.yellow
    blue            = Colors.blue
    lblue           = Colors.light_blue
    purple          = Colors.purple
    cyan            = Colors.cyan
    white           = Colors.white
    black           = Colors.black
    reset           = "\033[0m"

class Console:
    def __init__(
        self, 
        bounder : str = ",",
        spacer  : str = ": "
    ):

        self._bounder   = bounder
        self._spacer    = spacer

        Thread(
            target = self.title_thread, 
            daemon = True
        ).start()

    def title_thread(self):
        while True:
            system(f"title Checkout V3 - @NinjaRide ^| @EinTim - Stats: Finished: [{GLOBAL_VARS.metrics.redeems}] - Failed: [{GLOBAL_VARS.metrics.fails}] - Captcha: [{GLOBAL_VARS.metrics.captcha_tokens}] - Tokens: [{len(FILES.tokens) + len(FILES.linked_tokens)}] - VCCs: [{FILES.len_vccs()}] - Promos: [{len(FILES.promos)}]")
            sleep(.5)

    def log(self, msg):
        with LOGGER_LOCK:
            print(f"{msg}{Col.reset}")

    def timestamp(self):
        return f"{Col.white}[{getattr(Col, CONFIG.timestamp_color)}{strftime('%H:%M:%S')}{Col.white}]" 
    
    def extra(self, col="white", *args, **kwargs):
        formatted_args = [f"{getattr(Col, col)}{value}" for value in args]
        formatted_kwargs = [f"{Col.gray}{key}{self._spacer}{getattr(Col, col)}{value}" for key, value in kwargs.items()]

        extra_values = formatted_args + formatted_kwargs
        formatted_extra = f"{Col.white}{self._bounder}{getattr(Col, col)} ".join(extra_values) if extra_values else ""
        
        if formatted_extra:
            return f"{Col.white}{CONFIG.connector} {formatted_extra}"
        
        return ""

    def end(self, col, msg, *args, **kwargs):
        return f"{Col.white}{msg} {getattr(Col, col)}{self.extra(col, *args, **kwargs)}"
    
    def success(self, msg: str, *args, **kwargs):
        self.log(f"{self.timestamp()} [{getattr(Col, CONFIG.success_color)}{CONFIG.success_icon}{Col.white}]{Col.gray} - {self.end(CONFIG.success_color_end, str(msg), *args, **kwargs)}")

    def info(self, msg: str, *args, **kwargs):
        if CONFIG.logger_level > 1 or (not args and not kwargs):
            self.log(f"{self.timestamp()} [{getattr(Col, CONFIG.info_color)}{CONFIG.info_icon}{Col.white}]{Col.gray} - {self.end(CONFIG.info_color_end, str(msg), *args, **kwargs)}") 

    def warn(self, msg: str, *args, **kwargs):
        if CONFIG.logger_level > 0:
            self.log(f"{self.timestamp()} [{getattr(Col, CONFIG.warn_color)}{CONFIG.warn_icon}{Col.white}]{Col.gray} - {self.end(CONFIG.warn_color_end, str(msg), *args, **kwargs)}")

    def error(self, msg: str, *args, **kwargs):
        self.log(f"{self.timestamp()} [{getattr(Col, CONFIG.error_color)}{CONFIG.error_icon}{Col.white}]{Col.gray} - {self.end(CONFIG.error_color_end, str(msg), *args, **kwargs)}")
    
    def extra_info(self, msg: str, *args, **kwargs):
        if CONFIG.show_extra_info:
            self.log(f"{self.timestamp()} [{getattr(Col, CONFIG.extra_info_color)}{CONFIG.extra_info_icon}{Col.white}]{Col.gray} - {self.end(CONFIG.extra_info_color_end, str(msg), *args, **kwargs)}") 

    def input_print(self) -> str:
        return input(f"{self.timestamp()} [{Col.yellow}>{Col.white}]{Col.white} ")

LOGGER = Console()