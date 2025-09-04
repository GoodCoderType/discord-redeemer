from modules.redeemer.worker    import SESSION_MANAGER
from modules.client.webhook     import WEBHOOK_CLIENT
from modules.client.client      import TlsClient
from modules.bot.bot_utils      import BOT_UTILS
from modules.utils.logger       import LOGGER
from modules.utils.winapi       import WINAPI
from modules.utils.utils        import FILES, CONFIG, GLOBAL_VARS, Redeem_Modes
from modules.utils.menu         import MENU
from dataclasses                import dataclass
from discord.ext                import commands
from discord.ui                 import Button, View
from threading                  import Thread
from requests                   import get
from logging                    import CRITICAL, getLogger
from pathlib                    import Path
from io                         import BytesIO
import discord  
import asyncio

getLogger("discord.client").setLevel(CRITICAL)
getLogger("discord.gateway").setLevel(CRITICAL)

bot = commands.Bot(
    command_prefix = "!",
    intents = discord.Intents.all()
)

@dataclass
class BotFile:
    data: bytes
    name: str
    mimetype: str = "text/plain"


class Buttons(View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(
        label = "Stop Threads", 
        style = discord.ButtonStyle.danger, 
        custom_id = "stop_threads",
    )
    async def stop_threads(self, interaction: discord.Interaction, button: discord.ui.Button):
        GLOBAL_VARS.hard_stop = True
        await interaction.response.send_message(embed = BOT_UTILS.embed("Threads Stopped", "Threads Are Stopping.", discord.colour.Color.green(), "Threads Stopped"), ephemeral=True)

    @discord.ui.button(
        label = "Toggle Pause", 
        style = discord.ButtonStyle.grey, 
        custom_id = "toggle_threads"
    )
    async def toggle_threads(self, interaction: discord.Interaction, button: discord.ui.Button):
        GLOBAL_VARS.paused = not GLOBAL_VARS.paused
        await interaction.response.send_message(embed = BOT_UTILS.embed("Threads Toggled", f"Threads Are {'Pausing' if GLOBAL_VARS.paused else 'Resuming'}.", discord.colour.Color.green(), "Threads Toggled"), ephemeral=True)
    

class BotGeneral(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logs_channel = None

    async def send_log(self, embed: discord.Embed):
        if self.logs_channel:
            await self.logs_channel.send(embed = embed)
    
    async def check_owner(self, interaction: discord.Interaction, response_embed: discord.Embed) -> bool:
        status_owner = BOT_UTILS.check_owner(interaction.user.id)

        if not status_owner:
            await self.send_log(response_embed)
            await interaction.response.send_message(embed = response_embed, ephemeral = True)

        return status_owner
    
    async def fetch_paste_ee(self, paste_ee: str) -> list[str]:
        if "paste.ee/p/" in paste_ee:
            paste_ee = paste_ee.split("paste.ee/p/")[1]

        url = f"https://paste.ee/d/{paste_ee}"

        try:
            content = get(url).text
            lines = content.splitlines()
        except:
            return []
        
        return lines

    async def finalize_session(self, channel: discord.TextChannel):
        folder_path = Path(FILES.output_directory)
        files: list[discord.File] = []
            
        for file in folder_path.iterdir():
            if file.is_file():
                files.append(discord.File(str(file)))

        await channel.send(files = files)

        MENU.print_menu()
        MENU.print_info("INPUT", "Threads Amount?")

    @discord.app_commands.command(name = "launch_session", description = "Allows You To Launch A Session.")
    @discord.app_commands.choices(mode = [
        discord.app_commands.Choice(name = "Normal", value = Redeem_Modes.normal),
        discord.app_commands.Choice(name = "Add VCC Only", value = Redeem_Modes.add_vcc_only),
        discord.app_commands.Choice(name = "Redeem Promo Only", value = Redeem_Modes.redeem_promo_only),
        discord.app_commands.Choice(name = "Remove VCC Only", value = Redeem_Modes.remove_vcc_only)
    ])
    async def launch_session(self, interaction: discord.Interaction, mode: discord.app_commands.Choice[int], threads_amount: int):
        buttons: discord.ui.View = Buttons()
        channel: discord.TextChannel = await bot.fetch_channel(interaction.channel_id)
        response_embed: discord.Embed = BOT_UTILS.warn_embed("You Are Not The Owner, You Cannot Launch A Session!", User = interaction.user)

        if not await self.check_owner(interaction, response_embed):
            return

        GLOBAL_VARS.mode = mode

        if not SESSION_MANAGER.start_session(threads_amount):
            response_embed = BOT_UTILS.warn_embed("Session Already Running!")
            await interaction.response.send_message(embed = response_embed)
            return
        
        session_kwargs = {
            "Threads":  threads_amount,
            "Tokens":   len(FILES.tokens) + len(FILES.linked_tokens),
            "VCCS":     FILES.len_vccs(),
            "Promos":   len(FILES.promos),
            "Redeems":  GLOBAL_VARS.metrics.redeems,
            "Fails":    GLOBAL_VARS.metrics.fails,
            "Captchas": GLOBAL_VARS.metrics.captcha_tokens
        }

        session_message: discord.Message = await channel.send(embed = BOT_UTILS.session_embed(
            description = "Starting Session",
            **session_kwargs
        ), view = buttons)

        while any(thread.is_alive() for thread in GLOBAL_VARS.sessions):
            session_kwargs.update({
                "Tokens":   len(FILES.tokens) + len(FILES.linked_tokens),
                "VCCS":     FILES.len_vccs(),
                "Promos":   len(FILES.promos),
                "Redeems":  GLOBAL_VARS.metrics.redeems,
                "Fails":    GLOBAL_VARS.metrics.fails,
                "Captchas": GLOBAL_VARS.metrics.captcha_tokens
            })

            await session_message.edit(embed = BOT_UTILS.session_embed(
                description = "Session Details",
                **session_kwargs
            ))

            await asyncio.sleep(5)

        SESSION_MANAGER.join_threads()

        await session_message.edit(embed = BOT_UTILS.session_embed(
            description = "Session Finished",
            **session_kwargs
        ))

        await self.finalize_session(channel)

    @discord.app_commands.command(name = "restock", description= "Restock Material Type.")
    @discord.app_commands.choices(type = [
        discord.app_commands.Choice(name = "VCCS", value = "vccs"),
        discord.app_commands.Choice(name = "PROMOS", value = "promos"),
        discord.app_commands.Choice(name = "TOKENS", value = "tokens")
    ])
    async def restock(self, interaction: discord.Interaction, type: discord.app_commands.Choice[str], file: discord.Attachment = None, paste_ee: str = None):
        lines: list[str] = []
        response_embed: discord.Embed = BOT_UTILS.warn_embed("You Are Not The Owner, You Cannot Restock!", User = interaction.user)

        if not await self.check_owner(interaction, response_embed):
            return

        if not file and not paste_ee:
            response_embed = BOT_UTILS.warn_embed("You Must Provide A File Or A Paste.ee Link!")
            await interaction.response.send_message(embed = response_embed)
            return

        if paste_ee:
            lines = await self.fetch_paste_ee(paste_ee)

            if not lines:
                response_embed = BOT_UTILS.error_embed("Could Not Fetch Paste.ee!")
                await interaction.response.send_message(embed = response_embed)
                return

        if file:
            lines.extend((await file.read()).decode().splitlines())

        FILES.output("./input", type.value, lines)
        FILES.update_materials()

        response_embed = BOT_UTILS.success_embed(
            description = "Materials Have Been Restocked Successfully!",
            Tokens = len(FILES.tokens) + len(FILES.linked_tokens),
            VCCS = FILES.len_vccs(),
            Promos = len(FILES.promos)
        )

        await interaction.response.send_message(embed = response_embed)

    @discord.app_commands.command(name = "materials", description= "Shows Current Materials.")
    async def materials(self, interaction: discord.Interaction):
        response_embed: discord.Embed = BOT_UTILS.warn_embed("You Are Not The Owner, You Cannot See Materials", User = interaction.user)

        if not await self.check_owner(interaction, response_embed):
            return
        
        FILES.update_materials()

        response_embed = BOT_UTILS.success_embed(
            "Total Materials Loaded",
            Tokens = len(FILES.tokens) + len(FILES.linked_tokens),
            VCCS = FILES.len_vccs(),
            Promos = len(FILES.promos)             
        )

        await interaction.response.send_message(embed = response_embed)
    
    @discord.app_commands.command(name="clear_materials", description="Allows You To Clear Materials.")
    @discord.app_commands.choices(type = [
        discord.app_commands.Choice(name = "VCCS", value = "vccs"),
        discord.app_commands.Choice(name = "PROMOS", value = "promos"),
        discord.app_commands.Choice(name = "TOKENS", value = "tokens")
    ])
    async def clear_materials(self, interaction: discord.Interaction, type: discord.app_commands.Choice[str]):
        response_embed: discord.Embed = BOT_UTILS.warn_embed("You Are Not The Owner, You Cannot Clear Materials!", User = interaction.user)

        if not await self.check_owner(interaction, response_embed):
            return

        FILES.clear_file("./input", type.value)
        FILES.update_materials()

        response_embed = BOT_UTILS.success_embed(
            description = "Materials Have Been Cleared Successfully.",
            Tokens = len(FILES.tokens) + len(FILES.linked_tokens),
            VCCS = FILES.len_vccs(),
            Promos = len(FILES.promos)
        )

        await interaction.response.send_message(embed = response_embed)

    @discord.app_commands.command(name="clear_output", description="Allows You To Cleat Output.")
    async def clear_output(self, interaction: discord.Interaction):
        response_embed: discord.Embed = BOT_UTILS.warn_embed("You Are Not The Owner, You Cannot Clear Output!", User = interaction.user)

        if not await self.check_owner(interaction, response_embed):
            return

        for file in Path(FILES.output_directory).iterdir():
            if file.is_file():
                FILES.clear_file(FILES.output_directory, file.name.split(".")[0])
        
        FILES.update_materials()

        response_embed = BOT_UTILS.success_embed(
            description = "Output Has Been Cleared Successfully.",
        )

        await interaction.response.send_message(embed = response_embed)

    @commands.Cog.listener("on_ready")
    async def initialize(self):
        await bot.change_presence(
            activity = discord.Activity(
                type = discord.ActivityType.watching, 
                name = "For Redeems"
            )
        )

        if type(CONFIG.bot_logs_id) is int:
            self.logs_channel = bot.get_channel(CONFIG.bot_logs_id)

            if not self.logs_channel:
                LOGGER.error("The logs channel was not found.")

        await bot.tree.sync()

async def load_cog():
    await bot.add_cog(BotGeneral(commands.Cog)) # amazing coding kill me

def start_bot():
    asyncio.run(load_cog())
    bot.run(CONFIG.bot_token, log_handler=None)
