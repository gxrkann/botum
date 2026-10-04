import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import os


class OwnerProtect(commands.Cog):
    """Bot sahibinin ve sunucunun korunmasi"""

    def __init__(self, bot):
        self.bot = bot
        self.config_file = 'owner_protect.json'
        self.settings = self.load()

    def load(self):
        defaults = {
            'enabled': True,
            'owner_ids': [],
            'protect_roles': [],
            'protected_bots': True,
            'log_channel_id': None
        }
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                defaults.update(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return defaults

    def save(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"[koruma] Ayar kaydedilemedi: {e}", flush=True)

    def is_owner(self, member) -> bool:
        if member.id == self.bot.owner_id:
            return True
        return member.id in [int(x) for x in self.settings.get('owner_ids', [])]

    def is_protected(self, member) -> bool:
        if self.is_owner(member):
            return True
        if member.bot and self.settings.get('protected_bots', True):
            return True
        protected = {int(x) for x in self.settings.get('protect_roles', [])}
        if protected:
            for role in member.roles:
                if role.id in protected:
                    return True
        if member.guild.owner and member.id == member.guild.owner.id:
            return True
        return False

    async def log(self, guild, action, target, actor, blocked=False):
        cid = self.settings.get('log_channel_id')
        if not cid:
            return
        channel = self.bot.get_channel(cid)
        if not channel:
            return

        embed = discord.Embed(
            title=("🚫 " if blocked else "ℹ️ ") + action,
            color=discord.Color.red() if blocked else discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Hedef", value=f"{target.mention} (`{target.id}`)", inline=False)
        embed.add_field(name="İşlemi Yapan", value=f"{actor.mention} (`{actor.id}`)", inline=False)
        embed.add_field(name="Sonuç", value="❌ ENGELLENDİ" if blocked else "✅ İzin verildi", inline=False)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    # ==================== ANA KOMUT ====================
    @app_commands.command(name='koruma', description='Bot ve sunucu koruma sistemi')
    @app_commands.describe(
        islem='İşlem',
        uye='Üye',
        rol='Korunacak rol',
        kanal='Log kanalı'
    )
    @app_commands.choices(islem=[
        app_commands.Choice(name='Durum - Koruma durumunu gör', value='durum'),
        app_commands.Choice(name='Aç/Kapat - Korumayı aç veya kapat', value='ac'),
        app_commands.Choice(name='Ekle - Ek korunan kişi ekle', value='ekle'),
        app_commands.Choice(name='Çıkar - Korumadan kişi çıkar', value='cikar'),
        app_commands.Choice(name='Rol Ekle - Korunacak rol ekle', value='rol_ekle'),
        app_commands.Choice(name='Log - Log kanalı ayarla', value='log'),
    ])
    async def koruma(self, interaction: discord.Interaction, islem: str,
                     uye: discord.Member | None = None,
                     rol: discord.Role | None = None,
                     kanal: discord.TextChannel | None = None):

        admin = interaction.app_commands.checks.has_permissions(administrator=True)

        # Durum herkes icin
        if islem == 'durum':
            embed = discord.Embed(
                title="🛡️ Koruma Durumu",
                color=discord.Color.green() if self.settings['enabled'] else discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Koruma", value="Açık" if self.settings['enabled'] else "Kapalı", inline=True)
            embed.add_field(name="Bot Sahibi", value=f"<@{self.bot.owner_id}>" if self.bot.owner_id else "Bilinmiyor", inline=True)
            embed.add_field(name="Botlar Korumalı", value="Evet" if self.settings['protected_bots'] else "Hayır", inline=True)
            embed.add_field(name="Ek Korunan Kişi", value=str(len(self.settings['owner_ids'])), inline=True)
            embed.add_field(name="Korunan Rol", value=str(len(self.settings['protect_roles'])), inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Geri kalan islemler yonetici gerektirir
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Bu işlem için **Yönetici** yetkisi gerekir!", ephemeral=True)
            return

        if islem == 'ac':
            self.settings['enabled'] = not self.settings['enabled']
            self.save()
            durum = "Açık" if self.settings['enabled'] else "Kapalı"
            await interaction.response.send_message(f"🛡️ Koruma: **{durum}**", ephemeral=True)

        elif islem == 'ekle':
            if not uye:
                await interaction.response.send_message("❌ Üye seçmelisin!", ephemeral=True)
                return
            if str(uye.id) not in self.settings['owner_ids']:
                self.settings['owner_ids'].append(str(uye.id))
                self.save()
            await interaction.response.send_message(
                f"✅ {uye.mention} eklendi. Artık sadece o da botu atabilir.", ephemeral=True)

        elif islem == 'cikar':
            if not uye:
                await interaction.response.send_message("❌ Üye seçmelisin!", ephemeral=True)
                return
            if str(uye.id) in self.settings['owner_ids']:
                self.settings['owner_ids'].remove(str(uye.id))
                self.save()
            await interaction.response.send_message(
                f"✅ {uye.mention} koruma listesinden çıkarıldı.", ephemeral=True)

        elif islem == 'rol_ekle':
            if not rol:
                await interaction.response.send_message("❌ Rol seçmelisin!", ephemeral=True)
                return
            if str(rol.id) not in self.settings['protect_roles']:
                self.settings['protect_roles'].append(str(rol.id))
                self.save()
            await interaction.response.send_message(
                f"✅ {rol.mention} korunan rollere eklendi.", ephemeral=True)

        elif islem == 'log':
            if not kanal:
                await interaction.response.send_message("❌ Kanal seçmelisin!", ephemeral=True)
                return
            self.settings['log_channel_id'] = kanal.id
            self.save()
            await interaction.response.send_message(
                f"✅ Koruma log kanalı: {kanal.mention}", ephemeral=True)

    # ==================== EVENT KORUMA ====================
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not self.settings['enabled']:
            return

        if member.id == self.bot.user.id:
            print(f"[KORUMA] Bot sunucudan atildi: {member.guild.name}", flush=True)
            try:
                await member.guild.owner.send(
                    "⚠️ **BOT SUNUCUDAN ATILDI!**\n\n"
                    f"**Sunucu:** {member.guild.name}\n\n"
                    "Botu geri ekle:\n"
                    f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot"
                )
            except discord.Forbidden:
                pass
            return

        if self.is_protected(member) and not self.is_owner(member):
            await self.log(member.guild, "Korunan Üye Sunucudan Ayrıldı",
                           member, member.guild.owner, blocked=True)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after.id != self.bot.user.id:
            return
        if before.roles != after.roles:
            try:
                await after.edit(roles=before.roles)
                await self.log(after.guild, "Bot Rolü Korundu",
                               after, after.guild.owner, blocked=True)
            except discord.Forbidden:
                pass


async def setup(bot):
    await bot.add_cog(OwnerProtect(bot))