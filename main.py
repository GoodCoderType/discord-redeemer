from modules.redeemer.worker    import SESSION_MANAGER # People will have fun skidding it
from modules.client.stripe      import StripeWrapper
from modules.bot.bot            import start_bot
from modules.utils.utils        import CONFIG, GLOBAL_VARS, FILES, Status, Checkout_ids, Redeem_Modes, MATERIALS_ENCRYPTION, FORCE_PARAMETERS
from modules.utils.logger       import LOGGER, Colors
from modules.utils.menu         import MENU
from modules.client.webhook     import WEBHOOK_CLIENT
from modules.client.gen         import START_GENS
from modules.utils.winapi       import WINAPI
from requests                   import get
from datetime                   import datetime
from threading                  import Thread
from msvcrt                     import kbhit, getch
from time                       import sleep
from requests                   import post
from os                         import system
from keyboard                   import is_pressed
import sys

def input_handler():
    while True:
        if is_pressed(CONFIG.pause_key): 
            if GLOBAL_VARS.paused:
                FILES.update_materials()
                CONFIG.load_config()
            GLOBAL_VARS.paused = not GLOBAL_VARS.paused
            LOGGER.info("Paused redeeming. Threads will stop after their current run." if GLOBAL_VARS.paused else "Resumed redeeming.")

            sleep(0.3) 

        sleep(0.1)


# forgive me for putting this into the main
should_run_webhook = CONFIG.webhook_enabled
def webhook_handler(webook_client):
    while True:
        if not should_run_webhook:
            continue

        url = webook_client.upload_image(WINAPI.render_console_buffer())
        WEBHOOK_CLIENT.edit_message([
            {
                "title": "Checkout V3 WebHook",
                "description": "Session active.",
                "color": 16711935, 
                "fields": [
                    {
                        "name": "`⏸️` Paused",
                        "value": "`yes`" if GLOBAL_VARS.paused else "`no`"
                    },
                    {
                        "name": "`✅` Redeems",
                        "value": f"`{GLOBAL_VARS.metrics.redeems}`"
                    },
                    {
                        "name": "`❌` Fails",
                        "value": f"`{GLOBAL_VARS.metrics.fails}`"
                    },
                    {
                        "name": "`👤` Captchas caught",
                        "value": f"`{GLOBAL_VARS.metrics.captcha_tokens}`"
                    },
                    {
                        "name": "`💳` Authentication errors",
                        "value": f"`{GLOBAL_VARS.metrics.auth_errors}`"
                    }
                ],
                "footer": {
                    "text": "Checkout V3",
                },
                "author": {
                    "name": "@EinTim - @NinjaRide",
                    "icon_url": "https://i.ibb.co/Fgdp8Q9/chrome-A1o1-P3-QOAO.png"
                },
                "image": {
                    "url": url
                },
                "timestamp": datetime.now().isoformat() + "Z" 
            }
        ], "")

        sleep(30)

