import discord.ext
import discord.ext.commands
import settings
import discord
import lib.vortex_api as Vortex

logger = settings.logging.getLogger('discord')

async def tryGetUser(interaction: discord.Interaction) -> Vortex.User | None:
    """
    Функция пытается найти связанного пользователя Discord через API.
    """
    logger.info(f'Attempt to find user {interaction.user.id} ({interaction.user.name})')
    try:
        link = await Vortex.GetDiscordUser(interaction.user.id)
    except:
        await interaction.response.send_message(content='Вы не привязали ваш аккаунт к Steam, используйте команду `/link`, чтобы сделать это.', ephemeral=True)
        logger.info(f'User not found')
        return None
    logger.info(f'User found: {link['user']["steamId"]}')
    return link['user']


async def checkAdmin(interaction: discord.Interaction):
    """
    Проверка пользователя на права администратора
    """
    logger.info(f'Checking administrator flag for: {interaction.user.id} ({interaction.user.name})')
    if interaction.user.guild_permissions.administrator == False:
        await interaction.response.send_message('Данная команда может быть использована только администратором.', ephemeral=True)
        return False
    return True
