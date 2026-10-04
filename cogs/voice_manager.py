import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import asyncio


class VoiceManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Bota ait ses kanallari
        self.hub_channels = []
        self.temp_channels = {}
        self.task_cache = {}

    # ==================== ASYNC KANAL SILME ====================
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
            print(f"[ses] Bos kanal silindi: {channel.name}", flush=True)
        except discord.NotFound:
            self.temp_channels.pop(channel.id, None)
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[ses] Kanal silme hatasi: {e}", flush=True)

    # ==================== HUB KANALI ====================
    @app_commands.command(name='ses_hub', description='Bota özel ses kanalı oluştur')
    @app_commands.describe(
        name='Kanal adı',
        limit='Kişi limiti (0 = sınırsız)',
        category='Kategori adı (boş bırakılırsa otomatik)'
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ses_hub(self, interaction: discord.Interaction, name: str = "🔊 Ses Odası",
                      limit: int = 0, category: str | None = None):
        # Ayni isimde kanal var mi
        existing = discord.utils.get(interaction.guild.voice_channels, name=name)
        if existing:
            await interaction.response.send_message(f"❌ `{name}` adında kanal zaten var!", ephemeral=True)
            return

        cat = None
        if category:
            cat = discord.utils.get(interaction.guild.categories, name=category)
            if not cat:
                try:
                    cat = await interaction.guild.create_category(category)
                except discord.Forbidden:
                    cat = None
        else:
            cat = discord.utils.get(interaction.guild.categories, name="Ses Odaları")
            if not cat:
                try:
                    cat = await interaction.guild.create_category("Ses Odaları")
                except discord.Forbidden:
                    cat = None

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(connect=False)
        }

        try:
            if cat:
                channel = await interaction.guild.create_voice_channel(
                    name, category=cat, user_limit=limit, overwrites=overwrites,
                    reason="Bot ses hub kanali"
                )
            else:
                channel = await interaction.guild.create_voice_channel(
                    name, user_limit=limit, overwrites=overwrites,
                    reason="Bot ses hub kanali"
                )
        except discord.Forbidden:
            await interaction.response.send_message("❌ Kanal oluşturamadım! Kanal Yönetimi yetkisi gerekli.", ephemeral=True)
            return

        self.hub_channels.append(channel.id)

        # Bot kanala baglanir
        try:
            if interaction.user.voice:
                await channel.connect()
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[ses] Hub'a baglanilamadi: {e}", flush=True)

        embed = discord.Embed(
            title="🔊 Ses Kanalı Hazır",
            description=f"{channel.mention} oluşturuldu!\n\nKural: Kanala gir → Sana özel kanal açılır",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Kişi Limiti", value=str(limit) if limit else "Sınırsız", inline=True)
        embed.add_field(name="Otomatik Silme", value="Boş kalınca 5 dk sonra", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='ses_hub_kaldir', description='Ses kanalı sistemini kaldır')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ses_hub_kaldir(self, interaction: discord.Interaction):
        silinen = 0
        for cid in list(self.hub_channels):
            channel = interaction.guild.get_channel(cid)
            if channel:
                try:
                    await channel.delete(reason="Ses hub kaldirildi")
                    silinen += 1
                except discord.Forbidden:
                    pass

        for cid in list(self.temp_channels.keys()):
            channel = interaction.guild.get_channel(cid)
            if channel:
                try:
                    await channel.delete(reason="Ses kanallari kaldirildi")
                    silinen += 1
                except discord.Forbidden:
                    pass

        self.hub_channels.clear()
        self.temp_channels.clear()

        await interaction.response.send_message(f"✅ Ses kanalı sistemi kaldırıldı ({silinen} kanal silindi)", ephemeral=True)

    @app_commands.command(name='ses_listesi', description='Açık ses kanallarını listele')
    async def ses_listesi(self, interaction: discord.Interaction):
        bot_channels = [
            interaction.guild.get_channel(cid)
            for cid in list(self.hub_channels) + list(self.temp_channels.keys())
        ]
        bot_channels = [c for c in bot_channels if c]

        if not bot_channels:
            await interaction.response.send_message("❌ Aktif ses kanalı yok!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔊 Bot Ses Kanalları",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        for ch in bot_channels:
            emoji = "🏠" if ch.id in self.hub_channels else "🚪"
            embed.add_field(
                name=f"{emoji} {ch.name}",
                value=f"Üye: {len(ch.members)} • Limit: {ch.user_limit or '∞'}",
                inline=True
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== GEÇİCİ KANAL ====================
    async def create_temp_channel(self, member, base_channel):
        """Üye için kişisel kanal oluştur"""
        guild = member.guild
        name = f"🔊 {member.display_name}"

        category = base_channel.category or discord.utils.get(guild.categories, name="Ses Odaları")

        # Ayni isimde var mi
        existing = discord.utils.get(guild.voice_channels, name=name)
        if existing:
            return existing

        overwrites = {
            member: discord.PermissionOverwrite(
                connect=True, manage_channels=True, move_members=True,
                mute_members=True, deafen_members=True
            ),
            guild.default_role: discord.PermissionOverwrite(connect=False),
            guild.me: discord.PermissionOverwrite(connect=True, manage_channels=True)
        }

        try:
            if category:
                channel = await guild.create_voice_channel(
                    name, category=category, user_limit=0, overwrites=overwrites,
                    reason=f"{member.display_name} icin ozel kanal"
                )
            else:
                channel = await guild.create_voice_channel(
                    name, user_limit=0, overwrites=overwrites,
                    reason=f"{member.display_name} icin ozel kanal"
                )
        except discord.Forbidden:
            return None

        self.temp_channels[channel.id] = {
            'owner_id': member.id,
            'created_at': datetime.now()
        }
        print(f"[ses] Ozel kanal acildi: {name}", flush=True)

        # Bos kalinca sil
        asyncio.create_task(self._delete_after_empty(channel))

        return channel

    # ==================== EVENT'LER ====================
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or member.id == self.bot.user.id:
            return

        # Botun kanallari
        if before.channel and before.channel.id in self.temp_channels:
            if before.channel.id not in [c.id for c in self.hub_channels]:
                if after.channel is None or after.channel.id != before.channel.id:
                    # Kanaldan cikti, baska birine tasindi mi?
                    if after.channel and after.channel.id in self.temp_channels:
                        data = self.temp_channels.get(after.channel.id)
                        if data and data['owner_id'] != member.id:
                            # Baska birinin kanali, bos mu kontrol et
                            pass
                    # Kendi kanalindan cikti mi
                    data = self.temp_channels.get(before.channel.id)
                    if data and data['owner_id'] == member.id:
                        if after.channel is None:
                            asyncio.create_task(self._delete_after_empty(before.channel))

        # Hub kanala girdi
        if after.channel and after.channel.id in self.hub_channels:
            if not self.bot.guilds:
                return
            guild = member.guild
            vc = guild.get_channel(after.channel.id)
            if not vc:
                return

            try:
                # Bot kanala girsin
                if vc and self.bot.voice_clients:
                    bot_vc = None
                    for c in self.bot.voice_clients:
                        if c.channel and c.channel.guild.id == guild.id:
                            bot_vc = c
                            break
                    if bot_vc:
                        if bot_vc.channel.id != vc.id:
                            await bot_vc.move_to(vc)

                # Uye icin kanal ac
                temp = await self.create_temp_channel(member, vc)
                if temp:
                    await member.move_to(temp)
            except discord.Forbidden:
                pass
            except Exception as e:
                print(f"[ses] Kanal acilamadi: {e}", flush=True)

        # Kendi kanalindan baska yere gitti
        if before.channel and before.channel.id in self.temp_channels:
            data = self.temp_channels.get(before.channel.id)
            if data and data['owner_id'] == member.id:
                if after.channel is None:
                    asyncio.create_task(self._delete_after_empty(before.channel))
                else:
                    # Yeni kanala gitti, eskisini bos birak
                    asyncio.create_task(self._delete_after_empty(before.channel))

        # Kanal silindi
        if before.channel and before.channel.id in self.temp_channels:
            try:
                if after.channel is None and before.channel:
                    self.temp_channels.pop(before.channel.id, None)
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # Sunucudan cikildi, kanallari temizle
        self.temp_channels = {k: v for k, v in self.temp_channels.items() if k not in [c.id for c in self.hub_channels]}
        for cid in list(self.temp_channels.keys()):
            self.temp_channels.pop(cid, None)

    # ==================== KULLANICI KANALI ====================
    @app_commands.command(name='kendi_kanalim', description='Kendi ses kanalını oluştur')
    @app_commands.describe(name='Kanal adı')
    async def kendi_kanalim(self, interaction: discord.Interaction, name: str | None = None):
        if not interaction.user.voice:
            await interaction.response.send_message("❌ Bir ses kanalında olmalısın!", ephemeral=True)
            return

        guild = interaction.guild
        channel_name = name or f"🔊 {interaction.user.display_name}"

        existing = discord.utils.get(guild.voice_channels, name=channel_name)
        if existing:
            await interaction.response.send_message(f"❌ `{channel_name}` zaten var!", ephemeral=True)
            return

        overwrites = {
            interaction.user: discord.PermissionOverwrite(
                connect=True, manage_channels=True, move_members=True
            ),
            guild.default_role: discord.PermissionOverwrite(connect=False),
            guild.me: discord.PermissionOverwrite(connect=True, manage_channels=True)
        }

        category = interaction.user.voice.channel.category

        try:
            if category:
                channel = await guild.create_voice_channel(
                    channel_name, category=category, overwrites=overwrites,
                    reason="Kullanici kanali"
                )
            else:
                channel = await guild.create_voice_channel(
                    channel_name, overwrites=overwrites, reason="Kullanici kanali"
                )
        except discord.Forbidden:
            await interaction.response.send_message("❌ Kanal açamadım! Yetki gerekli.", ephemeral=True)
            return

        self.temp_channels[channel.id] = {
            'owner_id': interaction.user.id,
            'created_at': datetime.now()
        }

        try:
            await interaction.user.move_to(channel)
        except discord.Forbidden:
            pass

        asyncio.create_task(self._delete_after_empty(channel))

        embed = discord.Embed(
            title="🔊 Kanalın Hazır",
            description=f"{channel.mention} açıldı ve seni taşıdım.\nBoş kalınca 5 dk sonra silinir.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='kanal_topla', description='Tüm bot kanallarını topla')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def kanal_topla(self, interaction: discord.Interaction):
        moved = 0
        for cid in list(self.temp_channels.keys()):
            channel = interaction.guild.get_channel(cid)
            if not channel:
                continue

            # Kanal sahibini bul
            for voice_client in self.bot.voice_clients:
                if voice_client.channel and voice_client.channel.id == cid:
                    owner = interaction.guild.get_member(
                        self.temp_channels[cid]['owner_id']
                    )
                    if owner and owner.voice:
                        target = next(
                            (c for c in self.bot.voice_clients
                             if c.channel and c.channel.guild.id == interaction.guild.id
                             and c.channel.id in self.hub_channels),
                            None
                        )
                        if target:
                            try:
                                await owner.move_to(target.channel)
                                moved += 1
                            except discord.Forbidden:
                                pass
                    break

        await interaction.response.send_message(f"✅ {moved} üye toplandı", ephemeral=True)


async def setup(bot):
    await bot.add_cog(VoiceManager(bot))