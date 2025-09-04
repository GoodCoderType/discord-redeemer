from Cryptodome.Util.Padding    import pad, unpad
from Cryptodome.PublicKey       import RSA
from Cryptodome.Cipher          import PKCS1_OAEP, AES
from discord.ext                import commands
from discord.ui                 import Button, View
from threading                  import Thread
from dataclasses                import dataclass, field, asdict
from requests                   import get
from logging                    import CRITICAL, getLogger
from pathlib                    import Path
from typing                     import List, Tuple
from base64                     import b64encode, b64decode
from json                       import loads
from os                         import urandom
from io                         import StringIO
import discord  
import asyncio

bot = commands.Bot(
    command_prefix = "!",
    intents = discord.Intents.all()
)

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

class MaterialsEncryption:
    def __init__(self):
        self.loaded = True
        self._rsa_public_key = PKCS1_OAEP.new(RSA.import_key(f"-----BEGIN RSA PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwgH4vkdGFmPY+YrMoEtjlBUMAsEeFDFs5dO+7vZR6eYkX+goKP1X+Ezm9QTZyGw1pK2bqTgATLn57TywsJrpsNdZZK0w7LYsUrCm5DnAohe8Sw07oySKm75UbgqZnRPHFbnZsDPNoecc+aj/XZpr/dTr0rH4DO9CgeEMm6JRB+zo9MjpvKcw5cY63SYfE5MX72cG9cPGDNw35ZCfvPfAOubFk2e0YP7RCDrzI+VhdfCcnfUbfND5nLvVgNCKKnUWBvzyJXDWmUazIaqlSERxhOy4gAdBj0UBJMf/RCc/+BuIOUG7Po7hv+pPuxvfjmJpwtT2ptfNErH0y/Lh79QeiQIDAQAB\n-----END RSA PUBLIC KEY-----"))
        self._extra = b'\x96\xfc]@\xb0\x16\xc6Ja(D\xc0\x2eWY\xe7\x9f\x94\x91\xf42i\x7f\xe28R\x8d1\xa4\xde^\xf5'
    
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
    
getLogger("discord.client").setLevel(CRITICAL)
getLogger("discord.gateway").setLevel(CRITICAL)

@bot.tree.command(name = "encrypt_vccs", description= "Make Custom Format VCCS.")
async def materials(interaction: discord.Interaction, file: discord.Attachment = None, vccs: str = None, max_threads: int = 0, hide_vccs: bool = False, delay_per_redeem: int = 0, max_vcc_use: int = 0, allow_turbo: bool = False):
    if not file and not vccs:
        await interaction.response.send_message("You Must Provide A File Or VCCS!", ephemeral = True)
        return
    elif file and vccs:
        await interaction.response.send_message("You Cannot Provide Both A File And VCCS!", ephemeral = True)
        return
    
    if file:
        data = (await file.read()).decode()
    else:
        data = "\n".join(vccs.split(" "))

    parameters = FORCE_PARAMETERS(max_threads, hide_vccs, delay_per_redeem, max_vcc_use, allow_turbo)

    encrypted = MaterialsEncryption().encrypt_vccs(data, parameters)

    file = discord.File(StringIO(encrypted), filename="vccs.txt")
    await interaction.response.send_message(file = file, ephemeral=True)
@bot.event
async def on_ready():
    print("Sorry for the shit code, it was made in 5m + a piss break")
    await bot.change_presence(activity = discord.Activity(type = discord.ActivityType.watching, name = "For Vccs"))
    await bot.tree.sync()

bot.run("")