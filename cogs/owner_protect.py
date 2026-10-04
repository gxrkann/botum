import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import os


class OwnerProtect(commands.Cog):
    """
    Bot sahibinin korunmasi.
    - Bot, sadece sahibinin (veya belirlenen rollerin) atabilecegi/kickleyebilecegi durum
    - Sunucu sahibi disinda kimse botu sunucudan atamaz
    """

    def __init__(self, bot):
        self.bot = bot
        self.config_file = 'owner_protect.json'
        self.settings = self.load()

    def load(self):
        """Koruma ayarlarini yukle"""
        defaults = {
            'enabled': True,
            'owner_ids': [],           # Ek korunan kullanicilar (bot sahibi disinda)
            'protect_roles': [],        # Korunan roller
            'protected_bots': True,     # Tum botlari koru
            'allow_ban': False,         # Ban da engellensin mi
            'log_channel_id': None
        }
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            defaults.update(saved)
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
        """Uye bot sahibi mi veya korumali mi"""
        if member.id == self.bot.owner_id:
            return True
        if member.id in [int(x) for x in self.settings.get('owner_ids', [])]:
            return True
        return False

    def is_protected(self, member) -> bool:
        """Hedef uye korumali mi"""
        if self.is_owner(member):
            return True

        # Tum botlar korunuyorsa
        if member.bot and self.settings.get('protected_bots', True):
            return True

        # Korunan roller
        protected_roles = {int(x) for x in self.settings.get('protect_roles', [])}
        if protected_roles:
            for role in member.roles:
                if role.id in protected_roles:
                    return True

        # Sunucu sahibi her zaman korumali
        if member.guild.owner and member.id == member.guild.owner.id:
            return True

        return False

    async def log(self, guild, action, target, actor, blocked=False):
        """Koruma logu"""
        cid = self.settings.get('log_channel_id')
        if not cid:
            return
        channel = self.bot.get_channel(cid)
        if not channel:
            return

        emoji = "🚫" if blocked else "ℹ️"
        color = discord.Color.red() if blocked else discord.Color.blue()

        embed = discord.Embed(
            title=f"{emoji} {action}",
            color=color,
            timestamp=datetime.now()
        )
        embed.add_field(name="Hedef", value=f"{target.mention} (`{target.id}`)", inline=False)
        embed.add_field(name="İşlemi Yapan", value=f"{actor.mention} (`{actor.id}`)", inline=False)
        if blocked:
            embed.add_field(name="Sonuç", value="❌ ENGELLENDİ", inline=False)
        else:
            embed.add_field(name="Sonuç", value="✅ İzin verildi", inline=False)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    # ==================== AYAR KOMUTLARI ====================
    @app_commands.command(name='koruma_ayarla', description='Bot sahibi korumasını ayarla')
    @app_commands.describe(
        enabled='Koruma açık mı',
        allow_ban='Ban da engellensin mi',
        log_channel='Log kanalı',
        protected_roles='Korunacak roller'
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def koruma_ayarla(self, interaction: discord.Interaction, enabled: bool = True,
                            allow_ban: bool = False, log_channel: discord.TextChannel | None = None,
                            protected_roles: discord.Role | None = None):
        self.settings['enabled'] = enabled
        self.settings['allow_ban'] = allow_ban

        if log_channel:
            self.settings['log_channel_id'] = log_channel.id
        if protected_roles:
            if str(protected_roles.id) not in self.settings['protect_roles']:
                self.settings['protect_roles'].append(str(protected_roles.id))

        self.save()

        embed = discord.Embed(
            title="🛡️ Koruma Ayarlandı",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Durum", value="Açık" if enabled else "Kapalı", inline=True)
        embed.add_field(name="Ban Engelli", value="Hayır" if allow_ban else "Evet", inline=True)
        embed.add_field(name="Log Kanalı", value=log_channel.mention if log_channel else "Kapalı", inline=False)
        embed.add_field(name="Korunan Roller", value=str(len(self.settings['protect_roles'])), inline=True)
        embed.add_field(name="Ek Korunan Kişi", value=str(len(self.settings['owner_ids'])), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='koruma_ekle', description='Ek korunan kişi ekle')
    @app_commands.describe(member='Korunacak kişi')
    @app_commands.checks.has_permissions(administrator=True)
    async def koruma_ekle(self, interaction: discord.Interaction, member: discord.Member):
        if str(member.id) not in self.settings['owner_ids']:
            self.settings['owner_ids'].append(str(member.id))
            self.save()
            await interaction.response.send_message(
                f"✅ {member.mention} eklendi. Artık sadece o da botu atabilir.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Zaten listede!", ephemeral=True)

    @app_commands.command(name='koruma_cikar', description='Ek korunan kişiyi çıkar')
    @app_commands.describe(member='Çıkarılacak kişi')
    @app_commands.checks.has_permissions(administrator=True)
    async def koruma_cikar(self, interaction: discord.Interaction, member: discord.Member):
        if str(member.id) in self.settings['owner_ids']:
            self.settings['owner_ids'].remove(str(member.id))
            self.save()
            await interaction.response.send_message(
                f"✅ {member.mention} koruma listesinden çıkarıldı.", ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Kişi listede değil!", ephemeral=True)

    @app_commands.command(name='koruma_durum', description='Koruma durumunu gör')
    async def koruma_durum(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛡️ Koruma Durumu",
            color=discord.Color.green() if self.settings['enabled'] else discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Koruma", value="Açık" if self.settings['enabled'] else "Kapalı", inline=True)
        embed.add_field(name="Bot Sahibi", value=f"<@{self.bot.owner_id}>" if self.bot.owner_id else "Bilinmiyor", inline=True)
        embed.add_field(name="Tüm Botlar Korumalı", value="Evet" if self.settings['protected_bots'] else "Hayır", inline=True)
        embed.add_field(name="Ban Engelli", value="Evet" if not self.settings['allow_ban'] else "Hayır", inline=True)
        embed.add_field(name="Ek Korunan", value=str(len(self.settings['owner_ids'])), inline=True)
        embed.add_field(name="Korunan Rol", value=str(len(self.settings['protect_roles'])), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== EVENT KORUMA ====================
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Bot atildi mi veya korumali biri atildi mi"""
        if not self.settings['enabled']:
            return

        # Bot atildi
        if member.id == self.bot.user.id:
            print(f"[KORUMA] Bot sunucudan atildi: {member.guild.name}", flush=True)
            try:
                await member.guild.owner.send(
                    f"⚠️ **BOT SUNUCUDAN ATILDI!**\n"
                    f"**Sunucu:** {member.guild.name}\n"
                    f"**Yapan:** {member.guild.owner.mention}\n\n"
                    f"Botu geri eklemek için davet linki:\n"
                    f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot"
                )
            except discord.Forbidden:
                pass
            return

        # Korumali biri mi atildi
        if self.is_protected(member) and not self.is_owner(member):
            await self.log(
                member.guild, "Korunan Üye Sunucudan Ayrıldı",
                member, member.guild.owner, blocked=True
            )

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Botun rolleri degistirildi mi"""
        if after.id != self.bot.user.id:
            return

        if before.roles != after.roles:
            # Rollere mudahale edilmis, eski haline dondur
            try:
                await after.edit(roles=before.roles)
                print("[KORUMA] Bot rolleri geri alindi", flush=True)
                await self.log(
                    after.guild, "Bot Rolü Korundu",
                    after, after.guild.owner, blocked=True
                )
            except discord.Forbidden:
                pass


async def setup(bot):
    await bot.add_cog(OwnerProtect(bot))