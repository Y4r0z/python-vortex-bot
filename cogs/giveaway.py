import discord
import lib.vortex_api as Vortex
import settings
from discord import app_commands
from discord.ext import commands
from tools.ds import tryGetUser
from tools.text import formatCoins
import datetime
from typing import Optional

logger = settings.logging.getLogger('discord')


def createEmbedText(giveaway: Vortex.Giveaway) -> str:
    time = int(datetime.datetime.fromisoformat(giveaway['activeUntil'])
               .replace(tzinfo=datetime.timezone.utc).timestamp())
    return f"Награда: **{formatCoins(giveaway['reward'])}**\nОкончание: <t:{time}:R>\nУчастники: **{giveaway['curUseCount']}/{giveaway['maxUseCount']}**"


def createGiveawayEmbed(giveaway: Vortex.Giveaway, user: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        color=discord.Color.green(),
        title='Раздача коинов!',
        description=createEmbedText(giveaway)
    )
    embed.set_author(name=user.display_name,
                    icon_url=user.avatar.url if user.avatar is not None else None)
    return embed


async def publishGiveaway(interaction: discord.Interaction, giveaway: Vortex.Giveaway) -> None:
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.followup.send("Команда должна использоваться в текстовом канале", ephemeral=True)
        return
    if not isinstance(interaction.user, discord.Member):
        await interaction.followup.send("Ошибка получения данных пользователя", ephemeral=True)
        return
    try:
        await interaction.channel.send(
            embed=createGiveawayEmbed(giveaway, interaction.user),
            view=GiveawayCheckoutView(giveaway)
        )
    except Exception as e:
        logger.error(f"Error publishing giveaway: {str(e)}")
        await interaction.followup.send("Произошла ошибка при публикации раздачи", ephemeral=True)


class GiveawayExistsView(discord.ui.View):
    def __init__(self, giveaway: Vortex.Giveaway):
        self.giveaway = giveaway
        super().__init__(timeout=180)

    @discord.ui.button(label='Опубликовать', style=discord.ButtonStyle.blurple)
    async def publish(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            if (user := await tryGetUser(interaction)) is None:
                return

            if self.giveaway['user']['id'] != user['id']:
                await interaction.followup.send('Только владелец раздачи может её опубликовать', ephemeral=True)
                return

            await publishGiveaway(interaction, self.giveaway)
            button.disabled = True
            await interaction.message.edit(view=None)
            logger.info(f'Giveaway ({self.giveaway["id"]}) published')
        except Exception as e:
            logger.error(f"Error in publish button: {str(e)}")
            await interaction.followup.send("Произошла ошибка при публикации раздачи", ephemeral=True)

    @discord.ui.button(label='Удалить', style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            if (user := await tryGetUser(interaction)) is None:
                return

            if self.giveaway['user']['id'] != user['id']:
                await interaction.followup.send('Только владелец раздачи может её удалить', ephemeral=True)
                return

            await Vortex.DeleteGiveaway(giveaway_id=self.giveaway['id'])
            await interaction.message.edit(content='Раздача удалена', view=None)
            logger.info(f'Giveaway ({self.giveaway["id"]}) deleted')
        except Exception as e:
            logger.error(f"Error deleting giveaway: {str(e)}")
            await interaction.followup.send('Не удалось удалить раздачу', ephemeral=True)


class GiveawayCheckoutView(discord.ui.View):
    def __init__(self, giveaway: Vortex.Giveaway):
        self.giveaway = giveaway
        super().__init__(timeout=None)

    @discord.ui.button(label='Забрать', style=discord.ButtonStyle.green)
    async def checkout(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Giveaway checkout called by {interaction.user.id} ({interaction.user.name})')

        try:
            if (user := await tryGetUser(interaction)) is None:
                return
            if not isinstance(interaction.user, discord.Member):
                return

            giveaway = await Vortex.CheckoutGiveaway(user['steamId'], self.giveaway['id'])

            if len(giveaway.keys()) == 1:
                status_messages = {
                    5: 'Мы не можете участвовать в своей раздаче',
                    4: 'Вы уже участвовали в этой раздаче',
                    3: 'Награды закончились',
                    2: 'Раздача закончилась',
                    1: 'Раздача больше не существует'
                }
                message = status_messages.get(giveaway['status'], 'Неизвестная ошибка')
                button.disabled = giveaway['status'] in [1, 2, 3]
                if interaction.message:
                    await interaction.message.edit(view=self)
            else:
                message = f'Вы успешно забрали **{formatCoins(giveaway["reward"])}**'
                button.disabled = giveaway['curUseCount'] == giveaway['maxUseCount']
                if interaction.message and interaction.message.embeds:
                    embed = interaction.message.embeds[0]
                    embed.description = createEmbedText(giveaway)
                    await interaction.message.edit(embed=embed, view=self)
                logger.info(f'Successful checkout')

            await interaction.followup.send(message, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in checkout: {str(e)}")
            await interaction.followup.send('Произошла ошибка при получении награды', ephemeral=True)


class GiveawayCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='giveaway', description='Создать раздачу коинов за ваш счёт')
    @discord.app_commands.rename(reward='награда', useCount='количество', minutes='длительность')
    @discord.app_commands.describe(
        reward='Сколько коинов получит игрок за участие',
        useCount='Максимальное количество участников',
        minutes='Сколько минут будет идти раздача'
    )
    async def giveawaycommand(
        self,
        interaction: discord.Interaction,
        reward: int,
        useCount: int,
        minutes: int = 1440
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Giveaway command called by {interaction.user.id} ({interaction.user.name})')

        try:
            if (user := await tryGetUser(interaction)) is None:
                return

            # Проверка существующих раздач
            history = await Vortex.GetGiveaways(user['steamId'])
            if len(history) > 0:
                first = history[0]
                ftime = int(datetime.datetime.fromisoformat(
                    first['activeUntil']).replace(tzinfo=datetime.timezone.utc).timestamp())
                logger.info(f'Giveaway exists')
                await interaction.followup.send(
                    f'У вас уже имеется активная раздача до <t:{ftime}:f>; '
                    f'{first["curUseCount"]}/{first["maxUseCount"]} участников; '
                    f'награда: {formatCoins(first["reward"])}.',
                    view=GiveawayExistsView(first),
                    ephemeral=True
                )
                return

            # Валидация параметров
            if reward <= 0:
                await interaction.followup.send('Слишком маленькая награда', ephemeral=True)
                return
            if useCount < 1:
                await interaction.followup.send('Количество участников должно быть больше 1', ephemeral=True)
                return
            if minutes < 1:
                await interaction.followup.send('Слишком маленькая длительность раздачи', ephemeral=True)
                return

            # Создание раздачи
            giveaway = await Vortex.CreateGiveaway(user['steamId'], useCount, reward, minutes)

            if len(giveaway.keys()) == 1:
                status_messages = {
                    4: 'Неверное количество участников раздачи',
                    3: 'Неверная длительность раздачи',
                    2: 'Недостаточно средств для создания раздачи',
                    1: 'Неверно указана награда'
                }
                message = status_messages.get(giveaway['status'], 'Неизвестная ошибка')
            else:
                message = 'Вы успешно создали раздачу'
                await publishGiveaway(interaction, giveaway)
                logger.info(f'Giveaway created')

            await interaction.followup.send(message, ephemeral=True)

        except Exception as e:
            logger.error(f"Error creating giveaway: {str(e)}")
            await interaction.followup.send(
                'Произошла ошибка при создании раздачи. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(GiveawayCommand(bot), guild=discord.Object(id=settings.GUILD_ID))