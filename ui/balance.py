import discord
import lib.steam_api as Steam
import lib.vortex_api as Vortex
from tools.text import formatCoins
import datetime
import settings


logger = settings.logging.getLogger('discord')

async def _tryGetUser(interaction: discord.Interaction) -> Vortex.User | None:
    logger.info(f'Attempt to find user {interaction.user.id} ({interaction.user.name})')
    try:
        link = await Vortex.GetDiscordUser(interaction.user.id)
    except:
        await interaction.response.send_message(content='Вы не привязали ваш аккаунт к Steam, используйте команду `/link`, чтобы сделать это.', ephemeral=True)
        logger.info(f'User not found')
        return None
    logger.info(f'User found: {link['user']["steamId"]}')
    return link['user']


async def _GetWalletEmbed(interaction: discord.Interaction) -> discord.Embed | None:
    user = await _tryGetUser(interaction)
    if user is None:
        logger.info(f'User not found -> embed not created')
        return None
    summary = await Steam.GetPlayerSummaries(user['steamId'])
    balance = await Vortex.GetBalance(user['steamId'])
    privileges = await Vortex.GetPrivilegeSet(user['steamId'])
    privlegesNames = Vortex.PrivilegeSetToString(privileges)
    embed = discord.Embed(color=discord.Color.blurple(), title='Информация об аккаунте', description=f'Баланс: {formatCoins(balance["value"])}')
    embed.set_author(name=summary['personaname'], url=summary['profileurl'], icon_url=summary['avatar'])
    embed.add_field(name='Привелегии:', value=privlegesNames)
    embed.set_footer(text=f'{datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}')
    return embed


async def SendWallet(interaction: discord.Interaction):
    embed = await _GetWalletEmbed(interaction)
    if embed is None:
        logger.info('Embed is not created: return')
        return
    await interaction.response.send_message(embed=embed, view=WalletView(), ephemeral=True)

class WalletView(discord.ui.View):
    @discord.ui.button(label='Обновить', style=discord.ButtonStyle.blurple)
    async def update(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f'Wallet update button pressed {interaction.user.id} ({interaction.user.name})')
        await interaction.response.edit_message(embed=(await _GetWalletEmbed(interaction)))
    
    @discord.ui.button(label='Поделиться', style=discord.ButtonStyle.blurple)
    async def share(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f'Wallet share button pressed {interaction.user.id} ({interaction.user.name})')
        embed = await _GetWalletEmbed(interaction)
        if embed is None:
            await interaction.response.send_message('Пользователь не найден')
            return
        await interaction.response.edit_message(embed=embed)
        if not isinstance(interaction.channel, discord.TextChannel): return
        else: await interaction.channel.send(f'Информация об аккаунте {interaction.user.mention}', embed=embed, silent=True)



class PayWarnView(discord.ui.View):
    def __init__(self, source: discord.Member | discord.User, target: discord.Member | discord.User, value: int, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.source = source
        self.target = target
        self.value = value
    
    @discord.ui.button(label='Поделиться', style=discord.ButtonStyle.blurple)
    async def warn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        if not isinstance(interaction.channel, discord.TextChannel): return
        await interaction.channel.send(f'{self.source.mention} передал {self.target.mention} {formatCoins(self.value)}', silent=True)

class BalanceShareView(discord.ui.View):
    def __init__(self, user: discord.Member | discord.User, value: int, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.user = user
        self.value = value
    
    @discord.ui.button(label='Поделиться', style=discord.ButtonStyle.blurple)
    async def share(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        if not isinstance(interaction.channel, discord.TextChannel): return
        await interaction.channel.send(f'Баланс игрока {self.user.mention}: {formatCoins(self.value)}', silent=True)