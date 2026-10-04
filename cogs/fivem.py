import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

class FiveM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_log_channel(self, guild_id: int, log_type='silah_katlanan'):
        """Silah loglari icin ozel kanali kullan (katlanan / kaybedilen)"""
        settings = await self.bot.db.get_settings(guild_id)
        if not settings:
            return None

        cid = settings.get(f'{log_type}_log_channel_id')
        if cid:
            channel = self.bot.get_channel(cid)
            if channel:
                return channel

        legacy = settings.get('log_channel_id')
        if legacy:
            return self.bot.get_channel(legacy)

        return None

    @app_commands.command(name='silah', description='Silah sistemi')
    @app_commands.describe(
        kategori='Kategori seç',
        member='Oyuncu',
        weapon='Silah markası',
        amount='Miktar',
        reason='Nasıl katlandı / Neden'
    )
    @app_commands.choices(kategori=[
        app_commands.Choice(name='Katlanan - Silah ver', value='katlanan'),
        app_commands.Choice(name='Kaybedilen - Silah kaybet', value='kaybedilen'),
        app_commands.Choice(name='Marka - Silah markası', value='marka'),
        app_commands.Choice(name='Miktar - Toplam miktar', value='miktar'),
        app_commands.Choice(name='Nasıl Katlandı - Katlanma yolu', value='nasil'),
        app_commands.Choice(name='Liste - Oyuncunun silahları', value='liste'),
        app_commands.Choice(name='İstatistik - Ekip istatistikleri', value='istatistik'),
        app_commands.Choice(name='Kayıp Listesi - Kaybedilen silahlar', value='kayip_liste')
    ])
    async def silah(self, interaction: discord.Interaction, kategori: str, member: discord.Member | None = None, weapon: str = None, amount: int = None, reason: str = None):
        if kategori == "katlanan":
            await self.silah_katlanan(interaction, member, weapon, amount, reason)
        elif kategori == "kaybedilen":
            await self.silah_kaybedilen(interaction, member, weapon, reason)
        elif kategori == "marka":
            await self.silah_marka(interaction, member, weapon)
        elif kategori == "miktar":
            await self.silah_miktar(interaction, member)
        elif kategori == "nasil":
            await self.silah_nasil(interaction, member, weapon, reason)
        elif kategori == "liste":
            await self.silah_liste(interaction, member)
        elif kategori == "istatistik":
            await self.silah_istatistik(interaction)
        elif kategori == "kayip_liste":
            await self.silah_kayip_liste(interaction)

    async def silah_katlanan(self, interaction: discord.Interaction, member: discord.Member, weapon: str, amount: int, reason: str):
        if not member or not weapon or not amount:
            await interaction.response.send_message("❌ Eksik bilgi! Kullanım: `/silah katlanan @Oyuncu AK-47 5000 Satın alma`", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("❌ Miktar 0'dan büyük olmalı!", ephemeral=True)
            return

        await self.bot.db.connection.execute(
            '''INSERT INTO fivem_weapons (guild_id, user_id, weapon_name, price, moderator_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (interaction.guild.id, member.id, weapon, amount, interaction.user.id, datetime.now().isoformat())
        )
        await self.bot.db.connection.commit()

        log_channel = await self.get_log_channel(interaction.guild.id, 'silah_katlanan')
        if log_channel:
            embed = discord.Embed(
                title="🔫 Silah Katlanandı",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Oyuncu", value=f"{member.mention} ({member.id})", inline=False)
            embed.add_field(name="Marka", value=weapon, inline=False)
            embed.add_field(name="Miktar", value=f"{amount} 💵", inline=False)
            embed.add_field(name="Nasıl Katlandı", value=reason or "Belirtilmedi", inline=False)
            embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed)

        embed = discord.Embed(
            title="🔫 Silah Katlanandı",
            description=f"{member.mention} oyuncusuna **{weapon}** marka silah katlandı! Miktar: **{amount} 💵** Yöntem: **{reason or 'Belirtilmedi'}**",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    async def silah_kaybedilen(self, interaction: discord.Interaction, member: discord.Member, weapon: str, reason: str):
        if not member or not weapon:
            await interaction.response.send_message("❌ Eksik bilgi! Kullanım: `/silah kaybedilen @Oyuncu AK-47 Öldürüldü`", ephemeral=True)
            return

        await self.bot.db.connection.execute(
            '''INSERT INTO fivem_weapons_lost (guild_id, user_id, weapon_name, reason, moderator_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (interaction.guild.id, member.id, weapon, reason or "Belirtilmedi", interaction.user.id, datetime.now().isoformat())
        )
        await self.bot.db.connection.commit()

        log_channel = await self.get_log_channel(interaction.guild.id, 'silah_kaybedilen')
        if log_channel:
            embed = discord.Embed(
                title="🔫 Silah Kaybedildi",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Oyuncu", value=f"{member.mention} ({member.id})", inline=False)
            embed.add_field(name="Marka", value=weapon, inline=False)
            embed.add_field(name="Neden", value=reason or "Belirtilmedi", inline=False)
            embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed)

        embed = discord.Embed(
            title="🔫 Silah Kaybedildi",
            description=f"{member.mention} oyuncusunun **{weapon}** marka silahı kaybedildi! Neden: **{reason or 'Belirtilmedi'}**",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    async def silah_marka(self, interaction: discord.Interaction, member: discord.Member, weapon: str):
        if not member or not weapon:
            await interaction.response.send_message("❌ Eksik bilgi! Kullanım: `/silah marka @Oyuncu AK-47`", ephemeral=True)
            return

        async with self.bot.db.connection.execute(
            'SELECT weapon_name, price, moderator_id, created_at FROM fivem_weapons WHERE guild_id = ? AND user_id = ? AND weapon_name = ? ORDER BY created_at DESC LIMIT 10',
            (interaction.guild.id, member.id, weapon)
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message("❌ Bu markada silah bulunamadı!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🔫 {member.name} - {weapon} Markası",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        total_value = 0
        for row in rows:
            moderator = interaction.guild.get_member(row[2])
            mod_name = moderator.mention if moderator else "Bilinmiyor"
            total_value += row[1]
            embed.add_field(
                name=f"{row[0]} - {row[1]} 💵",
                value=f"**Yetkili:** {mod_name}\n**Tarih:** {row[3][:10]}",
                inline=False
            )

        embed.set_footer(text=f"Toplam: {total_value} 💵")
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    async def silah_miktar(self, interaction: discord.Interaction, member: discord.Member):
        if not member:
            await interaction.response.send_message("❌ Oyuncu belirtmelisin!", ephemeral=True)
            return

        # Total katlanan
        async with self.bot.db.connection.execute(
            'SELECT COALESCE(SUM(price), 0) FROM fivem_weapons WHERE guild_id = ? AND user_id = ?',
            (interaction.guild.id, member.id)
        ) as cursor:
            katlanan = (await cursor.fetchone())[0]

        # Total kaybedilen
        async with self.bot.db.connection.execute(
            'SELECT COUNT(*) FROM fivem_weapons_lost WHERE guild_id = ? AND user_id = ?',
            (interaction.guild.id, member.id)
        ) as cursor:
            kaybedilen = (await cursor.fetchone())[0]

        # Net silah miktarı
        net = katlanan - kaybedilen

        embed = discord.Embed(
            title=f"🔫 {member.name} Silah Miktarı",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Katlanan", value=f"{katlanan} 💵", inline=False)
        embed.add_field(name="Kaybedilen", value=f"{kaybedilen} silah", inline=False)
        embed.add_field(name="Net Silah Miktarı", value=f"{net} 💵", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    async def silah_nasil(self, interaction: discord.Interaction, member: discord.Member, weapon: str, reason: str):
        if not member or not weapon or not reason:
            await interaction.response.send_message("❌ Eksik bilgi! Kullanım: `/silah nasil @Oyuncu AK-47 Satın alma`", ephemeral=True)
            return

        async with self.bot.db.connection.execute(
            'SELECT weapon_name, price, moderator_id, created_at FROM fivem_weapons WHERE guild_id = ? AND user_id = ? AND weapon_name = ? ORDER BY created_at DESC LIMIT 10',
            (interaction.guild.id, member.id, weapon)
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message("❌ Bu silah bulunamadı!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🔫 {member.name} - Nasıl Katlandı",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        for row in rows:
            moderator = interaction.guild.get_member(row[2])
            mod_name = moderator.mention if moderator else "Bilinmiyor"
            embed.add_field(
                name=f"{row[0]} - {row[1]} 💵",
                value=f"**Nasıl Katlandı:** {reason}\n**Yetkili:** {mod_name}\n**Tarih:** {row[3][:10]}",
                inline=False
            )

        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    async def silah_liste(self, interaction: discord.Interaction, member: discord.Member):
        if not member:
            await interaction.response.send_message("❌ Oyuncu belirtmelisin!", ephemeral=True)
            return

        async with self.bot.db.connection.execute(
            'SELECT weapon_name, price, moderator_id, created_at FROM fivem_weapons WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 10',
            (interaction.guild.id, member.id)
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message("❌ Bu oyuncunun silahı bulunamadı!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🔫 {member.name} Silahları",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        total_value = 0
        for row in rows:
            moderator = interaction.guild.get_member(row[2])
            mod_name = moderator.mention if moderator else "Bilinmiyor"
            total_value += row[1]
            embed.add_field(
                name=f"{row[0]} - {row[1]} 💵",
                value=f"**Yetkili:** {mod_name}\n**Tarih:** {row[3][:10]}",
                inline=False
            )

        embed.set_footer(text=f"Toplam Değer: {total_value} 💵")
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    async def silah_istatistik(self, interaction: discord.Interaction):
        async with self.bot.db.connection.execute(
            'SELECT COUNT(*), COALESCE(SUM(price), 0) FROM fivem_weapons WHERE guild_id = ?',
            (interaction.guild.id,)
        ) as cursor:
            won_row = await cursor.fetchone()

        async with self.bot.db.connection.execute(
            'SELECT COUNT(*) FROM fivem_weapons_lost WHERE guild_id = ?',
            (interaction.guild.id,)
        ) as cursor:
            lost_row = await cursor.fetchone()

        async with self.bot.db.connection.execute(
            '''SELECT user_id, COUNT(*) as weapon_count, SUM(price) as total_value
               FROM fivem_weapons WHERE guild_id = ? GROUP BY user_id ORDER BY total_value DESC LIMIT 10''',
            (interaction.guild.id,)
        ) as cursor:
            user_rows = await cursor.fetchall()

        embed = discord.Embed(
            title="🔫 Ekip Silah İstatistikleri",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        embed.add_field(name="Toplam Katlanan", value=f"{won_row[0]} silah - {won_row[1]} 💵", inline=False)
        embed.add_field(name="Toplam Kaybedilen", value=f"{lost_row[0]} silah", inline=False)

        if user_rows:
            user_text = ""
            for row in user_rows:
                user = interaction.guild.get_member(row[0])
                user_name = user.mention if user else f"Bilinmiyor ({row[0]})"
                user_text += f"{user_name}: {row[1]} silah - {row[2]} 💵\n"
            embed.add_field(name="Oyuncu Bazında", value=user_text, inline=False)

        await interaction.response.send_message(embed=embed)

    async def silah_kayip_liste(self, interaction: discord.Interaction):
        async with self.bot.db.connection.execute(
            'SELECT user_id, weapon_name, reason, moderator_id, created_at FROM fivem_weapons_lost WHERE guild_id = ? ORDER BY created_at DESC LIMIT 10',
            (interaction.guild.id,)
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message("❌ Kayıp silah bulunamadı!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔫 Kayıp Silah Listesi",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )

        for row in rows:
            user = interaction.guild.get_member(row[0])
            moderator = interaction.guild.get_member(row[3])
            user_name = user.mention if user else f"Bilinmiyor ({row[0]})"
            mod_name = moderator.mention if moderator else "Bilinmiyor"
            embed.add_field(
                name=f"{row[1]}",
                value=f"**Oyuncu:** {user_name}\n**Neden:** {row[2]}\n**Yetkili:** {mod_name}\n**Tarih:** {row[4][:10]}",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(FiveM(bot))
