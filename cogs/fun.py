import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='yazitura', description='Yazı tura at')
    async def yazitura(self, interaction: discord.Interaction):
        result = random.choice(["Yazı", "Tura"])
        emoji = "🪙" if result == "Yazı" else "👑"
        embed = discord.Embed(
            title=f"{emoji} {result}!",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='zar', description='Zar at')
    async def zar(self, interaction: discord.Interaction):
        dice = random.randint(1, 6)
        embed = discord.Embed(
            title=f"🎲 Zar: {dice}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='8ball', description='Sihirli 8 topuna soru sor')
    @app_commands.describe(question='Soru')
    async def eightball(self, interaction: discord.Interaction, question: str):
        responses = [
            "✅ Kesinlikle!", "✅ Evet!", "✅ Tabii ki!", "✅ Şüphesiz!",
            "🤔 Belki...", "🤔 Bilmiyorum...", "🤔 Daha sonra tekrar sor.",
            "❌ Hayır!", "❌ Asla!", "❌ İmkansız!", "❌ Kesinlikle hayır!",
        ]
        response = random.choice(responses)
        embed = discord.Embed(
            title="🎱 8-Ball",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Soru", value=question, inline=False)
        embed.add_field(name="Cevap", value=response, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='meme', description='Rastgele meme gönder')
    async def meme(self, interaction: discord.Interaction):
        memes = [
            "https://i.imgur.com/4BSr0v4.jpg",
            "https://i.imgur.com/3JZ8Z8Z.jpg",
            "https://i.imgur.com/5KZ9Z9Z.jpg",
        ]
        embed = discord.Embed(
            title="😂 Meme",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.set_image(url=random.choice(memes))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='avatar', description='Bir üyenin avatarını göster')
    @app_commands.describe(member='Avatarı gösterilecek üye')
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        embed = discord.Embed(
            title=f"🖼️ {member.name} Avatarı",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='servericon', description='Sunucu ikonunu göster')
    async def servericon(self, interaction: discord.Interaction):
        if not interaction.guild.icon:
            await interaction.response.send_message("❌ Bu sunucunun ikonu yok!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🖼️ {interaction.guild.name} İkonu",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_image(url=interaction.guild.icon.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='serverinfo', description='Sunucu bilgilerini göster')
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(
            title=f"📋 {guild.name} Bilgileri",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="ID", value=guild.id, inline=True)
        embed.add_field(name="Sahip", value=guild.owner.mention if guild.owner else "Bilinmiyor", inline=True)
        embed.add_field(name="Üye Sayısı", value=guild.member_count, inline=True)
        embed.add_field(name="Kanal Sayısı", value=len(guild.channels), inline=True)
        embed.add_field(name="Rol Sayısı", value=len(guild.roles), inline=True)
        embed.add_field(name="Oluşturulma", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='userinfo', description='Kullanıcı bilgilerini göster')
    @app_commands.describe(member='Bilgileri gösterilecek üye')
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        embed = discord.Embed(
            title=f"👤 {member.name} Bilgileri",
            color=member.color,
            timestamp=datetime.now()
        )
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Takma Ad", value=member.nick or "Yok", inline=True)
        embed.add_field(name="Hesap Oluşturulma", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="Sunucuya Katılma", value=member.joined_at.strftime("%d/%m/%Y") if member.joined_at else "Bilinmiyor", inline=True)
        embed.add_field(name="Roller", value=", ".join([r.mention for r in member.roles[1:]]) or "Yok", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='poll', description='Anket oluştur')
    @app_commands.describe(question='Anket sorusu', options='Seçenekler (virgülle ayır)')
    async def poll(self, interaction: discord.Interaction, question: str, options: str):
        opts = [opt.strip() for opt in options.split(",")]
        if len(opts) < 2:
            await interaction.response.send_message("❌ En az 2 seçenek girmelisin!", ephemeral=True)
            return
        if len(opts) > 10:
            await interaction.response.send_message("❌ En fazla 10 seçenek girebilirsin!", ephemeral=True)
            return

        numbers = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        description = "\n".join([f"{numbers[i]} {opt}" for i, opt in enumerate(opts)])

        embed = discord.Embed(
            title=f"📊 {question}",
            description=description,
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Anket: {interaction.user.name}")

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        for i in range(len(opts)):
            await message.add_reaction(numbers[i])

    @app_commands.command(name='guess', description='Sayı tahmin oyunu')
    @app_commands.describe(max_number='Maksimum sayı (varsayılan: 100)')
    async def guess(self, interaction: discord.Interaction, max_number: int = 100):
        number = random.randint(1, max_number)
        attempts = 0

        embed = discord.Embed(
            title="🎯 Sayı Tahmin Oyunu",
            description=f"1 ile {max_number} arasında bir sayı tuttum! Tahmin et!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        while True:
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60.0)
                try:
                    guess = int(msg.content)
                except ValueError:
                    await interaction.channel.send("❌ Bir sayı gir!")
                    continue

                attempts += 1
                if guess < number:
                    await interaction.channel.send("⬆️ Daha yüksek!")
                elif guess > number:
                    await interaction.channel.send("⬇️ Daha düşük!")
                else:
                    embed = discord.Embed(
                        title="🎉 Tebrikler!",
                        description=f"**{number}** sayısını {attempts} denemede buldun!",
                        color=discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    await interaction.channel.send(embed=embed)
                    break
            except asyncio.TimeoutError:
                await interaction.channel.send(f"⏰ Süre doldu! Sayı **{number}** idi.")
                break

    @app_commands.command(name='rps', description='Taş kağıt makas oyunu')
    @app_commands.describe(choice='Seçiminiz')
    @app_commands.choices(choice=[
        app_commands.Choice(name='Taş', value='tas'),
        app_commands.Choice(name='Kağıt', value='kagit'),
        app_commands.Choice(name='Makas', value='makas')
    ])
    async def rps(self, interaction: discord.Interaction, choice: str):
        bot_choice = random.choice(['tas', 'kagit', 'makas'])
        choice_names = {'tas': '🪨 Taş', 'kagit': '📄 Kağıt', 'makas': '✂️ Makas'}

        if choice == bot_choice:
            result = "🤝 Berabere!"
        elif (choice == 'tas' and bot_choice == 'makas') or \
             (choice == 'kagit' and bot_choice == 'tas') or \
             (choice == 'makas' and bot_choice == 'kagit'):
            result = "🎉 Kazandın!"
        else:
            result = "😢 Kaybettin!"

        embed = discord.Embed(
            title="✊ Taş Kağıt Makas",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Sen", value=choice_names[choice], inline=True)
        embed.add_field(name="Bot", value=choice_names[bot_choice], inline=True)
        embed.add_field(name="Sonuç", value=result, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='coinflip', description='Para at')
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["Yazı", "Tura"])
        embed = discord.Embed(
            title=f"🪙 {result}!",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='dice', description='Zar at')
    @app_commands.describe(sides='Zar yüz sayısı (varsayılan: 6)')
    async def dice(self, interaction: discord.Interaction, sides: int = 6):
        if sides < 2:
            await interaction.response.send_message("❌ En az 2 yüzlü zar girmelisin!", ephemeral=True)
            return
        result = random.randint(1, sides)
        embed = discord.Embed(
            title=f"🎲 Zar: {result}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='joke', description='Rastgele şaka')
    async def joke(self, interaction: discord.Interaction):
        jokes = [
            "Programcılar neden karanlıkta çalışır? Çünkü ışık bug'ları çeker! 🐛",
            "Bir SQL sorgusu girideki bardaktan su içmeye çalışıyor ve diyor ki: 'SELECT * FROM bardak WHERE dolu = true' ☕",
            "Neden programcılar Halloween'ı bayram sayar? Çünkü Oct 31 == Dec 25! 🎃",
            "Bir programcı markete gidiyor ve diyor ki: 'Bir elma alayım. Yoksa bir daha gelirim.' 🍎",
            "Debug nedir? Kodun içindeki hatayı bulmak. Debugging nedir? Bulduğun hatayı düzeltmek. 🐛",
        ]
        embed = discord.Embed(
            title="😂 Şaka",
            description=random.choice(jokes),
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='ship', description='İki üyeyi eşleştir')
    @app_commands.describe(member1='Birinci üye', member2='İkinci üye')
    async def ship(self, interaction: discord.Interaction, member1: discord.Member, member2: discord.Member):
        compatibility = random.randint(1, 100)
        hearts = "❤️" * (compatibility // 20) + "🤍" * (5 - compatibility // 20)

        embed = discord.Embed(
            title="💘 Ship Sonucu",
            color=discord.Color.pink(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Çift", value=f"{member1.mention} 💕 {member2.mention}", inline=False)
        embed.add_field(name="Uyumluluk", value=f"%{compatibility} {hearts}", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='howgay', description='Gaylik yüzdesi (eğlence)')
    @app_commands.describe(member='Üye')
    async def howgay(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        percentage = random.randint(0, 100)
        embed = discord.Embed(
            title="🏳️‍🌈 Gaylik Yüzdesi",
            description=f"{member.mention} %{percentage} gay!",
            color=discord.Color.pink(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='simprate', description='Simp yüzdesi (eğlence)')
    @app_commands.describe(member='Üye')
    async def simprate(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        percentage = random.randint(0, 100)
        embed = discord.Embed(
            title="💕 Simp Yüzdesi",
            description=f"{member.mention} %{percentage} simp!",
            color=discord.Color.pink(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='hotrate', description='Yakışıklılık yüzdesi (eğlence)')
    @app_commands.describe(member='Üye')
    async def hotrate(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        percentage = random.randint(0, 100)
        embed = discord.Embed(
            title="🔥 Yakışıklılık Yüzdesi",
            description=f"{member.mention} %{percentage} yakışıklı!",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Fun(bot))
