import discord
import settings
from discord import app_commands
from discord.ext import commands
from ui.balance import BalanceShareView
from tools.text import formatCoins
from tools.ds import tryGetUser
import datetime
import lib.vortex_api as Vortex


logger = settings.logging.getLogger('discord')

class DropShareView(discord.ui.View):
    def __init__(self, user: discord.Member | discord.User, value: int, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.user = user
        self.value = value
    
    @discord.ui.button(label='Поделиться', style=discord.ButtonStyle.blurple)
    async def share(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        if not isinstance(interaction.channel, discord.TextChannel): return
        await interaction.channel.send(f'Игроку {self.user.mention} выпало {formatCoins(self.value)} в `/drop`', silent=True)


class DropCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='drop', description='Бесплатно выдает коины')
    async def balance(self, interaction: discord.Interaction):
        logger.info(f'Drop command called by {interaction.user.id} ({interaction.user.name})')
        user = await tryGetUser(interaction)
        if user is None:
            logger.info(f'User not found)')
            return
        drop = await Vortex.GetMoneyDrop(user['steamId'])
        value = drop['value']
        time = int(datetime.datetime.fromisoformat(drop['nextDrop']).replace(tzinfo=datetime.timezone.utc).timestamp())
        timerMsg = f'Вы можете забрать больше коинов <t:{time}:R>'
        if value == 0:
            await interaction.response.send_message(f'Вы уже получали коины! {timerMsg}', ephemeral=True)
        else:
            await interaction.response.send_message(f'Вы получили {formatCoins(value)}. {timerMsg}', ephemeral=True, \
                                                    view=DropShareView(user=interaction.user, value=value))
        
    
async def setup(bot: commands.Bot):
    await bot.add_cog(DropCommand(bot), guild=discord.Object(id = settings.GUILD_ID))