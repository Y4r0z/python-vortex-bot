import discord
from settings import Preferences, SavePreferences, IsSetUp

class SetupView(discord.ui.View):
    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Роль VIP"
    )
    async def select_vip(self, interaction: discord.Interaction, select_item: discord.ui.RoleSelect):
        role = select_item.values[0]
        Preferences['vip_role_id'] = role.id
        await interaction.response.defer()
    

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Роль Premium",
    )
    async def select_premium(self, interaction: discord.Interaction, select_item: discord.ui.RoleSelect):
        role = select_item.values[0]
        Preferences['premium_role_id'] = role.id
        await interaction.response.defer()
    

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Роль Legend",
    )
    async def select_legend(self, interaction: discord.Interaction, select_item: discord.ui.RoleSelect):
        role = select_item.values[0]
        Preferences['legend_role_id'] = role.id
        await interaction.response.defer()


    @discord.ui.button(
        label='Подтвердить',
        style=discord.ButtonStyle.success
    )
    async def ok(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not IsSetUp():
            await interaction.response.send_message('Не все роли выбраны!', ephemeral=True)
        SavePreferences()
        await interaction.response.edit_message(content='Настройки сохранены!', view=None)
    

    @discord.ui.button(
        label='Отмена',
        style=discord.ButtonStyle.danger
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content='Сохранение настроек отменено!', view=None)


    


