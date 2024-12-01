import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.text import formatCoins
from tools.ds import tryGetUser, ShareView
import lib.vortex_api as Vortex
from typing import Optional

logger = settings.logging.getLogger('discord')

class PayCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='tip', description='Передать коины другому пользователю')
    @discord.app_commands.describe(target="Пользователь, которому вы передаете коины", value="Сколько коинов передать")
    @discord.app_commands.rename(target='кому', value='сколько')
    async def pay(self, interaction: discord.Interaction, target: discord.Member, value: int) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Pay (tip) command called by {interaction.user.id} ({interaction.user.name})')
        
        try:
            # Валидация входных данных
            if value <= 0:
                await interaction.followup.send('Сумма для передачи должна быть больше 0', ephemeral=True)
                return

            # Проверка на самого себя
            if target.id == interaction.user.id:
                await interaction.followup.send('Вы не можете передавать коины самому себе!', ephemeral=True)
                logger.info('User tried to pay themselves')
                return

            # Проверка на бота
            if target.bot:
                await interaction.followup.send('У бота нет кошелька! 😒', ephemeral=True)
                logger.info('User tried to pay bot')
                return

            # Проверка отправителя
            user = await tryGetUser(interaction)
            if user is None:
                logger.info('Sender not linked to Steam account')
                return

            # Проверка получателя
            try:
                user2 = await Vortex.GetDiscordUser(target.id)
                if not user2:
                    raise ValueError("Recipient not found")
            except Exception as e:
                logger.info(f'Recipient verification failed: {str(e)}')
                await interaction.followup.send(
                    f'Пользователь {target.mention} еще не связал свой аккаунт.',
                    ephemeral=True
                )
                return

            # Проверка баланса
            try:
                balance = await Vortex.GetBalance(user['steamId'])
                if value > balance['value']:
                    logger.info(f'Insufficient funds: has {balance["value"]}, tried to send {value}')
                    await interaction.followup.send(
                        'У вас недостаточно коинов для передачи.',
                        ephemeral=True
                    )
                    return
            except Exception as e:
                logger.error(f'Error checking balance: {str(e)}')
                await interaction.followup.send(
                    'Не удалось проверить баланс. Пожалуйста, попробуйте позже.',
                    ephemeral=True
                )
                return

            # Выполнение транзакции
            try:
                transaction = await Vortex.PayBalance(user['steamId'], user2['user']['steamId'], value)
            except Exception as e:
                logger.error(f'Transaction error: {str(e)}')
                await interaction.followup.send(
                    'Не удалось выполнить передачу коинов. Пожалуйста, попробуйте позже.',
                    ephemeral=True
                )
                return

            # Создаем view для шаринга
            current_channel: Optional[discord.TextChannel] = None
            if isinstance(interaction.channel, discord.TextChannel):
                current_channel = interaction.channel

            view = ShareView(
                f'{interaction.user.mention} передал {target.mention} {formatCoins(value)}',
                channel=current_channel
            )

            logger.info(f'Payment successful: {value} coins from {user["steamId"]} to {user2["user"]["steamId"]}')
            await interaction.followup.send(
                content=f'Вы передали {formatCoins(value)} игроку {target.mention}.\n'
                       f'Остаток на балансе: {formatCoins(transaction["source"]["value"])}',
                ephemeral=True,
                view=view
            )

        except Exception as e:
            logger.error(f'Unexpected error in pay command: {str(e)}')
            await interaction.followup.send(
                'Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(PayCommand(bot), guild=discord.Object(id=settings.GUILD_ID))