from modules.client.discord_websocket   import WebsocketDiscord, WebSocket, DISCORD_ENCRYPTION
from modules.client.discord             import DiscordWrapper
from modules.client.stripe              import StripeWrapper
from modules.utils.logger               import LOGGER
from modules.utils.utils                import UTILS_DISCORD, CONFIG, GLOBAL_VARS, FILES, PROMO, TOKEN, Status, Redeem_Modes, VCC, WorkerVars
from modules.utils.menu                 import MENU
from threading                          import Thread, Lock
from random                             import choice, randint
from string                             import ascii_letters
from uuid                               import uuid4
from time                               import perf_counter, sleep

REDEEM_LOCK = Lock()

class TokenCustomizer:
    @staticmethod
    def _do_bio(discord_wrapper: DiscordWrapper):
        if not CONFIG.bio_descriptions:
            return

        bio_description = choice(CONFIG.bio_descriptions)

        bio_description = f"{bio_description} ||{''.join(choice(ascii_letters) for _ in range(randint(5, 40)))}||"

        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me",
            "PATCH",
            json = {
                "bio": bio_description,
                "accent_color": None
            }
        )

        if not request:
            LOGGER.error("Failed To Change Bio, Check Proxies / Internet", discord_wrapper.token[:30])
            return

        if request.status_code == 200:
            return True

        return

    @staticmethod
    def _do_nick(discord_wrapper: DiscordWrapper):
        if not CONFIG.nicks:
            return

        nick = choice(CONFIG.nicks)

        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me",
            "PATCH",
            json = {
                "global_name": nick
            }
        )

        if not request:
            LOGGER.error("Failed To Change Nick, Check Proxies / Internet", discord_wrapper.token[:30])
            return

        if request.status_code == 200:
            return True

        return

    @staticmethod
    def _change_pass(discord_wrapper: DiscordWrapper, token: TOKEN):
        if not CONFIG.passwords:
            return

        if not ":" in token.full_token:
            LOGGER.warn("The format is token only, Skipping.", discord_wrapper.token[:30])
            return

        elif len(token.full_token.split(":")) == 2:
            LOGGER.warn("token is not email:pass:token, Skipping.", discord_wrapper.token[:30])
            return

        else:
            old_password = token.full_token.split(":")[1]

        password = choice(CONFIG.passwords)

        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me",
            "PATCH",
            json =  {
                "password": old_password,
                "new_password": password
            }

        )

        if not request:
            LOGGER.error("Failed To Change Password, Check Proxies / Internet", discord_wrapper.token[:30])
            return

        if request.status_code == 200:
            new_token = request.json()["token"]
            LOGGER.info("Changed Token Password", new_token[:30], old = discord_wrapper.token[:30])

            token.full_token = token.full_token.replace(token.formatted_token, new_token).replace(old_password, password)
            token.raw_line = token.raw_line.replace(token.formatted_token, new_token).replace(old_password, password)

            FILES.replace_a_line(FILES.output_directory, "redeemed", token.formatted_token, token.full_token)

            token.formatted_token = new_token
            discord_wrapper.token = new_token

            return True

        return

    @staticmethod
    def _change_token(discord_wrapper: DiscordWrapper, token: TOKEN):
        discord_wrapper.tls.client.headers.pop("authorization")

        request = discord_wrapper.tls.do_request("https://discord.com/api/v9/experiments") # Can't have token

        if not request:
            LOGGER.error("Failed to change token", discord_wrapper.token[:30], part = "1")
            return

        discord_wrapper.tls.client.headers["authorization"] = token.formatted_token

        x_fingerprint = request.json()["fingerprint"]

        websocket = WebSocket()

        discord_wrapper.tls.client.headers["X-Fingerprint"] = x_fingerprint

        Thread(target = websocket.open_ws).start()

        while not websocket.started:
             sleep(.1)

        private_key, public_key = DISCORD_ENCRYPTION.generate_rsa_key()
        result = DISCORD_ENCRYPTION.export_public_key_spki(public_key)

        websocket.send_data({"op": "init", "encoded_public_key": result})

        while not websocket.nonce_proof:
            sleep(.1)

        decoded_nonce = DISCORD_ENCRYPTION.decode(websocket.nonce_proof)
        decrypted_nonce = DISCORD_ENCRYPTION.decrypt_encrypted(private_key, decoded_nonce)

        websocket.send_data({"op": "nonce_proof", "nonce": DISCORD_ENCRYPTION.make_url_safe(decrypted_nonce)})

        while not websocket.fingerprint:
            sleep(.1)

        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me/remote-auth",
            "POST",
            json = {
                "fingerprint": websocket.fingerprint
            }
        )
        if not request:
            LOGGER.error("Failed to change token, Check Proxies / Internet", discord_wrapper.token[:30], part = "2")
            return

        handshake = request.json()["handshake_token"]

        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me/remote-auth/finish",
            "POST",
            json = {
                "handshake_token": handshake,
                "temporary_token": False
            }
        )

        if not request:
            LOGGER.error("Failed to change token, Check Proxies / Internet", discord_wrapper.token[:30], part = "3")
            return

        while not websocket.t_token:
            sleep(.1)

        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me/remote-auth/login",
            "POST",
            json = {
                "ticket": websocket.t_token
            }
        )
        if not request:
            LOGGER.error("Failed to change token, Check Proxies / Internet", discord_wrapper.token[:30], part = "4")
            return

        if "encrypted_token" in request.text:
            new_token = DISCORD_ENCRYPTION.decrypt_encrypted(private_key, DISCORD_ENCRYPTION.decode(request.json()["encrypted_token"])).decode("utf-8")
            LOGGER.info("Changed Token", new_token[:30], old = discord_wrapper.token[:30])

            token.full_token = token.full_token.replace(token.formatted_token, new_token)
            token.raw_line = token.raw_line.replace(token.formatted_token, new_token)

            FILES.replace_a_line(FILES.output_directory, "redeemed", token.formatted_token, token.full_token) # Deleting the line needs to make space for next one

            token.formatted_token = new_token
            discord_wrapper.token = new_token

            discord_wrapper.tls.do_request(
                "https://discord.com/api/v9/auth/logout",
                "POST",
                json = {
                    "provider": None,
                    "voip_provider": None
                }
            )

            discord_wrapper.tls.client.headers["authorization"] = token.formatted_token

            return True

        else:
            LOGGER.error("Failed to change token", discord_wrapper.token[:30], part = "5", response = request.text)

        return

    @staticmethod
    def customize_token(discord_wrapper: DiscordWrapper, token: TOKEN):
        status = []

        if CONFIG.customize_bio and TokenCustomizer._do_bio(discord_wrapper):
            status.append("bio")

        if CONFIG.customize_nick and TokenCustomizer._do_nick(discord_wrapper):
            status.append("nick")

        if CONFIG.change_password and TokenCustomizer._change_pass(discord_wrapper, token):
            status.append("pass_change")

        elif CONFIG.change_token and TokenCustomizer._change_token(discord_wrapper, token):
            status.append("token_change")

        if status:
            LOGGER.success("Customized Token", discord_wrapper.token[:30], status = ",".join(status))

        return

