import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='hatirlat', description='Hatırlatma oluştur')
    @app_commands.describe(
        time='Süre (örn: 10m, 1h, 1d)',
        reminder='Hatırlatma mesajı'
    )
    async def remind(self, interaction: discord.Interaction, time: str, reminder: str):
        duration_map = {'m': 60, 'h': 3600, 'd': 86400}
        try:
            unit = time[-1].lower()
            value = int(time[:-1])
            seconds = value * duration_map[unit]
        except:
            await interaction.response.send_message("❌ Geçersiz süre formatı! Örnek: 10m, 1h, 1d", ephemeral=True)
            return

        remind_at = datetime.now() + timedelta(seconds=seconds)
        await self.bot.db.add_reminder(interaction.user.id, interaction.guild.id, reminder, remind_at.isoformat())

        embed = discord.Embed(
            title="⏰ Hatırlatma Oluşturuldu",
            description=f"**{time}** sonra hatırlatacağım: {reminder}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

        await asyncio.sleep(seconds)
        await interaction.user.send(f"🔔 Hatırlatma: **{reminder}**")

    @app_commands.command(name='geri_sayim', description='Geri sayım başlat')
    @app_commands.describe(time='Süre (örn: 10m, 1h)')
    async def timer(self, interaction: discord.Interaction, time: str):
        duration_map = {'m': 60, 'h': 3600, 'd': 86400}
        try:
            unit = time[-1].lower()
            value = int(time[:-1])
            seconds = value * duration_map[unit]
        except:
            await interaction.response.send_message("❌ Geçersiz süre formatı! Örnek: 10m, 1h", ephemeral=True)
            return

        embed = discord.Embed(
            title="⏱️ Geri Sayım",
            description=f"**{time}** kaldı!",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        message = await interaction.response.send_message(embed=embed)

        while seconds > 0:
            await asyncio.sleep(1)
            seconds -= 1
            minutes, secs = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            time_str = f"{hours}:{minutes:02d}:{secs:02d}" if hours > 0 else f"{minutes}:{secs:02d}"
            embed.description = f"**{time_str}** kaldı!"
            await message.edit(embed=embed)

        embed = discord.Embed(
            title="⏰ Süre Doldu!",
            description="Geri sayım tamamlandı!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await message.edit(embed=embed)

    @app_commands.command(name='gecikme', description='Bot gecikmesini ölç')
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Gecikme: **{latency}ms**",
            color=discord.Color.green() if latency < 100 else discord.Color.orange() if latency < 200 else discord.Color.red(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='davet', description='Bot davet linkini al')
    async def invite(self, interaction: discord.Interaction):
        invite_url = f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot%20applications.commands"
        embed = discord.Embed(
            title="📨 Bot Davet Linki",
            description=f"[Botu sunucuna ekle]({invite_url})",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='destek', description='Destek sunucusuna katıl')
    async def support(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🆘 Destek",
            description="Destek almak için [buraya tıkla](https://discord.gg/support)",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='oy_ver', description='Bota oy ver')
    async def vote(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🗳️ Bota Oy Ver",
            description="Bota oy vermek için [buraya tıkla](https://top.gg/bot/your-bot-id/vote)",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='istatistik', description='Bot istatistiklerini göster')
    async def stats(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📊 Bot İstatistikleri",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Sunucu Sayısı", value=f"{len(self.bot.guilds)}", inline=True)
        embed.add_field(name="Kullanıcı Sayısı", value=f"{sum(g.member_count for g in self.bot.guilds)}", inline=True)
        embed.add_field(name="Kanal Sayısı", value=f"{sum(len(g.channels) for g in self.bot.guilds)}", inline=True)
        embed.add_field(name="Gecikme", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Uptime", value=self.get_uptime(), inline=True)
        embed.add_field(name="Komut Sayısı", value=f"{len(self.bot.tree.get_commands())}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='calisma_suresi', description='Botun çalışma süresini göster')
    async def uptime(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⏱️ Uptime",
            description=self.get_uptime(),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='hava_durumu', description='Hava durumu bilgisi')
    @app_commands.describe(city='Şehir adı')
    async def weather(self, interaction: discord.Interaction, city: str):
        # This is a placeholder - you'd need a weather API key
        embed = discord.Embed(
            title=f"🌤️ {city} Hava Durumu",
            description="Hava durumu API'si bağlı değil. Lütfen bir API anahtarı ekleyin.",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='ceviri', description='Metin çevir')
    @app_commands.describe(
        text='Çevrilecek metin',
        from_lang='Kaynak dil (örn: tr, en)',
        to_lang='Hedef dil (örn: en, de)'
    )
    async def translate(self, interaction: discord.Interaction, text: str, from_lang: str = "tr", to_lang: str = "en"):
        # This is a placeholder - you'd need a translation API
        embed = discord.Embed(
            title="🌐 Çeviri",
            description=f"**{from_lang} → {to_lang}**\n\n{text}\n\n(Çeviri API'si bağlı değil)",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='link_kisit', description='URL kısalt')
    @app_commands.describe(url='Kısaltılacak URL')
    async def shorten(self, interaction: discord.Interaction, url: str):
        # This is a placeholder - you'd need a URL shortener API
        embed = discord.Embed(
            title="🔗 URL Kısalt",
            description=f"Orijinal: {url}\nKısaltılmış: (API bağlı değil)",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='qr_kod', description='QR kod oluştur')
    @app_commands.describe(text='QR kod içeriği')
    async def qr(self, interaction: discord.Interaction, text: str):
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={text}"
        embed = discord.Embed(
            title="📱 QR Kod",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_image(url=qr_url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='ekran_goruntu', description='Web sitesi görüntüsü al')
    @app_commands.describe(url='Web sitesi URL\'si')
    async def screenshot(self, interaction: discord.Interaction, url: str):
        # This is a placeholder - you'd need a screenshot API
        embed = discord.Embed(
            title="📸 Ekran Görüntüsü",
            description=f"URL: {url}\n(Ekran görüntüsü API'si bağlı değil)",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='btc_fiyat', description='Bitcoin fiyatı')
    async def bitcoin(self, interaction: discord.Interaction):
        # This is a placeholder - you'd need a crypto API
        embed = discord.Embed(
            title="₿ Bitcoin Fiyatı",
            description="Kripto API'si bağlı değil.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='github_bilgi', description='GitHub kullanıcı bilgileri')
    @app_commands.describe(username='GitHub kullanıcı adı')
    async def github(self, interaction: discord.Interaction, username: str):
        # This is a placeholder - you'd need to use GitHub API
        embed = discord.Embed(
            title=f"🐙 {username} GitHub Profili",
            description="GitHub API'si bağlı değil.",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='npm_bilgi', description='npm paket bilgileri')
    @app_commands.describe(package='Paket adı')
    async def npm(self, interaction: discord.Interaction, package: str):
        # This is a placeholder - you'd need to use npm API
        embed = discord.Embed(
            title=f"📦 {package} Paketi",
            description="npm API'si bağlı değil.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='sozluk', description='Urban Dictionary tanımı')
    @app_commands.describe(word='Kelime')
    async def urban(self, interaction: discord.Interaction, word: str):
        # This is a placeholder - you'd need to use Urban Dictionary API
        embed = discord.Embed(
            title=f"📖 {word}",
            description="Urban Dictionary API'si bağlı değil.",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    def get_uptime(self) -> str:
        """Calculate bot uptime"""
        # This is a simplified version - you'd track actual start time
        return "Bilgi mevcut değil"

async def setup(bot):
    await bot.add_cog(Utility(bot))
