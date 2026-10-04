import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==================== BAN ====================
    @app_commands.command(name='ban', description='Bir üyeyi sunucudan yasakla')
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
    @app_commands.command(name='kick', description='Bir üyeyi sunucudan at')
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
    @app_commands.command(name='mute', description='Bir üyeyi sustur')
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
    @app_commands.command(name='unmute', description='Bir üyenin susturmasını kaldır')
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

    # ==================== WARN ====================
    @app_commands.command(name='warn', description='Bir üyeye uyarı ver')
    @app_commands.describe(member='Uyarılacak üye', reason='Uyarı nedeni')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        await self.bot.db.add_warning(member.id, interaction.guild.id, interaction.user.id, reason)
        warnings = await self.bot.db.get_warnings(member.id, interaction.guild.id)

        embed = discord.Embed(
            title="⚠️ Uyarı Verildi",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Üye", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="Yetkili", value=f"{interaction.user.mention}", inline=False)
        embed.add_field(name="Neden", value=reason, inline=False)
        embed.add_field(name="Toplam Uyarı", value=f"{len(warnings)}", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    # ==================== WARNINGS ====================
    @app_commands.command(name='warnings', description='Bir üyenin uyarılarını gör')
    @app_commands.describe(member='Uyarıları görüntülenecek üye')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        warnings = await self.bot.db.get_warnings(member.id, interaction.guild.id)
        if not warnings:
            await interaction.response.send_message(f"✅ {member.mention} hiç uyarı almamış!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"⚠️ {member.name} Uyarıları ({len(warnings)})",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        for i, warn in enumerate(warnings[:10], 1):
            moderator = interaction.guild.get_member(warn[3])
            mod_name = moderator.mention if moderator else "Bilinmiyor"
            embed.add_field(
                name=f"Uyarı #{i}",
                value=f"**Neden:** {warn[4]}\n**Yetkili:** {mod_name}\n**Tarih:** {warn[5][:10]}",
                inline=False
            )
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    # ==================== CLEAR ====================
    @app_commands.command(name='clear', description='Kanaldan mesaj sil')
    @app_commands.describe(
        amount='Silinecek mesaj sayısı (1-300)',
        channel='Kanal (boş bırakılırsa bulunduğun kanal)',
        member='Sadece bu üyenin mesajlarını sil',
        contains='Sadece içinde bu kelime geçen mesajları sil'
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int,
                    channel: discord.TextChannel | None = None,
                    member: discord.Member | None = None,
                    contains: str | None = None):
        if amount < 1 or amount > 300:
            await interaction.response.send_message("❌ 1-300 arasında bir sayı gir!", ephemeral=True)
            return

        target = channel or interaction.channel
        await interaction.response.defer(ephemeral=True)

        try:
            if member is None and contains is None:
                # Normal toplu silme
                deleted = await target.purge(limit=amount)
                await interaction.followup.send(f"🗑️ **{len(deleted)}** mesaj silindi!", ephemeral=True)

            else:
                # Filtreli silme - 2 haftadan eski mesajlar API ile silinmez
                cutoff = discord.utils.utcnow() - discord.timedelta(days=14)
                deleted_count = 0
                to_delete = []

                async for msg in target.history(limit=amount, oldest_first=False):
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
                    await interaction.followup.send("❌ Silinecek mesaj bulunamadı! (Not: 14 günden eski mesajlar silinemez)", ephemeral=True)
                    return

                # Toplu sil (34'erli gruplar - Discord rate limit)
                for i in range(0, len(to_delete), 34):
                    batch = to_delete[i:i + 34]
                    try:
                        await target.delete_messages(batch)
                        deleted_count += len(batch)
                    except discord.HTTPException:
                        # Yetki yoksa tek tek dene
                        for msg in batch:
                            try:
                                await msg.delete()
                                deleted_count += 1
                                await asyncio.sleep(0.4)
                            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                                pass

                await interaction.followup.send(f"🗑️ **{deleted_count}** mesaj silindi!", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("❌ Bu kanalda mesaj silme yetkim yok!", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Silme hatası: {e}", ephemeral=True)

    # ==================== SLOWMODE ====================
    @app_commands.command(name='slowmode', description='Kanalı yavaş moda al')
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
    @app_commands.command(name='lock', description='Kanalı kilitle')
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
    @app_commands.command(name='unlock', description='Kanalın kilidini aç')
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
    @app_commands.command(name='nick', description='Bir üyenin takma adını değiştir')
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
    @app_commands.command(name='role_add', description='Bir üyeye rol ekle')
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
    @app_commands.command(name='role_remove', description='Bir üyeden rol kaldır')
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
