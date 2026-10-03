import discord
from discord.ext import commands
from datetime import datetime

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Called when the bot joins a guild"""
        self.bot.logger.info(f"Joined guild: {guild.name} ({guild.id})")

        # Send welcome message to system channel
        if guild.system_channel:
            try:
                embed = discord.Embed(
                    title="👋 Merhaba!",
                    description="Ben bir Discord botuyum! `/help` yazarak komutlarımı görebilirsin.",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                await guild.system_channel.send(embed=embed)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Called when the bot leaves a guild"""
        self.bot.logger.info(f"Left guild: {guild.name} ({guild.id})")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Called when a member joins the guild"""
        settings = await self.bot.db.get_settings(member.guild.id)
        if not settings:
            return

        # Welcome message
        if settings.get('welcome_channel_id'):
            channel = self.bot.get_channel(settings['welcome_channel_id'])
            if channel:
                msg = settings.get('welcome_message', '🎉 {member} sunucuya katıldı!')
                await channel.send(msg.format(member=member.mention))

        # Auto role
        if settings.get('autorole_id'):
            role = member.guild.get_role(settings['autorole_id'])
            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Called when a member leaves the guild"""
        settings = await self.bot.db.get_settings(member.guild.id)
        if not settings:
            return

        if settings.get('leave_channel_id'):
            channel = self.bot.get_channel(settings['leave_channel_id'])
            if channel:
                msg = settings.get('leave_message', '👋 {member} sunucudan ayrıldı!')
                await channel.send(msg.format(member=member.mention))

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Called when a message is deleted"""
        if message.author.bot:
            return

        settings = await self.bot.db.get_settings(message.guild.id)
        if not settings or not settings.get('log_channel_id'):
            return

        channel = self.bot.get_channel(settings['log_channel_id'])
        if channel:
            embed = discord.Embed(
                title="🗑️ Mesaj Silindi",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Kanal", value=message.channel.mention, inline=False)
            embed.add_field(name="İçerik", value=message.content[:1024] or "Boş", inline=False)
            embed.add_field(name="Yazar", value=message.author.mention, inline=False)
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Called when a message is edited"""
        if before.author.bot:
            return

        settings = await self.bot.db.get_settings(before.guild.id)
        if not settings or not settings.get('log_channel_id'):
            return

        channel = self.bot.get_channel(settings['log_channel_id'])
        if channel:
            embed = discord.Embed(
                title="✏️ Mesaj Düzenlendi",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Kanal", value=before.channel.mention, inline=False)
            embed.add_field(name="Önce", value=before.content[:1024] or "Boş", inline=False)
            embed.add_field(name="Sonra", value=after.content[:1024] or "Boş", inline=False)
            embed.add_field(name="Yazar", value=before.author.mention, inline=False)
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Called when a member's voice state changes"""
        settings = await self.bot.db.get_settings(member.guild.id)
        if not settings or not settings.get('log_channel_id'):
            return

        channel = self.bot.get_channel(settings['log_channel_id'])
        if not channel:
            return

        if before.channel != after.channel:
            if after.channel:
                embed = discord.Embed(
                    title="🔊 Ses Kanalına Katıldı",
                    description=f"{member.mention} → {after.channel.mention}",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
            else:
                embed = discord.Embed(
                    title="🔇 Ses Kanaldan Ayrıldı",
                    description=f"{member.mention} ← {before.channel.mention}",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Called when a member's profile is updated"""
        settings = await self.bot.db.get_settings(after.guild.id)
        if not settings or not settings.get('log_channel_id'):
            return

        channel = self.bot.get_channel(settings['log_channel_id'])
        if not channel:
            return

        # Nickname change
        if before.nick != after.nick:
            embed = discord.Embed(
                title="📝 Takma Ad Değiştirildi",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Üye", value=after.mention, inline=False)
            embed.add_field(name="Önce", value=before.nick or "Yok", inline=False)
            embed.add_field(name="Sonra", value=after.nick or "Yok", inline=False)
            await channel.send(embed=embed)

        # Role change
        if before.roles != after.roles:
            added = set(after.roles) - set(before.roles)
            removed = set(before.roles) - set(after.roles)

            if added:
                embed = discord.Embed(
                    title="✅ Rol Eklendi",
                    description=f"{after.mention} → {', '.join([r.mention for r in added])}",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                await channel.send(embed=embed)

            if removed:
                embed = discord.Embed(
                    title="❌ Rol Kaldırıldı",
                    description=f"{after.mention} ← {', '.join([r.mention for r in removed])}",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Called when a channel is created"""
        settings = await self.bot.db.get_settings(channel.guild.id)
        if not settings or not settings.get('log_channel_id'):
            return

        log_channel = self.bot.get_channel(settings['log_channel_id'])
        if log_channel:
            embed = discord.Embed(
                title="📺 Kanal Oluşturuldu",
                description=f"{channel.mention}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Called when a channel is deleted"""
        settings = await self.bot.db.get_settings(channel.guild.id)
        if not settings or not settings.get('log_channel_id'):
            return

        log_channel = self.bot.get_channel(settings['log_channel_id'])
        if log_channel:
            embed = discord.Embed(
                title="🗑️ Kanal Silindi",
                description=f"{channel.name}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        """Called when a role is created"""
        settings = await self.bot.db.get_settings(role.guild.id)
        if not settings or not settings.get('log_channel_id'):
            return

        channel = self.bot.get_channel(settings['log_channel_id'])
        if channel:
            embed = discord.Embed(
                title="✅ Rol Oluşturuldu",
                description=f"{role.mention}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        """Called when a role is deleted"""
        settings = await self.bot.db.get_settings(role.guild.id)
        if not settings or not settings.get('log_channel_id'):
            return

        channel = self.bot.get_channel(settings['log_channel_id'])
        if channel:
            embed = discord.Embed(
                title="❌ Rol Silindi",
                description=f"{role.name}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Events(bot))
