import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

class Announcement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='duyuru', description='Duyuru yap')
    @app_commands.describe(
        message='Duyuru mesajı',
        channel='Duyuru kanalı',
        color='Embed rengi (örn: kırmızı, mavi, yeşil, altın, mor)',
        title='Duyuru başlığı',
        role='Etiketlenecek rol',
        everyone='@everyone etiketle',
        image='Duyuru arka plan resmi (URL)'
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def duyuru(self, interaction: discord.Interaction, message: str, channel: discord.TextChannel | None = None, color: str = "altın", title: str = "📢 Duyuru", role: discord.Role | None = None, everyone: bool = False, image: str = None):
        channel = channel or interaction.channel

        color_map = {
            'kırmızı': discord.Color.red(),
            'kirmizi': discord.Color.red(),
            'mavi': discord.Color.blue(),
            'yeşil': discord.Color.green(),
            'yesil': discord.Color.green(),
            'altın': discord.Color.gold(),
            'altin': discord.Color.gold(),
            'mor': discord.Color.purple(),
            'turuncu': discord.Color.orange(),
            'siyah': discord.Color.dark_theme(),
            'beyaz': discord.Color.light_gray(),
        }

        embed_color = color_map.get(color.lower(), discord.Color.gold())

        embed = discord.Embed(
            title=title,
            description=message,
            color=embed_color,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Duyuru: {interaction.user.name}")

        if image:
            embed.set_image(url=image)

        content = ""
        if everyone:
            content += "@everyone "
        if role:
            content += role.mention

        await interaction.response.send_message(f"✅ Duyuru {channel.mention} kanalında yapıldı!", ephemeral=True)
        await channel.send(content=content, embed=embed)

    @app_commands.command(name='duyuru_dm', description='Tüm üyelere DM ile duyuru gönder')
    @app_commands.describe(message='Duyuru mesajı')
    @app_commands.checks.has_permissions(administrator=True)
    async def duyuru_dm(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()

        embed = discord.Embed(
            title="📢 Duyuru",
            description=message,
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Duyuru: {interaction.user.name}")

        sent = 0
        failed = 0

        for member in interaction.guild.members:
            if not member.bot:
                try:
                    await member.send(embed=embed)
                    sent += 1
                except discord.Forbidden:
                    failed += 1

        embed_result = discord.Embed(
            title="📢 DM Duyuru Sonucu",
            description=f"**Gönderildi:** {sent}\n**Başarısız:** {failed}",
            color=discord.Color.green() if failed == 0 else discord.Color.orange(),
            timestamp=datetime.now()
        )
        await interaction.followup.send(embed=embed_result)

    @app_commands.command(name='ses_sok', description='Kullanıcıyı ses kanalına davet et')
    @app_commands.describe(
        member='Davet edilecek üye',
        channel='Ses kanalı (boş bırakılırsa mevcut kanal)'
    )
    @app_commands.checks.has_permissions(move_members=True)
    async def ses_sok(self, interaction: discord.Interaction, member: discord.Member, channel: discord.VoiceChannel | None = None):
        if not member.voice:
            await interaction.response.send_message("❌ Bu üye ses kanalında değil!", ephemeral=True)
            return

        target_channel = channel or member.voice.channel

        # Once gercekten tasimayi dene
        moved = False
        try:
            await member.move_to(target_channel)
            moved = True
        except discord.Forbidden:
            pass
        except discord.HTTPException as e:
            print(f"[ses_sok] Tasima hatasi: {e}", flush=True)

        # Davet linki olustur (her zaman)
        invite = None
        try:
            invite = await target_channel.create_invite(max_age=3600, reason="Ses daveti")
        except discord.Forbidden:
            pass

        if moved:
            desc = f"{member.mention} üyesi **{target_channel.mention}** kanalına taşındı!"
            color = discord.Color.green()
        else:
            desc = f"{member.mention} üyesine **{target_channel.mention}** daveti gönderildi.\nTaşıma yetkisi yok, davet linki gönderildi."
            color = discord.Color.blue()

        embed = discord.Embed(
            title="🎤 Ses Daveti",
            description=desc,
            color=color,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        if invite:
            embed.add_field(name="Bağlantı", value=f"[Kanalda Katıl]({invite.url})", inline=False)

        await interaction.response.send_message(embed=embed)

        # DM gonder
        try:
            dm_desc = f"{interaction.user.mention} seni **{target_channel.mention}** kanalına davet etti!"
            if moved:
                dm_desc = f"{interaction.user.mention} seni **{target_channel.mention}** kanalına taşıdı!"
            dm_embed = discord.Embed(
                title="🎤 Ses Daveti",
                description=dm_desc,
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            if invite:
                dm_embed.add_field(name="Bağlantı", value=f"[Kanalda Katıl]({invite.url})", inline=False)
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

    @app_commands.command(name='toplu_ses', description='Tüm ses kanaldaki üyeleri topla')
    @app_commands.describe(channel='Hedef ses kanalı')
    @app_commands.checks.has_permissions(move_members=True)
    async def toplu_ses(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        members_in_voice = [m for m in interaction.guild.members if m.voice and not m.bot]

        if not members_in_voice:
            await interaction.response.send_message("❌ Ses kanalında kimse yok!", ephemeral=True)
            return

        moved = 0
        for member in members_in_voice:
            try:
                await member.move_to(channel)
                moved += 1
            except discord.Forbidden:
                pass

        embed = discord.Embed(
            title="🎤 Toplu Ses Taşıma",
            description=f"**{moved}** üye {channel.mention} kanalına taşındı!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='ses_baglanti', description='Ses kanalına bağlantı oluştur')
    @app_commands.describe(channel='Ses kanalı')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ses_baglanti(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        invite = await channel.create_invite(max_age=3600, max_uses=0, reason="Ses daveti")

        embed = discord.Embed(
            title="🎤 Ses Bağlantısı",
            description=f"[Bağlantıya tıkla]({invite.url})",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Announcement(bot))
