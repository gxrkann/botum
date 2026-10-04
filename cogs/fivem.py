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
        reason='Nasıl katlandı / Neden',
        sayfa='Depo sayfası (her sayfada 12 silah)'
    )
    @app_commands.choices(kategori=[
        app_commands.Choice(name='Katlanan - Silah ver', value='katlanan'),
        app_commands.Choice(name='Kaybedilen - Silah kaybet', value='kaybedilen'),
        app_commands.Choice(name='Marka - Silah markası', value='marka'),
        app_commands.Choice(name='Miktar - Toplam miktar', value='miktar'),
        app_commands.Choice(name='Nasıl Katlandı - Katlanma yolu', value='nasil'),
        app_commands.Choice(name='Liste - Oyuncunun silahları', value='liste'),
        app_commands.Choice(name='İstatistik - Ekip istatistikleri', value='istatistik'),
        app_commands.Choice(name='Kayıp Listesi - Kaybedilen silahlar', value='kayip_liste'),
        app_commands.Choice(name='📦 Depo - Oyuncunun tüm silahları', value='depo')
    ])
    async def silah(self, interaction: discord.Interaction, kategori: str, member: discord.Member | None = None, weapon: str = None, amount: int = None, reason: str = None, sayfa: int = 1):
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
        elif kategori == "depo":
            await self.silah_depo(interaction, member, weapon, sayfa)

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

    async def silah_depo(self, interaction: discord.Interaction, member, weapon=None, sayfa: int = 1):
            """
            Oyuncunun TUM silahlarini gosterir (depo).

            - weapon verilmezse: tum silahlar gruplanmis ozet + toplam deger
            - weapon verilirse : sadece o silahin gecmisi (kim, ne zaman, deger)
            - sayfa ile sayfalama (12 kayit/sayfa)
            """
            if not member:
                await interaction.response.send_message(
                    "❌ **Oyuncu belirtmelisin!**\nKullanım: `/silah kategori:Depo üye:@kişi`",
                    ephemeral=True)
                return

            guild_id = interaction.guild.id
            await interaction.response.defer(ephemeral=True)

            # ---- Belirli bir silahin gecmisi ----
            if weapon:
                async with self.bot.db.connection.execute(
                    '''SELECT weapon_name, price, moderator_id, created_at
                       FROM fivem_weapons
                       WHERE guild_id = ? AND user_id = ? AND LOWER(weapon_name) = LOWER(?)
                       ORDER BY created_at DESC''',
                    (guild_id, member.id, weapon)
                ) as cursor:
                    rows = await cursor.fetchall()

                if not rows:
                    await interaction.followup.send(
                        f"❌ **{member.display_name}** deposunda `{weapon}` bulunamadı!",
                        ephemeral=True)
                    return

                per_page = 10
                toplam_sayfa = (len(rows) + per_page - 1) // per_page
                sayfa = max(1, min(sayfa, toplam_sayfa))
                bas = (sayfa - 1) * per_page
                dilim = rows[bas:bas + per_page]

                embed = discord.Embed(
                    title=f"🔫 {member.display_name} → {weapon} Geçmişi",
                    description=f"Toplam **{len(rows)}** kayıt",
                    color=discord.Color.purple(),
                    timestamp=datetime.now()
                )
                toplam_deger = sum(r[1] for r in rows if r[1])
                for i, row in enumerate(dilim, start=bas + 1):
                    mod = interaction.guild.get_member(row[2])
                    mod_ment = mod.mention if mod else "Bilinmiyor"
                    tarih = row[3][:10] if row[3] else "?"
                    embed.add_field(
                        name=f"#{i} • {row[0]} — {row[1]} 💵",
                        value=f"Yetkili: {mod_ment}  •  Tarih: {tarih}",
                        inline=False
                    )

                embed.set_footer(text=f"Sayfa {sayfa}/{toplam_sayfa} • Toplam Değer: {toplam_deger} 💵")
                try:
                    embed.set_thumbnail(url=member.display_avatar.url)
                except Exception:
                    pass

                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # ---- Tum silahlar (gruplanmis depo) ----
            async with self.bot.db.connection.execute(
                '''SELECT weapon_name, COUNT(*) as adet, COALESCE(SUM(price), 0) toplam,
                          MIN(created_at) ilk, MAX(created_at) son
                   FROM fivem_weapons
                   WHERE guild_id = ? AND user_id = ?
                   GROUP BY LOWER(weapon_name)
                   ORDER BY adet DESC, toplam DESC''',
                (guild_id, member.id)
            ) as cursor:
                gruplar = await cursor.fetchall()

            if not gruplar:
                await interaction.followup.send(
                    f"📦 **{member.display_name}** deposu **boş**!\n"
                    f"Henüz silah katlanmamış.", ephemeral=True)
                return

            toplam_adet = sum(g[1] for g in gruplar)
            toplam_deger = sum(g[2] for g in gruplar)

            # Sayfalama
            per_page = 12
            toplam_sayfa = (len(gruplar) + per_page - 1) // per_page
            sayfa = max(1, min(sayfa, toplam_sayfa))
            bas = (sayfa - 1) * per_page
            dilim = gruplar[bas:bas + per_page]

            embed = discord.Embed(
                title=f"📦 {member.display_name} — Depo",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )

            # Özet
            embed.add_field(
                name="📊 Özet",
                value=(f"🔫 **Toplam silah:** {toplam_adet}\n"
                       f"💰 **Toplam değer:** {toplam_deger:,} 💵\n"
                       f"🏷️ **Farklı silah:** {len(gruplar)}"),
                inline=False
            )

            # Silah listesi
            liste = ""
            for g in dilim:
                ad, adet, deger = g[0], g[1], g[2]
                ilk = g[3][:10] if g[3] else "?"
                son = g[4][:10] if g[4] else "?"
                liste += (f"`{ad}` — **{adet}** adet • **{deger:,}** 💵\n"
                          f"　 ilk: {ilk} · son: {son}\n")

            embed.add_field(name="🗃️ Silahlar", value=liste, inline=False)
            embed.set_footer(
                text=f"Sayfa {sayfa}/{toplam_sayfa} • Detay için: `/silah kategori:Depo üye:{member.display_name} silah:<ad>`"
            )

            try:
                embed.set_thumbnail(url=member.display_avatar.url)
            except Exception:
                pass

            await interaction.followup.send(embed=embed, ephemeral=True)

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


