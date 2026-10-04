import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import asyncio


class VoiceManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hub_channels = []
        self.temp_channels = {}

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

    # ==================== ANA KOMUT ====================
    @app_commands.command(name='ses', description='Ses kanalı sistemi')
    @app_commands.describe(
        islem='İşlem',
        kanal='Ses kanalı',
        limit='Kişi limiti',
        ad='Kanal adı'
    )
    @app_commands.choices(islem=[
        app_commands.Choice(name='Hub Oluştur - Bota özel kanal aç', value='hub'),
        app_commands.Choice(name='Kendi Kanalım - Kişisel kanal aç', value='kendi'),
        app_commands.Choice(name='Listele - Aktif kanalları gör', value='liste'),
        app_commands.Choice(name='Kaldır - Sistemi kaldır', value='kaldir'),
        app_commands.Choice(name='Topla - Kanalları topla', value='topla'),
    ])
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ses(self, interaction: discord.Interaction, islem: str,
                  kanal: discord.VoiceChannel | None = None,
                  limit: int = 0, ad: str | None = None):

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

    # ==================== EVENT'LER ====================
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
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


async def setup(bot):
    await bot.add_cog(VoiceManager(bot))