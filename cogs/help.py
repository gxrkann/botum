import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='help', description='Yardım menüsünü göster')
    @app_commands.describe(category='Kategori (opsiyonel)')
    async def help(self, interaction: discord.Interaction, category: str = None):
        if category:
            await self.show_category_help(interaction, category.lower())
        else:
            await self.show_main_help(interaction)

    async def show_main_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Bot Yardım Menüsü",
            description="Aşağıdaki kategorilerden birini seçerek detaylı bilgi alabilirsin.",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        categories = {
            "🛡️ **Moderasyon**": "Ban, kick, mute, warn, slowmode, temizleme ve daha fazlası",
            "🎵 **Müzik**": "Müzik çalma, sıra yönetimi, tekrar modu ve daha fazlası",
            "💰 **Ekonomi**": "Para kazanma, banka, transfer, çalışma ve daha fazlası",
            "📊 **Seviye**": "XP, seviye, sıralama ve daha fazlası",
            "🎉 **Eğlence**": "Oyunlar, şakalar, anketler ve daha fazlası",
            "🔧 **Yardımcı**": "Hatırlatma, timer, ping, istatistik ve daha fazlası",
        }

        for name, desc in categories.items():
            embed.add_field(name=name, value=desc, inline=False)

        embed.set_footer(text=f"Bot sahibi: {self.bot.get_user(int(self.bot.owner_id)) if hasattr(self.bot, 'owner_id') else 'Bilinmiyor'}")

        # Create buttons
        view = discord.ui.View()
        for category in ["moderation", "music", "economy", "levels", "fun", "utility"]:
            button = discord.ui.Button(
                label=category.capitalize(),
                style=discord.ButtonStyle.primary,
                custom_id=f"help_{category}"
            )
            button.callback = self.help_button_callback
            view.add_item(button)

        await interaction.response.send_message(embed=embed, view=view)

    async def show_category_help(self, interaction: discord.Interaction, category: str):
        commands_list = {
            "moderation": [
                ("/ban", "Üye yasakla"),
                ("/kick", "Üye at"),
                ("/mute", "Üye sustur"),
                ("/unmute", "Susturmayı kaldır"),
                ("/warn", "Uyarı ver"),
                ("/warnings", "Uyarıları gör"),
                ("/clear", "Mesaj sil"),
                ("/slowmode", "Yavaş mod"),
                ("/lock", "Kanal kilitle"),
                ("/unlock", "Kanal aç"),
                ("/nick", "Takma ad değiştir"),
                ("/role_add", "Rol ekle"),
                ("/role_remove", "Rol kaldır"),
            ],
            "music": [
                ("/play", "Müzik çal"),
                ("/skip", "Şarkı atla"),
                ("/pause", "Duraklat"),
                ("/resume", "Devam et"),
                ("/stop", "Durdur"),
                ("/queue", "Sırayı göster"),
                ("/loop", "Tekrar modu"),
                ("/volume", "Ses seviyesi"),
                ("/nowplaying", "Şimdi çalan"),
                ("/disconnect", "Botu ayır"),
            ],
            "fun": [
                ("/yazitura", "Yazı tura"),
                ("/zar", "Zar at"),
                ("/8ball", "8-Ball"),
                ("/meme", "Meme"),
                ("/avatar", "Avatar"),
                ("/servericon", "Sunucu ikonu"),
                ("/serverinfo", "Sunucu bilgisi"),
                ("/userinfo", "Kullanıcı bilgisi"),
                ("/poll", "Anket"),
                ("/guess", "Sayı tahmin"),
                ("/rps", "Taş kağıt makas"),
                ("/joke", "Şaka"),
                ("/ship", "Eşleştir"),
            ],
            "utility": [
                ("/remind", "Hatırlatma"),
                ("/timer", "Geri sayım"),
                ("/ping", "Gecikme"),
                ("/invite", "Davet linki"),
                ("/support", "Destek"),
                ("/vote", "Oy ver"),
                ("/stats", "İstatistik"),
                ("/uptime", "Çalışma süresi"),
                ("/qr", "QR kod"),
            ],
        }

        if category not in commands_list:
            await interaction.response.send_message("❌ Geçersiz kategori!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📖 {category.capitalize()} Komutları",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        for cmd, desc in commands_list[category]:
            embed.add_field(name=cmd, value=desc, inline=False)

        await interaction.response.send_message(embed=embed)

    async def help_button_callback(self, interaction: discord.Interaction):
        category = interaction.custom_id.replace("help_", "")
        await self.show_category_help(interaction, category)

async def setup(bot):
    await bot.add_cog(Help(bot))