# ==================== SUNUCU GIRIS TAKIBI ====================
    @app_commands.command(name='giris', description='FiveM sunucu giriş kayıtları (hangi sunucuda, hangi ID)')
    @app_commands.describe(
        islem='İşlem',
        uye='Oyuncu',
        sunucu='Sunucu adı',
        host='Sunucu adresi (connect endpoint)',
        oyuncu='Oyuncunun sunucudaki ismi',
        steam='Steam ID (örn: steam:110000112345678)',
        license='License ID',
        ip='IP adresi',
        limit='Kaç kayıt listelensin'
    )
    @app_commands.choices(islem=[
        app_commands.Choice(name='Kayıt Ekle - Giriş logla', value='ekle'),
        app_commands.Choice(name='Son Girişler - Sunucu bazlı liste', value='liste'),
        app_commands.Choice(name='Oyuncu Girişleri - Kişinin tüm sunucu geçmişi', value='oyuncu'),
        app_commands.Choice(name='Sunucu Ekle - Sunucu tanımla', value='sunucu_ekle'),
        app_commands.Choice(name='Sunucular - Tanımlı sunucular', value='sunucular'),
        app_commands.Choice(name='İstatistik - Kim hangi sunucuda oynuyor', value='istatistik'),
        app_commands.Choice(name='Temizle - Tüm kayıtları sil', value='temizle'),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giris(self, interaction: discord.Interaction, islem: str,
                    uye: discord.Member | None = None,
                    sunucu: str | None = None,
                    host: str | None = None,
                    oyuncu: str | None = None,
                    steam: str | None = None,
                    license: str | None = None,
                    ip: str | None = None,
                    limit: int = 20):
        gid = interaction.guild.id
        lim = max(1, min(100, limit or 20))

        # ---------- SUNUCU EKLE ----------
        if islem == 'sunucu_ekle':
            if not sunucu:
                await interaction.response.send_message("❌ Sunucu adı gir!", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)
            await self.bot.db.connection.execute(
                'INSERT INTO fivem_servers (guild_id, name, host) VALUES (?, ?, ?)',
                (gid, sunucu, host)
            )
            await self.bot.db.connection.commit()

            await interaction.followup.send(
                f"✅ **{sunucu}** eklendi\n"
                f"Adres: `{host or 'belirtilmedi'}`", ephemeral=True)
            return

        # ---------- SUNUCULAR ----------
        if islem == 'sunucular':
            async with self.bot.db.connection.execute(
                '''SELECT s.name, s.host, COUNT(c.id) giris_sayisi,
                          COUNT(DISTINCT c.user_id) oyuncu_sayisi
                   FROM fivem_servers s
                   LEFT JOIN fivem_connections c ON c.server_name = s.name AND c.guild_id = s.guild_id
                   WHERE s.guild_id = ? GROUP BY s.name, s.host''',
                (gid,)
            ) as cur:
                rows = await cur.fetchall()

            if not rows:
                await interaction.response.send_message(
                    "📭 **Tanımlı sunucu yok.**\n"
                    "Eklemek için: `/giris islem:Sunucu Ekle`", ephemeral=True)
                return

            embed = discord.Embed(title="🖥️ Tanımlı Sunucular",
                                  color=discord.Color.blue(), timestamp=datetime.now())
            for name, h, giris, oyuncu in rows:
                embed.add_field(
                    name=f"**{name}**",
                    value=f"Adres: `{h or '—'}`\n"
                          f"Giriş kaydı: **{giris}** • Oyuncu: **{oyuncu}**",
                    inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # ---------- KAYIT EKLE ----------
        if islem == 'ekle':
            if not uye:
                await interaction.response.send_message("❌ Oyuncu seçmelisin!", ephemeral=True)
                return
            if not sunucu:
                await interaction.response.send_message("❌ Sunucu adı gir!", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            await self.bot.db.connection.execute(
                '''INSERT INTO fivem_connections
                   (guild_id, user_id, server_name, player_name, steam_id, license_id, ip)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (gid, uye.id, sunucu, oyuncu or uye.display_name,
                 steam, license, ip)
            )
            await self.bot.db.connection.commit()

            embed = discord.Embed(
                title="🎮 Sunucu Girişi Kaydedildi",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Oyuncu", value=f"{uye.mention}\nSunucudaki isim: `{oyuncu or uye.display_name}`", inline=False)
            embed.add_field(name="Sunucu", value=f"**{sunucu}**\n`{host or 'adres belirtilmedi'}`", inline=False)
            if steam:
                embed.add_field(name="Steam ID", value=f"`{steam}`", inline=True)
            if license:
                embed.add_field(name="License ID", value=f"`{license}`", inline=True)
            if ip:
                embed.add_field(name="IP", value=f"`{ip}`", inline=True)
            embed.add_field(name="Discord ID", value=f"`{uye.id}`", inline=True)

            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # ---------- OYUNCUNUN GECMISI ----------
        if islem == 'oyuncu':
            if not uye:
                await interaction.response.send_message("❌ Oyuncu seçmelisin!", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)
            async with self.bot.db.connection.execute(
                '''SELECT server_name, player_name, steam_id, license_id, ip, created_at
                   FROM fivem_connections
                   WHERE guild_id = ? AND user_id = ?
                   ORDER BY id DESC LIMIT ?''',
                (gid, uye.id, lim)
            ) as cur:
                rows = await cur.fetchall()

            if not rows:
                await interaction.followup.send(
                    f"📭 {uye.mention} için **giriş kaydı yok**.\n"
                    f"Kayıt eklemek için: `/giris islem:Kayıt Ekle`", ephemeral=True)
                return

            sunucular = {r[0] for r in rows}
            embed = discord.Embed(
                title=f"🎮 {uye.display_name} — Sunucu Geçmişi",
                description=f"**{len(rows)}** kayıt • **{len(sunucular)}** farklı sunucu",
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )

            for r in rows[:20]:
                # Discord embed alan siniri: 25 alan / 6000 karakter
                detay = []
                if r[2]:
                    detay.append(f"Steam: `{r[2]}`")
                if r[3]:
                    detay.append(f"License: `{r[3]}`")
                if r[4]:
                    detay.append(f"IP: `{r[4]}`")
                detay_s = "\n".join(detay) or "ID yok"

                embed.add_field(
                    name=f"🖥️ {r[0]} • {r[5][:16] if r[5] else '?'}",
                    value=f"Sunucudaki isim: `{r[1] or '—'}`\n{detay_s}",
                    inline=False
                )

            try:
                embed.set_thumbnail(url=uye.display_avatar.url)
            except Exception:
                pass

            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # ---------- SON GIRISLER (SUNUCU BAZLI) ----------
        if islem == 'liste':
            await interaction.response.defer(ephemeral=True)

            if sunucu:
                sql = '''SELECT user_id, player_name, steam_id, license_id, ip, created_at
                         FROM fivem_connections
                         WHERE guild_id = ? AND server_name = ?
                         ORDER BY id DESC LIMIT ?'''
                params = (gid, sunucu, lim)
                baslik = f"🖥️ {sunucu} — Son Girişler"
            else:
                sql = '''SELECT user_id, server_name, player_name, steam_id, ip, created_at
                         FROM fivem_connections
                         WHERE guild_id = ? ORDER BY id DESC LIMIT ?'''
                params = (gid, lim)
                baslik = "🎮 Son Sunucu Girişleri"

            async with self.bot.db.connection.execute(sql, params) as cur:
                rows = await cur.fetchall()

            if not rows:
                await interaction.followup.send("📭 **Kayıt bulunamadı.**", ephemeral=True)
                return

            embed = discord.Embed(title=baslik, color=discord.Color.blue(),
                                  timestamp=datetime.now())
            embed.description = f"Son **{len(rows)}** kayıt"

            for r in rows[:20]:
                uid = r[0]
                u = interaction.guild.get_member(uid)
                isim = f"{u.mention}" if u else f"`{uid}`"
                sunucu_adi = r[1] if not sunucu else None

                detay = []
                if r[3]:
                    detay.append(f"Steam: `{r[3]}`")
                if r[4]:
                    detay.append(f"IP: `{r[4]}`")
                detay_s = "\n".join(detay) or "—"
                zaman = r[5][:16] if r[5] else "?"

                bas = f"**{isim}** • `{zaman}`"
                if sunucu_adi:
                    bas = f"**{isim}** → 🖥️ *{sunucu_adi}* • `{zaman}`"

                embed.add_field(name=bas[:256], value=detay_s[:1024], inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # ---------- ISTATISTIK ----------
        if islem == 'istatistik':
            await interaction.response.defer(ephemeral=True)
            async with self.bot.db.connection.execute(
                '''SELECT user_id, server_name, COUNT(*) n, MAX(created_at) son
                   FROM fivem_connections WHERE guild_id = ?
                   GROUP BY user_id, server_name
                   ORDER BY son DESC LIMIT 40''',
                (gid,)
            ) as cur:
                rows = await cur.fetchall()

            if not rows:
                await interaction.followup.send("📭 **Kayıt yok.**", ephemeral=True)
                return

            # Kisi bazli ozet
            kisi = {}
            for uid, sun, n, son in rows:
                d = kisi.setdefault(uid, {'sunucu': {}, 'toplam': 0})
                d['sunucu'][sun] = n
                d['toplam'] += n
                d['son'] = son

            embed = discord.Embed(
                title="📊 Kim Hangi Sunucuda Oynuyor",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.description = f"**{len(kisi)}** oyuncu • **{len({r[1] for r in rows})}** sunucu"

            for uid, d in list(kisi.items())[:15]:
                u = interaction.guild.get_member(uid)
                isim = u.mention if u else f"`{uid}`"
                sunucular = "\n".join(f"• **{s}**: {n} giriş"
                                      for s, n in sorted(d['sunucu'].items(),
                                                         key=lambda x: -x[1])[:5])
                embed.add_field(
                    name=f"{isim} — {d['toplam']} giriş",
                    value=sunucular[:1024], inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # ---------- TEMIZLE ----------
        if islem == 'temizle':
            await interaction.response.defer(ephemeral=True)
            async with self.bot.db.connection.execute(
                'SELECT COUNT(*) FROM fivem_connections WHERE guild_id = ?', (gid,)
            ) as cur:
                n = (await cur.fetchone())[0]

            await self.bot.db.connection.execute(
                'DELETE FROM fivem_connections WHERE guild_id = ?', (gid,))
            await self.bot.db.connection.commit()

            await interaction.followup.send(
                f"🗑️ **{n}** giriş kaydı silindi.", ephemeral=True)
            return


async def setup(bot):
    await bot.add_cog(FiveM(bot))
