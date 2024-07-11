import discord
import lib.steam_api as Steam
import lib.vortex_api as Vortex


async def _tryGetUser(interaction: discord.Interaction) -> Vortex.User | None:
    try:
        link = await Vortex.GetDiscordUser(interaction.user.id)
    except:
        await interaction.response.send_message(content='Вы не привязали ваш аккаунт к Steam, используйте команду `/link`, чтобы сделать это.', ephemeral=True)
        return None
    return link['user']


async def _GetWalletEmbed(interaction: discord.Interaction) -> discord.Embed:
    user = await _tryGetUser(interaction)
    if user is None: return
    summary = await Steam.GetPlayerSummaries(user['steamId'])
    balance = await Vortex.GetBalance(user['steamId'])
    privileges = await Vortex.GetUserPrivileges(user['steamId'])
    privlegesNames = '\n'.join([i['privilege']['name'].capitalize() for i in privileges])
    embed = discord.Embed(color=discord.Color.blurple(), title='Ваш кошелек', description=f'Ваш баланс (коины): {balance["value"]:,}')
    embed.set_author(name=summary['personaname'], url=summary['profileurl'], icon_url=summary['avatar'])
    embed.add_field(name='Ваши привелегии:', value=privlegesNames)
    return embed


async def SendWallet(interaction: discord.Interaction):
    await interaction.response.send_message(embed=(await _GetWalletEmbed(interaction)), view=WalletView(), ephemeral=True)

class WalletView(discord.ui.View):
    @discord.ui.button(label='Обновить', style=discord.ButtonStyle.blurple)
    async def update(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=(await _GetWalletEmbed(interaction)))



class PayWarnView(discord.ui.View):
    def __init__(self, source: discord.Member | discord.User, target: discord.Member | discord.User, value: int, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.source = source
        self.target = target
        self.value = value
    
    @discord.ui.button(label='Поделится', style=discord.ButtonStyle.blurple)
    async def warn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(content=f'{self.source.mention} передвал {self.target.mention} коины в количестве {self.value:,} ед.')

class BalanceShareView(discord.ui.View):
    def __init__(self, user: discord.Member | discord.User, value: int, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.user = user
        self.value = value
    
    @discord.ui.button(label='Поделится', style=discord.ButtonStyle.blurple)
    async def share(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f'Баланс игрока {self.user.mention}: {self.value:,}')