def setup_wizard():
    LOGGER.info("Welcome to Checkout V3! Would you like to run setup wizard? [y/n]")

    if LOGGER.input_print() != "y":
        return
        
    FILES.update_materials()

    if not FILES.get_proxy():
        LOGGER.info("No proxies found in input file. Would you like to add proxies now? [y/n]")

        result = LOGGER.input_print()

        if result.lower() == "y":
            LOGGER.info("Please enter your proxies in input/proxies.txt, one per line. Waiting for proxies.")

            while not FILES.get_proxy():
                FILES.update_materials()
                sleep(1)

                if not FILES.get_proxy():
                    continue

                LOGGER.info("Successfully found proxies, running self-check.")

                proxy = FILES.get_proxy()

                try:
                    get("https://discord.com/api/v9/experiments", proxies = {"http": proxy, "https": proxy}, timeout = 10).status_code
                except Exception as e:
                    LOGGER.error(f"Invalid proxy. Please try again, Would you like to like to skip this step? [y/n]", e)

                    result = LOGGER.input_print()

                    if result.lower() == "y":
                        CONFIG.proxyless = True
                        break

                    FILES.clear_file("./input", "proxies")
                    FILES.update_materials()
                    continue

                LOGGER.success("Successfully added proxies.")
                CONFIG.proxyless = False
                break
        
    else:
        LOGGER.success("Proxies found, skipping...")

    sleep(1)

    if not FILES.tokens and not FILES.linked_tokens:
        LOGGER.warn("No tokens found in input file. Would you like to add tokens now? [y/n]")

        result = LOGGER.input_print()

        if result.lower() == "y":

            LOGGER.info("Please enter your tokens in input/tokens.txt, one per line. Supported formats are: e:p:t / p:t / t + connector + promo. Waiting for tokens.")

            while not FILES.tokens and not FILES.linked_tokens:
                FILES.update_materials()
                sleep(1)
                
            LOGGER.success("Successfully added tokens.")
    else:
        LOGGER.success("Tokens found, skipping...")

    sleep(1)

    if not FILES.promos:

        LOGGER.info("No promos found in input file, but there are linked tokens, so you don't have to add them. Would you like to add promos now? [y/n]") if FILES.linked_tokens else LOGGER.warn("No promos found in input file. Would you like to add promos now? [y/n]")

        result = LOGGER.input_print()

        if result.lower() == "y":
            LOGGER.info("Please enter your promos in input/promos.txt, one per line. Waiting for promos.")

            while not FILES.promos:
                FILES.update_materials()
                sleep(1)

            LOGGER.success("Successfully added promos.")
            sleep(1)
    else:
        LOGGER.success("Promos found, skipping...")
        sleep(1)
        
    if not FILES.vccs:
        LOGGER.info("No VCCs found in input file. Would you like to add VCCs now? [y/n]")

        result = LOGGER.input_print()

        if result.lower() == "y":
            LOGGER.info("Please enter your VCCs in input/vccs.txt, one per line. Waiting for VCCs.")

            while True:
                FILES.update_materials()
                sleep(1)

                if not FILES.vccs:
                    continue

                LOGGER.success("Successfully added VCCs, Running self-check.")

                vcc = FILES.get_vcc()
                FILES.decrease_vcc_counter(vcc)
                stripe_wrapper = StripeWrapper(vcc)

                match stripe_wrapper.setup_client():
                    case Status.success:
                        LOGGER.success("Successfully Checked VCC.")
                        break

                    case Status.card_error: 
                        LOGGER.error("Failed To Setup Client For Stripe, Please Check If Your VCCS Are Valid Or Expired, Clearing VCC File, Would you like to like to skip this step? [y/n]")
                        FILES.clear_file("./input", "vccs")

                        result = LOGGER.input_print()

                        if result.lower() == "y":
                            break

                    case _:
                        LOGGER.error("Failed To Setup Client For Stripe, Please Check Your Proxies, Switching To Proxyless, Clearing Proxies File!")
                        FILES.clear_file("./input", "proxies")
                        CONFIG.proxyless = True
                        FILES.update_materials()
                        continue
                        
    else:
        LOGGER.success("VCCs found, skipping...")
                
    sleep(2)

    if not CONFIG.webhook_url:
        LOGGER.info("No webhook url found in config file. Would you like to add one now? [y/n]")

        result = LOGGER.input_print()

        if result.lower() == "y":
            while True:
                LOGGER.info("Please enter your webhook url. Type 'cancel' to cancel.")
                result = LOGGER.input_print()

                if result.lower() == "cancel":
                    break

                elif result.startswith("https://discord.com/api/webhooks/"):
                    status = get(result).status_code

                    if status == 404:
                        LOGGER.error("Invalid webhook url.")
                        continue

                    CONFIG.webhook_url = result
                    CONFIG.webhook_enabled = True
                    break

                else:
                    LOGGER.error("Invalid webhook url.")
                    continue

    else:
        LOGGER.success("Webhook url found, skipping...")
        sleep(1)

    LOGGER.info("No bot token found in config file. Feel free to add one afterwards.") if not CONFIG.bot_token else LOGGER.success("Bot token found, skipping...")
    sleep(3)

    LOGGER.info("Setup wizard complete. Welcome To CheckOut V3, Brought to you by EinTim x NinjaRide")
    sleep(5)

    return
    
