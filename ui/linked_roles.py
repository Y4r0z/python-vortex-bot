import discord
from settings import Preferences, SavePreferences, IsRoleExists

def roleFromId(role_id: int):
    return [discord.SelectDefaultValue(id=role_id, type=discord.SelectDefaultValueType.role)]

class LinkedRolesView(discord.ui.View):
    def __init__(self, *, timeout: float | None = 180, primary_role_id: int = None):
        super().__init__(timeout=timeout)
        self.primary_role = None
        self.secondary_role = None
        
        # Загружаем существующие настройки
        if primary_role_id and 'linked_roles' in Preferences:
            secondary_role_id = Preferences['linked_roles'].get(str(primary_role_id))
            if secondary_role_id:
                self.select_primary.default_values = roleFromId(primary_role_id)
                self.select_secondary.default_values = roleFromId(secondary_role_id)
        
    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Выберите основную роль"
    )
    async def select_primary(
        self,
        interaction: discord.Interaction,
        select_item: discord.ui.RoleSelect
    ):
        self.primary_role = select_item.values[0]
        await interaction.response.defer()

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Выберите связанную роль"
    )
    async def select_secondary(
        self,
        interaction: discord.Interaction,
        select_item: discord.ui.RoleSelect
    ):
        self.secondary_role = select_item.values[0]
        await interaction.response.defer()

    @discord.ui.button(label='Подтвердить', style=discord.ButtonStyle.success)
    async def ok(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not self.primary_role or not self.secondary_role:
            await interaction.response.send_message(
                'Необходимо выбрать обе роли!',
                ephemeral=True
            )
            return
            
        # Проверяем существование ролей в гильдии
        guild = interaction.guild
        primary_role = guild.get_role(self.primary_role.id)
        secondary_role = guild.get_role(self.secondary_role.id)
        
        if not primary_role or not secondary_role:
            await interaction.response.send_message(
                'Одна или обе выбранные роли не существуют в этом сервере!',
                ephemeral=True
            )
            return

        # Проверяем, существует ли уже такая связь
        if 'linked_roles' in Preferences:
            existing_secondary_id = Preferences['linked_roles'].get(str(self.primary_role.id))
            if existing_secondary_id == self.secondary_role.id:
                await interaction.response.send_message(
                    f'Роль {self.primary_role.mention} уже связана с ролью {self.secondary_role.mention}!',
                    ephemeral=True
                )
                return

        # Инициализируем словарь для связанных ролей, если его нет
        if 'linked_roles' not in Preferences:
            Preferences['linked_roles'] = {}
            
        # Сохраняем связь ролей
        Preferences['linked_roles'][str(self.primary_role.id)] = self.secondary_role.id
        SavePreferences()
        
        await interaction.response.edit_message(
            content=(
                f'Роли успешно связаны!\n'
                f'При выдаче роли {self.primary_role.mention} '
                f'будет автоматически выдаваться роль {self.secondary_role.mention}'
            ),
            view=None
        )

    @discord.ui.button(label='Отмена', style=discord.ButtonStyle.danger)
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content='Настройка связанных ролей отменена!',
            view=None
        )
