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
    async def _safe_send(self, interaction, content: str, **kwargs):
        """
        Her durumda kullaniciya mesaj gonder.

        Slash komutlari 3 saniye sonra 'zaman asimi' olur ve Discord
        komutu 'dusunuyor' diye birakir. Bir hata olursa yanit
        gonderilemezse komut sonsuza dek asili kalir. Bu yuzden:
          1) once normal yanit
          2) sonra followup (zaten defer edildiyse)
          3) son olarak interaction.edit (followup da olmuyorsa)
        """
        kwargs.setdefault('ephemeral', True)

        # 1) Henuz yanit verilmediyse
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(content, **kwargs)
                return
        except (discord.InteractionResponded, discord.HTTPException):
            pass

        # 2) defer edilmişse followup
        try:
            await interaction.followup.send(content, **kwargs)
            return
        except (discord.HTTPException, AttributeError, RuntimeError):
            pass

        # 3) Son care: interaction nesnesini duzenle
        try:
            await interaction.edit_original_response(content=content)
        except (discord.HTTPException, AttributeError, RuntimeError):
            pass

    async def on_app_command_error(self, interaction: discord.Interaction, error):
        """
        Slash komut hatalari.

        DIKKAT: buraya sadece AppCommandError degil, AttributeError gibi
        duz Exception'lar da gelir. Bu yuzden tum hatalar yakalanir ve
        kullaniciya mutlaka mesaj gonderilir - hicbir durumda asili kalmaz.
        """
        self.bot.logger.error(
            f"Slash komut hatasi: {type(error).__name__}: {error} "
            f"(komut: {getattr(interaction.command, 'name', '?')})",
            exc_info=error if not isinstance(error, app_commands.AppCommandError) else None
        )

        try:
            if isinstance(error, app_commands.MissingPermissions):
                await self._safe_send(
                    interaction,
                    f"❌ **Yetkin yok!**\nGerekli: {', '.join(error.missing_permissions)}"
                )

            elif isinstance(error, app_commands.BotMissingPermissions):
                await self._safe_send(
                    interaction,
                    f"❌ **Bot yetkisi yok!**\nGerekli: {', '.join(error.missing_permissions)}\n"
                    f"Sunucu → Bot rolü → İzinler"
                )

            elif isinstance(error, app_commands.CommandOnCooldown):
                await self._safe_send(
                    interaction,
                    f"⏰ **Bekleme süresi!** {error.retry_after:.1f} saniye sonra tekrar dene."
                )

            elif isinstance(error, app_commands.NoPrivateMessage):
                await self._safe_send(interaction, "❌ Bu komut sadece sunucuda kullanılabilir.")

            elif isinstance(error, app_commands.MissingAnyRole):
                await self._safe_send(interaction, "❌ Bu komut için gerekli role sahip değilsin.")

            elif isinstance(error, app_commands.MissingApplicationID):
                await self._safe_send(interaction, "❌ Komut kaydı henüz tamamlanmadı, birkaç saniye sonra dene.")

            else:
                await self._safe_send(
                    interaction,
                    f"❌ **Hata oluştu**\n```{type(error).__name__}: {str(error)[:300]}```\n"
                    f"Bu komutu `/help` sayfasına bildir."
                )

        except Exception:
            # Handlerin kendisi patlarsa sessizce gec - asili kalmak daha kotu
            pass

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
