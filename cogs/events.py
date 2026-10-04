import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import asyncio
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
            description="Sunucunuza eklendim! `/help` yazarak komutları görebilirsin.",
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

    @commands.Cog.listener()
    async def on_member_join(self, member):
        settings = await self.bot.db.get_settings(member.guild.id) or {}

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

        # Otomatik rol
        if settings.get('autorole_id'):
            role = member.guild.get_role(settings['autorole_id'])
            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        settings = await self.bot.db.get_settings(member.guild.id) or {}

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

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        embed = discord.Embed(
            title="✅ Rol Oluşturuldu",
            description=f"Rol oluşturuldu: {role.mention}\n**ID:** `{role.id}`",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await self._send_log(role.guild.id, 'mod', embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        embed = discord.Embed(
            title="🗑️ Rol Silindi",
            description=f"Rol silindi: **{role.name}**\n**ID:** `{role.id}`",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await self._send_log(role.guild.id, 'mod', embed)

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