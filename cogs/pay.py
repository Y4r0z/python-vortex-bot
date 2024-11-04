import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.text import formatCoins
from tools.ds import tryGetUser, ShareView
import lib.vortex_api as Vortex

logger = settings.logging.getLogger('discord')

class PayCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='tip', description='Передать коины другому пользователю')
    @discord.app_commands.describe(target="Пользователь, которому вы передаете коины", value="Сколько коинов передать")
    @discord.app_commands.rename(target='кому', value='сколько')
    async def pay(self, interaction: discord.Interaction, target: discord.Member, value: int):
        logger.info(f'Pay (tip) command called by {interaction.user.id} ({interaction.user.name})')
        
        # Проверка на самого себя
        if target.id == interaction.user.id:
            await interaction.response.send_message(content='Мы не можете передавать коины самому себе!', ephemeral=True)
            logger.info('User tried to pay himself: return')
            return

        # Проверка на бота
        if target.bot:
            await interaction.response.send_message(content='У бота нет кошелька! 😒', ephemeral=True)
            logger.info('User tried to pay bot: return')
            return

        # Проверка отправителя
        user = await tryGetUser(interaction)
        if user is None:
            logger.info('User not found: return')
            return

        # Проверка получателя
        try:
            user2 = await Vortex.GetDiscordUser(target.id)
        except:
            logger.info('User not linked: return')
            await interaction.response.send_message(
                content=f'Пользователь {target.mention} еще не связал свой аккаунт.',
                ephemeral=True
            )
            return

        # Проверка баланса
        balance = await Vortex.GetBalance(user['steamId'])
        if value > balance['value']:
            logger.info('User tried to pay more than he/she has: return')
            await interaction.response.send_message(
                content='У вас не хватет коинов для передачи.',
                ephemeral=True
            )
            return

        # Выполнение транзакции
        try:
            transaction = await Vortex.PayBalance(user['steamId'], user2['user']['steamId'], value)
        except Exception as e:
            logger.info(f'\nTransaction error:\n{str(e)}\n')
            await interaction.response.send_message(
                content='Не удалось передать коины.',
                ephemeral=True
            )
            return

        # Создаем view для шаринга в текущем канале
        current_channel = None
        if isinstance(interaction.channel, discord.TextChannel):
            current_channel = interaction.channel
        
        view = ShareView(
            f'{interaction.user.mention} передал {target.mention} {formatCoins(value)}',
            channel=current_channel
        )
        
        logger.info('Pay: success')
        await interaction.response.send_message(
            content=f'Вы передали {formatCoins(value)} игроку {target.mention}.\n'
                   f'Остаток на балансе: {formatCoins(transaction["source"]["value"])}',
            ephemeral=True,
            view=view
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(PayCommand(bot), guild=discord.Object(id = settings.GUILD_ID))