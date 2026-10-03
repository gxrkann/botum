import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import json
import os

class VoiceTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_data = {}
        self.data_file = "voice_data.json"
        self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.voice_data = json.load(f)
            except:
                self.voice_data = {}

    def save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.voice_data, f, indent=2)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        user_id = str(member.id)
        guild_id = str(member.guild.id)

        if guild_id not in self.voice_data:
            self.voice_data[guild_id] = {}

        if user_id not in self.voice_data[guild_id]:
            self.voice_data[guild_id][user_id] = {
                'total_seconds': 0,
                'sessions': []
            }

        # User joined a voice channel
        if not before.channel and after.channel:
            self.voice_data[guild_id][user_id]['join_time'] = datetime.now().isoformat()

        # User left a voice channel
        if before.channel and not after.channel:
            join_time_str = self.voice_data[guild_id][user_id].get('join_time')
            if join_time_str:
                join_time = datetime.fromisoformat(join_time_str)
                session_duration = (datetime.now() - join_time).total_seconds()
                self.voice_data[guild_id][user_id]['total_seconds'] += session_duration
                self.voice_data[guild_id][user_id]['sessions'].append({
                    'join': join_time_str,
                    'leave': datetime.now().isoformat(),
                    'duration': session_duration
                })
                self.save_data()

    @app_commands.command(name='ses_surem', description='Kendi ses süreni gör')
    async def ses_surem(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        if guild_id not in self.voice_data or user_id not in self.voice_data[guild_id]:
            await interaction.response.send_message("❌ Henüz ses kanalına girmedin!", ephemeral=True)
            return

        total_seconds = self.voice_data[guild_id][user_id]['total_seconds']

        # Add current session if in voice
        join_time_str = self.voice_data[guild_id][user_id].get('join_time')
        if join_time_str and interaction.user.voice:
            join_time = datetime.fromisoformat(join_time_str)
            total_seconds += (datetime.now() - join_time).total_seconds()

        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)

        embed = discord.Embed(
            title="🎤 Ses Süren",
            description=f"**{hours}s {minutes}d {seconds}sn**",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='ses_liste', description='Ses süreleri sıralaması')
    async def ses_liste(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)

        if guild_id not in self.voice_data or not self.voice_data[guild_id]:
            await interaction.response.send_message("❌ Henüz ses verisi yok!", ephemeral=True)
            return

        # Calculate total seconds for each user
        user_times = []
        for user_id, data in self.voice_data[guild_id].items():
            total_seconds = data['total_seconds']

            # Add current session if in voice
            member = interaction.guild.get_member(int(user_id))
            if member and member.voice:
                join_time_str = data.get('join_time')
                if join_time_str:
                    join_time = datetime.fromisoformat(join_time_str)
                    total_seconds += (datetime.now() - join_time).total_seconds()

            user_times.append((user_id, total_seconds))

        # Sort by total seconds
        user_times.sort(key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title="🎤 Ses Süreleri Sıralaması",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        for i, (user_id, total_seconds) in enumerate(user_times[:10], 1):
            member = interaction.guild.get_member(int(user_id))
            user_name = member.mention if member else f"Bilinmiyor ({user_id})"
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            embed.add_field(
                name=f"{i}. {user_name}",
                value=f"{hours}s {minutes}d",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='ses_detay', description='Bir üyenin ses detaylarını gör')
    @app_commands.describe(member='Üye')
    async def ses_detay(self, interaction: discord.Interaction, member: discord.Member):
        user_id = str(member.id)
        guild_id = str(interaction.guild.id)

        if guild_id not in self.voice_data or user_id not in self.voice_data[guild_id]:
            await interaction.response.send_message("❌ Bu üyenin ses verisi yok!", ephemeral=True)
            return

        data = self.voice_data[guild_id][user_id]
        total_seconds = data['total_seconds']

        # Add current session if in voice
        join_time_str = data.get('join_time')
        if join_time_str and member.voice:
            join_time = datetime.fromisoformat(join_time_str)
            total_seconds += (datetime.now() - join_time).total_seconds()

        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)

        embed = discord.Embed(
            title=f"🎤 {member.name} Ses Detayları",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Toplam Süre", value=f"{hours}s {minutes}d {seconds}sn", inline=False)
        embed.add_field(name="Oturum Sayısı", value=f"{len(data['sessions'])}", inline=False)

        # Show recent sessions
        recent_sessions = data['sessions'][-5:]
        if recent_sessions:
            session_text = ""
            for session in recent_sessions:
                duration = session['duration']
                mins = int(duration // 60)
                session_text += f"• {mins} dakika\n"
            embed.add_field(name="Son Oturumlar", value=session_text, inline=False)

        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(VoiceTracker(bot))
