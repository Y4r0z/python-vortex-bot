import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.ds import tryGetUser, tryGetOtherUser, ShareView
import lib.vortex_api as Vortex
from typing import Optional

logger = settings.logging.getLogger('discord')

def GetRankEmbed(member: discord.Member, rank: Vortex.Rank) -> discord.Embed:
    """Создает Discord Embed с информацией о ранге игрока."""
    try:
        embed = discord.Embed(
            color=discord.Color.dark_orange(),
            title='Ранг игрока',
            description=f'Ранг: {rank["rank"]}\nОчки: {rank["score"]}'
        )
        embed.set_author(
            name=member.display_name,
            icon_url=member.avatar.url if member.avatar else member.default_avatar.url
        )
        return embed
    except Exception as e:
        logger.error(f"Error creating rank embed: {str(e)}")
        raise

class ScoreCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='top', description='Показывает топ-10 игроков по очкам')
    async def top(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Top command called by {interaction.user.id} ({interaction.user.name})')
        
        try:
            if not (user := await tryGetUser(interaction)):
                return

            top = await Vortex.GetScoreTop(0, 10)  # Фиксированное значение 10
            topStr = '\n'.join([
                f"{i['rank']}. {i['steamInfo']['personaname']}  -  {i['score']}"
                for i in top
            ])
            
            view = ShareView(f'{interaction.user.mention} запросил топ игроков:\n```{topStr}```')
            await interaction.followup.send(
                content=f"Топ-10 игроков по очкам:\n```{topStr}```",
                ephemeral=True,
                view=view
            )
            
        except Exception as e:
            logger.error(f'Error in top command: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при получении топа игроков. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

    @app_commands.command(name='rank', description='Показывает место в топе')
    @discord.app_commands.describe(member='Пользователь, ранг которого вы хотите узнать')
    async def rank(self, interaction: discord.Interaction, member: Optional[discord.Member] = None) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Rank command called by {interaction.user.id} ({interaction.user.name})')
        
        try:
            if not isinstance(interaction.user, discord.Member):
                await interaction.followup.send('Вы выполнили команду не на сервере!', ephemeral=True)
                return

            # Определяем пользователя для проверки
            target_member = member or interaction.user
            target_user = await (tryGetOtherUser(member, interaction) if member else tryGetUser(interaction))
            
            if not target_user:
                return

            try:
                rank = await Vortex.GetPlayerRank(target_user['steamId'])
                if not rank:
                    raise ValueError("Rank data is empty")
            except Exception as e:
                logger.error(f'Error getting rank data: {str(e)}')
                await interaction.followup.send('Ранг еще не получен или произошла ошибка', ephemeral=True)
                return

            embed = GetRankEmbed(target_member, rank)
            
            # Добавляем кнопку "Поделиться" только если пользователь смотрит свой ранг
            if not member:
                view = ShareView(f'{interaction.user.mention} поделился своим рангом', embed=embed)
                await interaction.followup.send(embed=embed, ephemeral=True, view=view)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f'Error in rank command: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при получении ранга. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ScoreCommands(bot), guild=discord.Object(id=settings.GUILD_ID))