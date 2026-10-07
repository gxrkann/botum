import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import asyncio
import random
import time


class Events(commands.Cog):
    # Ayni rol degisikligi bu sure icinde tekrar tekrar loglanmaz.
    # Discord bir uyeye coklu rol eklendiginde her rol icin ayri
    # MEMBER_UPDATE olayi yolluyor ve log arka arkaya yigiluyordu.
    ROLE_DEDUP_SECONDS = 10.0

    def __init__(self, bot):
        self.bot = bot
        # (member_id, frozenset(rol_id)) -> son log zamani
        self._role_log_cache = {}

    def _should_log_roles(self, member_id: int, roles) -> bool:
        """Ayni rol degisikligi kisa sure icinde tekrar mi edildi?"""
        if not roles:
            return False
        key = (member_id, frozenset(r.id for r in roles))
        now = time.time()

        last = self._role_log_cache.get(key)
        if last is not None and (now - last) < self.ROLE_DEDUP_SECONDS:
            return False

        if len(self._role_log_cache) > 200:
            self._role_log_cache = {
                k: v for k, v in self._role_log_cache.items()
                if now - v < self.ROLE_DEDUP_SECONDS
            }

        self._role_log_cache[key] = now
        return True

    async def _log_channel(self, guild_id: int, log_type: str):
        """Log turunun kanalini getir. Ayarli kanal yoksa genel log kanalina duser."""
        settings = await self.bot.db.get_settings(guild_id)
        if not settings:
            return None

        # Once o log turune ozel kanal
        channel_id = settings.get(f'{log_type}_log_channel_id')
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                return channel

        # Yoksa eski genel log kanali
        legacy = settings.get('log_channel_id')
        if legacy:
            return self.bot.get_channel(legacy)

        return None

    async def _send_log(self, guild_id: int, log_type: str, embed: discord.Embed):
        """Log gonder, hata olursa sessizce gec"""
        channel = await self._log_channel(guild_id, log_type)
        if not channel:
            return False
        try:
            await channel.send(embed=embed)
            return True
        except (discord.Forbidden, discord.NotFound):
            return False
        except Exception as e:
            print(f"[events] Log hatasi: {e}", flush=True)
            return False

    # ==================== GIRIS / CIKIS ====================
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        self.bot.logger.info(f'Joined guild: {guild.name} ({guild.id})')

        embed = discord.Embed(
            title="👋 Merhaba!",
            description="Sunucunuza eklendim! `/yardim` yazarak komutları görebilirsin.",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await self._send_log(guild.id, 'member', embed)

        if guild.system_channel:
            try:
                await guild.system_channel.send(embed=embed)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        self.bot.logger.info(f'Left guild: {guild.name} ({guild.id})')

    def _dm_template(self, template: str, member, guild):
        """DM sablonunu doldurur. Bilinmeyen degiskenler calismaz."""
        repl = {
            'uye': member.display_name,
            'ad': member.display_name,
            'isim': member.display_name,
            'sunucu': guild.name,
            'sayi': str(guild.member_count),
            'id': str(member.id),
        }
        out = template or ''
        for key, val in repl.items():
            out = out.replace('{' + key + '}', val)
        return out

    async def _send_dm(self, member, guild, settings, key: str):
        """
        Uye giris/cikis DM'i gonderir.

        On ayarli:
          dm_giris_acik  -> gonderilsin mi
          dm_giris_mesaj  -> mesaj sablonu
        Kapatiliyorsa hicbir sey gonderilmez.
        """
        if not settings.get(key + '_acik'):
            return False

        template = settings.get(key + '_mesaj') or ''
        if not template.strip():
            return False

        content = self._dm_template(template, member, guild)
        if not content.strip():
            return False

        try:
            await member.send(content)
            return True
        except discord.Forbidden:
            # DM kapali - sessizce gec
            return False
        except Exception as e:
            self.bot.logger.error(f"DM gonderilemedi ({member.id}): {e}")
            return False

    @commands.Cog.listener()
    async def on_member_join(self, member):
        settings = await self.bot.db.get_settings(member.guild.id) or {}

        # DM gonder (asenkron - bekletme)
        asyncio.create_task(self._send_dm(member, member.guild, settings, 'dm_giris'))

        # Uyeye log
        embed = discord.Embed(
            title="📥 Üye Katıldı",
            description=f"{member.mention} ({member.id}) sunucuya katıldı.\n**Hesap Yaşı:** {self._age(member.created_at)}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(member.guild.id, 'member', embed)

        # Hosgeldin mesaji
        if settings.get('welcome_channel_id'):
            channel = self.bot.get_channel(settings['welcome_channel_id'])
            if channel:
                msg = settings.get('welcome_message') or '🎉 {member} sunucuya katıldı!'
                try:
                    await channel.send(msg.format(member=member.mention))
                except discord.Forbidden:
                    pass

        # Otomatik rol (eski sistem)
        if settings.get('autorole_id'):
            role = member.guild.get_role(settings['autorole_id'])
            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    pass

        # Rodeo - giren uyeye roller
        await self._rodeo_uyele(member, settings)

    async def _rodeo_uyele(self, member, settings: dict):
        """Sunucuya giren uyeye rodeo rollerini verir"""
        guild = member.guild
        me = guild.me

        if member.id == me.id or member.bot:
            return

        roller, mod = self._rodeo_ayarlar(settings)

        # Etiket otomatik acik ama rodeo listesinde yoksa (ayarlar bayatlamis)
        # etiketi cozumleyip listeye ekle
        if settings.get('sunucu_etiketi_otomatik'):
            etiket = await self._etiket_rolu_bul(guild, settings)
            if etiket and etiket.id not in roller:
                roller.append(etiket.id)
                await self._rodeo_listeye_ekle(guild.id, etiket.id)
            settings['sunucu_etiketi_role_id'] = etiket.id if etiket else None

        if not roller:
            return

        verilecek = []
        olu_kalan = []

        for rid in roller:
            role = guild.get_role(rid)
            # Rol yoksa (silinmis) listeden de dusur
            if not role:
                continue
            if role in member.roles:
                olu_kalan.append(rid)
                continue
            if role >= me.top_role:
                continue
            verilecek.append(role)
            olu_kalan.append(rid)

        # Listede olu (silinmis) roller varsa temizle - bir daha bakmayalim
        if len(olu_kalan) != len(roller):
            import json as _json
            try:
                await self.bot.db.update_setting(
                    guild.id, 'rodeo_rolleri', _json.dumps(olu_kalan))
            except Exception:
                pass

        if not verilecek:
            return

        if mod == 'rastgele':
            verilecek = [random.choice(verilecek)]

        try:
            await member.add_roles(*verilecek, reason="Rodeo: otomatik giris rolu")
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

    # ==================== SUNUCU ETIKETI ====================
    @app_commands.command(name='sunucu_etiketi', description='Sunucu etiketi (kullanıcı adının yanında görünen renkli rol)')
    @app_commands.describe(
        islem='İşlem',
        ad='Etiket rolünün adı (örn: ٥٠٠٥۰)',
        renk='Etiket rengi (hex, örn: #FF0000)',
        oto='Yeni gelenlere otomatik verilsin mi'
    )
    @app_commands.choices(islem=[
        app_commands.Choice(name='Oluştur / Güncelle - Etiket rolü yap', value='olustur'),
        app_commands.Choice(name='🆕 Otomatik Ver - Yeni gelenlere ver', value='oto_ac'),
        app_commands.Choice(name='🚫 Otomatik Ver - Yeni gelenlere verme', value='oto_kapat'),
        app_commands.Choice(name='⬆️ Yukarı Taşı - En üste koy', value='yukari'),
        app_commands.Choice(name='🗑️ Sil - Etiketi kaldır', value='sil'),
        app_commands.Choice(name='📊 Durum - Etiket bilgisi', value='durum'),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def sunucu_etiketi(self, interaction: discord.Interaction, islem: str,
                             ad: str | None = None,
                             renk: str | None = None,
                             oto: bool | None = None):

        guild = interaction.guild
        me = guild.me
        settings = await self.bot.db.get_settings(guild.id) or {}
        rid = settings.get('sunucu_etiketi_role_id')
        etiket_rolu = guild.get_role(rid) if rid else None

        # ---------- DURUM ----------
        if islem == 'durum':
            await interaction.response.defer(ephemeral=True)

            if not etiket_rolu:
                await interaction.followup.send(
                    "🏷️ **Sunucu etiketi yok.**\n\n"
                    "Oluştur: `/sunucu_etiketi islem:Oluştur ad:5005 renk:#FF0000`",
                    ephemeral=True)
                return

            otomatik = bool(settings.get('sunucu_etiketi_otomatik'))
            uye_sayisi = len(etiket_rolu.members)
            toplam = guild.member_count
            oran = (uye_sayisi / toplam * 100) if toplam else 0

            embed = discord.Embed(
                title="🏷️ Sunucu Etiketi Durumu",
                color=etiket_rolu.color if etiket_rolu.color.value else discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Rol", value=f"{etiket_rolu.mention}\n`{etiket_rolu.id}`", inline=False)
            embed.add_field(name="Renk", value=f"`{etiket_rolu.color}`", inline=True)
            embed.add_field(name="Görünüm", value="Açık (hoist)" if etiket_rolu.hoist else "Kapalı", inline=True)
            embed.add_field(name="Otomatik Ver", value="✅ Açık" if otomatik else "❌ Kapalı", inline=True)
            embed.add_field(
                name="Kapsama",
                value=f"**{uye_sayisi}** / {toplam} üye (**%{oran:.1f}**)",
                inline=False
            )

            # Ornek gorunum
            embed.add_field(
                name="👀 Örnek Görünüm",
                value=f"`{interaction.user.display_name}` → **{etiket_rolu.name}** {interaction.user.display_name}",
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # ---------- SIL ----------
        if islem == 'sil':
            await interaction.response.defer(ephemeral=True)

            if not etiket_rolu:
                await interaction.followup.send("❌ Silinecek etiket yok!", ephemeral=True)
                return

            # Once rolu sil, sonra ayarlardan cikar
            try:
                await etiket_rolu.delete(reason="Sunucu etiketi silindi")
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ Rol silinemedi! Botun rolü etiketten yukarıda olmalı.",
                    ephemeral=True)
                return
            except discord.HTTPException as e:
                await interaction.followup.send(f"❌ Silinemedi: `{e}`", ephemeral=True)
                return

            await self.bot.db.update_setting(guild.id, 'sunucu_etiketi_role_id', None)
            await self.bot.db.update_setting(guild.id, 'sunucu_etiketi_otomatik', 0)

            # Rodeo listesinden de cikar
            await self._rodeo_listeden_cikar(guild.id, etiket_rolu.id)

            await interaction.followup.send(
                f"🗑️ **{etiket_rolu.name}** etiketi silindi.", ephemeral=True)
            return

        # ---------- OTOMATIK AC / KAPAT ----------
        if islem in ('oto_ac', 'oto_kapat'):
            # Kayit bayatlamis olabilir - yeniden cozumle
            if not etiket_rolu:
                etiket_rolu = await self._etiket_rolu_bul(guild, settings)

            if not etiket_rolu:
                await interaction.response.send_message(
                    "❌ Sunucuda etiket rolü bulunamadı!\n\n"
                    "Önce oluştur: `/sunucu_etiketi islem:Oluştur ad:5005`",
                    ephemeral=True)
                return

            if islem == 'oto_ac':
                if etiket_rolu.position >= me.top_role.position:
                    await interaction.response.send_message(
                        "❌ Etiket rolü bot rolünden yukarıda, veremem!\n"
                        "`/sunucu_etiketi islem:Yukarı Taşı` ile yukarı taşı",
                        ephemeral=True)
                    return

                await self.bot.db.update_setting(guild.id, 'sunucu_etiketi_otomatik', 1)
                await self.bot.db.update_setting(guild.id, 'sunucu_etiketi_role_id',
                                                 etiket_rolu.id)
                eklendi = await self._rodeo_listeye_ekle(guild.id, etiket_rolu.id)

                await interaction.response.send_message(
                    f"✅ Otomatik verme **açık**\n\n"
                    f"Etiket: {etiket_rolu.mention}\n"
                    f"Artık sunucuya giren herkese verilecek, "
                    f"çıkınca otomatik geri alınacak."
                    + ("" if eklendi else
                       f"\n⚠️ Rodeo listesine eklenemedi, listede zaten var olabilir."),
                    ephemeral=True)
            else:
                await self.bot.db.update_setting(guild.id, 'sunucu_etiketi_otomatik', 0)
                cikti = await self._rodeo_listeden_cikar(guild.id, etiket_rolu.id)

                await interaction.response.send_message(
                    f"✅ Otomatik verme **kapalı**"
                    + (f"\nRodeo listesinden çıkarıldı." if cikti else ""),
                    ephemeral=True)
            return

        # ---------- YUKARI TASI ----------
        if islem == 'yukari':
            if not etiket_rolu:
                await interaction.response.send_message("❌ Etiket rolü yok!", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            try:
                # Botun rolunun hemen altina kadar yukselt
                await etiket_rolu.edit(position=me.top_role.position - 1,
                                       reason="Etiket en ustte")
                await interaction.followup.send(
                    f"⬆️ **{etiket_rolu.name}** yukarı taşındı.\n\n"
                    f"Artık üyelerin çoğu bu etiketi gösterir.",
                    ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ Taşınamadı! Botun rolünü etiketten yukarı çek.",
                    ephemeral=True)
            except discord.HTTPException as e:
                await interaction.followup.send(f"❌ Taşınamadı: `{e}`", ephemeral=True)
            return

        # ---------- OLUSTUR / GUNCELLE ----------
        await interaction.response.defer(ephemeral=True)

        ad = (ad or "").strip() or "5005"
        if len(ad) > 32:
            ad = ad[:32]

        # Rengi coz
        color = discord.Color.gold()
        if renk:
            try:
                color = discord.Color.from_str(renk.strip())
            except (ValueError, TypeError):
                await interaction.followup.send(
                    f"❌ Renk hatalı: `{renk}`\n"
                    f"Örnek format: `#FF0000` veya `FF0000`", ephemeral=True)
                return

        # Var olan rolü guncelle
        if etiket_rolu:
            try:
                await etiket_rolu.edit(name=ad, color=color, hoist=True,
                                        reason="Sunucu etiketi guncellendi")
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ Düzenlenemedi! Rol bot rolünden yukarıda olabilir.",
                    ephemeral=True)
                return

            await self.bot.db.update_setting(guild.id, 'sunucu_etiketi_role_id',
                                             etiket_rolu.id)

            otomatik = bool(settings.get('sunucu_etiketi_otomatik'))
            await interaction.followup.send(
                f"🏷️ Etiket güncellendi: **{ad}** `{renk or etiket_rolu.color}`\n\n"
                f"Rol: {etiket_rolu.mention}\n"
                f"Üyede etiket var mı: **{len(etiket_rolu.members)}** kişi\n\n"
                + ("✅ Otomatik verme **açık** — yeni gelenlere verilecek."
                   if otomatik else
                   f"⚠️ Otomatik verme kapalı. Açmak için:\n"
                   f"`/sunucu_etiketi islem:Otomatik Ver`"),
                ephemeral=True)
            return

        # Yeni rol olustur
        try:
            yeni = await guild.create_role(
                name=ad, color=color, hoist=True,
                reason="Sunucu etiketi olusturuldu"
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Rol oluşturulamadı! Botta **Rolleri Yönet** izni olmalı.",
                ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Oluşturulamadı: `{e}`", ephemeral=True)
            return

        # Yukari tasi (bot rolunun altina kadar)
        try:
            await yeni.edit(position=me.top_role.position - 1)
        except (discord.Forbidden, discord.HTTPException):
            pass

        await self.bot.db.update_setting(guild.id, 'sunucu_etiketi_role_id', yeni.id)

        # Otomatik verme acik mi?
        otomatik = bool(settings.get('sunucu_etiketi_otomatik'))
        if otomatik:
            await self._rodeo_listeye_ekle(guild.id, yeni.id)

        await interaction.followup.send(
            f"🏷️ **Sunucu etiketi oluşturuldu!**\n\n"
            f"Etiket: {yeni.mention} — `{ad}`\n"
            f"Renk: `{renk or 'varsayılan'}`\n"
            f"Durum: {'✅ Otomatik veriliyor' if otomatik else '❌ Otomatik kapalı'}\n\n"
            f"**Yeni gelenlere otomatik vermek için:**\n"
            f"`/sunucu_etiketi islem:Otomatik Ver`",
            ephemeral=True)

    async def _etiket_rolu_bul(self, guild, settings: dict = None):
        """
        Sunucu etiketi rolu cozumle - KENDINI ONARAN

        Normalde kayitli rol kullanilir. Ama kullanici etiketi Discord'dan
        elle degistirirse (rolu silip yenisini yapti gibi) kayit bayatlar.
        Bu durumda sunucudaki en ustteki hoist rolu bulunur ve yeni rolu
        etiket olarak kaydeder. Boylece sistem bozulmaz.
        """
        me = guild.me

        # 1) Kayitli rol gecerli mi?
        rid = (settings or {}).get('sunucu_etiketi_role_id')
        if rid:
            kayitli = guild.get_role(rid)
            if kayitli and not kayitli.managed:
                return kayitli

        # 2) Bayatti - sunucudaki hoist rollerine bak
        adaylar = [
            r for r in guild.roles
            if r.hoist and not r.is_default() and not r.managed
            and r.id != me.id
        ]

        if adaylar:
            # En yukaridaki = en gorunur etiket
            adaylar.sort(key=lambda r: -r.position)
            bulunan = adaylar[0]

            # Ayarlari tazele
            try:
                await self.bot.db.update_setting(guild.id,
                                                 'sunucu_etiketi_role_id', bulunan.id)
            except Exception:
                pass

            return bulunan

        return None

    async def _etiket_uyele_cikar(self, member, settings: dict):
        """Uye sunucudan ayrilinca etiket rolu geri alinir"""
        if member.id == self.bot.user.id or member.bot:
            return

        rol = await self._etiket_rolu_bul(member.guild, settings)
        if not rol:
            return
        if rol not in member.roles:
            return

        try:
            await member.remove_roles(rol, reason="Sunucu etiketi - ayrilma")
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        """Rol silinmesini logla + etiket ayarlarini onar"""
        embed = discord.Embed(
            title="🗑️ Rol Silindi",
            description=f"Rol silindi: **{role.name}**\n**ID:** `{role.id}`",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await self._send_log(role.guild.id, 'mod', embed)

        if role.is_default() or role.managed:
            return

        settings = await self.bot.db.get_settings(role.guild.id) or {}
        if settings.get('sunucu_etiketi_role_id') != role.id:
            return

        # Kayit silindi - temizle
        await self.bot.db.update_setting(role.guild.id, 'sunucu_etiketi_role_id', None)
        await self._rodeo_listeden_cikar(role.guild.id, role.id)

        # Kalan hoist rolunu etiket olarak benimsemeyi dene
        yeni = await self._etiket_rolu_bul(role.guild, {})
        if yeni and settings.get('sunucu_etiketi_otomatik'):
            await self._rodeo_listeye_ekle(role.guild.id, yeni.id)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        """Rol guncellemesini logla + etiket ayarlarini senkronla"""
        if before.name != after.name:
            embed = discord.Embed(
                title="✏️ Rol Güncellendi",
                description=f"**{before.name}** → **{after.name}**",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            await self._send_log(after.guild.id, 'mod', embed)

        if after.is_default() or after.managed:
            return

        # Etiket rolu elden gecirildi / yeni hoist rolu olustu
        if after.hoist and not before.hoist:
            settings = await self.bot.db.get_settings(after.guild.id) or {}
            kayitli = await self._etiket_rolu_bul(after.guild, settings)

            if not kayitli or after.position > kayitli.position:
                await self.bot.db.update_setting(
                    after.guild.id, 'sunucu_etiketi_role_id', after.id)
                if settings.get('sunucu_etiketi_otomatik'):
                    await self._rodeo_listeye_ekle(after.guild.id, after.id)

    async def _rodeo_listeye_ekle(self, guild_id: int, role_id: int) -> bool:
        """Rodeo listesine rol ekler"""
        import json as _json
        settings = await self.bot.db.get_settings(guild_id) or {}
        roller, mod = self._rodeo_ayarlar(settings)
        if role_id in roller:
            return False
        roller.append(role_id)
        await self.bot.db.update_setting(guild_id, 'rodeo_rolleri',
                                         _json.dumps(roller))
        return True

    async def _rodeo_listeden_cikar(self, guild_id: int, role_id: int) -> bool:
        """Rodeo listesinden rol cikarir"""
        import json as _json
        settings = await self.bot.db.get_settings(guild_id) or {}
        roller, mod = self._rodeo_ayarlar(settings)
        if role_id not in roller:
            return False
        roller.remove(role_id)
        await self.bot.db.update_setting(guild_id, 'rodeo_rolleri',
                                         _json.dumps(roller))
        return True

    # ==================== RODEO (GIRIS ROLLERI) ====================
    def _rodeo_ayarlar(self, settings: dict):
        """Rodeo rollerini ve modu cozer"""
        import json as _json
        roller = []
        raw = settings.get('rodeo_rolleri')
        if raw:
            try:
                roller = [int(x) for x in _json.loads(raw)]
            except (ValueError, TypeError, AttributeError):
                roller = []
        return roller, (settings.get('rodeo_mod') or 'hepsi')

    @app_commands.command(name='rodeo', description='Sunucuya girenlere otomatik rol verir')
    @app_commands.describe(
        islem='İşlem',
        rol='Verilecek rol',
        kisi='Rolü alacak üye'
    )
    @app_commands.choices(islem=[
        app_commands.Choice(name='Rol Ekle - Giriş rolü olarak ekle', value='ekle'),
        app_commands.Choice(name='Rol Kaldır - Listeden çıkar', value='kaldir'),
        app_commands.Choice(name='Mod Seç - Tümü / Rastgele', value='mod'),
        app_commands.Choice(name='Listele - Rodelo rolleri', value='liste'),
        app_commands.Choice(name='Sıfırla - Tümünü kaldır', value='sifirla'),
        app_commands.Choice(name='Üyeye Ver - Şimdi rol ver', value='ver'),
    ])
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rodeo(self, interaction: discord.Interaction, islem: str,
                    rol: discord.Role | None = None,
                    kisi: discord.Member | None = None):

        guild = interaction.guild
        gid = guild.id
        settings = await self.bot.db.get_settings(gid) or {}
        roller, mod = self._rodeo_ayarlar(settings)

        # ---------- LISTELE ----------
        if islem == 'liste':
            if not roller:
                await interaction.response.send_message(
                    "📭 **Rodeo rolü yok.**\n\n"
                    "Eklemek için: `/rodeo islem:Rol Ekle rol:@rol`", ephemeral=True)
                return

            lines = []
            silinmis = 0
            for rid in roller:
                r = guild.get_role(rid)
                if r:
                    lines.append(f"• {r.mention} — üye sayısı: **{len(r.members)}**")
                else:
                    silinmis += 1

            mod_adi = {'hepsi': 'Tüm roller verilir',
                       'rastgele': 'Rastgele 1 rol verilir'}.get(mod, mod)

            embed = discord.Embed(
                title="🎪 Rodeo Ayarları",
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            embed.description = "\n".join(lines[:20]) or "Rol bulunamadı"
            embed.add_field(name="Mod", value=mod_adi, inline=False)
            if silinmis:
                embed.add_field(
                    name="⚠️ Silinmiş Roller",
                    value=f"{silinmis} rol artık yok (listeden temizlenmeli)",
                    inline=False)
            embed.set_footer(text="Değiştirmek için: /rodeo islem:Rol Ekle")

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # ---------- MOD SEC ----------
        if islem == 'mod':
            yeni = 'rastgele' if mod == 'hepsi' else 'hepsi'
            await self.bot.db.update_setting(gid, 'rodeo_mod', yeni)
            await interaction.response.send_message(
                f"✅ Rodeo modu: **{'Rastgele 1 rol' if yeni == 'rastgele' else 'Tüm roller'}**",
                ephemeral=True)
            return

        # ---------- SIFIRLA ----------
        if islem == 'sifirla':
            adet = len(roller)
            await self.bot.db.update_setting(gid, 'rodeo_rolleri', '[]')
            await interaction.response.send_message(
                f"🗑️ **{adet}** rodeo rolü kaldırıldı.", ephemeral=True)
            return

        # ---------- ROL EKLE / KALDIR ----------
        if islem in ('ekle', 'kaldir'):
            if not rol:
                await interaction.response.send_message(
                    "❌ Rol seçmelisin!", ephemeral=True)
                return

            if islem == 'ekle':
                # Bot bu rolu verebilir mi?
                if rol >= guild.me.top_role:
                    await interaction.response.send_message(
                        "❌ Bu rol botun rolünden yukarıda, veremem!\n"
                        "Botun rolünü yükselt.", ephemeral=True)
                    return

                if rol in guild.roles and guild.me.top_role <= rol:
                    pass  # yukarida zaten kontrol edildi

                if rol.id in roller:
                    await interaction.response.send_message(
                        f"ℹ️ {rol.mention} zaten rodeo listesinde!", ephemeral=True)
                    return

                roller.append(rol.id)
                await interaction.response.send_message(
                    f"✅ **{rol.mention}** rodeo listesine eklendi.\n\n"
                    f"Artık sunucuya giren herkese verilecek.", ephemeral=True)
            else:
                if rol.id not in roller:
                    await interaction.response.send_message(
                        f"ℹ️ {rol.mention} rodeo listesinde değil!", ephemeral=True)
                    return
                roller.remove(rol.id)
                await interaction.response.send_message(
                    f"✅ **{rol.mention}** listeden çıkarıldı.", ephemeral=True)

            import json as _json
            await self.bot.db.update_setting(
                gid, 'rodeo_rolleri', _json.dumps(roller))
            return

        # ---------- UYEYE VER ----------
        if not kisi:
            await interaction.response.send_message("❌ Üye seçmelisin!", ephemeral=True)
            return

        if not roller:
            await interaction.response.send_message(
                "📭 **Rodeo rolü yok.** `/rodeo islem:Rol Ekle` ile ekle.",
                ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        verilecek = []
        for rid in roller:
            r = guild.get_role(rid)
            if r and rid not in [x.id for x in kisi.roles]:
                verilecek.append(r)

        if not verilecek:
            await interaction.followup.send(
                f"ℹ️ {kisi.mention} zaten tüm rodeo rollerine sahip.", ephemeral=True)
            return

        if mod == 'rastgele':
            verilecek = [random.choice(verilecek)]

        try:
            await kisi.add_roles(*verilecek, reason="Rodeo otomatik rol")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Rol veremedim! Botun rolü bu rollerden yukarıda olmalı.",
                ephemeral=True)
            return

        await interaction.followup.send(
            f"✅ {kisi.mention} → {' '.join(r.mention for r in verilecek)}",
            ephemeral=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        settings = await self.bot.db.get_settings(member.guild.id) or {}

        # DM gonder
        asyncio.create_task(self._send_dm(member, member.guild, settings, 'dm_cikis'))

        # Sunucu etiketi geri alinsin
        asyncio.create_task(self._etiket_uyele_cikar(member, settings))

        roles = ', '.join(r.mention for r in member.roles[1:]) or 'Yok'

        embed = discord.Embed(
            title="📤 Üye Ayrıldı",
            description=f"{member.mention} ({member.id}) sunucudan ayrıldı.\n**Rolleri:** {roles}",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(member.guild.id, 'member', embed)

        if settings.get('leave_channel_id'):
            channel = self.bot.get_channel(settings['leave_channel_id'])
            if channel:
                msg = settings.get('leave_message') or '👋 {member} sunucudan ayrıldı!'
                try:
                    await channel.send(msg.format(member=member.mention))
                except discord.Forbidden:
                    pass

    # ==================== MESAJ ====================
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return

        content = message.content or "*Boş / embed*"
        if message.embeds:
            content = "*Embed mesajı*"

        embed = discord.Embed(
            title="🗑️ Mesaj Silindi",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Yazar", value=f"{message.author.mention} (`{message.author.id}`)", inline=False)
        embed.add_field(name="Kanal", value=message.channel.mention, inline=False)
        embed.add_field(name="İçerik", value=content[:1024], inline=False)
        try:
            embed.set_thumbnail(url=message.author.display_avatar.url)
        except Exception:
            pass

        await self._send_log(message.guild.id, 'message', embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot:
            return
        if before.content == after.content:
            return

        embed = discord.Embed(
            title="✏️ Mesaj Düzenlendi",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Yazar", value=f"{before.author.mention} (`{before.author.id}`)", inline=False)
        embed.add_field(name="Kanal", value=before.channel.mention, inline=False)
        embed.add_field(name="Önce", value=(before.content or "*Boş*")[:1024], inline=False)
        embed.add_field(name="Sonra", value=(after.content or "*Boş*")[:1024], inline=False)
        try:
            embed.set_thumbnail(url=before.author.display_avatar.url)
        except Exception:
            pass

        await self._send_log(after.guild.id, 'message', embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages:
            return

        channels = {m.channel.mention for m in messages}
        authors = {m.author.mention for m in messages}

        embed = discord.Embed(
            title="🗑️ Toplu Mesaj Silindi",
            description=f"**{len(messages)}** mesaj toplu silindi.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Kanal", value=", ".join(channels), inline=False)
        embed.add_field(name="Yazarlar", value=", ".join(list(authors)[:10]), inline=False)

        await self._send_log(messages[0].guild.id, 'message', embed)

    # ==================== SES ====================
    @commands.Cog.listener()
    async def _find_voice_actor(self, guild, member, kinds):
        """Ses kanalı işlemini kim yaptı? Audit log'dan bulur."""
        action_map = {
            'kick': discord.AuditLogAction.member_disconnect,
            'move': discord.AuditLogAction.member_move,
            'mute': discord.AuditLogAction.member_mute,
            'deafen': discord.AuditLogAction.member_deafen,
            'update': discord.AuditLogAction.member_update,
        }
        actions = [action_map[k] for k in kinds if k in action_map]
        if not actions:
            return None

        now = datetime.now(timezone.utc)
        try:
            async for entry in guild.audit_logs(limit=8):
                if entry.action not in actions:
                    continue
                target = entry.target
                if not isinstance(target, discord.Member) or target.id != member.id:
                    continue
                if (now - entry.created_at).total_seconds() > 15:
                    break
                return entry.user
        except discord.Forbidden:
            return None
        except Exception:
            return None
        return None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        Ses logu - SADECE islem bazli kayitlar.

        Normal kanal giris/cikis kalabaliklastiriyordu ve atildi mi
        yoksa kendisi mi cikti anlasilamiyordu. Artik sadece:
          • Biri tarafindan atildi
          • Biri tarafindan tasiindi
          • Sunucu susturuldu / sagirlastirildi
        kaydedilir ve kimin yaptigi audit log'dan bulunur.
        """
        if member.bot:
            return
        if before.channel == after.channel:
            return

        # K hicbir kanaldan giris - asla "biri yapti" olamaz, sorgu gereksiz
        if before.channel is None:
            return

        # Atildi mi, tasindi mi belirle
        kinds = []
        if after.channel is None:
            kinds.append('kick')       # atildi VEYA kendisi cikti
        else:
            kinds.append('move')       # tasiindi VEYA kendisi tasindi

        # Kullanici kendi ciktiysa/yer degistirdiyse audit log'da kayit
        # olmaz, actor None doner ve log dusmez. Boylece sadece
        # BASKASININ yaptigi islemler kaydedilir.
        await asyncio.sleep(1.2)
        actor = await self._find_voice_actor(member.guild, member, kinds)

        if actor is None:
            # Kimse yapmadi -> kullanici kendi cikmis/tasimistir, loglama
            return

        if actor.bot:
            return

        # Botun kendi hub tasimalari (bot oldugu icin zaten ustte elendi)

        if 'kick' in kinds:
            title = "🔨 Ses Kanalından Atıldı"
            desc = f"{member.mention} → **{before.channel.mention}** kanalından çıkarıldı"
            color = discord.Color.red()
        else:
            title = "➡️ Ses Kanalı Taşındı"
            desc = (f"{member.mention}\n{before.channel.mention} → "
                    f"**{after.channel.mention}**")
            color = discord.Color.orange()

        embed = discord.Embed(title=title, description=desc, color=color,
                              timestamp=datetime.now())
        embed.add_field(name="İşlemi Yapan",
                        value=f"{actor.mention} (`{actor.id}`)", inline=False)
        embed.add_field(name="Üye ID", value=f"`{member.id}`", inline=True)

        if before.channel is not None:
            embed.add_field(name="Kanal", value=before.channel.mention, inline=True)

        try:
            embed.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass

        await self._send_log(member.guild.id, 'voice', embed)

    # ==================== UYE GUNCELLEME ====================
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Takma ad degisikligi -> uye-log
        if before.nick != after.nick:
            embed = discord.Embed(
                title="📝 Takma Ad Değişti",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Üye", value=f"{after.mention} (`{after.id}`)", inline=False)
            embed.add_field(name="Önce", value=before.nick or "*Yok*", inline=True)
            embed.add_field(name="Sonra", value=after.nick or "*Yok*", inline=True)
            await self._send_log(after.guild.id, 'member', embed)

        # Rol degisiklikleri -> rol-log
        added = set(after.roles) - set(before.roles)
        removed = set(before.roles) - set(after.roles)

        if added and self._should_log_roles(after.id, added):
            embed = discord.Embed(
                title="✅ Rol Eklendi",
                description=f"{after.mention} → {', '.join(r.mention for r in added)}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Üye ID", value=f"`{after.id}`", inline=True)
            embed.add_field(name="Eklenen Roller", value=", ".join(r.name for r in added), inline=False)
            await self._send_log(after.guild.id, 'rol', embed)

        if removed and self._should_log_roles(after.id, removed):
            embed = discord.Embed(
                title="❌ Rol Kaldırıldı",
                description=f"{after.mention} ← {', '.join(r.mention for r in removed)}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Üye ID", value=f"`{after.id}`", inline=True)
            embed.add_field(name="Kaldırılan Roller", value=", ".join(r.name for r in removed), inline=False)
            await self._send_log(after.guild.id, 'rol', embed)

    # ==================== KANAL / ROL ====================
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(
            title="📺 Kanal Oluşturuldu",
            description=f"Kanal oluşturuldu: **{channel.mention}**\n**ID:** `{channel.id}`",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await self._send_log(channel.guild.id, 'mod', embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(
            title="🗑️ Kanal Silindi",
            description=f"Kanal silindi: **{channel.name}**\n**ID:** `{channel.id}`",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await self._send_log(channel.guild.id, 'mod', embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if before.name == after.name:
            return
        embed = discord.Embed(
            title="✏️ Kanal Düzenlendi",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Kanal", value=after.mention, inline=False)
        embed.add_field(name="Önce", value=before.name, inline=True)
        embed.add_field(name="Sonra", value=after.name, inline=True)
        await self._send_log(after.guild.id, 'mod', embed)

    # ==================== MODERASYON LOGLARI ====================
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = discord.Embed(
            title="🔨 Üye Yasaklandı",
            description=f"{user.mention} (`{user.id}`) yasaklandı.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await self._send_log(guild.id, 'mod', embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        embed = discord.Embed(
            title="🔓 Yasağa Kaldırıldı",
            description=f"{user.mention} (`{user.id}`) yasaktan kaldırıldı.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await self._send_log(guild.id, 'mod', embed)

    # ==================== YARDIMCI ====================
    def _age(self, dt):
        if not dt:
            return "Bilinmiyor"
        delta = datetime.now() - dt.replace(tzinfo=None)
        days = delta.days
        if days >= 365:
            return f"{days // 365} yıl {days % 365} gün"
        if days >= 30:
            return f"{days // 30} ay {days % 30} gün"
        return f"{days} gün"

    # ==================== AYAR KOMUTLARI ====================
    @app_commands.command(name='hosgeldin_kanal', description='Hoş geldin mesajı kanalı')
    @app_commands.describe(channel='Kanal')
    @app_commands.checks.has_permissions(administrator=True)
    async def hosgeldin_kanal(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        await self.bot.db.update_setting(interaction.guild.id, 'welcome_channel_id', channel.id if channel else None)
        msg = f"✅ Hoş geldin kanalı: **{channel.mention}**" if channel else "✅ Hoş geldin kanalı kapatıldı"
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name='gorusur_kanal', description='Görüşürüz mesajı kanalı')
    @app_commands.describe(channel='Kanal')
    @app_commands.checks.has_permissions(administrator=True)
    async def gorusur_kanal(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        await self.bot.db.update_setting(interaction.guild.id, 'leave_channel_id', channel.id if channel else None)
        msg = f"✅ Görüşürüz kanalı: **{channel.mention}**" if channel else "✅ Görüşürüz kanalı kapatıldı"
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name='log_test', description='Tüm log kanallarını test et')
    @app_commands.checks.has_permissions(administrator=True)
    async def log_test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        settings = await self.bot.db.get_settings(interaction.guild.id) or {}
        types = ['guard', 'mod', 'message', 'voice', 'member',
                 'silah_katlanan', 'silah_kaybedilen', 'farm']

        report = []
        for t in types:
            cid = settings.get(f'{t}_log_channel_id')
            channel = self.bot.get_channel(cid) if cid else None
            if channel:
                try:
                    await channel.send(f"✅ **Log testi** — `{t}` kanalı çalışıyor!", delete_after=10)
                    report.append(f"✅ `{t}` → {channel.mention}")
                except (discord.Forbidden, discord.NotFound) as e:
                    report.append(f"❌ `{t}` → {channel.mention} (yetki hatası)")
            else:
                report.append(f"⚠️ `{t}` → ayarlanmamış")

        legacy = settings.get('log_channel_id')
        if legacy:
            ch = self.bot.get_channel(legacy)
            report.append(f"ℹ️ Genel log kanalı: {ch.mention if ch else 'bulunamadı'}")

        await interaction.followup.send("**Log Kanalı Durumu**\n" + "\n".join(report), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Events(bot))