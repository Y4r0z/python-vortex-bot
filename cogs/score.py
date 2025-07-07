import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.ds import tryGetUser, tryGetOtherUser, ShareView
import lib.vortex_api as Vortex
from typing import Optional

logger = settings.logging.getLogger('discord')

def GetPlayerStatsEmbed(member: discord.Member, rank: Vortex.Rank, rating: Vortex.PlayerRating, steam_info: dict) -> discord.Embed:
    try:
        shooting = rating['shooting_skills']
        efficiency = rating['game_efficiency']
        combat = rating['combat_effectiveness']
        experience = rating['experience_activity']
        total = rating['total']
        
        description = f"""📊 **Статистика сезона**

**Ранг:** {rank["rank"]} | **Очки:** {rank["score"]:,}

━━━━━━━━━━━━━━━━━━━━━━

⭐ **Общий рейтинг игрока**

🎯 **Стрельба:** {shooting['points']:,} очков ({shooting['normalized_score']:.1f})

⚡ **Навыки игры:** {efficiency['points']:,} очков ({efficiency['normalized_score']:.1f})

⚔️ **Боевые навыки:** {combat['points']:,} очков ({combat['normalized_score']:.1f})

🏆 **Опыт и активность:** {experience['points']:,} очков ({experience['normalized_score']:.1f})

━━━━━━━━━━━━━━━━━━━━━━

👑 **Класс:** {total['class']}
⭐ **Общий рейтинг:** {total['rating']:.1f}
📈 **Всего очков:** {total['points']:,}"""
        
        embed = discord.Embed(
            color=discord.Color.from_rgb(255, 215, 0),
            description=description
        )
        embed.set_author(
            name=steam_info['personaname'],
            url=steam_info['profileurl'],
            icon_url=steam_info['avatarmedium']
        )
        
        return embed
    except Exception as e:
        logger.error(f"Error creating player stats embed: {str(e)}")
        raise

def GetBasicRankEmbed(member: discord.Member, rank: Vortex.Rank) -> discord.Embed:
    try:
        description = f"""📊 **Статистика сезона**
Ранг: **{rank["rank"]}**
Очки: **{rank["score"]:,}**

❌ **Детальная статистика недоступна**
Рейтинговая система временно недоступна"""
        
        embed = discord.Embed(
            color=discord.Color.orange(),
            description=description
        )
        embed.set_author(
            name=member.display_name,
            icon_url=member.avatar.url if member.avatar else member.default_avatar.url
        )
        embed.set_footer(text="Статистика игрока")
        
        return embed
    except Exception as e:
        logger.error(f"Error creating basic rank embed: {str(e)}")
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

            top = await Vortex.GetScoreTop(0, 10)
            topStr = '\n'.join([
                f"{i['rank']}. {i['steamInfo']['personaname']}  -  {i['score']:,}"
                for i in top
            ])
            
            view = ShareView(f'{interaction.user.mention} запросил топ игроков:\n```{topStr}```')
            await interaction.followup.send(
                content=f"🏆 **Топ-10 игроков по очкам:**\n```{topStr}```",
                ephemeral=True,
                view=view
            )
            
        except Exception as e:
            logger.error(f'Error in top command: {str(e)}')
            await interaction.followup.send(
                '❌ Произошла ошибка при получении топа игроков. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

    @app_commands.command(name='rank', description='Показывает статистику и рейтинг игрока')
    @discord.app_commands.describe(member='Пользователь, статистику которого вы хотите узнать')
    async def rank(self, interaction: discord.Interaction, member: Optional[discord.Member] = None) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Rank command called by {interaction.user.id} ({interaction.user.name})')
        
        try:
            if not isinstance(interaction.user, discord.Member):
                await interaction.followup.send('❌ Вы выполнили команду не на сервере!', ephemeral=True)
                return

            target_member = member or interaction.user
            target_user = await (tryGetOtherUser(member, interaction) if member else tryGetUser(interaction))
            
            if not target_user:
                return

            steam_id = target_user['steamId']

            try:
                rank = await Vortex.GetPlayerRank(steam_id)
                if not rank:
                    raise ValueError("Rank data is empty")
            except Exception as e:
                logger.error(f'Error getting rank data: {str(e)}')
                await interaction.followup.send('❌ Ранг еще не получен или произошла ошибка', ephemeral=True)
                return

            try:
                rating = await Vortex.GetPlayerRating(steam_id)
                steam_info = await Vortex.GetBulkProfile(steam_id)
                
                embed = GetPlayerStatsEmbed(target_member, rank, rating, steam_info['steamInfo'])
                
                share_text = f'{interaction.user.mention} поделился статистикой игрока:'
                view = ShareView(share_text, embed=embed)
                await interaction.followup.send(embed=embed, ephemeral=True, view=view)
                    
            except Exception as e:
                logger.error(f'Error getting detailed stats: {str(e)}')
                
                embed = GetBasicRankEmbed(target_member, rank)
                
                share_text = f'{interaction.user.mention} поделился рангом игрока:' if member else f'{interaction.user.mention} поделился своим рангом'
                view = ShareView(share_text, embed=embed)
                await interaction.followup.send(embed=embed, ephemeral=True, view=view)

        except Exception as e:
            logger.error(f'Error in rank command: {str(e)}')
            await interaction.followup.send(
                '❌ Произошла ошибка при получении статистики. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ScoreCommands(bot), guild=discord.Object(id=settings.GUILD_ID))