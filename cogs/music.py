import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import re
from urllib.parse import urlparse

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.current = {}
        self.loop_mode = {}
        # yt_dlp agir bir modul - sadece gercekten kullanilanda yukle
        self._yt_dlp = None
        self.volumes = {}

        self.ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
        }

        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

    def get_queue(self, guild_id: int):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]

    def get_loop_mode(self, guild_id: int):
        if guild_id not in self.loop_mode:
            self.loop_mode[guild_id] = 'off'
        return self.loop_mode[guild_id]

    def get_volume(self, guild_id: int):
        if guild_id not in self.volumes:
            self.volumes[guild_id] = 100
        return self.volumes[guild_id]

    async def play_next(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        queue = self.get_queue(guild_id)
        loop_mode = self.get_loop_mode(guild_id)

        if loop_mode == 'one' and self.current.get(guild_id):
            queue.insert(0, self.current[guild_id])
        elif loop_mode == 'all' and self.current.get(guild_id):
            queue.append(self.current[guild_id])

        if not queue:
            self.current[guild_id] = None
            return

        song = queue.pop(0)
        self.current[guild_id] = song

        try:
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_connected():
                source = discord.FFmpegPCMAudio(song['url'], **self.ffmpeg_options)
                volume = self.get_volume(guild_id) / 100
                source = discord.PCMVolumeTransformer(source, volume=volume)

                voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.play_next(interaction), self.bot.loop
                ))

                embed = discord.Embed(
                    title="🎵 Şimdi Çalıyor",
                    description=f"[{song['title']}]({song['webpage_url']})",
                    color=discord.Color.green()
                )
                embed.add_field(name="Süre", value=song.get('duration', 'Bilinmiyor'), inline=True)
                embed.add_field(name="İsteyen", value=song['requester'].mention, inline=True)
                if song.get('thumbnail'):
                    embed.set_thumbnail(url=song['thumbnail'])

                await interaction.channel.send(embed=embed)
        except Exception as e:
            print(f"Music play error: {e}")
            await self.play_next(interaction)

    @app_commands.command(name='play', description='Müzik çal')
    @app_commands.describe(query='Şarkı adı veya YouTube/Spotify linki')
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        # Check voice channel
        if not interaction.user.voice:
            await interaction.followup.send("❌ Bir ses kanalına bağlı olmalısın!", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        voice_client = interaction.guild.voice_client

        if voice_client and voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
        elif not voice_client:
            voice_client = await voice_channel.connect()

        # Search for song
        try:
            # yt_dlp agir bir modul - ilk kullanimda yukle
            if self._yt_dlp is None:
                try:
                    import yt_dlp
                    self._yt_dlp = yt_dlp
                except ImportError:
                    await interaction.response.send_message(
                        "❌ yt-dlp kurulu değil! Müzik komutları çalışmaz.", ephemeral=True)
                    return

            with self._yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                if 'entries' in info:
                    info = info['entries'][0]

                song = {
                    'title': info['title'],
                    'url': info['url'],
                    'webpage_url': info['webpage_url'],
                    'duration': self.format_duration(info.get('duration', 0)),
                    'thumbnail': info.get('thumbnail'),
                    'requester': interaction.user
                }

                queue = self.get_queue(interaction.guild.id)
                queue.append(song)

                if not voice_client.is_playing():
                    await self.play_next(interaction)
                else:
                    embed = discord.Embed(
                        title="🎵 Sıraya Eklendi",
                        description=f"[{song['title']}]({song['webpage_url']})",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Sıra", value=f"{len(queue)}", inline=True)
                    await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Müzik bulunamadı: {e}", ephemeral=True)

    @app_commands.command(name='skip', description='Şimdi çalan şarkıyı atla')
    async def skip(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            await interaction.response.send_message("❌ Şu an çalan bir şey yok!", ephemeral=True)
            return

        voice_client.stop()
        await interaction.response.send_message("⏭️ Şarkı atlandı!")

    @app_commands.command(name='pause', description='Müziği duraklat')
    async def pause(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            await interaction.response.send_message("❌ Şu an çalan bir şey yok!", ephemeral=True)
            return

        voice_client.pause()
        await interaction.response.send_message("⏸️ Müzik duraklatıldı!")

    @app_commands.command(name='resume', description='Müziği devam ettir')
    async def resume(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_paused():
            await interaction.response.send_message("❌ Müzik duraklatılmamış!", ephemeral=True)
            return

        voice_client.resume()
        await interaction.response.send_message("▶️ Müzik devam ediyor!")

    @app_commands.command(name='stop', description='Müziği durdur ve sırayı temizle')
    async def stop(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client:
            await interaction.response.send_message("❌ Bir ses kanalında değilim!", ephemeral=True)
            return

        self.queues[interaction.guild.id] = []
        self.current[interaction.guild.id] = None
        voice_client.stop()
        await interaction.response.send_message("⏹️ Müzik durduruldu ve sıra temizlendi!")

    @app_commands.command(name='queue', description='Çalma sırasını göster')
    async def queue(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        current = self.current.get(interaction.guild.id)

        if not current and not queue:
            await interaction.response.send_message("❌ Sıra boş!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎵 Çalma Sırası",
            color=discord.Color.blue()
        )

        if current:
            embed.add_field(
                name="Şimdi Çalıyor",
                value=f"[{current['title']}]({current['webpage_url']})",
                inline=False
            )

        if queue:
            queue_text = ""
            for i, song in enumerate(queue[:10], 1):
                queue_text += f"{i}. [{song['title']}]({song['webpage_url']})\n"
            if len(queue) > 10:
                queue_text += f"... ve {len(queue) - 10} şarkı daha"
            embed.add_field(name="Sıra", value=queue_text, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='loop', description='Tekrar modunu ayarla')
    @app_commands.describe(mode='Tekrar modu: off, one, all')
    @app_commands.choices(mode=[
        app_commands.Choice(name='Kapalı', value='off'),
        app_commands.Choice(name='Tek Şarkı', value='one'),
        app_commands.Choice(name='Tüm Sıra', value='all')
    ])
    async def loop(self, interaction: discord.Interaction, mode: str):
        self.loop_mode[interaction.guild.id] = mode
        mode_names = {'off': 'Kapalı', 'one': 'Tek Şarkı', 'all': 'Tüm Sıra'}
        await interaction.response.send_message(f"🔁 Tekrar modu: **{mode_names[mode]}**")

    @app_commands.command(name='volume', description='Ses seviyesini ayarla')
    @app_commands.describe(volume='Ses seviyesi (0-100)')
    async def volume(self, interaction: discord.Interaction, volume: int):
        if volume < 0 or volume > 100:
            await interaction.response.send_message("❌ 0-100 arasında bir sayı gir!", ephemeral=True)
            return

        self.volumes[interaction.guild.id] = volume
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.source:
            voice_client.source.volume = volume / 100

        await interaction.response.send_message(f"🔊 Ses seviyesi: **{volume}%**")

    @app_commands.command(name='nowplaying', description='Şimdi çalan şarkıyı göster')
    async def nowplaying(self, interaction: discord.Interaction):
        current = self.current.get(interaction.guild.id)
        if not current:
            await interaction.response.send_message("❌ Şu an çalan bir şey yok!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎵 Şimdi Çalıyor",
            description=f"[{current['title']}]({current['webpage_url']})",
            color=discord.Color.green()
        )
        embed.add_field(name="Süre", value=current.get('duration', 'Bilinmiyor'), inline=True)
        embed.add_field(name="İsteyen", value=current['requester'].mention, inline=True)
        if current.get('thumbnail'):
            embed.set_thumbnail(url=current['thumbnail'])

        await interaction.response.send_message(embed=embed)

    def format_duration(self, seconds: int) -> str:
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

async def setup(bot):
    await bot.add_cog(Music(bot))
