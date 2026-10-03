import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

class Farm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_farms = {}

    async def get_log_channel(self, guild_id: int):
        settings = await self.bot.db.get_settings(guild_id)
        if settings and settings.get('log_channel_id'):
            return self.bot.get_channel(settings['log_channel_id'])
        return None

    @app_commands.command(name='farm_ekle', description='Farm ekle (onay bekler)')
    @app_commands.describe(
        member='Farm verilecek üye',
        amount='Farm miktarı',
        reason='Farm nedeni'
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def farm_ekle(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Belirtilmedi"):
        if amount <= 0:
            await interaction.response.send_message("❌ Farm miktarı 0'dan büyük olmalı!", ephemeral=True)
            return

        farm_id = f"{interaction.guild.id}_{member.id}_{datetime.now().timestamp()}"

        self.pending_farms[farm_id] = {
            'guild_id': interaction.guild.id,
            'user_id': member.id,
            'amount': amount,
            'reason': reason,
            'moderator_id': interaction.user.id
        }

        embed = discord.Embed(
            title="🌾 Farm Onay Bekliyor",
            description=f"{member.mention} üyesine **{amount} 🪙** farm verilecek.",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Neden", value=reason, inline=False)
        embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)

        view = FarmApprovalView(farm_id, self.bot)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name='farm_sil', description='Farm sil (onay bekler)')
    @app_commands.describe(member='Farm silinecek üye')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def farm_sil(self, interaction: discord.Interaction, member: discord.Member):
        farm_id = f"{interaction.guild.id}_{member.id}_{datetime.now().timestamp()}_del"

        self.pending_farms[farm_id] = {
            'guild_id': interaction.guild.id,
            'user_id': member.id,
            'action': 'delete',
            'moderator_id': interaction.user.id
        }

        embed = discord.Embed(
            title="🌾 Farm Silme Onay Bekliyor",
            description=f"{member.mention} üyesinin farmı silinecek.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)

        view = FarmDeleteApprovalView(farm_id, self.bot)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name='farm_liste', description='Farm listesini göster')
    async def farm_liste(self, interaction: discord.Interaction):
        async with self.bot.db.connection.execute(
            'SELECT user_id, amount, reason, moderator_id, created_at FROM farms WHERE guild_id = ? ORDER BY created_at DESC LIMIT 10',
            (interaction.guild.id,)
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message("❌ Henüz farm eklenmemiş!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🌾 Farm Listesi",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )

        for row in rows:
            user = interaction.guild.get_member(row[0])
            moderator = interaction.guild.get_member(row[3])
            user_name = user.mention if user else f"Bilinmiyor ({row[0]})"
            mod_name = moderator.mention if moderator else "Bilinmiyor"
            embed.add_field(
                name=f"{user_name} - {row[1]} 🪙",
                value=f"**Neden:** {row[2]}\n**Yetkili:** {mod_name}\n**Tarih:** {row[4][:10]}",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='farm_istatistik', description='Kim ne kadar farm yapmış')
    async def farm_istatistik(self, interaction: discord.Interaction):
        # Total farms
        async with self.bot.db.connection.execute(
            'SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM farms WHERE guild_id = ?',
            (interaction.guild.id,)
        ) as cursor:
            total_row = await cursor.fetchone()

        # Per user stats
        async with self.bot.db.connection.execute(
            '''SELECT user_id, COUNT(*) as farm_count, SUM(amount) as total_amount
               FROM farms WHERE guild_id = ? GROUP BY user_id ORDER BY total_amount DESC LIMIT 10''',
            (interaction.guild.id,)
        ) as cursor:
            user_rows = await cursor.fetchall()

        embed = discord.Embed(
            title="🌾 Farm İstatistikleri",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )

        embed.add_field(name="Toplam Farm Sayısı", value=f"{total_row[0]}", inline=False)
        embed.add_field(name="Toplam Farm Miktarı", value=f"{total_row[1]} 🪙", inline=False)

        if user_rows:
            user_text = ""
            for row in user_rows:
                user = interaction.guild.get_member(row[0])
                user_name = user.mention if user else f"Bilinmiyor ({row[0]})"
                user_text += f"{user_name}: {row[1]} farm - {row[2]} 🪙\n"
            embed.add_field(name="Oyuncu Bazında", value=user_text, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='farm_log', description='Farm log kanalını ayarla')
    @app_commands.describe(channel='Log kanalı')
    @app_commands.checks.has_permissions(administrator=True)
    async def farm_log(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.bot.db.update_setting(interaction.guild.id, 'log_channel_id', channel.id)

        embed = discord.Embed(
            title="🌾 Farm Log Kanalı Ayarlandı",
            description=f"Farm logları {channel.mention} kanalına gönderilecek.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)


class FarmApprovalView(discord.ui.View):
    def __init__(self, farm_id: str, bot):
        super().__init__(timeout=300)
        self.farm_id = farm_id
        self.bot = bot

    @discord.ui.button(label="✅ Onayla", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        farm_data = self.bot.get_cog('Farm').pending_farms.pop(self.farm_id, None)
        if not farm_data:
            await interaction.response.send_message("❌ Bu farm isteği süresi doldu!", ephemeral=True)
            return

        await self.bot.db.connection.execute(
            '''INSERT INTO farms (guild_id, user_id, amount, reason, moderator_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (farm_data['guild_id'], farm_data['user_id'], farm_data['amount'], farm_data['reason'], farm_data['moderator_id'], datetime.now().isoformat())
        )
        await self.bot.db.connection.commit()

        log_channel = await self.bot.get_cog('Farm').get_log_channel(farm_data['guild_id'])
        if log_channel:
            embed = discord.Embed(
                title="🌾 Farm Eklendi",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            user = interaction.guild.get_member(farm_data['user_id'])
            moderator = interaction.guild.get_member(farm_data['moderator_id'])
            embed.add_field(name="Üye", value=f"{user.mention if user else farm_data['user_id']} ({farm_data['user_id']})", inline=False)
            embed.add_field(name="Miktar", value=f"{farm_data['amount']} 🪙", inline=False)
            embed.add_field(name="Neden", value=farm_data['reason'], inline=False)
            embed.add_field(name="Yetkili", value=f"{moderator.mention if moderator else farm_data['moderator_id']}", inline=False)
            if user:
                embed.set_thumbnail(url=user.display_avatar.url)
            await log_channel.send(embed=embed)

        embed = discord.Embed(
            title="🌾 Farm Eklendi",
            description=f"Farm onaylandı ve loga eklendi!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="❌ Reddet", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bot.get_cog('Farm').pending_farms.pop(self.farm_id, None)
        await interaction.response.send_message("❌ Farm isteği reddedildi!", ephemeral=True)


class FarmDeleteApprovalView(discord.ui.View):
    def __init__(self, farm_id: str, bot):
        super().__init__(timeout=300)
        self.farm_id = farm_id
        self.bot = bot

    @discord.ui.button(label="✅ Onayla", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        farm_data = self.bot.get_cog('Farm').pending_farms.pop(self.farm_id, None)
        if not farm_data:
            await interaction.response.send_message("❌ Bu farm isteği süresi doldu!", ephemeral=True)
            return

        cursor = await self.bot.db.connection.execute(
            'DELETE FROM farms WHERE guild_id = ? AND user_id = ?',
            (farm_data['guild_id'], farm_data['user_id'])
        )
        await self.bot.db.connection.commit()

        if cursor.rowcount == 0:
            await interaction.response.send_message("❌ Bu üyenin farmı bulunamadı!", ephemeral=True)
            return

        log_channel = await self.bot.get_cog('Farm').get_log_channel(farm_data['guild_id'])
        if log_channel:
            embed = discord.Embed(
                title="🌾 Farm Silindi",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            user = interaction.guild.get_member(farm_data['user_id'])
            moderator = interaction.guild.get_member(farm_data['moderator_id'])
            embed.add_field(name="Üye", value=f"{user.mention if user else farm_data['user_id']} ({farm_data['user_id']})", inline=False)
            embed.add_field(name="Yetkili", value=f"{moderator.mention if moderator else farm_data['moderator_id']}", inline=False)
            if user:
                embed.set_thumbnail(url=user.display_avatar.url)
            await log_channel.send(embed=embed)

        embed = discord.Embed(
            title="🌾 Farm Silindi",
            description=f"Farm onaylandı ve loga eklendi!",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="❌ Reddet", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bot.get_cog('Farm').pending_farms.pop(self.farm_id, None)
        await interaction.response.send_message("❌ Farm silme isteği reddedildi!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Farm(bot))
