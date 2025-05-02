import discord
from lib.steam_api import GetPlayerSummaries, PlayerSummary, ResolveVanityURL
from lib.vortex_api import GetDiscordUser, LinkUser, GetDiscordUserSteam
import settings
from tools.ds import syncAllRoles
import lib.vortex_api as Vortex
import urllib.parse

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
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message('Вы выполнили команду не на сервере!', ephemeral=True)
            return
            
        try:
            existing_link = await GetDiscordUserSteam(self.steam['steamid'])
            if existing_link:
                await interaction.response.edit_message(
                    view=None, 
                    embed=embedFromSteam(
                        self.steam, 
                        f'Этот Steam-аккаунт уже привязан к другому Discord-аккаунту.'
                    )
                )
                return
        except Exception:
            pass
            
        link = await LinkUser(steam_id=self.steam['steamid'], discord_id=interaction.user.id)
        await interaction.user.add_roles(discord.Object(id=settings.Preferences['linked_role_id']))
        await syncAllRoles(interaction.user)
        await interaction.response.edit_message(view=None, embed=embedFromSteam(self.steam, f'Вы связали ваш аккаунт Discord с аккаунтом Steam: {link["user"]["steamId"]}.'))
        

    @discord.ui.button(label='Отмена', style=discord.ButtonStyle.danger)
    async def failure(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None, embed=embedFromSteam(self.steam, 'Операция отменена.'))
    

class LinkModal(discord.ui.Modal, title='Интеграция со Steam'):
    steamid: discord.ui.TextInput = discord.ui.TextInput(
        style=discord.TextStyle.short,
        label="Steam ID / Ссылка на профиль",
        required=True, 
        placeholder='https://steamcommunity.com/profiles/76561198163385515/')
    
    async def on_submit(self, interaction: discord.Interaction):
        steam_id = ""
        summary = None
        
        try:
            try:
                summary = await GetPlayerSummaries(self.steamid.value)
                steam_id = summary['steamid']
            except:
                path = urllib.parse.urlparse(self.steamid.value).path
                vanity = list(filter(lambda x: x!='', path.split('/')))[-1]
                steam_id = await ResolveVanityURL(vanity)
                summary = await GetPlayerSummaries(steam_id)
                
            try:
                existing_link = await GetDiscordUserSteam(steam_id)
                if existing_link:
                    await interaction.response.send_message(
                        f'Этот Steam-аккаунт уже привязан к другому Discord-аккаунту.',
                        ephemeral=True
                    )
                    return
            except Exception:
                pass
                
            view = AcceptLinkView(steam=summary)
            await interaction.response.send_message(
                view=view, 
                embed=embedFromSteam(summary, 'Подтвердите, что это ваш аккаунт'), 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message('Игрок с данным Steam ID не найден!', ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error): 
        await interaction.response.send_message('Игрок с данным Steam ID не найден!', ephemeral=True)

class LinkView(discord.ui.View):
    @discord.ui.button(label="Привязать Steam", style=discord.ButtonStyle.blurple)
    async def link(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await GetDiscordUser(interaction.user.id)
            await interaction.response.send_message('Вы уже привязали свой аккаунт', ephemeral=True)
            return          
        except:
            pass
        link_modal = LinkModal()
        await interaction.response.send_modal(link_modal)