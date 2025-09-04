
from modules.utils.utils        import FILES, CONFIG
from time               import gmtime, strftime
import discord  

FOOTER = lambda msg : f"@NinjaRide - @EinTim -> {msg} • {strftime('%H:%M:%S', gmtime())}"
class BotUtils:
    @staticmethod
    def check_owner(id: int) -> bool:
        return id in CONFIG.owner_id
    
    @staticmethod
    def embed(
        title: str, 
        description: str,
        color: discord.colour.Colour,
        footer: str,
        url: str = None,
        **kwargs
    ) -> discord.Embed:

        formatted_description = description

        if kwargs:
            formatted_kwargs = [f"> **{key}:** `{value}`" for key, value in kwargs.items()]
            formatted_description = f"{formatted_description}\n{'\n'.join(formatted_kwargs)}"

        embed = discord.Embed(
            title = title, 
            description = formatted_description, 
            color = color
        ).set_thumbnail(url = "https://i.ibb.co/RBqfkJS/ninjago.png").set_footer(text = FOOTER(footer))       
        
        if url:
            embed.set_image(url = url)

        return embed
    
    @staticmethod
    def success_embed(description: str, **kwargs) -> discord.Embed:
        return BotUtils.embed(title = "✅ Success", description = description, color = discord.colour.Color.green(), footer = "Success", **kwargs)
    
    @staticmethod
    def warn_embed(description: str, **kwargs) -> discord.Embed:
        return BotUtils.embed(title = "⚠️ Warning", description = description, color = discord.colour.Color.yellow(), footer = "Warning", **kwargs)
    
    @staticmethod
    def error_embed(description: str, **kwargs) -> discord.Embed:
        return BotUtils.embed(title = "❌ Error", description = description, color = discord.colour.Color.red(), footer = "Error", **kwargs)
    
    @staticmethod
    def session_embed(description: str, **kwargs) -> discord.Embed:
        return BotUtils.embed(title = "Current Session", description = description, color = discord.colour.Color.purple(), footer = "Session", **kwargs)
    
BOT_UTILS = BotUtils()