import discord
import settings
from discord import app_commands
from discord.ext import commands
from ui.balance import BalanceShareView
from tools.text import formatCoins
from tools.ds import tryGetUser, tryGetOtherUser, ShareView
import lib.vortex_api as Vortex


logger = settings.logging.getLogger('discord')

def GetRankEmbed(member: discord.Member, rank: Vortex.Rank):
    embed = discord.Embed(
        color=discord.Color.dark_orange(),
        title='Ранг игрока',
        description=f'Ранг: {rank["rank"]}\nОчки: {rank["score"]}'
    )
    embed.set_author(name=member.display_name, icon_url=member.avatar.url if member.avatar else member.default_avatar.url)
    return embed


class ScoreCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='top', description='Показывает, сколько коинов у вас на счету')
    async def top(self, interaction: discord.Interaction, count: int = 10):
        logger.info(f'Top command called by {interaction.user.id} ({interaction.user.name})')
        if not (user:=await tryGetUser(interaction)): return
        top = await Vortex.GetScoreTop(0, count)
        topStr= '\n'.join([f"{i['rank']}. {i['steamInfo']['personaname']}  -  {i['score']}" for i in top])
        await interaction.response.send_message(
            content=f"Топ игроков по очкам:\n```{topStr}```",
            ephemeral=True
        )
    
    @app_commands.command(name='rank', description='Показывает ваше место в топе')
    @discord.app_commands.describe(member='Пользователь, ранг которого вы хотите узнать')
    async def rank(self, interaction: discord.Interaction, member: discord.Member | None):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message('Вы выполнили команду не на сервере!', ephemeral=True)
            return
        if member:
            if not (user:=await tryGetOtherUser(member, interaction)): return
        else:
            if not (user:=await tryGetUser(interaction)): return
        try:
            rank = await Vortex.GetPlayerRank(user['steamId'])
        except:
            await interaction.response.send_message('Ранг еще не получен', ephemeral=True)
            return
        embed = GetRankEmbed(member or interaction.user, rank)
        if not member:
            view = ShareView(f'{interaction.user.mention} поделился своим рангом', embed=embed)
            await interaction.response.send_message(embed=embed, ephemeral=True, view=view)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True,)
        
            
        
        
    
async def setup(bot: commands.Bot):
    await bot.add_cog(ScoreCommands(bot), guild=discord.Object(id = settings.GUILD_ID))