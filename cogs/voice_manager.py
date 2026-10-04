import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import asyncio
import os
import json
import wave
import tempfile


def _ensure_silence_file() -> str:
    """
    Sessiz ses dosyasi olusturur (5 saniye, 48kHz stereo 16-bit).

    Bot kanala baglandiginda konusuyor gibi gorunsun diye gerekli.
    Dosya bir kez olusturulup tekrar kullanilir, internet gerektirmez.
    """
    path = os.path.join(tempfile.gettempdir(), 'bot_silence.wav')
    if os.path.exists(path):
        return path

    try:
        with wave.open(path, 'wb') as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(48000)
            # 5 saniye sessizlik (~960 KB)
            w.writeframes(b'\x00' * (48000 * 2 * 2 * 5))
    except Exception:
        return None
    return path


class VoiceManager(commands.Cog):
    """
    Ses kanalı sistemi:
      • Botu seçtiğin kanala sessiz (kulaklığı kapalı) ekleme
      • Kişisel kanal / hub sistemi
      • Ses kanalı koruması - sadece yetkili kişiler taşıyabilir/çıkarabilir
    """

    PROTECT_FILE = 'voice_protect.json'

    def __init__(self, bot):
        self.bot = bot
        self.hub_channels = []
        self.temp_channels = {}
        self.silence_file = None
        self.protect = self._load_protect()

    # ==================== KORUMA AYARLARI ====================
    def _load_protect(self) -> dict:
        try:
            with open(self.PROTECT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save_protect(self):
        try:
            with open(self.PROTECT_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.protect, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"[ses] Koruma ayari kaydedilemedi: {e}", flush=True)

    def _cfg(self, guild_id: int) -> dict:
        key = str(guild_id)
        return self.protect.get(key, {'channels': [], 'allowed': [], 'enabled': True})

    def _set_cfg(self, guild_id: int, cfg: dict):
        self.protect[str(guild_id)] = cfg

    def _is_allowed(self, cfg: dict, user_id: int) -> bool:
        """Bu kisi korunan kanallarda hareket edebilir mi?"""
        if user_id == self.bot.owner_id:
            return True
        return user_id in [int(x) for x in cfg.get('allowed', [])]

    # ==================== KORUMA LISTENER ====================
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        await self._voice_protect_check(member, before, after)

        if member.bot or member.id == self.bot.user.id:
            return

        # Hub kanala girdi -> kisisel kanal ac
        if after.channel and after.channel.id in self.hub_channels:
            vc = member.guild.get_channel(after.channel.id)
            if not vc:
                return

            # Bot da kanala girsin
            for c in self.bot.voice_clients:
                if c.guild.id == member.guild.id and c.channel and c.channel.id != vc.id:
                    try:
                        await c.move_to(vc)
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                    break

            temp = await self._create_temp_channel(member, vc)
            if temp:
                try:
                    await member.move_to(temp)
                except discord.Forbidden:
                    pass

        # Kisisel kanaldan ayrildi -> bos ise sil
        if before.channel and before.channel.id in self.temp_channels:
            data = self.temp_channels.get(before.channel.id)
            if data and data['owner_id'] == member.id:
                asyncio.create_task(self._delete_after_empty(before.channel))

    async def _find_actor(self, guild, member, kinds):
        """Kim taşıdı/çıkardı? Audit log'dan bulur."""
        action_map = {
            'kick': discord.AuditLogAction.member_disconnect,
            'move': discord.AuditLogAction.member_move,
            'mute': discord.AuditLogAction.member_mute,
            'deafen': discord.AuditLogAction.member_deafen,
        }
        actions = [action_map[k] for k in kinds if k in action_map]
        if not actions:
            return None

        now = datetime.now(timezone.utc)
        try:
            async for entry in guild.audit_logs(limit=6):
                if entry.action not in actions:
                    continue
                target = entry.target
                if not isinstance(target, discord.Member) or target.id != member.id:
                    continue
                if (now - entry.created_at).total_seconds() > 12:
                    break
                return entry.user
        except discord.Forbidden:
            return None
        except Exception:
            return None
        return None

    async def _voice_protect_check(self, member, before, after):
        """Korunan kanalda yetkisiz hareketi geri al"""
        if member.bot:
            return

        kinds = []
        if before.channel and not after.channel:
            kinds.append('kick')
        elif before.channel and after.channel and before.channel.id != after.channel.id:
            kinds.append('move')
        if not before.self_deaf and after.self_deaf:
            kinds.append('deafen')
        if not before.self_mute and after.self_mute:
            kinds.append('mute')

        if not kinds:
            return

        cfg = self._cfg(member.guild.id)
        if not cfg.get('enabled', True):
            return

        protected = {int(x) for x in cfg.get('channels', [])}
        if not protected:
            return

        # Kanalin biri korunuyor mu?
        touched = {c.id for c in (before.channel, after.channel) if c}
        if not (touched & protected):
            return

        # Botun kendi islemleri (hub tasima) muhtemel - audit log'da
        # bot gorunur, o da her zaman serbest.
        await asyncio.sleep(1.2)
        actor = await self._find_actor(member.guild, member, kinds)
        if actor is None:
            return

        if self._is_allowed(cfg, actor.id):
            return

        # --- Geri al ---
        reverted = []
        try:
            if ('kick' in kinds or 'move' in kinds) and before.channel:
                if before.channel.type == discord.ChannelType.stage_voice:
                    await member.move_to(before.channel)
                else:
                    await member.move_to(before.channel)
                reverted.append('taşındı')
            if 'deafen' in kinds:
                await member.edit(self_deaf=False)
                reverted.append('sağırlaştırma kaldırıldı')
            if 'mute' in kinds:
                await member.edit(self_mute=False)
                reverted.append('susturma kaldırıldı')
        except discord.Forbidden:
            return
        except discord.HTTPException:
            return

        if not reverted:
            return

        try:
            await member.guild.owner.send(
                f"🛡️ **Ses Koruması**\n"
                f"**Kanal:** {before.channel.mention if before.channel else '?'}\n"
                f"**Üye:** {member.mention}\n"
                f"**Yapan:** {actor.mention} (`{actor.id}`)\n"
                f"**Geri alınan:** {', '.join(reverted)}\n"
                f"↩️ Başarıyla engellendi."
            )
        except (discord.Forbidden, AttributeError):
            pass

    async def _delete_after_empty(self, channel, delay: int = 300):
        """Kanal bosalınca gecikmeli sil"""
        await asyncio.sleep(delay)
        try:
            if channel.id in self.hub_channels:
                return
            if len(channel.members) > 0:
                return
            await channel.delete(reason="Bos kanal otomatik silindi")
            self.temp_channels.pop(channel.id, None)
        except (discord.NotFound, discord.Forbidden):
            self.temp_channels.pop(channel.id, None)
        except Exception:
            pass

    async def _create_temp_channel(self, member, base_channel, overwrites_extra=None):
        """Uye icin kişisel kanal olustur"""
        guild = member.guild
        name = f"🔊 {member.display_name}"

        existing = discord.utils.get(guild.voice_channels, name=name)
        if existing:
            return existing

        perms = discord.PermissionOverwrite(
            connect=True, manage_channels=True, move_members=True,
            mute_members=True, deafen_members=True
        )
        if overwrites_extra:
            for k, v in overwrites_extra.items():
                perms.update(**{k: v})

        overwrites = {
            member: perms,
            guild.default_role: discord.PermissionOverwrite(connect=False),
            guild.me: discord.PermissionOverwrite(connect=True, manage_channels=True)
        }

        category = base_channel.category if base_channel else None

        try:
            if category:
                channel = await guild.create_voice_channel(
                    name, category=category, overwrites=overwrites,
                    reason=f"{member.display_name} icin ozel kanal")
            else:
                channel = await guild.create_voice_channel(
                    name, overwrites=overwrites,
                    reason=f"{member.display_name} icin ozel kanal")
        except discord.Forbidden:
            return None

        self.temp_channels[channel.id] = {
            'owner_id': member.id,
            'created_at': datetime.now()
        }

        asyncio.create_task(self._delete_after_empty(channel))
        return channel

    def _vc(self, guild):
        """Botun o sunucudaki ses istemcisi (yoksa None)"""
        for c in self.bot.voice_clients:
            if c.guild.id == guild.id:
                return c
        return None

    async def _handle_status(self, interaction):
        """Botun ses durumu"""
        await interaction.response.defer(ephemeral=True)
        client = self._vc(interaction.guild)
        cfg = self._cfg(interaction.guild.id)

        if not client or not client.channel:
            await interaction.followup.send(
                "⚪ Bot **ses kanalında değil**.\n"
                "Bağlamak için: `/ses_ekle`", ephemeral=True)
            return

        ch = client.channel
        korunan = [c for c in cfg.get('channels', []) if int(c) != ch.id]

        lines = [
            f"🟢 Bot **{ch.mention}** kanalında",
            f"👥 Kanalda **{len(ch.members)}** kişi",
            f"🔇 Mikrofon: {'kapalı' if ch.members and self.bot.user in ch.members and ch.members[self.bot.user.id].self_mute else 'açık'}",
        ]
        if korunan:
            lines.append(f"🛡️ Korunan kanal sayısı: **{len(korunan)}**")

        await interaction.followup.send("\n".join(lines), ephemeral=True)

    async def _handle_protect(self, interaction, islem, kanal, uye):
        """Ses kanalı koruma ayarları"""
        cfg = self._cfg(interaction.guild.id)
        cfg.setdefault('channels', [])
        cfg.setdefault('allowed', [])

        if islem == 'koru':
            if not kanal:
                await interaction.response.send_message(
                    "❌ Korunacak ses kanalını seçmelisin!", ephemeral=True)
                return

            chans = [int(x) for x in cfg['channels']]
            if kanal.id in chans:
                await interaction.response.send_message(
                    f"🛡️ **{kanal.mention}** zaten korumada.", ephemeral=True)
                return

            chans.append(kanal.id)
            cfg['channels'] = chans
            self._set_cfg(interaction.guild.id, cfg)
            self._save_protect()

            # Botun yetkisi var mi?
            perms = interaction.guild.me.guild_permissions
            uyari = ""
            if not perms.move_members:
                uyari = "\n\n⚠️ Botta **Üyeleri Taşı** izni yok, geri alma çalışmayabilir."

            await interaction.response.send_message(
                f"🛡️ **{kanal.mention}** korumaya alındı.\n\n"
                f"Artık sadece **sen** ve izinli kişiler taşıyabilir/çıkarabilir/susturabilir.\n"
                f"Birisi yaparsa **otomatik geri alınır** ve sana bildirim gider.\n\n"
                f"➕ Başkasına izin vermek: `/ses serbest`{uyari}", ephemeral=True)

        elif islem == 'koruma_kaldir':
            count = len(cfg['channels'])
            cfg['channels'] = []
            self._set_cfg(interaction.guild.id, cfg)
            self._save_protect()
            await interaction.response.send_message(
                f"✅ Koruma kaldırıldı ({count} kanal).", ephemeral=True)

        elif islem == 'serbest':
            if not uye:
                await interaction.response.send_message(
                    "❌ İzin verilecek kişiyi seçmelisin!", ephemeral=True)
                return

            allowed = [int(x) for x in cfg['allowed']]
            if uye.id not in allowed:
                allowed.append(uye.id)
            cfg['allowed'] = allowed
            self._set_cfg(interaction.guild.id, cfg)
            self._save_protect()

            await interaction.response.send_message(
                f"✅ {uye.mention} artık korunan kanallarda "
                f"taşıyabilir / çıkarabilir / susturabilir.", ephemeral=True)

    # ==================== ANA KOMUT ====================
    @app_commands.command(name='ses', description='Ses kanalı sistemi')
    @app_commands.describe(
        islem='İşlem',
        kanal='Ses kanalı',
        limit='Kişi limiti',
        ad='Kanal adı',
        uye='İzin verilecek kişi'
    )
    @app_commands.choices(islem=[
        app_commands.Choice(name='📍 Durum - Bot nerede', value='durum'),
        app_commands.Choice(name='🛡️ Koru - Bu kanalı korumaya al', value='koru'),
        app_commands.Choice(name='🔓 Koruma Kaldır', value='koruma_kaldir'),
        app_commands.Choice(name='➕ Serbest - Biri de taşıyabilsin', value='serbest'),
        app_commands.Choice(name='Hub Oluştur - Bota özel kanal aç', value='hub'),
        app_commands.Choice(name='Kendi Kanalım - Kişisel kanal aç', value='kendi'),
        app_commands.Choice(name='Listele - Aktif kanalları gör', value='liste'),
        app_commands.Choice(name='Kaldır - Sistemi kaldır', value='kaldir'),
        app_commands.Choice(name='Topla - Kanalları topla', value='topla'),
    ])
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ses(self, interaction: discord.Interaction, islem: str,
                  kanal: discord.VoiceChannel | None = None,
                  limit: int = 0, ad: str | None = None,
                  uye: discord.Member | None = None):

        # ============ KORUMA AYARLARI ============
        if islem in ('koru', 'koruma_kaldir', 'serbest'):
            await self._handle_protect(interaction, islem, kanal, uye)
            return

        # ============ DURUM ============
        if islem == 'durum':
            await self._handle_status(interaction)
            return

        if islem == 'liste':
            channels = [
                interaction.guild.get_channel(cid)
                for cid in list(self.hub_channels) + list(self.temp_channels.keys())
            ]
            channels = [c for c in channels if c]

            if not channels:
                await interaction.response.send_message("❌ Aktif ses kanalı yok!", ephemeral=True)
                return

            embed = discord.Embed(title="🔊 Bot Ses Kanalları",
                                  color=discord.Color.blue(), timestamp=datetime.now())
            for ch in channels:
                emoji = "🏠" if ch.id in self.hub_channels else "🚪"
                embed.add_field(
                    name=f"{emoji} {ch.name}",
                    value=f"Üye: {len(ch.members)} • Limit: {ch.user_limit or '∞'}",
                    inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if islem == 'kendi':
            if not interaction.user.voice:
                await interaction.response.send_message("❌ Bir ses kanalında olmalısın!", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)
            name = ad or f"🔊 {interaction.user.display_name}"

            channel = await self._create_temp_channel(interaction.user, interaction.user.voice.channel)
            if not channel:
                await interaction.followup.send("❌ Kanal açamadım! Yetki gerekli.", ephemeral=True)
                return

            try:
                await interaction.user.move_to(channel)
            except discord.Forbidden:
                pass

            await interaction.followup.send(
                f"🔊 **{channel.mention}** açıldı ve seni taşıdım.\nBoş kalınca 5 dk sonra silinir.",
                ephemeral=True)
            return

        if islem == 'kaldir':
            await interaction.response.defer(ephemeral=True)
            silinen = 0
            for cid in list(self.hub_channels) + list(self.temp_channels.keys()):
                channel = interaction.guild.get_channel(cid)
                if channel:
                    try:
                        await channel.delete(reason="Ses sistemi kaldirildi")
                        silinen += 1
                    except discord.Forbidden:
                        pass
            self.hub_channels.clear()
            self.temp_channels.clear()
            await interaction.followup.send(f"✅ Sistem kaldırıldı ({silinen} kanal silindi)", ephemeral=True)
            return

        if islem == 'topla':
            await interaction.response.defer(ephemeral=True)
            hub = next((interaction.guild.get_channel(cid) for cid in self.hub_channels), None)
            if not hub:
                await interaction.followup.send("❌ Önce `/ses hub` ile kanal oluştur!", ephemeral=True)
                return

            moved = 0
            for cid in list(self.temp_channels.keys()):
                data = self.temp_channels.get(cid)
                if not data:
                    continue
                member = interaction.guild.get_member(data['owner_id'])
                if member and member.voice:
                    try:
                        await member.move_to(hub)
                        moved += 1
                    except discord.Forbidden:
                        pass

            await interaction.followup.send(f"✅ {moved} üye {hub.mention} kanalına toplandı", ephemeral=True)
            return

        # islem == 'hub'
        await interaction.response.defer(ephemeral=True)

        name = ad or "🔊 Ses Odası"
        existing = discord.utils.get(interaction.guild.voice_channels, name=name)
        if existing:
            await interaction.followup.send(f"❌ `{name}` zaten var!", ephemeral=True)
            return

        cat = discord.utils.get(interaction.guild.categories, name="Ses Odaları")
        if not cat:
            try:
                cat = await interaction.guild.create_category("Ses Odaları")
            except discord.Forbidden:
                cat = None

        overwrites = {interaction.guild.default_role: discord.PermissionOverwrite(connect=False)}

        try:
            if cat:
                channel = await interaction.guild.create_voice_channel(
                    name, category=cat, user_limit=limit, overwrites=overwrites,
                    reason="Bot ses hub kanali")
            else:
                channel = await interaction.guild.create_voice_channel(
                    name, user_limit=limit, overwrites=overwrites,
                    reason="Bot ses hub kanali")
        except discord.Forbidden:
            await interaction.followup.send("❌ Kanal oluşturamadım!", ephemeral=True)
            return

        self.hub_channels.append(channel.id)

        try:
            if interaction.user.voice:
                await channel.connect()
        except (discord.Forbidden, discord.HTTPException):
            pass

        await interaction.followup.send(
            f"🔊 **{channel.mention}** oluşturuldu!\n\n"
            f"Kural: Kanala gir → Sana özel kanal açılır, boş kalınca 5 dk sonra silinir.",
            ephemeral=True)

    # ==================== BOTU KANALA EKLE (SESSIZ) ====================
    @app_commands.command(name='ses_ekle', description='Botu seçtiğin ses kanalına sessiz ekler')
    @app_commands.describe(kanal='Botun ekleneceği ses kanalı')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ses_ekle(self, interaction: discord.Interaction, kanal: discord.VoiceChannel):
        await interaction.response.defer(ephemeral=True)

        perms = kanal.permissions_for(interaction.guild.me)
        if perms is not None:
            if not perms.connect:
                await interaction.followup.send(
                    "❌ **Bağlanma iznim yok!**\n"
                    "Sunucu → Bot rolü → İzinler → `Bağlan` → **AÇ**",
                    ephemeral=True)
                return
            if not perms.speak:
                await interaction.followup.send(
                    "❌ **Konuşma iznim yok!**\n"
                    "Sunucu → Bot rolü → İzinler → `Konuş` → **AÇ**",
                    ephemeral=True)
                return

        try:
            # Kulakligi kapali (self_mute) sekilde baglan
            vc = await kanal.connect(self_mute=True, self_deaf=False)

            if self.silence_file is None:
                self.silence_file = _ensure_silence_file()
            if self.silence_file:
                try:
                    vc.play(discord.FFmpegPCMAudio(
                        self.silence_file,
                        before_options='-stream_loop -1 -loglevel warning'
                    ), volume=0.02)
                except Exception:
                    pass

            await interaction.followup.send(
                f"✅ Bot **{kanal.mention}** kanalına eklendi.\n"
                f"🔇 Mikrofonu kapalı (kimseye duyulmuyor)\n"
                f"👥 Kanalda şu an **{len(kanal.members)}** kişi var",
                ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ **Bağlanma izni reddedildi.**\n\n"
                "Kontrol et:\n"
                "• Botun rolü kanalın üstünde mi\n"
                "• Sunucuda 2FA açıksa rol geçici olabilir",
                ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Bağlanamadım: `{e}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Ses bağlantısı kurulamadı: `{type(e).__name__}`\n\n"
                "**Sunucuda olabilir:** ses kanalı limiti dolu veya "
                "`davyy[voice]` kurulu değil.",
                ephemeral=True)

    @app_commands.command(name='ses_cikar', description='Botu ses kanalından çıkarır')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ses_cikar(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        client = self._vc(interaction.guild)
        if not client:
            await interaction.followup.send("ℹ️ Bot zaten ses kanalında değil.", ephemeral=True)
            return

        name = client.channel.name if client.channel else '?'
        try:
            await client.disconnect(force=True)

            # Muzik kuyrugu varsa temizle (eski /disconnect komutunun islevi)
            temizlendi = ''
            music = self.bot.get_cog('Music')
            if music is not None:
                gid = interaction.guild.id
                if music.queues.get(gid):
                    music.queues[gid] = []
                    music.current[gid] = None
                    temizlendi = '\n🎵 Müzik kuyruğu temizlendi'

            await interaction.followup.send(
                f"🚪 Bot **{name}** kanalından ayrıldı.{temizlendi}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ayrılamadım: `{e}`", ephemeral=True)


async def setup(bot):
    await bot.add_cog(VoiceManager(bot))
