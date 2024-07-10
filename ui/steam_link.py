import discord
from lib.steam_api import GetPlayerSummaries, PlayerSummary
from lib.vortex_api import GetDiscordUser, LinkUser


def embedFromSteam(summary : PlayerSummary, title: str) -> discord.Embed:
    embed = discord.Embed(
            color=discord.Color.blurple(),
            title=title
        )
    embed.set_author(name=summary['personaname'], url=summary['profileurl'], icon_url=summary['avatar'])
    return embed


class AcceptLinkView(discord.ui.View):
    def __init__(self, steam: PlayerSummary, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.steam = steam
    
    @discord.ui.button(label='Подтвердить', style=discord.ButtonStyle.success)
    async def success(self, interaction: discord.Interaction, button: discord.ui.Button):
        link = await LinkUser(steam_id=self.steam['steamid'], discord_id=interaction.user.id)
        await interaction.response.edit_message(view=None, embed=embedFromSteam(self.steam, f'Вы связали ваш аккаунт Discord с аккаунтом Steam: {link["user"]["steamId"]}.'))
        

    @discord.ui.button(label='Отмена', style=discord.ButtonStyle.danger)
    async def failure(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None, embed=embedFromSteam(self.steam, 'Операция отменена.'))
    

class LinkModal(discord.ui.Modal, title='Интеграция со Steam'):
    steamid = discord.ui.TextInput(
        style=discord.TextStyle.short,
        label="Steam ID",
        required=True, 
        placeholder='76561198086700922')
    
    async def on_submit(self, interaction: discord.Interaction):
        summary = await GetPlayerSummaries(steam_id=self.steamid.value)
        view = AcceptLinkView(steam=summary)
        await interaction.response.send_message(view=view, embed=embedFromSteam(summary, 'Подтвердите, что это ваш аккаунт'), ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error):
        await interaction.response.send_message('Игрок с данным Steam ID не найден!', ephemeral=True)

class LinkView(discord.ui.View):
    @discord.ui.button(label="Привязать Steam", style=discord.ButtonStyle.blurple)
    async def link(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user = await GetDiscordUser(interaction.user.id)
            if user is not None: 
                await interaction.response.send_message('Вы уже привязали свой аккаунт', ephemeral=True)
                return
        except:
            pass
        link_modal = LinkModal()
        await interaction.response.send_modal(link_modal)