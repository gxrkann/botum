import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import random
import asyncio

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_giveaways = {}

    @app_commands.command(name='cekilis_baslat', description='Çekiliş başlat')
    @app_commands.describe(
        prize='Ödül',
        winners='Kazanan sayısı',
        duration='Süre (örn: 10m, 1h, 1d)',
        channel='Çekiliş kanalı'
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def cekilis_baslat(self, interaction: discord.Interaction, prize: str, winners: int, duration: str, channel: discord.TextChannel = None):
        channel = channel or interaction.channel

        duration_map = {'m': 60, 'h': 3600, 'd': 86400}
        try:
            unit = duration[-1].lower()
            value = int(duration[:-1])
            seconds = value * duration_map[unit]
        except:
            await interaction.response.send_message("❌ Geçersiz süre formatı! Örnek: 10m, 1h, 1d", ephemeral=True)
            return

        if winners < 1 or winners > 10:
            await interaction.response.send_message("❌ Kazanan sayısı 1-10 arasında olmalı!", ephemeral=True)
            return

        end_time = datetime.now() + timedelta(seconds=seconds)

        embed = discord.Embed(
            title="🎉 Çekiliş",
            description=f"**Ödül:** {prize}\n**Kazanan Sayısı:** {winners}\n**Süre:** {duration}\n**Başlatan:** {interaction.user.mention}",
            color=discord.Color.gold(),
            timestamp=end_time
        )
        embed.set_footer(text="Katılmak için butona tıkla!")

        view = GiveawayView(self.bot, prize, winners, end_time, channel.id, interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(f"✅ Çekiliş {channel.mention} kanalında başlatıldı!")
        message = await channel.send(embed=embed, view=view)

        self.active_giveaways[message.id] = {
            'prize': prize,
            'winners': winners,
            'end_time': end_time,
            'channel_id': channel.id,
            'guild_id': interaction.guild.id,
            'host_id': interaction.user.id,
            'participants': []
        }

        asyncio.create_task(self.wait_for_giveaway(message.id, seconds))

    @app_commands.command(name='cekilis_bitir', description='Çekilişi erken bitir')
    @app_commands.describe(message_id='Çekiliş mesaj ID\'si')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def cekilis_bitir(self, interaction: discord.Interaction, message_id: str):
        try:
            message_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("❌ Geçersiz mesaj ID!", ephemeral=True)
            return

        giveaway = self.active_giveaways.pop(message_id, None)
        if not giveaway:
            await interaction.response.send_message("❌ Bu mesaj bir çekiliş değil veya süresi dolmuş!", ephemeral=True)
            return

        channel = self.bot.get_channel(giveaway['channel_id'])
        if not channel:
            await interaction.response.send_message("❌ Kanal bulunamadı!", ephemeral=True)
            return

        try:
            message = await channel.fetch_message(message_id)
            users = []
            for msg_reaction in message.reactions:
                if str(msg_reaction.emoji) == "🎉":
                    users = [user async for user in msg_reaction.users() if not user.bot]
                    break

            if not users:
                await channel.send("❌ Çekilişte katılımcı olmadı!")
                return

            winner_count = min(giveaway['winners'], len(users))
            winners_list = random.sample(users, winner_count)
            winner_mentions = [w.mention for w in winners_list]

            embed = discord.Embed(
                title="🎉 Çekiliş Sonuçları",
                description=f"**Ödül:** {giveaway['prize']}\n**Kazananlar:** {', '.join(winner_mentions)}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            await channel.send(embed=embed)
            await interaction.response.send_message("✅ Çekiliş bitirildi!", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("❌ Mesaj bulunamadı!", ephemeral=True)

    @app_commands.command(name='cekilis_sil', description='Çekilişi sil')
    @app_commands.describe(message_id='Çekiliş mesaj ID\'si')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def cekilis_sil(self, interaction: discord.Interaction, message_id: str):
        try:
            message_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("❌ Geçersiz mesaj ID!", ephemeral=True)
            return

        giveaway = self.active_giveaways.pop(message_id, None)
        if not giveaway:
            await interaction.response.send_message("❌ Bu mesaj bir çekiliş değil veya süresi dolmuş!", ephemeral=True)
            return

        channel = self.bot.get_channel(giveaway['channel_id'])
        if channel:
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
            except discord.NotFound:
                pass

        await interaction.response.send_message("✅ Çekiliş silindi!", ephemeral=True)

    @app_commands.command(name='cekilis_liste', description='Aktif çekilişleri listele')
    async def cekilis_liste(self, interaction: discord.Interaction):
        if not self.active_giveaways:
            await interaction.response.send_message("❌ Aktif çekiliş yok!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎉 Aktif Çekilişler",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

        for msg_id, data in self.active_giveaways.items():
            if data['guild_id'] == interaction.guild.id:
                channel = self.bot.get_channel(data['channel_id'])
                channel_mention = channel.mention if channel else "Bilinmiyor"
                embed.add_field(
                    name=f"Ödül: {data['prize']}",
                    value=f"Kazanan: {data['winners']}\nKanal: {channel_mention}\nMesaj ID: {msg_id}",
                    inline=False
                )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='cekilis_reroll', description='Çekilişi yeniden çek')
    @app_commands.describe(message_id='Çekiliş mesaj ID\'si')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def cekilis_reroll(self, interaction: discord.Interaction, message_id: str):
        try:
            message_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("❌ Geçersiz mesaj ID!", ephemeral=True)
            return

        channel = interaction.channel
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            await interaction.response.send_message("❌ Mesaj bulunamadı!", ephemeral=True)
            return

        users = []
        for msg_reaction in message.reactions:
            if str(msg_reaction.emoji) == "🎉":
                users = [user async for user in msg_reaction.users() if not user.bot]
                break

        if not users:
            await interaction.response.send_message("❌ Çekilişte katılımcı olmadı!", ephemeral=True)
            return

        winner = random.choice(users)

        embed = discord.Embed(
            title="🎉 Çekiliş Yeniden Çekildi",
            description=f"**Yeni Kazanan:** {winner.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    async def wait_for_giveaway(self, message_id: int, seconds: int):
        await asyncio.sleep(seconds)
        giveaway = self.active_giveaways.pop(message_id, None)
        if not giveaway:
            return

        channel = self.bot.get_channel(giveaway['channel_id'])
        if not channel:
            return

        try:
            message = await channel.fetch_message(message_id)
            users = []
            for msg_reaction in message.reactions:
                if str(msg_reaction.emoji) == "🎉":
                    users = [user async for user in msg_reaction.users() if not user.bot]
                    break

            if not users:
                await channel.send("❌ Çekilişte katılımcı olmadı!")
                return

            winner_count = min(giveaway['winners'], len(users))
            winners_list = random.sample(users, winner_count)
            winner_mentions = [w.mention for w in winners_list]

            embed = discord.Embed(
                title="🎉 Çekiliş Sonuçları",
                description=f"**Ödül:** {giveaway['prize']}\n**Kazananlar:** {', '.join(winner_mentions)}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            await channel.send(embed=embed)
        except discord.NotFound:
            pass


class GiveawayView(discord.ui.View):
    def __init__(self, bot, prize, winners, end_time, channel_id, guild_id, host_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.prize = prize
        self.winners = winners
        self.end_time = end_time
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.host_id = host_id

    @discord.ui.button(label="🎉 Katıl", style=discord.ButtonStyle.green, custom_id="giveaway_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎉 Çekilişe katıldın! Şanslı olsun!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