class Redeemer:
    def _check_billing(self, discord_wrapper: DiscordWrapper) -> Status:
        if not CONFIG.check_billing:
            return Status.success

        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me/billing/payments?limit=20"
        )

        if not request:
            LOGGER.error("Failed To Check Billing, Check Proxies / Internet", discord_wrapper.token[:30])
            return Status.proxy_error

        for bill in request.json():
            if bill["status"] == 5:
                LOGGER.warn("Billing Is Not Clean, Skipping.", discord_wrapper.token[:30])
                return Status.token_error

        return Status.success

    def _get_payment_method(self, discord_wrapper: DiscordWrapper, stripe_wrapper: StripeWrapper, worker_vars: WorkerVars) -> Status|str:
        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me/billing/stripe/setup-intents",
            "POST"
        )

        if not request:
            LOGGER.error("Failed To Get Client Secret, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
            worker_vars.payment_method = Status.proxy_error
            return

        match request.status_code:
            case 429:
                LOGGER.error("Failed To Get Client Secret, Rate Limit", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
                worker_vars.payment_method = Status.token_rate_limit
                return

        client_secret = request.json()["client_secret"]

        payment_method = stripe_wrapper.setup_intents(client_secret)

        match payment_method:
            case Status.proxy_error:
                LOGGER.error("Failed To Add Card, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
                worker_vars.payment_method = Status.proxy_error
                return

            case Status.card_error:
                LOGGER.error("Failed To Add Card, Invalid Card.", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), part="STRIPE")
                worker_vars.payment_method = Status.card_error
                return

        worker_vars.payment_method = payment_method
        return

    def _get_billing_token(self, discord_wrapper: DiscordWrapper, stripe_wrapper: StripeWrapper, worker_vars: WorkerVars) -> Status|str:
        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me/billing/payment-sources/validate-billing-address",
            "POST",
            json = {
                "billing_address":   {
                    "name"        : stripe_wrapper.name,
                    "line_1"      : stripe_wrapper.street,
                    "line_2"      : stripe_wrapper.address_2,
                    "city"        : CONFIG.billing.city,
                    "state"       : CONFIG.billing.state,
                    "postal_code" : stripe_wrapper.postal,
                    "country"     : CONFIG.billing.country,
                    "email"       : ""
                }
            }
        )

        if not request:
            LOGGER.error("Failed To Get Billing Token, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
            worker_vars.billing_token = Status.proxy_error
            return

        if "token" not in request.json().keys():
            LOGGER.error("Failed To Get Billing Token, Invalid Billing, Check Config", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
            worker_vars.billing_token = Status.config_error
            return

        worker_vars.billing_token = request.json()["token"]
        return

    def _find_vcc(self, discord_wrapper: DiscordWrapper, stripe_wrapper: StripeWrapper, billing_token: str) -> Status|str:
        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me/billing/payment-sources"
        )

        if not request:
            LOGGER.error("Failed To Get Payment Sources, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
            return Status.proxy_error

        if billing_token:
            for vcc in request.json():
                if vcc["type"] == 1 and vcc["last_4"] == stripe_wrapper.vcc.card_number[-4:]:
                    return vcc["id"]

            if not CONFIG.look_for_card_on_token:
                return Status.card_error

            LOGGER.info("Couldn't Add Card, Trying To Find VCC On Token", discord_wrapper.token[:30])
            return self._find_vcc(discord_wrapper, stripe_wrapper, None)
        else:
            for vcc in request.json():
                if vcc["invalid"] == False or CONFIG.use_card_from_account_if_invalid:
                    return vcc["id"]

            LOGGER.warn("No Valid VCC Found", discord_wrapper.token[:30])
            return Status.token_error

    def _remove_vcc(self, discord_wrapper: DiscordWrapper, stripe_wrapper: StripeWrapper, payment_source_id: str):
        if not CONFIG.remove_vcc and GLOBAL_VARS.mode != Redeem_Modes.remove_vcc_only:
            return

        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me/billing/subscriptions"
        )

        if not request:
            LOGGER.error("Failed To Get Subscriptions, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
            return

        if request.status_code != 200:
            LOGGER.error("Failed To Get Subscriptions, SHOW US", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), r_text = request.text)
            return

        if request.json() != []: # If there is a subscription remove it
            nitro_sub_id = request.json()[0]["id"]

            request = discord_wrapper.tls.do_request(
                f"https://discord.com/api/v9/users/@me/billing/subscriptions/{nitro_sub_id}?location_stack=user%20settings&location_stack=subscription%20header&location_stack=premium%20subscription%20cancellation%20modal",
                "PATCH",
                json = {
                    "payment_source_token": None,
                    "gateway_checkout_context": None,
                    "items": []
                }
            )

            if not request:
                LOGGER.error("Failed To Stop Subscription, Cannot Remove VCC, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
                return

        request = discord_wrapper.tls.do_request(
            f"https://discord.com/api/v9/users/@me/billing/payment-sources/{payment_source_id}",
            "DELETE"
        )

        if not request:
            LOGGER.error("Failed To Remove VCC, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
            return

        LOGGER.success("Removed VCC", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
        return

    def _find_redeem(self, discord_wrapper: DiscordWrapper, stripe_wrapper: StripeWrapper, payment_source_id: str) -> Status|str:
        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me/billing/payments?limit=20"
        )

        if not request:
            LOGGER.error("Failed To Get Payments, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
            return Status.proxy_error

        for payment in request.json():
            if payment["status"] == 5 and payment["payment_source"]["id"] == payment_source_id:
                return Status.success

        return Status.promo_error

    def _add_card(self, discord_wrapper: DiscordWrapper, stripe_wrapper: StripeWrapper, billing_token: str, payment_method: str) -> int|str:
        if not billing_token:
            vcc = self._find_vcc(discord_wrapper, stripe_wrapper, billing_token)
            return vcc

        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me/billing/payment-sources",
            "POST",
            json = {
                "payment_gateway": 1,
                "token": payment_method,
                "billing_address_token": billing_token,
                "billing_address":{
                   "name"       : stripe_wrapper.name,
                   "line_1"     : stripe_wrapper.street,
                   "line_2"     : stripe_wrapper.address_2,
                   "city"       : CONFIG.billing.city,
                   "state"      : CONFIG.billing.state,
                   "postal_code": stripe_wrapper.postal,
                   "country"    : CONFIG.billing.country,
                   "email"      : ""
                }
            }
        )

        if not request:
            LOGGER.error("Failed To Add Card, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
            return Status.proxy_error

        match request.status_code:
            case 200:
                return request.json()["id"] # Payment Source

            case 429:
                LOGGER.warn("Failed To Add Card, Rate Limit", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
                return Status.token_rate_limit

            case 400:
                if "captcha_key" in request.json().keys():
                    vcc = self._find_vcc(discord_wrapper, stripe_wrapper, billing_token)

                    if type(vcc) != str:
                        LOGGER.warn("Failed To Add Card, Captcha", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
                        return Status.token_captcha_error

                    return vcc

                elif "Duplicate payment source" in request.text:
                    return self._find_vcc(discord_wrapper, stripe_wrapper, billing_token)

                else:
                    LOGGER.error("Failed To Add Card, Invalid Card.", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), message = request.text, part="DISCORD")
                    return Status.card_error


    def _handle_status(self, status: Status, token: TOKEN, stripe_wrapper: StripeWrapper = None, promo: PROMO = None, websocket_token: WebsocketDiscord = None) -> Status:
        match status:
            case Status.proxy_error:
                FILES.decrease_vcc_counter(stripe_wrapper.vcc) # TODO: If proxy error happens on promo fetch and redeem, we shouldn't decrease the usage
                websocket_token.close_websocket()
                return Status.proxy_error

            case Status.token_rate_limit:
                FILES.decrease_vcc_counter(stripe_wrapper.vcc)

                FILES.output_token_promo(token.raw_line, promo, "rate_limit")
                websocket_token.close_websocket()
                return Status.token_error

            case Status.token_captcha_error:
                GLOBAL_VARS.metrics.captcha_tokens += 1

                FILES.decrease_vcc_counter(stripe_wrapper.vcc)

                FILES.output_token_promo(token.raw_line, promo, "captcha_error")
                websocket_token.close_websocket()
                return Status.token_error

            case Status.config_error: # Hard stop, since all tokens would fail.
                FILES.decrease_vcc_counter(stripe_wrapper.vcc)
                FILES.output_token_promo(token.raw_line, promo, "config_error")
                websocket_token.close_websocket()
                #GLOBAL_VARS.hard_stop = True
                return Status.config_error

            case Status.token_error:
                FILES.decrease_vcc_counter(stripe_wrapper.vcc)
                FILES.output_token_promo(token.raw_line, promo, "token_error")
                websocket_token.close_websocket()
                return Status.token_error

            case Status.card_error:
                FILES.remove_vcc(stripe_wrapper.vcc)

                if type(stripe_wrapper.vcc) == VCC:
                    FILES.output_and_remove("vccs", stripe_wrapper.vcc.raw_vcc, "invalid_vcc")

                return Status.card_error

            case Status.promo_error:
                FILES.output_and_remove("promos", promo.raw_promo, "invalid_promo")
                return Status.promo_error

            case Status.token_promo_error:
                FILES.output_token_promo(token.raw_line, promo, "token_error", True)
                websocket_token.close_websocket()
                return Status.token_promo_error

            case Status.token_card_error: # Not remove the card since its not card fault but token, but don't give its use back either, since its already added on the acc
                FILES.output_and_remove("tokens", token.raw_line, "token_error")
                websocket_token.close_websocket()
                return Status.token_error

            case Status.token_redeem:
                FILES.delete_a_line("input", "tokens", token.raw_line)
                FILES.delete_a_line("input", "promos", promo.raw_promo)
                FILES.output(FILES.output_directory, "redeemed", token.full_token)
                GLOBAL_VARS.metrics.redeems += 1
                websocket_token.close_websocket()
                return Status.success

            case Status.token_vcc_add:
                FILES.delete_a_line("input", "tokens", token.raw_line)
                FILES.output(FILES.output_directory, "vcc_added", token.full_token)
                GLOBAL_VARS.metrics.redeems += 1
                websocket_token.close_websocket()
                return Status.success

            case Status.token_vcc_remove:
                FILES.delete_a_line("input", "tokens", token.raw_line)
                FILES.output(FILES.output_directory, "vcc_removed", token.full_token)
                GLOBAL_VARS.metrics.redeems += 1
                websocket_token.close_websocket()
                return Status.success

        return Status.success
    def _fetch_promo(self, discord_wrapper: DiscordWrapper, promo: PROMO):
        if promo.link and "/" in promo.link:
            request = discord_wrapper.tls.do_request(
                f"https://discord.com/api/v9/entitlements/partner-promotions/{promo.link.split('/')[0]}",
                "POST",
                json = {
                    "jwt": promo.link.split("/")[1]
                }
            )

            if not request:
                return Status.proxy_error

            if request.status_code == 200:
                LOGGER.extra_info("Linked Promo", discord_wrapper.token[:30], promo = request.json()["code"][:30])
                promo.linked_promo = True
                promo.link = request.json()["code"]
                return Status.success

            elif request.status_code == 429:
                LOGGER.warn("Rate Limit, While Fetching Promo", discord_wrapper.token[:30], promo = promo.link.split("/")[1][:30], duration = request.json()["retry_after"])
                sleep(request.json()["retry_after"])
                return self._fetch_promo(discord_wrapper, promo)

            elif "Gift already claimed." in request.text:
                LOGGER.warn("Already Used Promo", discord_wrapper.token[:30], promo = promo.link.split("/")[1][:30])
                return Status.promo_error

            elif request.json()["code"] == 0:
                LOGGER.warn("Flagged Promo, Using Other.", discord_wrapper.token[:30], promo = promo.link.split("/")[1][:30])
                return Status.promo_error

            elif "Token is invalid." in request.text:
                LOGGER.warn("The PromoLink Is Invalid.", discord_wrapper.token[:30], promo = promo.link.split("/")[1][:30])
                return Status.promo_error

            elif "Unknown gift" in request.text:
                LOGGER.warn("Unknown Gift.", discord_wrapper.token[:30], promo = promo.link.split("/")[1][:30])
                return Status.promo_error

            elif "This promotion is invalid." in request.text:
                LOGGER.warn("This Promotion Is Invalid.", discord_wrapper.token[:30], promo = promo.link.split("/")[1][:30])
                return Status.promo_error

            elif "User has already claimed promotion." in request.text:
               LOGGER.warn("User has already claimed promotion.", discord_wrapper.token[:30], promo = promo.link.split("/")[1][:30])
               return Status.token_card_error

            elif "Previous purchase error." in request.text:
                LOGGER.warn("Token Cannot Use The Gift.", discord_wrapper.token[:30], promo = promo.link.split("/")[1][:30])
                return Status.token_card_error

            elif "New subscription required" in request.text:
                LOGGER.warn("New Subscription Required, Token Issue.", discord_wrapper.token[:30], promo = promo.link.split("/")[1][:30])
                return Status.token_card_error

            else:
                LOGGER.warn("Unknown Error While Fetching Promo, SHOWS US.", discord_wrapper.token[:30], promo = promo.link.split("/")[1][:30], response = request.text)
                return Status.token_promo_error

        return promo

    def _authenticate_vcc(self, discord_wrapper: DiscordWrapper, stripe_wrapper: StripeWrapper, payment_id: str):
        request = discord_wrapper.tls.do_request(
            f"https://discord.com/api/v9/users/@me/billing/stripe/payment-intents/payments/{payment_id}"
        )

        if not request:
            LOGGER.error("Failed To Authenticate VCC, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
            return Status.proxy_error

        stripe_client_secret = request.json()["stripe_payment_intent_client_secret"]

        match stripe_wrapper.authenticate_vcc(stripe_client_secret):
            case Status.proxy_error:
                LOGGER.error("Failed To Authenticate VCC, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
                return Status.proxy_error

            case Status.card_error:
                LOGGER.error("Failed To Authenticate VCC, Bad VCC.", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
                return Status.card_error

        for _ in range(5):
            sleep(1)

            request = discord_wrapper.tls.do_request(
                f"https://discord.com/api/v9/users/@me/billing/payments/{payment_id}"
            )

            if not request:
                LOGGER.error("Failed To Authenticate VCC, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
                return Status.proxy_error

            if "status" not in request.json().keys():
                continue # The vcc is has not got its status yet from the auth.

            if request.json()["status"] == 5:
                return Status.success

            elif request.json()["status"] == 2:
                LOGGER.error("Failed To Authenticate VCC, Bad VCC.", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
                break

        LOGGER.error("Failed To Authenticate VCC, Bad VCC.", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))
        return Status.card_error

    def _redeem_promo(self, discord_wrapper: DiscordWrapper, stripe_wrapper: StripeWrapper, payment_source_id: str, promo: PROMO, start_counter: float, tries: int = 0):
        if not promo.trial_promo:
            request = discord_wrapper.tls.do_request(
                f"https://discord.com/api/v9/entitlements/gift-codes/{promo.link}/redeem",
                "POST",
                json = {
                    "channel_id": None,
                    "payment_source_id": payment_source_id,
                    "gateway_checkout_context": None
                }
            )
        else:
            currency: str = ""
            price: int = 0

            request = discord_wrapper.tls.do_request("https://discord.com/api/v9/store/published-listings/skus/521847234246082599/subscription-plans")

            try:
                for sub in request.json():
                    if sub["id"] == "511651880837840896":
                        subscription_prices = sub["prices"]["0"]["payment_source_prices"]
                        for price in subscription_prices:
                            currency = subscription_prices[price][0]["currency"]
                            price = int(subscription_prices[price][0]["amount"])
                            break

                        break
            except:
                LOGGER.error("Failed to fetch currency information for trial!", request.text)
                return Status.token_card_error

            LOGGER.extra_info("Fetched trial currency information", currency, price)

            request = discord_wrapper.tls.do_request(
                "https://discord.com/api/v9/users/@me/billing/subscriptions",
                "POST",
                json = {
                    "items": [
                        {
                          "plan_id": "511651880837840896",
                          "quantity": 1
                        }
                    ],
                    "payment_source_id": payment_source_id,
                    "payment_source_token": None,
                    "trial_id": promo.trial_id,
                    "return_url": None,
                    "currency": currency,
                    "metadata": {
                        "user_trial_offer_id": promo.user_trial_offer_id
                    },
                    "gateway_checkout_context": None,
                    "purchase_token": str(uuid4()),
                    "load_id": str(uuid4()),
                    "expected_invoice_price": {
                        "amount": 0,
                        "currency": currency
                    },
                    "expected_renewal_price": {
                        "amount": price,
                        "currency": currency
                    }
                }
            )

        if not request:
            LOGGER.error("Failed To Reedem Promo, Check Proxies / Internet", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])
            return Status.proxy_error

        if request.status_code == 200:
            LOGGER.success("Redeemed Promo", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30], t = f"{perf_counter() - start_counter:.2f}s")
            return Status.token_redeem

        elif "This gift has been redeemed already." in request.text or "This resource is currently overloaded" in request.text:
            if self._find_redeem(discord_wrapper, stripe_wrapper, payment_source_id) == Status.success:
                LOGGER.success("Redeemed Promo", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30], t = f"{perf_counter() - start_counter:.2f}s")
                return Status.token_redeem

            if "This resource is currently overloaded" in request.text:
                LOGGER.error("Failed To Reedem Promo, Resource Currently Overloaded, Retrying", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])
                return self._redeem_promo(discord_wrapper, stripe_wrapper, payment_source_id, promo, start_counter, tries)
            else:
                LOGGER.warn("Already Used Promo, If linked use token|promo format.", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30], t = f"{perf_counter() - start_counter:.2f}s")

            if promo.linked_promo:
                return Status.token_promo_error

            return Status.promo_error

        elif "Authentication required" in request.text:
            status = Status.card_error

            while tries <= CONFIG.auth_retry:
                status = self._authenticate_vcc(discord_wrapper, stripe_wrapper, request.json()["payment_id"])

                if status == Status.success:
                    return self._redeem_promo(discord_wrapper, stripe_wrapper, payment_source_id, promo, start_counter)

                GLOBAL_VARS.metrics.auth_errors += 1
                return self._redeem_promo(discord_wrapper, stripe_wrapper, payment_source_id, promo, start_counter, tries + 1)

            return status

        elif request.status_code == 429:
            LOGGER.warn("Rate Limit While Redeeming Promo, Sleeping", discord_wrapper.token[:30], promo = repr(promo)[:30], duration = request.json()["retry_after"])
            sleep(request.json()["retry_after"])
            return self._redeem_promo(discord_wrapper, stripe_wrapper, payment_source_id, promo, start_counter, tries)

        elif "This payment method cannot be used" in request.text:
            LOGGER.warn("Invalid VCC, Payment Method Cannot Be Used, VCC Already At Max Uses?", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])
            return Status.card_error

        elif "The card was declined" in request.text:
            LOGGER.warn("Invalid VCC, Card Declined", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])
            return Status.card_error

        elif "There was an error processing the card." in request.text:
            LOGGER.warn("Invalid VCC, Couldn't Process Card", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])
            return Status.card_error

        elif "enough funds to complete the purchase." in request.text:
            LOGGER.warn("Insufficient Funds On VCC.", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])
            return Status.card_error

        elif "The card number is not valid" in request.text:
            LOGGER.warn("Invalid VCC, Card Number Invalid, Is The VCC Deleted?", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])
            return Status.card_error

        elif "You have already owned this SKU." in request.text:
            LOGGER.warn("Token Already Redeemed This Promo", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])
            return Status.token_card_error

        elif "Cannot redeem this gift in your location" in request.text:
            LOGGER.warn("Cannot Redeem Promo In Your Location", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])
            return Status.token_card_error

        elif "Cannot redeem gift" in request.text:
            LOGGER.warn("Cannot Redeem Gift, Is The Token Aged Enough?", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])
            return Status.token_card_error

        elif "New subscription required to redeem gift." in request.text:
            LOGGER.warn("New Subscription Required, Token already has nitro.", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])
            return Status.token_card_error

        elif "Unknown Gift Code" in request.text:
            LOGGER.warn("Unknown Promo", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])

            if promo.linked_promo:
                return Status.token_promo_error

            return Status.promo_error

        elif "This gift code belongs to someone else" in request.text:
            LOGGER.warn("This Promo Belongs To Someone Else, Check if you are using linked tokens using token|promo format", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30])

            if promo.linked_promo:
                return Status.token_promo_error

            return Status.promo_error

        elif "500: Internal" in request.text:
            return self._redeem_promo(discord_wrapper, stripe_wrapper, payment_source_id, promo, start_counter, tries)

        else:
            LOGGER.warn("Unknown Error While Reedeming Promo, SHOWS US.", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), promo = repr(promo)[:30], response = request.text)
            return Status.token_promo_error

    def _find_trial(self, discord_wrapper: DiscordWrapper) -> PROMO|None:
        request = discord_wrapper.tls.do_request(
            "https://discord.com/api/v9/users/@me/billing/user-offer",
            "POST",
            json = {}
        )

        if not request:
            LOGGER.error("Failed To Find Trial, Check Proxies / Internet", discord_wrapper.token[:30])
            return None

        if "message" in request.json().keys():
            LOGGER.extra_info("Failed To Find Trial, User Likely Has No Trial", discord_wrapper.token[:30], r_text = request.json()["message"])
            return None

        if request.status_code != 200:
            LOGGER.extra_info("Failed To Find Trial, User Likely Has No Trial", discord_wrapper.token[:30], r_text = request.text)
            return None

        user_trial_offer_id: str = request.json()["user_trial_offer"]["id"]
        trial_id: str = request.json()["user_trial_offer"]["trial_id"]

        promo: PROMO = PROMO(None, None, True, True, user_trial_offer_id, trial_id)
        LOGGER.success("Found Trial On Token", discord_wrapper.token[:30], trial_id = trial_id[:30])
        return promo

    def _pause_handler(self):
        if CONFIG.pause_after_redeems and GLOBAL_VARS.metrics.redeems and GLOBAL_VARS.metrics.redeems % CONFIG.pause_after_redeems == 0:
            GLOBAL_VARS.paused = True
            LOGGER.info("Paused Thread, Redeem Target Reached.")

        while GLOBAL_VARS.paused:
            sleep(.1)

    def _turbo_mode_handler(self) -> bool:
        waited = False

        with REDEEM_LOCK:
            while CONFIG.turbo_mode and GLOBAL_VARS.in_redeem == GLOBAL_VARS.threads_amount:
                waited = True
                sleep(.1)

            GLOBAL_VARS.in_redeem += 1

        return waited

    def worker(self):
        worker_vars: WorkerVars = WorkerVars()

        while FILES.tokens and FILES.vccs_left() and not GLOBAL_VARS.hard_stop:
            self._pause_handler()

            finished = False

            raw_token, token, promo = FILES.get_token()

            if not token:
                continue

            LOGGER.extra_info("Logging Into Token", token.formatted_token[:30])

            discord_wrapper = DiscordWrapper(token.formatted_token)
            websocket_token = WebsocketDiscord(discord_wrapper.token, 0, discord_wrapper, UTILS_DISCORD.browser_user_agent)

            match discord_wrapper.set_headers():
                case 401:
                    GLOBAL_VARS.metrics.fails += 1
                    LOGGER.error("Could Not Login Into Token, Invalid Token", token.formatted_token[:30])
                    FILES.output_and_remove("tokens", raw_token, "invalid_token")
                    continue

                case 403:
                    GLOBAL_VARS.metrics.fails += 1
                    LOGGER.error("Could Not Login Into Token, Require Verification", token.formatted_token[:30])
                    FILES.output_and_remove("tokens", raw_token, "verify_locked")
                    continue

                case None:
                    LOGGER.error("Could Not Login Into Token, Check Proxies / Internet", token.formatted_token[:30])
                    FILES.output_and_remove("tokens", raw_token, "failed_proxy_error")
                    continue

                case _: 
                    websocket_token.start_websocket()

            if not promo and not FILES.promos_left():
                promo = self._find_trial(discord_wrapper)

            if not promo and not FILES.promos_left():
                break

            if CONFIG.token_unflagger:
                discord_wrapper.accept_tos()

            LOGGER.extra_info("Logged Into Token", token.formatted_token[:30], proxy_timezone = discord_wrapper.tls.client.headers["x-discord-timezone"])

            while (FILES.promos_left() or promo) and FILES.vccs_left() and not finished:
                vcc = FILES.get_vcc()

                if not vcc:
                    continue

                stripe_wrapper = StripeWrapper(vcc)

                match self._handle_status(stripe_wrapper.setup_client(), token, stripe_wrapper, promo, websocket_token):
                    case Status.success: pass
                    case Status.card_error: continue
                    case _:
                        GLOBAL_VARS.metrics.fails += 1
                        break

                match self._handle_status(self._check_billing(discord_wrapper), token, stripe_wrapper, promo, websocket_token):
                    case Status.success: pass
                    case _:
                        GLOBAL_VARS.metrics.fails += 1
                        break

                start_counter = perf_counter()

                if not CONFIG.turbo_mode:
                    text = "Finding VCC" if vcc == "USING FROM ACCOUNT" else "Using VCC"
                    LOGGER.extra_info("Genned Stripe Fingerprint", token.formatted_token[:30], stripe_fp = stripe_wrapper.fp.id)
                    LOGGER.info(text, token.formatted_token[:30], vcc = repr(stripe_wrapper.vcc), t = f"{perf_counter() - start_counter:.2f}s")

                worker_vars.billing_token = None
                worker_vars.payment_method = None

                if GLOBAL_VARS.mode in (Redeem_Modes.normal, Redeem_Modes.add_vcc_only):
                    billing_thread = Thread(
                        target = self._get_billing_token,
                        args = (discord_wrapper, stripe_wrapper, worker_vars, )
                    )

                    payment_method_thread = Thread(
                        target = self._get_payment_method,
                        args = (discord_wrapper, stripe_wrapper, worker_vars, )
                    )

                    billing_thread.start()
                    payment_method_thread.start()

                    billing_thread.join()
                    payment_method_thread.join()

                    match self._handle_status(worker_vars.billing_token, token, stripe_wrapper, promo, websocket_token):
                        case Status.success: pass
                        case _:
                            GLOBAL_VARS.metrics.fails += 1
                            break

                    match self._handle_status(worker_vars.payment_method, token, stripe_wrapper, promo, websocket_token):
                        case Status.success: pass
                        case Status.card_error: continue
                        case _:
                            GLOBAL_VARS.metrics.fails += 1
                            break

                payment_source = self._add_card(discord_wrapper, stripe_wrapper, worker_vars.billing_token, worker_vars.payment_method)

                match self._handle_status(payment_source, token, stripe_wrapper, promo, websocket_token):
                    case Status.success: pass
                    case Status.card_error: continue
                    case _:
                        GLOBAL_VARS.metrics.fails += 1
                        break

                start_counter = perf_counter() if self._turbo_mode_handler() else start_counter

                text = "Successfully Found Card" if vcc == "USING FROM ACCOUNT" else "Successfully Added Card"
                LOGGER.success(text, discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc))

                if GLOBAL_VARS.mode == Redeem_Modes.add_vcc_only:
                    finished = True
                    self._handle_status(Status.token_vcc_add, token, stripe_wrapper, promo, websocket_token)
                    GLOBAL_VARS.in_redeem -= 1
                    continue

                elif GLOBAL_VARS.mode == Redeem_Modes.remove_vcc_only:
                    finished = True
                    self._remove_vcc(discord_wrapper, stripe_wrapper, payment_source)
                    self._handle_status(Status.token_vcc_remove, token, stripe_wrapper, promo, websocket_token)
                    GLOBAL_VARS.in_redeem -= 1
                    continue

                while (FILES.promos_left() or promo):
                    if not promo or not promo.linked_promo: # if promo already exists, we check if its a linked one
                        promo = FILES.get_promo()

                    if not promo:
                        continue

                    match self._handle_status(self._fetch_promo(discord_wrapper, promo), token, stripe_wrapper, promo, websocket_token):
                        case Status.success: pass
                        case Status.promo_error: continue
                        case _:
                            GLOBAL_VARS.metrics.fails += 1
                            finished = True
                            break

                    if CONFIG.threads_redeem_one_by_one:
                        GLOBAL_VARS.global_sleep_mutex.acquire()

                    match self._handle_status(self._redeem_promo(discord_wrapper, stripe_wrapper, payment_source, promo, start_counter), token, stripe_wrapper, promo, websocket_token):
                        case Status.promo_error:
                            if CONFIG.threads_redeem_one_by_one:
                                GLOBAL_VARS.global_sleep_mutex.release()
                            continue

                        case Status.card_error:
                            if CONFIG.fetch_new_vcc:
                                break

                            GLOBAL_VARS.metrics.fails += 1
                            FILES.output_and_remove("tokens", raw_token, "fail_redeem_vcc_error")

                            finished = True
                            break

                        case Status.success:
                            finished = True

                            self._remove_vcc(discord_wrapper, stripe_wrapper, payment_source)
                            TokenCustomizer.customize_token(discord_wrapper, token)

                            if CONFIG.sleep_duration > 0:
                                time_sleep = CONFIG.sleep_duration if not CONFIG.minimum_redeem_time else CONFIG.sleep_duration - (perf_counter() - start_counter)

                                if time_sleep > 0:
                                    LOGGER.info("Sleeping.", f"{time_sleep:.2f}s", discord_wrapper.token[:30], vcc = repr(stripe_wrapper.vcc), t = f"{perf_counter() - start_counter:.2f}s")
                                    sleep(CONFIG.sleep_duration)

                            break

                        case _:
                            GLOBAL_VARS.metrics.fails += 1
                            finished = True
                            break

                if CONFIG.threads_redeem_one_by_one and GLOBAL_VARS.global_sleep_mutex.locked():
                    GLOBAL_VARS.global_sleep_mutex.release()

                GLOBAL_VARS.in_redeem -= 1

        LOGGER.info("Thread Stopped", tokens_left = len(FILES.tokens), linked_tokens_left = len(FILES.linked_tokens), vccs_left = FILES.len_vccs(), promos_left = len(FILES.promos))

class SessionManager:
    def start_session(self, threads_amount: str|int) -> bool:
        if GLOBAL_VARS.sessions:
            return False

        if type(threads_amount) == str:
            threads_amount = int(threads_amount)

        while not UTILS_DISCORD.stripe_key:
            LOGGER.info("Waiting To Scrape Discord Details.")
            sleep(10)

        GLOBAL_VARS.threads_amount = threads_amount
        GLOBAL_VARS.hard_stop = False

        FILES.update_materials()

        for _ in range(GLOBAL_VARS.threads_amount * (2 if CONFIG.turbo_mode else 1)):
            thread = Thread(target = REDEEMER.worker)
            GLOBAL_VARS.sessions.append(thread)
            thread.start()

        return True

    def join_threads(self, input_print: bool = False):
        for thread in GLOBAL_VARS.sessions:
            thread.join()

        if input_print:
            LOGGER.info("Threads Finished, Press Enter To Clean Up.")
            LOGGER.input_print()

        FILES.update_materials()
        GLOBAL_VARS.sessions.clear()

SESSION_MANAGER = SessionManager()
REDEEMER = Redeemer()