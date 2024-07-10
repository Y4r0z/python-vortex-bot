import settings
import discord
from discord.ext import commands
from ui.steam_link import LinkView
import lib.vortex_api

def main():
    intents = discord.Intents.default()
    intents.message_content = True

    guild = discord.Object(id=1259824273552441425)

    bot = commands.Bot(intents=intents, command_prefix='!')
    

    @bot.event
    async def on_ready():
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        #view = LinkView()
        #channel = bot.get_channel(1259824274059825165)
        #await channel.send(view=view, silent=True)

    @bot.tree.command(name='setup', description='Настраивает бота в данном канале')
    async def setupcommand(interaction: discord.Interaction):
        await interaction.response.send_message('ok', ephemeral=True)

    bot.run(settings.DISCORD_TOKEN)


if __name__ == '__main__':
    main()