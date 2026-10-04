import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime, timedelta

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='balance', description='Bakiyeni gör')
    @app_commands.describe(member='Bakiyesi görüntülenecek üye (opsiyonel)')
    async def balance(self, interaction: discord.Interaction, member: discord.Member | None = None):
        member = member or interaction.user
        await self.bot.db.create_user(member.id, interaction.guild.id)
        data = await self.bot.db.get_balance(member.id, interaction.guild.id)

        embed = discord.Embed(
            title=f"💰 {member.name} Bakiyesi",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Cüzdan", value=f"{data['balance']} 🪙", inline=True)
        embed.add_field(name="Banka", value=f"{data['bank']} 🪙", inline=True)
        embed.add_field(name="Toplam", value=f"{data['balance'] + data['bank']} 🪙", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='daily', description='Günlük ödülünü al')
    async def daily(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        await self.bot.db.create_user(user_id, guild_id)

        # Check last daily
        async with self.bot.db.connection.execute(
            'SELECT last_daily, daily_streak FROM economy WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()

        now = datetime.now()
        if row and row[0]:
            last_daily = datetime.fromisoformat(row[0])
            if now - last_daily < timedelta(hours=20):
                remaining = timedelta(hours=20) - (now - last_daily)
                hours, remainder = divmod(remaining.seconds, 3600)
                minutes = remainder // 60
                await interaction.response.send_message(
                    f"⏰ Günlük ödülünü zaten aldın! {hours}s {minutes}d sonra tekrar gel.",
                    ephemeral=True
                )
                return

        # Calculate reward
        streak = row[1] if row else 0
        if row and row[0]:
            last_daily = datetime.fromisoformat(row[0])
            if now - last_daily < timedelta(hours=48):
                streak += 1
            else:
                streak = 0

        base_reward = 500
        streak_bonus = min(streak * 50, 500)
        total_reward = base_reward + streak_bonus

        await self.bot.db.update_balance(user_id, guild_id, total_reward)
        await self.bot.db.connection.execute(
            'UPDATE economy SET last_daily = ?, daily_streak = ? WHERE user_id = ? AND guild_id = ?',
            (now.isoformat(), streak, user_id, guild_id)
        )
        await self.bot.db.connection.commit()

        embed = discord.Embed(
            title="🎁 Günlük Ödül",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Ödül", value=f"{total_reward} 🪙", inline=False)
        embed.add_field(name="Seri", value=f"{streak} gün 🔥", inline=False)
        if streak_bonus > 0:
            embed.add_field(name="Seri Bonusu", value=f"+{streak_bonus} 🪙", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='deposit', description='Paranı bankaya yatır')
    @app_commands.describe(amount='Yatırılacak miktar (all = tümü)')
    async def deposit(self, interaction: discord.Interaction, amount: str):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        await self.bot.db.create_user(user_id, guild_id)
        data = await self.bot.db.get_balance(user_id, guild_id)

        if amount.lower() == 'all':
            amount = data['balance']
        else:
            try:
                amount = int(amount)
            except ValueError:
                await interaction.response.send_message("❌ Geçersiz miktar!", ephemeral=True)
                return

        if amount <= 0:
            await interaction.response.send_message("❌ Pozitif bir sayı gir!", ephemeral=True)
            return

        if amount > data['balance']:
            await interaction.response.send_message("❌ Yeterli paran yok!", ephemeral=True)
            return

        await self.bot.db.update_balance(user_id, guild_id, -amount)
        await self.bot.db.update_bank(user_id, guild_id, amount)

        embed = discord.Embed(
            title="🏦 Para Yatırıldı",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Yatırılan", value=f"{amount} 🪙", inline=False)
        embed.add_field(name="Yeni Bakiye", value=f"{data['balance'] - amount} 🪙", inline=False)
        embed.add_field(name="Banka", value=f"{data['bank'] + amount} 🪙", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='withdraw', description='Bankadan para çek')
    @app_commands.describe(amount='Çekilecek miktar (all = tümü)')
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        await self.bot.db.create_user(user_id, guild_id)
        data = await self.bot.db.get_balance(user_id, guild_id)

        if amount.lower() == 'all':
            amount = data['bank']
        else:
            try:
                amount = int(amount)
            except ValueError:
                await interaction.response.send_message("❌ Geçersiz miktar!", ephemeral=True)
                return

        if amount <= 0:
            await interaction.response.send_message("❌ Pozitif bir sayı gir!", ephemeral=True)
            return

        if amount > data['bank']:
            await interaction.response.send_message("❌ Bankanda yeterli para yok!", ephemeral=True)
            return

        await self.bot.db.update_balance(user_id, guild_id, amount)
        await self.bot.db.update_bank(user_id, guild_id, -amount)

        embed = discord.Embed(
            title="💸 Para Çekildi",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Çekilen", value=f"{amount} 🪙", inline=False)
        embed.add_field(name="Cüzdan", value=f"{data['balance'] + amount} 🪙", inline=False)
        embed.add_field(name="Banka", value=f"{data['bank'] - amount} 🪙", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='transfer', description='Başka bir üyeye para gönder')
    @app_commands.describe(member='Alıcı üye', amount='Gönderilecek miktar')
    async def transfer(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.id == interaction.user.id:
            await interaction.response.send_message("❌ Kendine para gönderemezsin!", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("❌ Pozitif bir sayı gir!", ephemeral=True)
            return

        sender_id = interaction.user.id
        guild_id = interaction.guild.id
        await self.bot.db.create_user(sender_id, guild_id)
        await self.bot.db.create_user(member.id, guild_id)

        sender_data = await self.bot.db.get_balance(sender_id, guild_id)
        if amount > sender_data['balance']:
            await interaction.response.send_message("❌ Yeterli paran yok!", ephemeral=True)
            return

        await self.bot.db.update_balance(sender_id, guild_id, -amount)
        await self.bot.db.update_balance(member.id, guild_id, amount)

        embed = discord.Embed(
            title="💸 Para Gönderildi",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Gönderen", value=f"{interaction.user.mention}", inline=False)
        embed.add_field(name="Alıcı", value=f"{member.mention}", inline=False)
        embed.add_field(name="Miktar", value=f"{amount} 🪙", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='work', description='Çalış ve para kazan')
    async def work(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        await self.bot.db.create_user(user_id, guild_id)

        # Check cooldown
        async with self.bot.db.connection.execute(
            'SELECT last_work FROM economy WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()

        now = datetime.now()
        if row and row[0]:
            last_work = datetime.fromisoformat(row[0])
            if now - last_work < timedelta(hours=1):
                remaining = timedelta(hours=1) - (now - last_work)
                minutes = remaining.seconds // 60
                await interaction.response.send_message(
                    f"⏰ Çalışma dinlenmesinde! {minutes} dakika sonra tekrar gel.",
                    ephemeral=True
                )
                return

        # Random job and earnings
        jobs = [
            ("💻", "Yazılımcı", 100, 300),
            ("🍕", "Pizza dağıtıcısı", 80, 200),
            ("🎨", "Grafik tasarımcı", 150, 400),
            ("📦", "Kargo çalışanı", 90, 250),
            ("🧹", "Temizlikçi", 70, 180),
            ("🎧", "DJ", 200, 500),
        ]
        emoji, job, min_pay, max_pay = random.choice(jobs)
        earnings = random.randint(min_pay, max_pay)

        await self.bot.db.update_balance(user_id, guild_id, earnings)
        await self.bot.db.connection.execute(
            'UPDATE economy SET last_work = ? WHERE user_id = ? AND guild_id = ?',
            (now.isoformat(), user_id, guild_id)
        )
        await self.bot.db.connection.commit()

        embed = discord.Embed(
            title=f"{emoji} {job}",
            description=f"Çalıştın ve **{earnings} 🪙** kazandın!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='rob', description='Başka bir üyeyi soymaya çalış')
    @app_commands.describe(member='Soyulacak üye')
    async def rob(self, interaction: discord.Interaction, member: discord.Member):
        if member.id == interaction.user.id:
            await interaction.response.send_message("❌ Kendini soyamazsın!", ephemeral=True)
            return

        user_id = interaction.user.id
        guild_id = interaction.guild.id
        await self.bot.db.create_user(user_id, guild_id)
        await self.bot.db.create_user(member.id, guild_id)

        # Check cooldown
        async with self.bot.db.connection.execute(
            'SELECT last_rob FROM economy WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()

        now = datetime.now()
        if row and row[0]:
            last_rob = datetime.fromisoformat(row[0])
            if now - last_rob < timedelta(hours=2):
                remaining = timedelta(hours=2) - (now - last_rob)
                minutes = remaining.seconds // 60
                await interaction.response.send_message(
                    f"⏰ Soygunluk dinlenmesinde! {minutes} dakika sonra tekrar gel.",
                    ephemeral=True
                )
                return

        victim_data = await self.bot.db.get_balance(member.id, guild_id)
        if victim_data['balance'] < 100:
            await interaction.response.send_message("❌ Bu üyenin çalacak parası yok!", ephemeral=True)
            return

        # 50% chance to succeed
        if random.random() < 0.5:
            amount = random.randint(100, min(victim_data['balance'], 1000))
            await self.bot.db.update_balance(user_id, guild_id, amount)
            await self.bot.db.update_balance(member.id, guild_id, -amount)
            await self.bot.db.connection.execute(
                'UPDATE economy SET last_rob = ? WHERE user_id = ? AND guild_id = ?',
                (now.isoformat(), user_id, guild_id)
            )
            await self.bot.db.connection.commit()

            embed = discord.Embed(
                title="🔫 Başarılı Soygunluk!",
                description=f"{member.mention}'den **{amount} 🪙** çaldın!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            await interaction.response.send_message(embed=embed)
        else:
            fine = random.randint(50, 200)
            await self.bot.db.update_balance(user_id, guild_id, -fine)
            await self.bot.db.connection.execute(
                'UPDATE economy SET last_rob = ? WHERE user_id = ? AND guild_id = ?',
                (now.isoformat(), user_id, guild_id)
            )
            await self.bot.db.connection.commit()

            embed = discord.Embed(
                title="🚨 Yakalandın!",
                description=f"Soygunluk başarısız! **{fine} 🪙** ceza ödedin!",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name='leaderboard', description='Zenginlik sıralaması')
    async def leaderboard(self, interaction: discord.Interaction):
        async with self.bot.db.connection.execute(
            'SELECT user_id, balance, bank FROM economy WHERE guild_id = ? ORDER BY (balance + bank) DESC LIMIT 10',
            (interaction.guild.id,)
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message("❌ Henüz kimse para kazanmamış!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 Zenginlik Sıralaması",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(rows):
            user = interaction.guild.get_member(row[0])
            if user:
                medal = medals[i] if i < 3 else f"**{i+1}.**"
                total = row[1] + row[2]
                embed.add_field(
                    name=f"{medal} {user.name}",
                    value=f"Cüzdan: {row[1]} 🪙 | Banka: {row[2]} 🪙 | Toplam: {total} 🪙",
                    inline=False
                )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
