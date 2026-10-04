import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import json
import os
import asyncio

class Guard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_dir = "backups"
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
        self.action_log = {}

    async def get_log_channel(self, guild_id: int):
        """Guard loglari icin ozel kanal, yoksa genel log kanalina duser"""
        settings = await self.bot.db.get_settings(guild_id)
        if not settings:
            return None

        guard_cid = settings.get('guard_log_channel_id')
        if guard_cid:
            channel = self.bot.get_channel(guard_cid)
            if channel:
                return channel

        legacy = settings.get('log_channel_id')
        if legacy:
            return self.bot.get_channel(legacy)

        return None

    async def log_action(self, guild_id: int, action: str, target: str, moderator: str, reason: str):
        log_channel = await self.get_log_channel(guild_id)
        if log_channel:
            embed = discord.Embed(
                title=f"🛡️ Guard: {action}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Hedef", value=target, inline=False)
            embed.add_field(name="Yetkili", value=moderator, inline=False)
            embed.add_field(name="Neden", value=reason, inline=False)
            await log_channel.send(embed=embed)

    async def check_guard(self, guild_id: int, protection: str):
        async with self.bot.db.connection.execute(
            'SELECT settings FROM guard_settings WHERE guild_id = ?',
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            settings = json.loads(row[0])
            return settings.get('enabled', False) and protection in settings.get('protections', [])

    # ==================== BOT KORUMA ====================
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.id == self.bot.user.id:
            guild = member.guild
            log_channel = discord.utils.get(guild.channels, name="guard-log")
            if log_channel:
                embed = discord.Embed(
                    title="⚠️ Bot Atıldı!",
                    description=f"{member.mention} sunucudan atıldı! Bu bir hata olabilir.",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after.id == self.bot.user.id:
            if before.roles != after.roles:
                try:
                    await after.edit(roles=before.roles)
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        # bot.user bir ClientUser - rolleri guild.me uzerinden alinir
        guild_me = role.guild.me
        if guild_me is None:
            return

        if role.name == guild_me.name or role in guild_me.roles:
            try:
                new_role = await role.guild.create_role(
                    name=role.name,
                    color=role.color,
                    permissions=role.permissions,
                    reason="Bot rolü geri yüklendi"
                )
                await guild_me.add_roles(new_role)
            except discord.Forbidden:
                pass

    # ==================== LOG KANALLARI ====================
    async def create_log_channel(self, guild: discord.Guild, log_type: str):
        """Otomatik log kanalı oluştur"""
        channel_names = {
            'guard': 'guard-log',
            'mod': 'mod-log',
            'message': 'mesaj-log',
            'voice': 'ses-log',
            'member': 'üye-log',
            'silah_katlanan': 'katlanan-silah',
            'silah_kaybedilen': 'kaybedilen-silah',
            'farm': 'farm-log',
            'all': 'bot-log'
        }

        channel_name = channel_names.get(log_type, f'{log_type}-log')

        # Kanal var mi kontrol et
        existing = discord.utils.get(guild.channels, name=channel_name)
        if existing:
            print(f"[log-kanal] Mevcut: {channel_name}", flush=True)
            return existing

        # Kategori olustur veya bul
        category = discord.utils.get(guild.categories, name="Bot Logs")
        if not category:
            try:
                category = await guild.create_category("Bot Logs")
                print(f"[log-kanal] Kategori olusturuldu: Bot Logs", flush=True)
            except discord.Forbidden as e:
                print(f"[log-kanal] Kategori olusturulamadi (Forbidden): {e}", flush=True)
                category = None
            except discord.HTTPException as e:
                print(f"[log-kanal] Kategori hatasi (HTTP {e.status}): {e.text}", flush=True)
                category = None

        # Kanali olustur
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }

            if category:
                channel = await guild.create_text_channel(
                    channel_name,
                    category=category,
                    overwrites=overwrites,
                    reason=f"Bot {log_type} log kanalı"
                )
            else:
                channel = await guild.create_text_channel(
                    channel_name,
                    overwrites=overwrites,
                    reason=f"Bot {log_type} log kanalı"
                )

            return channel
        except discord.Forbidden:
            return None

    @app_commands.command(name='log_kanal', description='Log kanalı ayarla')
    @app_commands.describe(
        log_type='Log türü',
        channel='Log kanalı (boş bırakılırsa otomatik oluşturulur)'
    )
    @app_commands.choices(log_type=[
        app_commands.Choice(name='Guard - Guard logları', value='guard'),
        app_commands.Choice(name='Moderasyon - Mod logları', value='mod'),
        app_commands.Choice(name='Mesaj - Mesaj silme/düzenleme', value='message'),
        app_commands.Choice(name='Ses - Ses kanalı logları', value='voice'),
        app_commands.Choice(name='Üye - Üye katılma/ayrılma', value='member'),
        app_commands.Choice(name='Tümü - Tüm loglar', value='all')
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def log_kanal(self, interaction: discord.Interaction, log_type: str, channel: discord.TextChannel | None = None):
        if channel is None:
            # Kanal olusturulunca 3 saniyeyi asabilir
            await interaction.response.defer(ephemeral=True)

            channel = await self.create_log_channel(interaction.guild, log_type)
            if not channel:
                await interaction.followup.send("❌ Log kanalı oluşturulamadı! Yetkilerimi kontrol et.", ephemeral=True)
                return

        # Veritabanına kaydet
        await self.bot.db.update_setting(interaction.guild.id, f'{log_type}_log_channel_id', channel.id)

        embed = discord.Embed(
            title="📋 Log Kanalı Ayarlandı",
            description=f"**Log Türü:** {log_type}\n**Kanal:** {channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name='log_otomatik', description='Tüm log kanallarını otomatik oluştur')
    @app_commands.checks.has_permissions(administrator=True)
    async def log_otomatik(self, interaction: discord.Interaction):
        """Tüm log kanallarını otomatik oluştur"""
        await interaction.response.defer(ephemeral=True)

        log_types = ['guard', 'mod', 'message', 'voice', 'member',
                     'silah_katlanan', 'silah_kaybedilen', 'farm']

        progress = discord.Embed(
            title="📋 Log Kanalları Oluşturuluyor",
            description="Başlatılıyor...",
            color=discord.Color.blue()
        )
        status = await interaction.followup.send(embed=progress, ephemeral=True)

        created_channels = []
        total = len(log_types)

        for i, log_type in enumerate(log_types, 1):
            progress.description = f"**{i}/{total}** oluşturuluyor: `{log_type}`\n\n" + \
                                   ("\n".join(created_channels) if created_channels else "_Henüz başlanmadı_")
            await status.edit(embed=progress)

            channel = await self.create_log_channel(interaction.guild, log_type)
            if channel:
                await self.bot.db.update_setting(interaction.guild.id, f'{log_type}_log_channel_id', channel.id)
                created_channels.append(f"✅ `{log_type}` → {channel.mention}")

            # Discord kanal olusturmayi hiz sinirlamasiyla - bekle
            if i < total:
                await asyncio.sleep(2.5)

        final = discord.Embed(
            title="📋 Log Kanalları Hazır",
            description="\n".join(created_channels) if created_channels else "Hiç kanal oluşturulamadı.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await status.edit(embed=final)

    # ==================== GUARD KOMUTLARI ====================
    @app_commands.command(name='guard_ayarla', description='Guard sistemini ayarla')
    @app_commands.describe(
        korumalar='Korumaları aç/kapat (örn: ban,kick,rol,kanal,webhook,raid,spam,nuke,emoji,bot)',
        log_channel='Log kanalı (boş bırakılırsa otomatik oluşturulur)'
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def guard_ayarla(self, interaction: discord.Interaction, korumalar: str, log_channel: discord.TextChannel | None = None):
        # Kanal otomatik olusturulacaksa once defer et
        if log_channel is None:
            await interaction.response.defer(ephemeral=True)

            log_channel = await self.create_log_channel(interaction.guild, 'guard')
            if not log_channel:
                await interaction.followup.send("❌ Log kanalı oluşturulamadı! Yetkilerimi kontrol et.", ephemeral=True)
                return

        settings = {
            'enabled': True,
            'protections': [k.strip().strip() for k in korumalar.split(',')],
            'log_channel_id': log_channel.id
        }

        await self.bot.db.connection.execute(
            '''INSERT OR REPLACE INTO guard_settings (guild_id, settings) VALUES (?, ?)''',
            (interaction.guild.id, json.dumps(settings))
        )
        await self.bot.db.connection.commit()

        embed = discord.Embed(
            title="🛡️ Guard Sistemi Ayarlandı",
            description=f"**Korumalar:** {korumalar}\n**Log Kanalı:** {log_channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name='guard_durum', description='Guard durumunu gör')
    async def guard_durum(self, interaction: discord.Interaction):
        async with self.bot.db.connection.execute(
            'SELECT settings FROM guard_settings WHERE guild_id = ?',
            (interaction.guild.id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message("❌ Guard sistemi ayarlanmamış!", ephemeral=True)
            return

        settings = json.loads(row[0])
        embed = discord.Embed(
            title="🛡️ Guard Durumu",
            color=discord.Color.green() if settings['enabled'] else discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Durum", value="Aktif" if settings['enabled'] else "Pasif", inline=False)
        embed.add_field(name="Korumalar", value=", ".join(settings['protections']), inline=False)
        await interaction.response.send_message(embed=embed)

    # ==================== BACKUP ====================
    @app_commands.command(name='backup_al', description='Sunucuyu yedekle')
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_al(self, interaction: discord.Interaction):
        await interaction.response.defer()

        guild = interaction.guild
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(self.backup_dir, f"{guild.id}_{timestamp}.json")

        backup_data = {
            'guild_id': guild.id,
            'guild_name': guild.name,
            'created_at': datetime.now().isoformat(),
            'roles': [],
            'channels': [],
            'members': [],
            'emojis': []
        }

        for role in guild.roles:
            if not role.is_default():
                backup_data['roles'].append({
                    'id': role.id,
                    'name': role.name,
                    'color': str(role.color),
                    'permissions': role.permissions.value,
                    'position': role.position,
                    'mentionable': role.mentionable,
                    'hoist': role.hoist
                })

        for channel in guild.channels:
            backup_data['channels'].append({
                'id': channel.id,
                'name': channel.name,
                'type': str(channel.type),
                'position': channel.position,
                'category_id': channel.category_id
            })

        for member in guild.members:
            if not member.bot:
                backup_data['members'].append({
                    'id': member.id,
                    'name': member.name,
                    'nick': member.nick,
                    'roles': [role.id for role in member.roles if not role.is_default()]
                })

        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)

        embed = discord.Embed(
            title="💾 Yedek Alındı",
            description=f"**Dosya:** `{os.path.basename(backup_file)}`\n**Rol:** {len(backup_data['roles'])}\n**Kanal:** {len(backup_data['channels'])}\n**Üye:** {len(backup_data['members'])}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name='backup_liste', description='Yedekleri listele')
    async def backup_liste(self, interaction: discord.Interaction):
        backups = []
        for filename in os.listdir(self.backup_dir):
            if filename.startswith(str(interaction.guild.id)):
                backups.append(filename)

        if not backups:
            await interaction.response.send_message("❌ Yedek bulunamadı!", ephemeral=True)
            return

        embed = discord.Embed(
            title="💾 Yedekler",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        for backup in sorted(backups, reverse=True)[:10]:
            embed.add_field(name=backup, value=f"`{backup}`", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='backup_yukle', description='Yedekten geri yükle')
    @app_commands.describe(filename='Yedek dosyası adı')
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_yukle(self, interaction: discord.Interaction, filename: str):
        await interaction.response.defer()

        backup_file = os.path.join(self.backup_dir, filename)
        if not os.path.exists(backup_file):
            await interaction.followup.send("❌ Yedek dosyası bulunamadı!", ephemeral=True)
            return

        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)

        guild = interaction.guild
        restored = {'roles': 0, 'channels': 0}

        for role_data in backup_data.get('roles', []):
            try:
                role = guild.get_role(role_data['id'])
                if role:
                    await role.edit(
                        name=role_data['name'],
                        color=discord.Color.from_str(role_data['color']),
                        permissions=discord.Permissions(role_data['permissions']),
                        hoist=role_data['hoist'],
                        mentionable=role_data['mentionable']
                    )
                else:
                    await guild.create_role(
                        name=role_data['name'],
                        color=discord.Color.from_str(role_data['color']),
                        permissions=discord.Permissions(role_data['permissions']),
                        hoist=role_data['hoist'],
                        mentionable=role_data['mentionable']
                    )
                restored['roles'] += 1
            except discord.Forbidden:
                pass

        for channel_data in backup_data.get('channels', []):
            try:
                channel = guild.get_channel(channel_data['id'])
                if channel:
                    await channel.edit(name=channel_data['name'])
                else:
                    await guild.create_text_channel(channel_data['name'])
                restored['channels'] += 1
            except discord.Forbidden:
                pass

        embed = discord.Embed(
            title="💾 Yedek Geri Yüklendi",
            description=f"**Rol:** {restored['roles']}\n**Kanal:** {restored['channels']}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name='backup_sil', description='Yedek sil')
    @app_commands.describe(filename='Yedek dosyası adı')
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_sil(self, interaction: discord.Interaction, filename: str):
        backup_file = os.path.join(self.backup_dir, filename)
        if not os.path.exists(backup_file):
            await interaction.response.send_message("❌ Yedek dosyası bulunamadı!", ephemeral=True)
            return

        os.remove(backup_file)
        await interaction.response.send_message(f"✅ `{filename}` silindi!", ephemeral=True)

    # ==================== EVENT GUARD ====================
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        if not await self.check_guard(role.guild.id, 'rol'):
            return

        dangerous_permissions = [
            'administrator', 'manage_guild', 'manage_roles',
            'manage_channels', 'ban_members', 'kick_members'
        ]

        for perm in dangerous_permissions:
            if getattr(role.permissions, perm, False):
                try:
                    await role.delete(reason="Guard: Tehlikeli izinli rol")
                    await self.log_action(role.guild.id, "Rol Silindi", role.name, "Guard", "Tehlikeli izinler")
                except discord.Forbidden:
                    pass
                break

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if not await self.check_guard(channel.guild.id, 'kanal'):
            return

        if channel.name in ['admin', 'moderator', 'staff', 'owner']:
            try:
                await channel.delete(reason="Guard: Şüpheli kanal")
                await self.log_action(channel.guild.id, "Kanal Silindi", channel.name, "Guard", "Şüpheli isim")
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not await self.check_guard(member.guild.id, 'raid'):
            return

        recent_joins = [m for m in member.guild.members if (datetime.now() - m.joined_at).total_seconds() < 10]
        if len(recent_joins) > 5:
            await self.log_action(member.guild.id, "Raid Algılandı", f"{len(recent_joins)} üye", "Guard", "Ani üye artışı")

            for m in recent_joins:
                try:
                    await m.timeout(timedelta(minutes=10), reason="Guard: Raid koruması")
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not await self.check_guard(message.guild.id, 'spam'):
            return

        user_messages = [m async for m in message.channel.history(limit=20) if m.author == message.author]
        if len(user_messages) >= 5:
            time_diff = (user_messages[0].created_at - user_messages[4].created_at).total_seconds()
            if time_diff < 10:
                try:
                    await message.author.timeout(timedelta(minutes=5), reason="Guard: Spam koruması")
                    await self.log_action(message.guild.id, "Spam Algılandı", message.author.mention, "Guard", "Spam")
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        if not await self.check_guard(after.id, 'nuke'):
            return

        # Check if server name changed suspiciously
        if before.name != after.name:
            await self.log_action(after.id, "Sunucu Adı Değişti", f"{before.name} → {after.name}", "Guard", "Şüpheli değişiklik")

        # Check if server icon was removed
        if before.icon and not after.icon:
            await self.log_action(after.id, "Sunucu İkonu Silindi", "İkon silindi", "Guard", "Şüpheli değişiklik")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if not await self.check_guard(channel.guild.id, 'kanal'):
            return

        await self.log_action(channel.guild.id, "Kanal Silindi", channel.name, "Guard", "Kanal silme")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if not await self.check_guard(after.guild.id, 'rol'):
            return

        # Check if dangerous permissions were added
        dangerous_permissions = ['administrator', 'manage_guild', 'manage_roles', 'ban_members', 'kick_members']
        for perm in dangerous_permissions:
            if not getattr(before.permissions, perm, False) and getattr(after.permissions, perm, False):
                try:
                    await after.edit(permissions=before.permissions)
                    await self.log_action(after.guild.id, "Rol İzinleri Geri Alındı", after.name, "Guard", "Tehlikeli izin eklendi")
                except discord.Forbidden:
                    pass
                break

    @commands.Cog.listener()
    async def on_webhook_update(self, channel):
        if not await self.check_guard(channel.guild.id, 'webhook'):
            return

        webhooks = await channel.webhooks()
        for webhook in webhooks:
            if webhook.name in ['Guard', 'Security', 'Anti-Raid']:
                continue
            try:
                await webhook.delete(reason="Guard: Şüpheli webhook")
                await self.log_action(channel.guild.id, "Webhook Silindi", webhook.name, "Guard", "Şüpheli webhook")
            except discord.Forbidden:
                pass

    # ==================== KARANTİNA ====================
    @app_commands.command(name='karantina', description='Kullanıcıyı karantinaya al')
    @app_commands.describe(member='Karantinaya alınacak üye', reason='Karantina nedeni', duration='Süre (örn: 10m, 1h, 1d)')
    @app_commands.checks.has_permissions(administrator=True)
    async def karantina(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Belirtilmedi", duration: str = "1h"):
        # Rol olusturulup tum kanallar duzenlenirken 3 saniyeyi asabilir
        await interaction.response.defer()

        duration_map = {'m': 60, 'h': 3600, 'd': 86400}
        try:
            unit = duration[-1].lower()
            value = int(duration[:-1])
            seconds = value * duration_map[unit]
        except:
            await interaction.followup.send("❌ Geçersiz süre formatı! Örnek: 10m, 1h, 1d", ephemeral=True)
            return

        quarantine_role = discord.utils.get(interaction.guild.roles, name="Karantina")
        if not quarantine_role:
            try:
                quarantine_role = await interaction.guild.create_role(name="Karantina", color=discord.Color.dark_red(), reason="Karantina sistemi")
                for channel in interaction.guild.channels:
                    await channel.set_permissions(quarantine_role, send_messages=False, speak=False)
            except discord.Forbidden:
                await interaction.followup.send("❌ Karantina rolü oluşturulamadı!", ephemeral=True)
                return

        try:
            await member.add_roles(quarantine_role, reason=f"Karantina: {reason}")

            await self.bot.db.connection.execute(
                '''INSERT INTO quarantines (guild_id, user_id, reason, moderator_id, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (interaction.guild.id, member.id, reason, interaction.user.id, datetime.now().isoformat(), (datetime.now() + timedelta(seconds=seconds)).isoformat())
            )
            await self.bot.db.connection.commit()

            await self.log_action(interaction.guild.id, "Karantina", member.mention, interaction.user.mention, reason)

            embed = discord.Embed(title="🔒 Karantina", description=f"{member.mention} üyesi karantinaya alındı! Süre: **{duration}**", color=discord.Color.red(), timestamp=datetime.now())
            await interaction.followup.send(embed=embed)

            asyncio.create_task(self.auto_remove_quarantine(member, quarantine_role, seconds))
        except discord.Forbidden:
            await interaction.followup.send("❌ Bu üyeyi karantinaya alamıyorum!", ephemeral=True)

    @app_commands.command(name='karantina_cikar', description='Karantinadan çıkar')
    @app_commands.describe(member='Karantinadan çıkarılacak üye')
    @app_commands.checks.has_permissions(administrator=True)
    async def karantina_cikar(self, interaction: discord.Interaction, member: discord.Member):
        quarantine_role = discord.utils.get(interaction.guild.roles, name="Karantina")
        if not quarantine_role or quarantine_role not in member.roles:
            await interaction.response.send_message("❌ Bu üye karantinada değil!", ephemeral=True)
            return

        await member.remove_roles(quarantine_role)
        await self.bot.db.connection.execute('DELETE FROM quarantines WHERE guild_id = ? AND user_id = ?', (interaction.guild.id, member.id))
        await self.bot.db.connection.commit()

        embed = discord.Embed(title="🔓 Karantinadan Çıkarıldı", description=f"{member.mention} üyesi karantinadan çıkarıldı!", color=discord.Color.green(), timestamp=datetime.now())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='karantina_liste', description='Karantinadaki üyeleri listele')
    async def karantina_liste(self, interaction: discord.Interaction):
        async with self.bot.db.connection.execute('SELECT user_id, reason, moderator_id, created_at, expires_at FROM quarantines WHERE guild_id = ?', (interaction.guild.id,)) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message("❌ Karantinada üye yok!", ephemeral=True)
            return

        embed = discord.Embed(title="🔒 Karantinadaki Üyeler", color=discord.Color.red(), timestamp=datetime.now())
        for row in rows:
            user = interaction.guild.get_member(row[0])
            moderator = interaction.guild.get_member(row[2])
            user_name = user.mention if user else f"Bilinmiyor ({row[0]})"
            mod_name = moderator.mention if moderator else "Bilinmiyor"
            embed.add_field(name=f"{user_name}", value=f"**Neden:** {row[1]}\n**Yetkili:** {mod_name}\n**Bitiş:** {row[4][:10]}", inline=False)

        await interaction.response.send_message(embed=embed)

    async def auto_remove_quarantine(self, member, role, seconds):
        await asyncio.sleep(seconds)
        try:
            await member.remove_roles(role)
        except:
            pass

    # ==================== SUNUCU KARANTİNASI ====================
    @app_commands.command(name='sunucu_karantina', description='Tüm sunucuyu karantinaya al')
    @app_commands.describe(reason='Karantina nedeni', duration='Süre (örn: 10m, 1h, 1d)')
    @app_commands.checks.has_permissions(administrator=True)
    async def sunucu_karantina(self, interaction: discord.Interaction, reason: str = "Sunucu karantinası", duration: str = "1h"):
        await interaction.response.defer()

        duration_map = {'m': 60, 'h': 3600, 'd': 86400}
        try:
            unit = duration[-1].lower()
            value = int(duration[:-1])
            seconds = value * duration_map[unit]
        except:
            await interaction.followup.send("❌ Geçersiz süre formatı! Örnek: 10m, 1h, 1d", ephemeral=True)
            return

        guild = interaction.guild
        quarantine_role = discord.utils.get(guild.roles, name="Karantina")
        if not quarantine_role:
            try:
                quarantine_role = await guild.create_role(name="Karantina", color=discord.Color.dark_red(), reason="Sunucu karantina sistemi")
            except discord.Forbidden:
                await interaction.response.send_message("❌ Karantina rolü oluşturulamadı!", ephemeral=True)
                return

        locked_channels = []
        for channel in guild.channels:
            try:
                await channel.set_permissions(quarantine_role, send_messages=False, speak=False)
                locked_channels.append(channel.name)
            except discord.Forbidden:
                pass

        try:
            await guild.default_role.set_permissions(send_messages=False, speak=False)
        except discord.Forbidden:
            pass

        await self.bot.db.connection.execute(
            '''INSERT INTO server_quarantines (guild_id, reason, moderator_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?)''',
            (guild.id, reason, interaction.user.id, datetime.now().isoformat(), (datetime.now() + timedelta(seconds=seconds)).isoformat())
        )
        await self.bot.db.connection.commit()

        await self.log_action(guild.id, "Sunucu Karantinası", guild.name, interaction.user.mention, reason)

        embed = discord.Embed(title="🔒 Sunucu Karantinası", description=f"**{guild.name}** sunucusu karantinaya alındı! Süre: **{duration}**", color=discord.Color.red(), timestamp=datetime.now())
        await interaction.followup.send(embed=embed)

        asyncio.create_task(self.auto_unlock_server(guild, quarantine_role, seconds))

    @app_commands.command(name='sunucu_karantina_cikar', description='Sunucu karantinasını kaldır')
    @app_commands.checks.has_permissions(administrator=True)
    async def sunucu_karantina_cikar(self, interaction: discord.Interaction):
        guild = interaction.guild
        quarantine_role = discord.utils.get(guild.roles, name="Karantina")
        if quarantine_role:
            for member in guild.members:
                if quarantine_role in member.roles:
                    try:
                        await member.remove_roles(quarantine_role)
                    except discord.Forbidden:
                        pass

        for channel in guild.channels:
            try:
                await channel.set_permissions(guild.default_role, send_messages=None, speak=None)
            except discord.Forbidden:
                pass

        await self.bot.db.connection.execute('DELETE FROM server_quarantines WHERE guild_id = ?', (guild.id,))
        await self.bot.db.connection.commit()

        embed = discord.Embed(title="🔓 Sunucu Karantinası Kaldırıldı", description=f"**{guild.name}** sunucusunun karantinası kaldırıldı!", color=discord.Color.green(), timestamp=datetime.now())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='sunucu_karantina_durum', description='Sunucu karantina durumunu gör')
    async def sunucu_karantina_durum(self, interaction: discord.Interaction):
        async with self.bot.db.connection.execute('SELECT reason, moderator_id, created_at, expires_at FROM server_quarantines WHERE guild_id = ?', (interaction.guild.id,)) as cursor:
            row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message("❌ Sunucu karantinası yok!", ephemeral=True)
            return

        moderator = interaction.guild.get_member(row[1])
        mod_name = moderator.mention if moderator else "Bilinmiyor"

        embed = discord.Embed(title="🔒 Sunucu Karantina Durumu", color=discord.Color.red(), timestamp=datetime.now())
        embed.add_field(name="Neden", value=row[0], inline=False)
        embed.add_field(name="Yetkili", value=mod_name, inline=False)
        embed.add_field(name="Başlangıç", value=row[2][:10], inline=False)
        embed.add_field(name="Bitiş", value=row[3][:10], inline=False)
        await interaction.response.send_message(embed=embed)

    async def auto_unlock_server(self, guild, quarantine_role, seconds):
        await asyncio.sleep(seconds)
        try:
            for channel in guild.channels:
                try:
                    await channel.set_permissions(guild.default_role, send_messages=None, speak=None)
                except discord.Forbidden:
                    pass

            for member in guild.members:
                if quarantine_role in member.roles:
                    try:
                        await member.remove_roles(quarantine_role)
                    except discord.Forbidden:
                        pass

            await self.bot.db.connection.execute('DELETE FROM server_quarantines WHERE guild_id = ?', (guild.id,))
            await self.bot.db.connection.commit()
        except:
            pass

async def setup(bot):
    await bot.add_cog(Guard(bot))
