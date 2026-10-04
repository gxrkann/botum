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
        # Katilimcilar buton ID -> set(user_id)
        self.giveaway_participants = {}

    @app_commands.command(name='cekilis_baslat', description='Çekiliş başlat')
    @app_commands.describe(
        prize='Ödül',
        winners='Kazanan sayısı',
        duration='Süre (örn: 10m, 1h, 1d)',
        channel='Çekiliş kanalı'
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def cekilis_baslat(self, interaction: discord.Interaction, prize: str, winners: int, duration: str, channel: discord.TextChannel | None = None):
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

        # Buton icin benzersiz ID (her cekilise ozel olmali)
        button_id = f"giveaway_{interaction.guild.id}_{int(datetime.now().timestamp())}"

        embed = discord.Embed(
            title="🎉 Çekiliş",
            description=f"**Ödül:** {prize}\n**Kazanan Sayısı:** {winners}\n**Süre:** {duration}\n**Başlatan:** {interaction.user.mention}",
            color=discord.Color.gold(),
            timestamp=end_time
        )
        embed.set_footer(text="Katılmak için aşağıdaki butona tıkla!")
        embed.set_footer(text="Katılmak için aşağıdaki butona tıkla!")

        view = GiveawayView(self.bot, button_id, prize, winners, end_time,
                            channel.id, interaction.guild.id, interaction.user.id)

        await interaction.response.send_message(f"✅ Çekiliş {channel.mention} kanalında başlatıldı!")
        message = await channel.send(embed=embed, view=view)

        self.active_giveaways[message.id] = {
            'prize': prize,
            'winners': winners,
            'end_time': end_time,
            'channel_id': channel.id,
            'guild_id': interaction.guild.id,
            'host_id': interaction.user.id,
            'button_id': button_id,
            'message_id': message.id
        }
        # Katilimci listesi buton ID ile tutulur
        self.giveaway_participants[button_id] = set()

        asyncio.create_task(self.wait_for_giveaway(message.id, seconds))

    def _get_participant_ids(self, giveaway):
        """Cekilis katilimcilarini buton listesinden al"""
        button_id = giveaway.get('button_id')
        ids = self.giveaway_participants.get(button_id, set())
        result = []
        for uid in ids:
            user = self.bot.get_user(uid)
            if user is not None and not user.bot:
                result.append(uid)
        return result

    async def _notify_host(self, giveaway, winners, prize, participant_count, action='bit'):
        """Cekilisi baslatan kisiye DM gonder"""
        host = self.bot.get_user(giveaway.get('host_id'))
        if not host:
            return

        winner_mentions = ', '.join(w.mention for w in winners)

        if action == 'bit':
            title = "🎉 Çekiliş Tamamlandı"
            desc = (f"**{prize}** çekilişiniz sona erdi!\n\n"
                    f"**Kazanan:** {winner_mentions}\n"
                    f"**Katılımcı:** {participant_count}")
            color = discord.Color.green()
        elif action == 'bitir':
            title = "⏹️ Çekiliş Erken Bitirildi"
            desc = (f"**{prize}** çekilişini erken bitirdiniz.\n\n"
                    f"**Kazanan:** {winner_mentions}\n"
                    f"**Katılımcı:** {participant_count}")
            color = discord.Color.orange()
        else:
            title = "🔄 Çekiliş Yeniden Çekildi"
            desc = (f"**{prize}** çekilişi yeniden çekildi.\n\n"
                    f"**Yeni Kazanan:** {winner_mentions}\n"
                    f"**Katılımcı:** {participant_count}")
            color = discord.Color.blue()

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color,
            timestamp=datetime.now()
        )

        try:
            await host.send(embed=embed)
            print(f"[cekilis] Host DM gonderildi: {host.id}", flush=True)
        except discord.Forbidden:
            print(f"[cekilis] Host DM kapali: {host.id}", flush=True)
        except Exception as e:
            print(f"[cekilis] Host DM hatasi: {e}", flush=True)

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
            user_ids = self._get_participant_ids(giveaway)
            users = [self.bot.get_user(i) for i in user_ids]
            users = [u for u in users if u is not None]

            if not users:
                await channel.send(f"❌ Çekilişe kimse katılmadı!\n**{len(user_ids)}** katılımcı kaydı bulundu.")
                return

            winner_count = min(giveaway['winners'], len(users))
            winners_list = random.sample(users, winner_count)
            winner_mentions = [w.mention for w in winners_list]

            embed = discord.Embed(
                title="🎉 Çekiliş Sonuçları",
                description=f"**Ödül:** {giveaway['prize']}\n**Kazananlar:** {', '.join(winner_mentions)}\n**Katılımcı:** {len(users)}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            await channel.send(embed=embed)
            await self._notify_host(giveaway, winners_list, giveaway['prize'], len(users), 'bitir')
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
            user_ids = self._get_participant_ids(giveaway)
            users = [self.bot.get_user(i) for i in user_ids]
            users = [u for u in users if u is not None]

            # Katilimci listesini temizle
            self.giveaway_participants.pop(giveaway.get('button_id'), None)

            if not users:
                await channel.send(f"❌ Çekilişe kimse katılmadı! **{giveaway['prize']}** ödülü verilemedi.")
                return

            winner_count = min(giveaway['winners'], len(users))
            winners_list = random.sample(users, winner_count)
            winner_mentions = [w.mention for w in winners_list]

            embed = discord.Embed(
                title="🎉 Çekiliş Sonuçları",
                description=f"**Ödül:** {giveaway['prize']}\n**Kazananlar:** {', '.join(winner_mentions)}\n**Katılımcı:** {len(users)}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            await channel.send(embed=embed)
        except discord.NotFound:
            pass


class GiveawayView(discord.ui.View):
    def __init__(self, bot, button_id, prize, winners, end_time, channel_id, guild_id, host_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.button_id = button_id
        self.prize = prize
        self.winners = winners
        self.end_time = end_time
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.host_id = host_id

    @discord.ui.button(label="🎉 Katıl", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = self.bot.get_cog('Giveaway')
        if not cog:
            await interaction.response.send_message("❌ Çekiliş sistemi yüklenemedi!", ephemeral=True)
            return

        if self.button_id not in cog.giveaway_participants:
            cog.giveaway_participants[self.button_id] = set()

        participants = cog.giveaway_participants[self.button_id]
        user_id = interaction.user.id

        if user_id in participants:
            participants.discard(user_id)
            await interaction.response.send_message("↩️ Çekilişten çıktın!", ephemeral=True)
        else:
            participants.add(user_id)
            await interaction.response.send_message(
                f"🎉 Çekilişe katıldın! Şanslı olsun!\n**Katılımcı:** {len(participants)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
