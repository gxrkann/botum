import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import asyncio

from cogs import fivem_catalog as Katalog


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

    async def _sil(self, interaction, content=None, embed=None, saniye: int = 25):
        """
        Mesaji gonderir ve belirtilen sure sonra otomatik siler.

        Komut mesajlari kanali kirletmesin diye. Eylem zaten kaydedildi,
        kullaniciya zaman icinde bildirilmis oluyor.
        """
        kwargs = {}
        if embed:
            kwargs['embed'] = embed
        else:
            kwargs['content'] = content

        try:
            if interaction.response.is_done():
                msg = await interaction.followup.send(**kwargs)
            else:
                msg = await interaction.response.send_message(**kwargs)
        except discord.HTTPException:
            return None

        # Sadece herkese acik mesajlari sil (ephemeral silinmez zaten)
        if saniye > 0 and saniye <= 3600:
            async def temizle():
                await asyncio.sleep(saniye)
                try:
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
            asyncio.create_task(temizle())

        return msg

    @app_commands.command(name='silah', description='Silah sistemi')
    @app_commands.describe(
        kategori='Kategori seç',
        member='Oyuncu',
        weapon='Silah modeli (örn: AK-47)',
        amount='Adet (kaç tane) veya fiyat',
        reason='Nasıl katlandı / Neden',
        sayfa='Depo / katalog sayfası'
    )
    @app_commands.choices(kategori=[
        app_commands.Choice(name='🔫 Katlanan - Silah ver', value='katlanan'),
        app_commands.Choice(name='💀 Kaybedilen - Silah kaybet', value='kaybedilen'),
        app_commands.Choice(name='📖 Katalog - Tüm silahlar (marka/model)', value='katalog'),
        app_commands.Choice(name='🏷️ Marka Listesi - Markalar', value='marka'),
        app_commands.Choice(name='📊 Miktar - Adet ve değer', value='miktar'),
        app_commands.Choice(name='📝 Nasıl Katlandı', value='nasil'),
        app_commands.Choice(name='📜 Liste - Oyuncunun silahları', value='liste'),
        app_commands.Choice(name='📈 İstatistik - Ekip istatistikleri', value='istatistik'),
        app_commands.Choice(name='❌ Kayıp Listesi', value='kayip_liste'),
        app_commands.Choice(name='📦 Depo - Tüm silahları', value='depo'),
    ])
    async def silah(self, interaction: discord.Interaction, kategori: str,
                    member: discord.Member | None = None,
                    weapon: str | None = None,
                    amount: int | None = None,
                    reason: str | None = None,
                    sayfa: int = 1):
        if kategori == "katlanan":
            await self.silah_katlanan(interaction, member, weapon, amount, reason)
        elif kategori == "kaybedilen":
            await self.silah_kaybedilen(interaction, member, weapon, reason)
        elif kategori == "marka":
            await self.silah_marka(interaction, member, weapon)
        elif kategori == "katalog":
            await self.silah_katalog(interaction, weapon, sayfa)
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

    async def _giris_bildirimi(self, member, bilgi, weapon, fiyat, neden, katlandi_mi):
        """
        Oyuncuyu Discord DM ile bilgilendirir.

        Discord uzerinde kanal mesaji birakmamak icin oyuncuya
        dogrudan DM atilir. Ayrica gonderilen mesajlar otomatik silinir.
        """
        if member.bot:
            return

        baslik = "🔫 Silah Katlandı" if katlandi_mi else "💀 Silah Kaybedildi"
        renk = 0x2ECC71 if katlandi_mi else 0xE74C3C

        satir = f"**Marka:** {bilgi['marka']}\n**Model:** {weapon}\n**Kategori:** {bilgi['kategori']}\n"
        satir += f"**Fiyat:** {fiyat:,} ₺\n" if katlandi_mi else ""
        satir += f"**Sebep:** {neden}"

        embed = discord.Embed(
            title=baslik,
            description=f"{self.bot.user.mention} sunucusunda ({member.guild.name})\n\n{satir}",
            color=renk,
            timestamp=datetime.now()
        )
        try:
            embed.set_thumbnail(url=member.guild.icon.url)
        except Exception:
            pass

        try:
            dm = await member.send(embed=embed)

            # DM mesajini da bir sure sonra temizle
            async def dm_temizle():
                await asyncio.sleep(60)
                try:
                    await dm.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
            asyncio.create_task(dm_temizle())
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

    async def silah_katalog(self, interaction: discord.Interaction, marka: str | None = None, sayfa: int = 1):
        """Marka ve modele gore ayrilmis silah katalogu"""
        await interaction.response.defer(ephemeral=True)

        if marka:
            # Tek markanin modelleri
            m = marka.strip().lower()
            modeller = [(model, bilgi) for model, bilgi in Katalog.SILAH_KATALOG.items()
                        if bilgi['marka'].lower() == m or model.lower() == m]

            if not modeller:
                await interaction.followup.send(
                    f"❌ **\"{marka}\"** markası bulunamadı.\n\n"
                    f"Markanın adını kontrol et veya `/silah katalog` ile listeyi gör.",
                    ephemeral=True)
                return

            bilgi = modeller[0][1]
            embed = discord.Embed(
                title=f"🏷️ {bilgi['marka']} — Modeller",
                color=discord.Color.dark_grey(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="Kategori",
                value=f"**{bilgi['kategori']}**",
                inline=True
            )
            embed.add_field(
                name="Model Sayısı",
                value=f"**{len(modeller)}**",
                inline=True
            )

            for model, b in sorted(modeller, key=lambda x: x[1]['fiyat']):
                embed.add_field(
                    name=f"🔫 {model}",
                    value=f"Alt: **{b['alt']}** • Fiyat: **{b['fiyat']:,}** 💵",
                    inline=False
                )

            embed.set_footer(text="Silah vermek için: /silah katlanan üye:@kişi weapon:AK-47 amount:25000")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Marka listesi (sayfali)
        markalar = Katalog.markalar()
        sirali = sorted(markalar.items(), key=lambda x: x[0])

        per_page = 8
        toplam_sayfa = (len(sirali) + per_page - 1) // per_page
        sayfa = max(1, min(sayfa, toplam_sayfa))
        bas = (sayfa - 1) * per_page
        dilim = sirali[bas:bas + per_page]

        embed = discord.Embed(
            title="📖 Silah Kataloğu",
            description=f"**{len(Katalog.SILAH_KATALOG)}** model • **{len(sirali)}** marka",
            color=discord.Color.dark_grey(),
            timestamp=datetime.now()
        )

        for marka_adi, modeller in dilim:
            en_ucuz = min(b['fiyat'] for _, b in modeller)
            en_pahali = max(b['fiyat'] for _, b in modeller)
            model_isimleri = ", ".join(sorted(m for m, _ in modeller)[:6])
            if len(modeller) > 6:
                model_isimleri += f" *+{len(modeller) - 6} model*"

            embed.add_field(
                name=f"🏷️ {marka_adi} ({len(modeller)})",
                value=f"{model_isimleri}\n💵 {en_ucuz:,} — {en_pahali:,}",
                inline=False
            )

        embed.set_footer(text=f"Sayfa {sayfa}/{toplam_sayfa} • Marka detayı: /silah katalog weapon:<marka>")
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def silah_katlanan(self, interaction: discord.Interaction, member: discord.Member, weapon: str, amount: int, reason: str):
        if not member or not weapon:
            await interaction.response.send_message(
                "❌ Eksik bilgi!\n"
                "**Kullanım:** `/silah katlanan üye:@Oyuncu weapon:AK-47 amount:25000`\n"
                "*amount = fiyat (₺)*", ephemeral=True)
            return

        if not amount or amount <= 0:
            await interaction.response.send_message(
                "❌ **Fiyat 0'dan büyük olmalı!**\n"
                "Katalog fiyatları: `/silah katalog`", ephemeral=True)
            return

        # Katalog bilgisi
        bilgi = Katalog.silah_bilgi(weapon)

        await self.bot.db.connection.execute(
            '''INSERT INTO fivem_weapons
               (guild_id, user_id, weapon_name, price, marka, silah_kategori, adet, moderator_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)''',
            (interaction.guild.id, member.id, bilgi.get('alt') and weapon or weapon,
             amount, bilgi['marka'], bilgi['kategori'],
             interaction.user.id, datetime.now().isoformat())
        )
        await self.bot.db.connection.commit()

        log_channel = await self.get_log_channel(interaction.guild.id, 'silah_katlanan')
        if log_channel:
            embed = discord.Embed(
                title="🔫 Silah Katlandı",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Oyuncu", value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="Marka", value=f"**{bilgi['marka']}**", inline=True)
            embed.add_field(name="Model", value=f"**{weapon}**", inline=True)
            embed.add_field(name="Kategori", value=f"**{bilgi['kategori']}**", inline=True)
            embed.add_field(name="Fiyat", value=f"**{amount:,}** 💵", inline=True)
            embed.add_field(name="Nasıl Katlandı", value=reason or "Belirtilmedi", inline=False)
            embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
            try:
                embed.set_thumbnail(url=member.display_avatar.url)
            except Exception:
                pass
            await log_channel.send(embed=embed)

        embed = discord.Embed(
            title="🔫 Silah Katlandı",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Oyuncu", value=member.mention, inline=False)
        embed.add_field(name="Marka", value=f"**{bilgi['marka']}**", inline=True)
        embed.add_field(name="Model", value=f"**{weapon}**", inline=True)
        embed.add_field(name="Kategori", value=f"**{bilgi['kategori']}**", inline=True)
        embed.add_field(name="Fiyat", value=f"**{amount:,}** 💵", inline=True)
        embed.add_field(name="Yöntem", value=reason or "Belirtilmedi", inline=False)

        await self._sil(interaction, embed=embed, saniye=25)
        await self._giris_bildirimi(member, bilgi, weapon, amount, reason or "Belirtilmedi", True)

    async def silah_kaybedilen(self, interaction: discord.Interaction, member: discord.Member, weapon: str, reason: str):
        if not member or not weapon:
            await interaction.response.send_message(
                "❌ Eksik bilgi!\n"
                "**Kullanım:** `/silah kaybedilen üye:@Oyuncu weapon:AK-47`", ephemeral=True)
            return

        bilgi = Katalog.silah_bilgi(weapon)

        await self.bot.db.connection.execute(
            '''INSERT INTO fivem_weapons_lost (guild_id, user_id, weapon_name, reason, moderator_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (interaction.guild.id, member.id, weapon, reason or "Belirtilmedi", interaction.user.id, datetime.now().isoformat())
        )
        await self.bot.db.connection.commit()

        log_channel = await self.get_log_channel(interaction.guild.id, 'silah_kaybedilen')
        if log_channel:
            embed = discord.Embed(
                title="💀 Silah Kaybedildi",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Oyuncu", value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="Marka", value=f"**{bilgi['marka']}**", inline=True)
            embed.add_field(name="Model", value=f"**{weapon}**", inline=True)
            embed.add_field(name="Kategori", value=f"**{bilgi['kategori']}**", inline=True)
            embed.add_field(name="Neden", value=reason or "Belirtilmedi", inline=False)
            embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
            try:
                embed.set_thumbnail(url=member.display_avatar.url)
            except Exception:
                pass
            await log_channel.send(embed=embed)

        embed = discord.Embed(
            title="💀 Silah Kaybedildi",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Oyuncu", value=member.mention, inline=False)
        embed.add_field(name="Marka", value=f"**{bilgi['marka']}**", inline=True)
        embed.add_field(name="Model", value=f"**{weapon}**", inline=True)
        embed.add_field(name="Kategori", value=f"**{bilgi['kategori']}**", inline=True)
        embed.add_field(name="Neden", value=reason or "Belirtilmedi", inline=False)

        await self._sil(interaction, embed=embed, saniye=25)
        await self._giris_bildirimi(member, bilgi, weapon, 0, reason or "Belirtilmedi", False)

    async def silah_marka(self, interaction: discord.Interaction, member: discord.Member, weapon: str):
        """Oyuncunun TEK bir markadaki tum silahlari"""
        if not member:
            await interaction.response.send_message(
                "❌ Oyuncu belirtmelisin!\n"
                "**Kullanım:** `/silah marka üye:@Oyuncu weapon:Kalashnikov`", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Marka verilmediyse: oyuncunun tum markalari
        if not weapon:
            async with self.bot.db.connection.execute(
                '''SELECT COALESCE(marka, 'Bilinmiyor') marka, COUNT(*) adet,
                          COALESCE(SUM(price), 0) toplam
                   FROM fivem_weapons WHERE guild_id = ? AND user_id = ?
                   GROUP BY COALESCE(marka, 'Bilinmiyor')
                   ORDER BY adet DESC''',
                (interaction.guild.id, member.id)
            ) as cur:
                rows = await cur.fetchall()

            if not rows:
                await interaction.followup.send(
                    f"📭 {member.mention} henüz silah katlanmamış.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"🏷️ {member.display_name} — Marka Bazında",
                description=f"**{len(rows)}** farklı marka • "
                            f"**{sum(r[1] for r in rows)}** silah",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            for marka, adet, toplam in rows[:20]:
                embed.add_field(
                    name=f"🏷️ {marka}",
                    value=f"🔫 **{adet}** silah • 💵 **{toplam:,}**",
                    inline=False
                )
            try:
                embed.set_thumbnail(url=member.display_avatar.url)
            except Exception:
                pass

            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        bilgi = Katalog.silah_bilgi(weapon)
        marka = bilgi['marka']

        async with self.bot.db.connection.execute(
            '''SELECT weapon_name, price, moderator_id, created_at, silah_kategori
               FROM fivem_weapons
               WHERE guild_id = ? AND user_id = ?
                 AND LOWER(COALESCE(marka, '')) = LOWER(?)
               ORDER BY created_at DESC LIMIT 15''',
            (interaction.guild.id, member.id, marka)
        ) as cur:
            rows = await cur.fetchall()

        if not rows:
            await interaction.followup.send(
                f"❌ **{member.display_name}** deposunda **{marka}** markası yok!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🔫 {member.display_name} — {marka}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="Özet",
            value=(f"🔫 **{len(rows)}** kayıt\n"
                   f"💵 **Toplam:** {sum(r[1] for r in rows):,}"),
            inline=False
        )

        for i, row in enumerate(rows, 1):
            moderator = interaction.guild.get_member(row[2])
            mod_ment = moderator.mention if moderator else "Bilinmiyor"
            tarih = row[3][:10] if row[3] else "?"
            embed.add_field(
                name=f"#{i} • {row[0]} — {row[1]:,} 💵",
                value=f"Kategori: **{row[4] or '-'}** • Yetkili: {mod_ment} • {tarih}",
                inline=False
            )

        try:
            embed.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def silah_miktar(self, interaction: discord.Interaction, member: discord.Member):
        """ADET ve DEGER ayri gosterilir - ikisi karistirilamaz"""
        if not member:
            await interaction.response.send_message(
                "❌ Oyuncu belirtmelisin!\n"
                "**Kullanım:** `/silah miktar üye:@Oyuncu`", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # KATLANAN: adet + deger ayri
        async with self.bot.db.connection.execute(
            '''SELECT COUNT(*), COALESCE(SUM(price), 0)
               FROM fivem_weapons WHERE guild_id = ? AND user_id = ?''',
            (interaction.guild.id, member.id)
        ) as cur:
            katlanan_adet, katlanan_deger = await cur.fetchone()

        # KAYBEDILEN: adet + deger
        async with self.bot.db.connection.execute(
            '''SELECT COUNT(*), COALESCE(
                 (SELECT COALESCE(SUM(price), 0) FROM fivem_weapons
                  WHERE guild_id = f.guild_id AND user_id = f.user_id
                    AND LOWER(weapon_name) = LOWER(f.weapon_name)), 0)
               FROM fivem_weapons_lost f
               WHERE guild_id = ? AND user_id = ?''',
            (interaction.guild.id, member.id)
        ) as cur:
            kaybedilen_adet, kaybedilen_deger = await cur.fetchone()

        net_adet = (katlanan_adet or 0) - (kaybedilen_adet or 0)
        net_deger = (katlanan_deger or 0) - (kaybedilen_deger or 0)

        embed = discord.Embed(
            title=f"📊 {member.display_name} — Silah Miktarı",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        embed.add_field(
            name="🔫 Adet",
            value=(f"Katlanan: **{katlanan_adet or 0}** silah\n"
                   f"Kaybedilen: **{kaybedilen_adet or 0}** silah\n"
                   f"─────────────\n"
                   f"**Net: {net_adet} silah**"),
            inline=True
        )

        embed.add_field(
            name="💵 Değer",
            value=(f"Katlanan: **{katlanan_deger or 0:,}** ₺\n"
                   f"Kaybedilen: **{kaybedilen_deger or 0:,}** ₺\n"
                   f"─────────────\n"
                   f"**Net: {net_deger:,} ₺**"),
            inline=True
        )

        # Kategori dagilimi
        async with self.bot.db.connection.execute(
            '''SELECT COALESCE(silah_kategori, 'Diger') kat, COUNT(*) adet
               FROM fivem_weapons WHERE guild_id = ? AND user_id = ?
               GROUP BY COALESCE(silah_kategori, 'Diger')
               ORDER BY adet DESC LIMIT 8''',
            (interaction.guild.id, member.id)
        ) as cur:
            kat_dagilim = await cur.fetchall()

        if kat_dagilim:
            dagilim = " • ".join(f"**{k}**: {n}" for k, n in kat_dagilim)
            embed.add_field(name="📂 Kategori Dağılımı", value=dagilim, inline=False)

        embed.set_footer(text="Detaylı liste için: /silah depo • /silah marka")
        try:
            embed.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass

        await interaction.followup.send(embed=embed, ephemeral=True)

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

        await interaction.response.defer(ephemeral=True)

        async with self.bot.db.connection.execute(
            '''SELECT weapon_name, price, moderator_id, created_at,
                      COALESCE(marka, 'Bilinmiyor'), COALESCE(silah_kategori, 'Diger')
               FROM fivem_weapons
               WHERE guild_id = ? AND user_id = ?
               ORDER BY created_at DESC LIMIT 10''',
            (interaction.guild.id, member.id)
        ) as cur:
            rows = await cur.fetchall()

        if not rows:
            await interaction.followup.send(
                f"📭 {member.mention} henüz silah katlanmamış.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📜 {member.display_name} — Son Silahlar",
            description=f"Son **{len(rows)}** kayıt",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        for row in rows:
            moderator = interaction.guild.get_member(row[2])
            mod_ment = moderator.mention if moderator else "Bilinmiyor"
            tarih = row[3][:10] if row[3] else "?"
            embed.add_field(
                name=f"🔫 {row[0]} — {row[1]:,} 💵",
                value=f"Marka: **{row[4]}** • Kategori: **{row[5]}**\n"
                      f"Yetkili: {mod_ment} • {tarih}",
                inline=False
            )

        embed.set_footer(text="Tüm silahlar için: /silah depo")
        try:
            embed.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def silah_istatistik(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        async with self.bot.db.connection.execute(
            'SELECT COUNT(*), COALESCE(SUM(price), 0) FROM fivem_weapons WHERE guild_id = ?',
            (interaction.guild.id,)
        ) as cur:
            katlanan_adet, katlanan_deger = await cur.fetchone()

        async with self.bot.db.connection.execute(
            'SELECT COUNT(*) FROM fivem_weapons_lost WHERE guild_id = ?',
            (interaction.guild.id,)
        ) as cur:
            kaybedilen = (await cur.fetchone())[0]

        async with self.bot.db.connection.execute(
            '''SELECT user_id, COUNT(*) as weapon_count, SUM(price) as total_value
               FROM fivem_weapons WHERE guild_id = ? GROUP BY user_id ORDER BY total_value DESC LIMIT 10''',
            (interaction.guild.id,)
        ) as cur:
            user_rows = await cur.fetchall()

        # En cok kullanilan markalar
        async with self.bot.db.connection.execute(
            '''SELECT COALESCE(marka, 'Bilinmiyor') marka, COUNT(*) adet,
                      COALESCE(SUM(price), 0) toplam
               FROM fivem_weapons WHERE guild_id = ?
               GROUP BY COALESCE(marka, 'Bilinmiyor')
               ORDER BY adet DESC LIMIT 8''',
            (interaction.guild.id,)
        ) as cur:
            marka_rows = await cur.fetchall()

        embed = discord.Embed(
            title="📈 Ekip Silah İstatistikleri",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        embed.add_field(
            name="🔫 Genel",
            value=(f"Katlanan: **{katlanan_adet}** silah — **{katlanan_deger:,}** ₺\n"
                   f"Kaybedilen: **{kaybedilen}** silah\n"
                   f"Net: **{katlanan_adet - kaybedilen}** silah"),
            inline=False
        )

        if marka_rows:
            marka_text = "\n".join(
                f"🏷️ **{m}** — {a} silah ({t:,} ₺)" for m, a, t in marka_rows)
            embed.add_field(name="Marka Dağılımı", value=marka_text, inline=False)

        if user_rows:
            user_text = ""
            for row in user_rows:
                user = interaction.guild.get_member(row[0])
                user_name = user.mention if user else f"`{row[0]}`"
                user_text += f"{user_name} — **{row[1]}** silah • {row[2]:,} ₺\n"
            embed.add_field(name="👥 Oyuncu Bazında", value=user_text, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

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

            # ---- Tum silahlar (MARKA bazli depo) ----
            async with self.bot.db.connection.execute(
                '''SELECT COALESCE(marka, 'Bilinmiyor') marka, weapon_name,
                          COUNT(*) as adet, COALESCE(SUM(price), 0) toplam,
                          COALESCE(silah_kategori, 'Diger') kat,
                          MIN(created_at) ilk, MAX(created_at) son
                   FROM fivem_weapons
                   WHERE guild_id = ? AND user_id = ?
                   GROUP BY COALESCE(marka, 'Bilinmiyor'), LOWER(weapon_name)
                   ORDER BY adet DESC, toplam DESC''',
                (guild_id, member.id)
            ) as cur:
                gruplar = await cur.fetchall()

            if not gruplar:
                await interaction.followup.send(
                    f"📦 **{member.display_name}** deposu **boş**!\n"
                    f"Henüz silah katlanmamış.", ephemeral=True)
                return

            toplam_adet = sum(g[2] for g in gruplar)
            toplam_deger = sum(g[3] for g in gruplar)
            marka_sayisi = len({g[0] for g in gruplar})

            # Sayfalama
            per_page = 10
            toplam_sayfa = (len(gruplar) + per_page - 1) // per_page
            sayfa = max(1, min(sayfa, toplam_sayfa))
            bas = (sayfa - 1) * per_page
            dilim = gruplar[bas:bas + per_page]

            embed = discord.Embed(
                title=f"📦 {member.display_name} — Depo",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )

            # Özet - ADET ve DEGER ayri
            embed.add_field(
                name="📊 Özet",
                value=(f"🔫 **Toplam silah:** {toplam_adet} adet\n"
                       f"💵 **Toplam değer:** {toplam_deger:,} ₺\n"
                       f"🏷️ **Marka:** {marka_sayisi} farklı"),
                inline=False
            )

            # Silahlar - marka ve model ayri gosterilir
            liste = ""
            for marka, model, adet, deger, kat, ilk, son in dilim:
                liste += (f"🏷️ **{marka}** — `{model}`\n"
                          f"　 **{adet}** adet • **{deger:,}** ₺ • {kat}\n"
                          f"　 ilk: {ilk[:10] if ilk else '?'} · son: {son[:10] if son else '?'}\n")

            embed.add_field(name="🗃️ Silahlar", value=liste, inline=False)
            embed.set_footer(
                text=f"Sayfa {sayfa}/{toplam_sayfa} • Marka özeti: /silah marka"
            )

            try:
                embed.set_thumbnail(url=member.display_avatar.url)
            except Exception:
                pass

            await interaction.followup.send(embed=embed, ephemeral=True)
            return


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
