import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Yetkin Yok!",
                description=f"Bu komutu kullanmak için gerekli yetkilere sahip değilsin: {', '.join(error.missing_permissions)}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                title="❌ Bot Yetkisi Yok!",
                description=f"Bu komutu çalıştırmak için gerekli yetkilere sahip değilim: {', '.join(error.missing_permissions)}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Eksik Argüman!",
                description=f"`{error.param.name}` argümanı eksik!",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="❌ Geçersiz Argüman!",
                description=f"Geçersiz argüman: {error}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ Bekleme Süresi!",
                description=f"Bu komutu {error.retry_after:.1f} saniye sonra tekrar kullanabilirsin.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.NoPrivateMessage):
            embed = discord.Embed(
                title="❌ Özel Mesaj!",
                description="Bu komut özel mesajlarda kullanılamaz!",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)

        else:
            embed = discord.Embed(
                title="❌ Hata!",
                description=f"Beklenmeyen bir hata oluştu: {str(error)}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)
            self.bot.logger.error(f"Command error: {error}")

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle slash command errors"""
        if isinstance(error, app_commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Yetkin Yok!",
                description=f"Bu komutu kullanmak için gerekli yetkilere sahip değilsin: {', '.join(error.missing_permissions)}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif isinstance(error, app_commands.BotMissingPermissions):
            embed = discord.Embed(
                title="❌ Bot Yetkisi Yok!",
                description=f"Bu komutu çalıştırmak için gerekli yetkilere sahip değilim: {', '.join(error.missing_permissions)}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif isinstance(error, app_commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ Bekleme Süresi!",
                description=f"Bu komutu {error.retry_after:.1f} saniye sonra tekrar kullanabilirsin.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        else:
            embed = discord.Embed(
                title="❌ Hata!",
                description=f"Beklenmeyen bir hata oluştu: {str(error)}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            self.bot.logger.error(f"App command error: {error}")

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
