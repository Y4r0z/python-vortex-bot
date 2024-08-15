import discord
from settings import Preferences, SavePreferences, IsSetUp, IsRoleExists
"""
View can have only 5 rows (selects)
"""

def roleFromId(role_id: int):
    return [discord.SelectDefaultValue(id=role_id, type=discord.SelectDefaultValueType.role)]

class SetupView(discord.ui.View):
    def __init__(self, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.select_linked.default_values = roleFromId(Preferences['linked_role_id']) \
            if IsRoleExists('linked_role_id') else []
        self.select_vip.default_values = roleFromId(Preferences['vip_role_id']) \
            if IsRoleExists('vip_role_id') else []
        self.select_premium.default_values = roleFromId(Preferences['premium_role_id']) \
            if IsRoleExists('premium_role_id') else []
        self.select_legend.default_values = roleFromId(Preferences['legend_role_id']) \
            if IsRoleExists('legend_role_id') else []
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Роль для привязанных аккаунтов")
    async def select_linked(self, interaction: discord.Interaction, select_item: discord.ui.RoleSelect):
        role = select_item.values[0]
        Preferences['linked_role_id'] = role.id
        await interaction.response.defer()

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Роль VIP")
    async def select_vip(self, interaction: discord.Interaction, select_item: discord.ui.RoleSelect):
        role = select_item.values[0]
        Preferences['vip_role_id'] = role.id
        await interaction.response.defer()
    

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Роль Premium")
    async def select_premium(self, interaction: discord.Interaction, select_item: discord.ui.RoleSelect):
        role = select_item.values[0]
        Preferences['premium_role_id'] = role.id
        await interaction.response.defer()
    

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Роль Legend")
    async def select_legend(self, interaction: discord.Interaction, select_item: discord.ui.RoleSelect):
        role = select_item.values[0]
        Preferences['legend_role_id'] = role.id
        await interaction.response.defer()


    @discord.ui.button(label='Подтвердить', style=discord.ButtonStyle.success)
    async def ok(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not IsSetUp():
            await interaction.response.send_message('Не все роли выбраны!', ephemeral=True)
            return
        SavePreferences()
        await interaction.response.edit_message(content='Настройки сохранены!', view=None)
    

    @discord.ui.button(label='Отмена', style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content='Сохранение настроек отменено!', view=None)


    


