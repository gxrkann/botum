import discord
from discord.ext import commands
from discord import app_commands
import random
import math
from datetime import datetime, timedelta

class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate XP required for a level"""
        return int(5 * (level ** 2) + 50 * level + 100)

    def calculate_level_from_xp(self, xp: int) -> int:
        """Calculate level from total XP"""
        level = 0
        while xp >= self.calculate_xp_for_level(level):
            xp -= self.calculate_xp_for_level(level)
            level += 1
        return level

    @app_commands.command(name='rank', description='Seviye kartını gör')
    @app_commands.describe(member='Seviyesi görüntülenecek üye (opsiyonel)')
    async def rank(self, interaction: discord.Interaction, member: discord.Member | None = None):
        member = member or interaction.user
        data = await self.bot.db.get_level(member.id, interaction.guild.id)

        if not data:
            await interaction.response.send_message("❌ Bu üye henüz seviye kazanmamış!", ephemeral=True)
            return

        xp = data['xp']
        level = data['level']
        messages = data['messages']

        xp_for_current = self.calculate_xp_for_level(level)
        xp_for_next = self.calculate_xp_for_level(level + 1)
        progress = (xp - xp_for_current) / (xp_for_next - xp_for_current) * 100

        embed = discord.Embed(
            title=f"📊 {member.name} Seviye Kartı",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Seviye", value=f"**{level}**", inline=True)
        embed.add_field(name="Toplam XP", value=f"**{xp}**", inline=True)
        embed.add_field(name="Mesaj", value=f"**{messages}**", inline=True)
        embed.add_field(name="Sonraki Seviye", value=f"{xp_for_next - xp} XP kaldı", inline=False)

        # Progress bar
        bar_length = 20
        filled = int(bar_length * progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        embed.add_field(name="İlerleme", value=f"`{bar}` %{progress:.1f}", inline=False)

        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='leaderboard', description='Seviye sıralaması')
    async def leaderboard(self, interaction: discord.Interaction):
        async with self.bot.db.connection.execute(
            'SELECT user_id, xp, level, messages FROM levels WHERE guild_id = ? ORDER BY xp DESC LIMIT 10',
            (interaction.guild.id,)
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message("❌ Henüz kimse seviye kazanmamış!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 Seviye Sıralaması",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(rows):
            user = interaction.guild.get_member(row[0])
            if user:
                medal = medals[i] if i < 3 else f"**{i+1}.**"
                embed.add_field(
                    name=f"{medal} {user.name}",
                    value=f"Seviye: {row[2]} | XP: {row[1]} | Mesaj: {row[3]}",
                    inline=False
                )

        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # Cooldown check
        user_id = message.author.id
        guild_id = message.guild.id
        cooldown_key = f"{user_id}_{guild_id}"

        if cooldown_key in self.cooldowns:
            if datetime.now() - self.cooldowns[cooldown_key] < timedelta(seconds=60):
                return

        self.cooldowns[cooldown_key] = datetime.now()

        # Add XP
        xp_gained = random.randint(15, 25)
        await self.bot.db.update_xp(user_id, guild_id, xp_gained)

        # Check level up
        data = await self.bot.db.get_level(user_id, guild_id)
        if data:
            new_level = self.calculate_level_from_xp(data['xp'])
            if new_level > data['level']:
                await self.bot.db.set_level(user_id, guild_id, new_level)

                # Send level up message
                settings = await self.bot.db.get_settings(guild_id)
                if settings and settings.get('levelup_channel_id'):
                    channel = self.bot.get_channel(settings['levelup_channel_id'])
                    if channel:
                        msg = settings.get('levelup_message', '🎉 {member} seviye atladı! Yeni seviye: **{level}**')
                        await channel.send(msg.format(member=message.author.mention, level=new_level))
                        return

                await message.channel.send(f"🎉 Tebrikler {message.author.mention}! **{new_level}** seviyeye ulaştın!")

async def setup(bot):
    await bot.add_cog(Levels(bot))
