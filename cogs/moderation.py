import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==================== BAN ====================
    @app_commands.command(name='yasakla', description='Bir üyeyi sunucudan yasakla')
    @app_commands.describe(
        member='Yasaklanacak üye',
        reason='Yasaklama nedeni',
        delete_days='Silinecek mesaj gün sayısı (0-7)'
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Belirtilmedi", delete_days: int = 0):
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ Bu üyeyi yasaklayamazsın! (Yetki sırası düşük)", ephemeral=True)
            return

        try:
            await member.ban(reason=f"{interaction.user}: {reason}", delete_message_days=delete_days)
            embed = discord.Embed(
                title="🔨 Üye Yasaklandı",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Üye", value=f"{member.mention} ({member.id})", inline=False)
            embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="Neden", value=reason, inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Bu üyeyi yasaklayamıyorum! Yetkilerimi kontrol et.", ephemeral=True)

    # ==================== KICK ====================
    @app_commands.command(name='at', description='Bir üyeyi sunucudan at')
    @app_commands.describe(member='Atılacak üye', reason='Atılma nedeni')
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Belirtilmedi"):
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ Bu üyeyi atamazsın! (Yetki sırası düşük)", ephemeral=True)
            return

        try:
            await member.kick(reason=f"{interaction.user}: {reason}")
            embed = discord.Embed(
                title="👢 Üye Atıldı",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Üye", value=f"{member.mention} ({member.id})", inline=False)
            embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="Neden", value=reason, inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Bu üyeyi atamıyorum! Yetkilerimi kontrol et.", ephemeral=True)

    # ==================== MUTE ====================
    @app_commands.command(name='sustur', description='Bir üyeyi sustur')
    @app_commands.describe(
        member='Susturulacak üye',
        duration='Süre (örn: 10m, 1h, 1d)',
        reason='Susturma nedeni'
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "Belirtilmedi"):
        # Parse duration
        duration_map = {'m': 60, 'h': 3600, 'd': 86400}
        try:
            unit = duration[-1].lower()
            value = int(duration[:-1])
            seconds = value * duration_map[unit]
        except:
            await interaction.response.send_message("❌ Geçersiz süre formatı! Örnek: 10m, 1h, 1d", ephemeral=True)
            return

        # Get or create mute role
        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
        if not mute_role:
            try:
                mute_role = await interaction.guild.create_role(
                    name="Muted",
                    color=discord.Color.dark_gray(),
                    reason="Mute sistemi için oluşturuldu"
                )
                for channel in interaction.guild.channels:
                    await channel.set_permissions(mute_role, send_messages=False, speak=False)
            except discord.Forbidden:
                await interaction.response.send_message("❌ Mute rolü oluşturamadım! Yetkilerimi kontrol et.", ephemeral=True)
                return

        try:
            await member.add_roles(mute_role, reason=f"{interaction.user}: {reason}")
            embed = discord.Embed(
                title="🔇 Üye Susturuldu",
                color=discord.Color.yellow(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Üye", value=f"{member.mention} ({member.id})", inline=False)
            embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="Süre", value=duration, inline=False)
            embed.add_field(name="Neden", value=reason, inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            await interaction.response.send_message(embed=embed)

            # Auto unmute
            await asyncio.sleep(seconds)
            if mute_role in member.roles:
                await member.remove_roles(mute_role)
                await interaction.channel.send(f"🔊 {member.mention} susturması kaldırıldı!")
        except discord.Forbidden:
            await interaction.response.send_message("❌ Bu üyeyi susturamıyorum! Yetkilerimi kontrol et.", ephemeral=True)

    # ==================== UNMUTE ====================
    @app_commands.command(name='susturma_kaldir', description='Bir üyenin susturmasını kaldır')
    @app_commands.describe(member='Susturması kaldırılacak üye')
    @app_commands.checks.has_permissions(manage_roles=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
        if not mute_role or mute_role not in member.roles:
            await interaction.response.send_message("❌ Bu üye zaten susturulmamış!", ephemeral=True)
            return

        await member.remove_roles(mute_role)
        embed = discord.Embed(
            title="🔊 Susturma Kaldırıldı",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Üye", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    # ==================== SEVIYELI UYARI SISTEMI ====================
    MAX_UYARI_SEVIYESI = 10

    async def _uyari_rolleri(self, guild_id: int) -> dict:
        """{1: role_id, 2: role_id, ...}"""
        import json as _json
        s = await self.bot.db.get_settings(guild_id) or {}
        raw = s.get('uyari_rolleri')
        if not raw:
            return {}
        try:
            return {int(k): int(v) for k, v in _json.loads(raw).items()}
        except (ValueError, TypeError, AttributeError):
            return {}

    async def _uyari_rolleri_kaydet(self, guild_id: int, roller: dict):
        import json as _json
        await self.bot.db.update_setting(
            guild_id, 'uyari_rolleri',
            _json.dumps({str(k): v for k, v in roller.items()}))

    @app_commands.command(name='uyari', description='Seviyeli uyarı sistemi (1x, 2x, 3x...)')
    @app_commands.describe(
        islem='İşlem',
        uye='İşlem yapılacak üye',
        seviye='Uyarı seviyesi (1-10)',
        rol='Uyarı seviyesine atanacak rol',
        neden='Uyarı nedeni'
    )
    @app_commands.choices(islem=[
        app_commands.Choice(name='1x/2x/3x Uyarı Ver', value='ver'),
        app_commands.Choice(name='Geçmişi Gör', value='gecmis'),
        app_commands.Choice(name='Uyarıyı Kaldır', value='al'),
        app_commands.Choice(name='Tüm Uyarıları Temizle', value='temizle'),
        app_commands.Choice(name='Uyarı Rolü Ayarla', value='rol'),
        app_commands.Choice(name='Rol Listesi', value='liste'),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def uyari(self, interaction: discord.Interaction, islem: str,
                    uye: discord.Member | None = None,
                    seviye: int | None = None,
                    rol: discord.Role | None = None,
                    neden: str | None = None):

        guild_id = interaction.guild.id
        roller = await self._uyari_rolleri(guild_id)
        MAX = self.MAX_UYARI_SEVIYESI

        # Gecmis gecmise sadece uye gerekir, roller gerekmez
        if islem == 'gecmis' and not uye:
            await interaction.response.send_message("❌ Üye seçmelisin!", ephemeral=True)
            return

        # ---------- ROL LISTESI ----------
        if islem == 'liste':
            if not roller:
                await interaction.response.send_message(
                    "⚠️ **Hiç uyarı rolü ayarlanmamış!**\n\n"
                    f"Ayarlamak için: `/uyari islem:Rol Ayarla seviye:1 rol:@rol`",
                    ephemeral=True)
                return

            embed = discord.Embed(
                title="⚠️ Uyarı Rolleri",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            lines = []
            for lvl in range(1, MAX + 1):
                rid = roller.get(lvl)
                if rid:
                    r = interaction.guild.get_role(rid)
                    lines.append(f"{lvl}x → {r.mention if r else '⚠️ Silinmiş rol'}")
                else:
                    lines.append(f"{lvl}x → *Ayar yok*")
            embed.add_field(
                value="\n".join(lines[:10]),
                name="Seviye → Rol",
                inline=False
            )
            if len(lines) > 10:
                embed.add_field(
                    value="\n".join(lines[10:]),
                    name="Seviye → Rol (devam)",
                    inline=False
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # ---------- ROL AYARLA ----------
        if islem == 'rol':
            if not seviye or seviye < 1 or seviye > MAX:
                await interaction.response.send_message(
                    f"❌ Seviye **1-{MAX}** arasında olmalı!", ephemeral=True)
                return
            if not rol:
                await interaction.response.send_message(
                    "❌ Rol seçmelisin!", ephemeral=True)
                return

            # Rol sunucuda var mi?
            gercek = interaction.guild.get_role(rol.id)
            if not gercek:
                await interaction.response.send_message(
                    "❌ Bu rol artık sunucuda yok!", ephemeral=True)
                return

            roller[seviye] = rol.id
            await self._uyari_rolleri_kaydet(guild_id, roller)

            await interaction.response.send_message(
                f"✅ **{seviye}x uyarı** → {gercek.mention}\n"
                f"`/uyari islem:ver uye:@kişi seviye:{seviye}` ile uygulanır.",
                ephemeral=True)
            return

        # Bundan sonrasi (ver / al / temizle) uye gerektirir
        if not uye:
            await interaction.response.send_message("❌ Üye seçmelisin!", ephemeral=True)
            return

        # ---------- GECMISI GOR ----------
        if islem == 'gecmis':
            await interaction.response.defer(ephemeral=True)
            gecmis = await self.bot.db.get_warnings(uye.id, guild_id)

            if not gecmis:
                await interaction.followup.send(
                    f"✅ {uye.mention} hiç uyarı almamış!", ephemeral=True)
                return

            # Hangi rol verilmis?
            aktif_rol = None
            for lvl, rid in sorted(roller.items(), reverse=True):
                r = interaction.guild.get_role(rid)
                if r and r in uye.roles:
                    aktif_rol = f"{lvl}x — {r.mention}"
                    break

            embed = discord.Embed(
                title=f"⚠️ {uye.display_name} Uyarı Geçmişi ({len(gecmis)})",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            if aktif_rol:
                embed.add_field(name="Aktif Seviye", value=aktif_rol, inline=False)

            for i, w in enumerate(gecmis[-12:][::-1], 1):
                mod = interaction.guild.get_member(w[3])
                mod_ment = mod.mention if mod else "Bilinmiyor"
                embed.add_field(
                    name=f"#{len(gecmis) - i + 1} • {w[5][:10] if w[5] else '?'}",
                    value=f"**Neden:** {w[4]}\n**Yetkili:** {mod_ment}",
                    inline=False
                )

            if len(gecmis) > 12:
                embed.set_footer(text=f"İlk {len(gecmis) - 12} kayıt gizli")

            try:
                embed.set_thumbnail(url=uye.display_avatar.url)
            except Exception:
                pass

            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # ---------- UYARI KALDIR / TEMIZLE ----------
        if islem in ('al', 'temizle'):
            await interaction.response.defer(ephemeral=True)

            temizle = islem == 'temizle'
            kaldirilan = []

            for lvl, rid in list(roller.items()):
                r = interaction.guild.get_role(rid)
                if r and r in uye.roles:
                    try:
                        await uye.remove_roles(r, reason="Uyarı sistemi")
                        kaldirilan.append(f"{lvl}x")
                    except discord.Forbidden:
                        pass

            if temizle:
                await self.bot.db.clear_warnings(uye.id, guild_id)

            await interaction.followup.send(
                f"✅ {uye.mention} için uyarılar temizlendi."
                + (f" Silinen seviyeler: {', '.join(kaldirilan)}" if kaldirilan else "")
                + ("\nGeçmiş kayıtlar da silindi." if temizle else ""),
                ephemeral=True)
            return

        # ---------- UYARI VER ----------
        if not seviye or seviye < 1 or seviye > MAX:
            await interaction.response.send_message(
                f"❌ Seviye **1-{MAX}** arasında olmalı!", ephemeral=True)
            return

        rol_id = roller.get(seviye)
        if not rol_id:
            await interaction.response.send_message(
                f"❌ **{seviye}x** uyarı rolü ayarlanmamış!\n\n"
                f"Ayarlamak için: `/uyari islem:Rol Ayarla seviye:{seviye} rol:@rol`",
                ephemeral=True)
            return

        uyari_rolu = interaction.guild.get_role(rol_id)
        if not uyari_rolu:
            await interaction.response.send_message(
                f"❌ **{seviye}x** rolü sunucuda bulunamadı (silinmiş olabilir)!",
                ephemeral=True)
            return

        # Yetki sirasi kontrolu
        if uyari_rolu >= interaction.user.top_role:
            await interaction.response.send_message(
                "❌ Bu rol senin rolünden yukarıda, veremem!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        neden = neden or "Sebep belirtilmedi"
        await self.bot.db.add_warning(uye.id, guild_id, interaction.user.id,
                                     f"[{seviye}x] {neden}")
        tum_warnings = await self.bot.db.get_warnings(uye.id, guild_id)

        # Rolu ekle, alt seviyeleri kaldir
        eklenen = []
        try:
            await uye.add_roles(uyari_rolu, reason=f"{seviye}x uyarı")
            eklenen.append(f"{seviye}x")

            for lvl, rid in roller.items():
                if lvl >= seviye:
                    continue
                alt = interaction.guild.get_role(rid)
                if alt and alt in uye.roles:
                    await uye.remove_roles(alt, reason="Seviye güncellendi")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Rol veremedim! Bot rolü uyarı rolünden yukarıda olmalı.",
                ephemeral=True)
            return

        embed = discord.Embed(
            title=f"⚠️ {seviye}x Uyarı Verildi",
            description=f"**{seviye}x** uyarı rolü verildi: {uyari_rolu.mention}",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Üye", value=f"{uye.mention} (`{uye.id}`)", inline=False)
        embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
        embed.add_field(name="Neden", value=neden, inline=False)
        embed.add_field(name="Toplam Uyarı", value=f"**{len(tum_warnings)}** kayıt", inline=False)
        try:
            embed.set_thumbnail(url=uye.display_avatar.url)
        except Exception:
            pass

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ==================== CLEAR ====================
    @app_commands.command(name='temizle', description='Kanaldan mesaj sil (en fazla 500)')
    @app_commands.describe(
        amount='Silinecek mesaj sayısı (1-500)',
        channel='Kanal (boş bırakılırsa bulunduğun kanal)',
        member='Sadece bu üyenin mesajlarını sil',
        contains='Sadece içinde bu kelime geçen mesajları sil'
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int,
                    channel: discord.TextChannel | None = None,
                    member: discord.Member | None = None,
                    contains: str | None = None):
        if amount < 1 or amount > 500:
            await interaction.response.send_message(
                "❌ **1-500** arasında bir sayı gir!", ephemeral=True)
            return

        target = channel or interaction.channel
        await interaction.response.defer(ephemeral=True)

        try:
            if member is None and contains is None:
                # Normal toplu silme (Discord 100'erli gruplar halinde yapar)
                deleted = await target.purge(limit=amount)
                await interaction.followup.send(
                    f"🗑️ **{len(deleted)}** mesaj silindi.", ephemeral=True)

            else:
                # Filtreli silme - 2 haftadan eski mesajlar API ile silinmez
                cutoff = discord.utils.utcnow() - discord.timedelta(days=14)
                deleted_count = 0
                to_delete = []

                # Filtre varsa eslesme az olacagindan daha fazla mesaj tara
                scan_limit = min(5000, max(amount * 5, 500))

                async for msg in target.history(limit=scan_limit, oldest_first=False):
                    if msg.created_at < cutoff:
                        break
                    if member is not None and msg.author.id != member.id:
                        continue
                    if contains is not None and contains.lower() not in msg.content.lower():
                        continue
                    to_delete.append(msg)
                    if len(to_delete) >= amount:
                        break

                if not to_delete:
                    await interaction.followup.send(
                        "❌ Silinecek mesaj bulunamadı!\n"
                        "*Not: 14 günden eski mesajlar Discord tarafından silinemez.*",
                        ephemeral=True)
                    return

                # Toplu sil - Discord tek istekte en fazla 100 mesaj kabul eder
                for i in range(0, len(to_delete), 100):
                    batch = to_delete[i:i + 100]
                    try:
                        await target.delete_messages(batch)
                        deleted_count += len(batch)
                        # Buyuk silimlerde rate limit'e takilmayalim
                        if i + 100 < len(to_delete):
                            await asyncio.sleep(1.0)
                    except discord.HTTPException:
                        # Yetki/yas sorunu varsa tek tek dene
                        for msg in batch:
                            try:
                                await msg.delete()
                                deleted_count += 1
                                await asyncio.sleep(0.4)
                            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                                pass

                await interaction.followup.send(
                    f"🗑️ **{deleted_count}** mesaj silindi.", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Bu kanalda mesaj silme yetkim yok!", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Silme hatası: {e}", ephemeral=True)

    # ==================== SLOWMODE ====================
    @app_commands.command(name='yavas_mod', description='Kanalı yavaş moda al')
    @app_commands.describe(seconds='Yavaş mod süresi (saniye)', reason='Neden')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int, reason: str = "Belirtilmedi"):
        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message("❌ 0-21600 arasında bir sayı gir!", ephemeral=True)
            return

        await interaction.channel.edit(slowmode_delay=seconds)
        embed = discord.Embed(
            title="🐌 Yavaş Mod Aktif",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Kanal", value=interaction.channel.mention, inline=False)
        embed.add_field(name="Süre", value=f"{seconds} saniye", inline=False)
        embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
        embed.add_field(name="Neden", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    # ==================== LOCK ====================
    @app_commands.command(name='kilitle', description='Kanalı kilitle')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        embed = discord.Embed(
            title="🔒 Kanal Kilitlendi",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Kanal", value=interaction.channel.mention, inline=False)
        embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
        await interaction.response.send_message(embed=embed)

    # ==================== UNLOCK ====================
    @app_commands.command(name='kilit_ac', description='Kanalın kilidini aç')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
        embed = discord.Embed(
            title="🔓 Kanal Açıldı",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Kanal", value=interaction.channel.mention, inline=False)
        embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
        await interaction.response.send_message(embed=embed)

    # ==================== NICKNAME ====================
    @app_commands.command(name='takma_ad', description='Bir üyenin takma adını değiştir')
    @app_commands.describe(member='Takma adı değiştirilecek üye', nickname='Yeni takma ad')
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, member: discord.Member, nickname: str):
        try:
            await member.edit(nick=nickname)
            embed = discord.Embed(
                title="📝 Takma Ad Değiştirildi",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Üye", value=f"{member.mention}", inline=False)
            embed.add_field(name="Yeni Takma Ad", value=nickname, inline=False)
            embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Bu üyenin takma adını değiştiremem! Yetkilerimi kontrol et.", ephemeral=True)

    # ==================== ROLE ADD ====================
    @app_commands.command(name='rol_ekle', description='Bir üyeye rol ekle')
    @app_commands.describe(member='Rol eklenecek üye', role='Eklenecek rol')
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role_add(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if role >= interaction.user.top_role:
            await interaction.response.send_message("❌ Bu rolü ekleyemezsin! (Yetki sırası düşük)", ephemeral=True)
            return

        await member.add_roles(role)
        embed = discord.Embed(
            title="✅ Rol Eklendi",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Üye", value=f"{member.mention}", inline=False)
        embed.add_field(name="Rol", value=f"{role.mention}", inline=False)
        embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
        await interaction.response.send_message(embed=embed)

    # ==================== ROLE REMOVE ====================
    @app_commands.command(name='rol_kaldir', description='Bir üyeden rol kaldır')
    @app_commands.describe(member='Rol kaldırılacak üye', role='Kaldırılacak rol')
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role_remove(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if role >= interaction.user.top_role:
            await interaction.response.send_message("❌ Bu rolü kaldıramazsın! (Yetki sırası düşük)", ephemeral=True)
            return

        await member.remove_roles(role)
        embed = discord.Embed(
            title="✅ Rol Kaldırıldı",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Üye", value=f"{member.mention}", inline=False)
        embed.add_field(name="Rol", value=f"{role.mention}", inline=False)
        embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