if __name__ == "__main__":
    productid = 26
    version = "1.5.4"
            
    initialized = True
    
    def session_runner():
        system("cls")
        FILES.update_materials()
        MENU.print_info("INPUT", "Threads Amount?")

        threads_amount = LOGGER.input_print().strip()

        if not threads_amount.isdigit():
            return
        
        if FILES.forced_parameters:
            threads_amount = FILES.forced_parameters.max_threads if FILES.forced_parameters.max_threads < int(threads_amount) and FILES.forced_parameters.max_threads else int(threads_amount)

        should_run_webhook = SESSION_MANAGER.start_session(threads_amount)

        if not should_run_webhook:
            SESSION_MANAGER.join_threads()
            return
  
        SESSION_MANAGER.join_threads(input_print = True)

        if CONFIG.webhook_enabled and webhook_valid:
            WEBHOOK_CLIENT.finalize()

        should_run_webhook = False
    def billing_setter() -> bool:
        while True:
            MENU.print_menu_billing_spoofer(CONFIG.billing_config_code)
            toggle = LOGGER.input_print().strip()

            if not toggle.isdigit() or int(toggle) > 4 or int(toggle) < 0:
                LOGGER.error("Invalid selection.")
                sleep(2)
                continue

            elif int(toggle) == 4:
                return

            CONFIG.billing_config_code = CONFIG.billing_config_code ^ (1 << int(toggle))
            
    def enforce_air():
        if productid is not Checkout_ids.checkout_air_id:
            return

        blocked_features: tuple = (
            "use_gen_promo",
            "use_gen_vcc",
            "remove_vcc",
            "customize_bio",
            "customize_nick",
            "change_password",
            "change_token",
            "fetch_new_vcc",
            "bot_enabled",
            "webhook_enabled"
        )

        found_blocked_features: bool = False

        for feature in blocked_features:
            config_setting: bool = getattr(CONFIG, feature)

            if config_setting:
                found_blocked_features = True
                LOGGER.warn("This Config Setting Is Only Available For Full Version", feature)
                setattr(CONFIG, feature, False)
                sleep(.5)

        if found_blocked_features:
            sleep(5)

    def enforce_parameters():
        if FILES.forced_parameters is None:
            return

        if FILES.forced_parameters.hide_vccs:
            CONFIG.censor_sensitive_information = True

        if FILES.forced_parameters.minimum_delay:
            CONFIG.sleep_duration = FILES.forced_parameters.minimum_delay

        if FILES.forced_parameters.max_redeem_per_vcc:
            CONFIG.vcc_uses = FILES.forced_parameters.max_redeem_per_vcc

        if not FILES.forced_parameters.allow_turbo:
            CONFIG.turbo_mode = False

    MENU.print_menu()
    enforce_air()
    
    if initialized:   

        webhook_valid = True
        
        if CONFIG.webhook_enabled and not WEBHOOK_CLIENT.check_webhook():
            LOGGER.info("Webhook is invalid...")
            should_run_webhook = False
            webhook_valid = False
            sleep(2)
        
        elif CONFIG.webhook_enabled and not WEBHOOK_CLIENT.check_message_id():
            LOGGER.info("Sending webhook init message.")
            message_id = WEBHOOK_CLIENT.send_message(None, "Hello!")
            WEBHOOK_CLIENT.set_message_id(message_id)
            CONFIG.webhook_msg_id = message_id
            sleep(2)

        Thread(target = input_handler, daemon=True).start()

        if CONFIG.webhook_enabled and should_run_webhook:
            webhook_thread = Thread(target=webhook_handler, args=(WEBHOOK_CLIENT,), daemon=True)
            webhook_thread.start()

        if CONFIG.bot_token and CONFIG.bot_enabled:
            Thread(target = start_bot, daemon=True).start()

        while True:
            gen_status = START_GENS()

            MENU.print_menu(True, gen_status, FILES.forced_parameters)

            option = LOGGER.input_print().strip()

            match option:
                case "1":
                    GLOBAL_VARS.mode = Redeem_Modes.normal
                case "2":
                    GLOBAL_VARS.mode = Redeem_Modes.add_vcc_only
                case "3":
                    GLOBAL_VARS.mode = Redeem_Modes.redeem_promo_only
                case "4":
                    GLOBAL_VARS.mode = Redeem_Modes.remove_vcc_only
                case "6":
                    billing_setter()
                    continue
                case "7":
                    CONFIG.load_config()
                    continue
                case _:
                    LOGGER.error("Invalid selection.")
                    sleep(2)
                    continue

            enforce_air()
            enforce_parameters()
            session_runner()
