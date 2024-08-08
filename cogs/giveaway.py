import discord
import lib.vortex_api as Vortex
import settings
from discord import app_commands
from discord.ext import commands
from tools.ds import tryGetUser
from tools.text import formatCoins
import datetime

logger = settings.logging.getLogger('discord')


def createEmbedText(giveaway: Vortex.Giveaway):
    time = int(datetime.datetime.fromisoformat(giveaway['activeUntil']).replace(tzinfo=datetime.timezone.utc).timestamp())
    return f"Награда: **{formatCoins(giveaway['reward'])}**\nОкончание: <t:{time}:R>\nУчастники: **{giveaway['curUseCount']}/{giveaway['maxUseCount']}**"

def createGiveawayEmbed(giveaway: Vortex.Giveaway, user: discord.Member):   
    embed = discord.Embed(
        color=discord.Color.green(), 
        title=f'Раздача коинов!', 
        description=createEmbedText(giveaway)
    )
    embed.set_author(name=user.display_name, icon_url=user.avatar.url if user.avatar is not None else None)
    return embed

async def publichGiveaway(interaction: discord.Interaction, giveaway: Vortex.Giveaway):
    if not isinstance(interaction.channel, discord.TextChannel): return
    if not isinstance(interaction.user, discord.Member): return
    await interaction.channel.send(embed=createGiveawayEmbed(giveaway, interaction.user), view=GiveawayCheckoutView(giveaway))



class GiveawayExistsView(discord.ui.View):
    def __init__(self, giveaway: Vortex.Giveaway):
        self.giveaway = giveaway
        super().__init__(timeout=180)
    
    @discord.ui.button(label='Опубликовать',style=discord.ButtonStyle.blurple)
    async def publish(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (user:=await tryGetUser(interaction)) is None: return
        if self.giveaway['user']['id'] != user['id']:
            await interaction.response.send_message('Только владелец раздачи может её опубликовать', ephemeral=True)
            return
        await publichGiveaway(interaction, self.giveaway)
        button.disabled = True
        await interaction.response.edit_message(view=None)
        logger.info(f'Giveaway ({self.giveaway['id']}) published')
        
    
    @discord.ui.button(label='Удалить', style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (user:=await tryGetUser(interaction)) is None: return
        if self.giveaway['user']['id'] != user['id']:
            await interaction.response.send_message('Только владелец раздачи может её удалить', ephemeral=True)
            return
        try:
            await Vortex.DeleteGiveaway(giveaway_id=self.giveaway['id'])
        except:
            await interaction.response.send_message('Не удалось удалить раздачу', ephemeral=True)
        else:
            await interaction.response.edit_message(content='Раздача удалена', view=None)
            logger.info(f'Giveaway ({self.giveaway['id']}) deleted')




class GiveawayCheckoutView(discord.ui.View):
    def __init__(self, giveaway: Vortex.Giveaway):
        self.giveaway = giveaway
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Забрать', style=discord.ButtonStyle.green)
    async def checkout(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f'Giveaway checkout called by {interaction.user.id} ({interaction.user.name})')
        if (user:=await tryGetUser(interaction)) is None: return
        if not isinstance(interaction.user, discord.Member): return
        try:
            giveaway = await Vortex.CheckoutGiveaway(user['steamId'], self.giveaway['id'])
        except:
            await interaction.response.send_message('Не удалось забрать награду', ephemeral=True)
            return
        if len(giveaway.keys()) == 1:
            match(giveaway['status']):
                case 5:
                    message = 'Мы не можете участвовать в своей раздаче'
                case 4:
                    message = 'Вы уже участвовали в этой раздаче'
                case 3:
                    message = 'Награды закончились'
                case 2:
                    message = 'Раздача закончилась'
                case 1:
                    message = 'Раздача больше не существует'
                case _:
                    message = f'Неизвестная ошибка'
            button.disabled = giveaway['status'] in [1, 2, 3]
            if interaction.message: await interaction.message.edit(view=self)
        else:
            message = f'Вы успешно забрали **{formatCoins(giveaway["reward"])}**'
            button.disabled = giveaway['curUseCount'] == giveaway['maxUseCount']
            embed = interaction.message.embeds[0]
            embed.description = createEmbedText(giveaway)
            if interaction.message: await interaction.message.edit(embed=embed, view=self)
            logger.info(f'Successful checkout')
        await interaction.response.send_message(message, ephemeral=True)
        





class GiveawayCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='giveaway', description='Создать раздачу коинов за ваш счёт')
    @discord.app_commands.rename(reward='награда', useCount='количество', minutes='длительность')
    @discord.app_commands.describe(reward='Сколько коинов получит игрок за участие', useCount='Максимальное количество участников', minutes='Сколько минут будет идти раздача')
    async def linkcommand(self, interaction: discord.Interaction, reward:int, useCount: int, minutes: int = 1440):
        logger.info(f'Giveaway command called by {interaction.user.id} ({interaction.user.name})')
        if (user:=await tryGetUser(interaction)) is None: return
        history = await Vortex.GetGiveaways(user['steamId'])
        if len(history) > 0:
            first = history[0]
            ftime = int(datetime.datetime.fromisoformat(first['activeUntil']).replace(tzinfo=datetime.timezone.utc).timestamp())
            logger.info(f'Giveaway exists')
            await interaction.response.send_message(
                f'У вас уже имеется активная раздача до <t:{ftime}:f>; {first["curUseCount"]}/{first['maxUseCount']} участников; награда: {formatCoins(first['reward'])}.',
                view=GiveawayExistsView(first),
                ephemeral=True
            )
            return
        if reward <= 0:
            await interaction.response.send_message('Слишком маленькая награда', ephemeral=True)
            return
        if useCount < 1:
            await interaction.response.send_message('Количество участников должно быть больше 1', ephemeral=True)
            return
        if minutes < 1:
            await interaction.response.send_message('Слишком маленькая длительность раздачи', ephemeral=True)
            return
        giveaway = await Vortex.CreateGiveaway(user['steamId'], useCount, reward, minutes)
        if len(giveaway.keys()) == 1:
            match(giveaway['status']):
                case 4:
                    message = 'Неверное количество участников раздачи'
                case 3:
                    message = 'Неверная длительность раздачи'
                case 2:
                    message = 'Недостаточно средств для создания раздачи'
                case 1:
                    message = 'Неверно указана награда'
                case _:
                    message = 'Неизвестная ошибка'
        else:
            message = 'Вы успешно создали раздачу'
            await publichGiveaway(interaction, giveaway)
            logger.info(f'Giveaway created')
        await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GiveawayCommand(bot), guild=discord.Object(id = settings.GUILD_ID))

