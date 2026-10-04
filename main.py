import discord
from discord.ext import commands
import asyncio
import os
import sys
import logging
from database import Database

# Environment variables - works with both .env and hosting platforms
def get_env(key, default=None):
    """Get environment variable from os.environ or .env file"""
    value = os.environ.get(key)
    if value is None:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            value = os.environ.get(key, default)
        except ImportError:
            value = default
    return value

# Logging setup - hosting ortamında dosya yazılamayabilir, o yüzden güvenli
log_handlers = [logging.StreamHandler(sys.stdout)]
try:
    log_handlers.insert(0, logging.FileHandler('bot.log', encoding='utf-8'))
except (OSError, PermissionError):
    pass  # Dosya yazılamıyorsa sadece konsola yaz

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger('discord_bot')

# Bot configuration
class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()

        # MESSAGE CONTENT INTENT - zorunlu, portal'da açık olmalı
        intents.message_content = True

        # SERVER MEMBERS INTENT - açık değilse bot çöker, o yüzden opsiyonel
        if get_env('ENABLE_MEMBERS_INTENT', 'true').lower() == 'true':
            intents.members = True

        intents.voice_states = True

        super().__init__(
            command_prefix=get_env('PREFIX', '!'),
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        
        self.db = Database()
        self.logger = logger

    async def setup_hook(self):
        """Called when the bot is starting up"""
        await self.db.connect()
        
        # Load all cogs
        cogs = [
            'cogs.moderation',
            'cogs.music',
            'cogs.utility',
            'cogs.events',
            'cogs.error_handler',
            'cogs.help',
            'cogs.farm',
            'cogs.fivem',
            'cogs.giveaway',
            'cogs.voice_tracker',
            'cogs.voice_manager',
            'cogs.owner_protect',
            'cogs.guard',
            'cogs.announcement',
            'dashboard'
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f'Loaded: {cog}')
            except Exception as e:
                logger.error(f'Failed to load {cog}: {e}')

    async def sync_commands(self):
        """
        Slash komutlarini sunucuya ozel kaydet.

        Discord global kayitta 100 komut siniri koyar. Bizde 100+ komut
        oldugu icin sunucu bazli (guild) kayit kullanilir - sunucu basina
        100 komut siniri var ve tek sunucuda yeterli.
        """
        total = len(self.tree.get_commands())
        logger.info(f'Toplam {total} komut tanimli')

        # 1) Global kaydi temizle (eski global varsa sil)
        try:
            guild_ids = [g.id for g in self.guilds]
            await self.tree.clear_commands(guild_ids=guild_ids,
                                           app_commands=self.application.commands if hasattr(self, 'application') else None)
        except Exception:
            pass

        # 2) Her sunucuya ozel kaydet
        synced_total = 0
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                synced_total += len(synced)
                logger.info(f'{guild.name}: {len(synced)} komut kaydedildi')
            except Exception as e:
                logger.error(f'{guild.name} sync hatasi: {e}')

        # 3) Sunucu yoksa gecici olarak global dene
        if not self.guilds:
            try:
                if total <= 100:
                    synced = await self.tree.sync()
                    logger.info(f'Gecici global kayit: {len(synced)} komut')
                else:
                    logger.warning(
                        f'{total} komut var ama global sinir 100. '
                        'Bot bir sunucuya eklenince sunucu bazli kayit yapilacak.'
                    )
            except Exception as e:
                logger.error(f'Gecici sync hatasi: {e}')

        if synced_total:
            logger.info(f'Toplam {synced_total} komut aktif')
        else:
            logger.info('Henuz sunucu yok - komutlar bir sunucuya eklenince kaydedilecek')

    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')

        await self.apply_activity()
        await self.sync_commands()

    def _load_activity_config(self):
        """Dashboard'dan kaydedilen oyun/activity ayarlarini yukle"""
        config = {
            'status': get_env('BOT_STATUS', 'FiveM'),
            'large_image': get_env('BOT_LARGE_IMAGE', None),
            'large_text': get_env('BOT_LARGE_TEXT', None),
            'small_image': get_env('BOT_SMALL_IMAGE', None),
            'small_text': get_env('BOT_SMALL_TEXT', None)
        }

        try:
            import json
            with open('bot_config.json', 'r', encoding='utf-8') as f:
                saved = json.load(f)
            for key in config:
                if saved.get(key):
                    config[key] = saved[key]
        except (FileNotFoundError, json.JSONDecodeError, ImportError):
            pass

        return config

    async def apply_activity(self):
        """Oynadigi oyun bilgisini guncelle"""
        config = self._load_activity_config()
        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name=config['status'],
            large_image=config['large_image'],
            large_text=config['large_text'],
            small_image=config['small_image'],
            small_text=config['small_text']
        )
        await self.change_presence(activity=activity)

    async def close(self):
        await self.db.close()
        await super().close()

# Create bot instance
bot = Bot()

# Owner-only commands
@bot.command(name='bot_pp')
@commands.is_owner()
async def bot_pp(ctx, image_url: str = None):
    """Botun profil resmini değiştir (Owner only)"""
    try:
        if image_url:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()
                        await bot.user.edit(avatar=image_data)
                        await ctx.send("✅ Botun profil resmi değiştirildi!")
                    else:
                        await ctx.send("❌ Resim indirilemedi!")
        else:
            await ctx.send("❌ Bir resim URL'si girin! Kullanım: `!bot_pp https://example.com/image.png`")
    except Exception as e:
        await ctx.send(f"❌ Hata: {e}")

@bot.command(name='bot_banner')
@commands.is_owner()
async def bot_banner(ctx, image_url: str = None):
    """Botun banner resmini değiştir (Owner only)"""
    try:
        if image_url:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()
                        await bot.user.edit(banner=image_data)
                        await ctx.send("✅ Botun banner resmi değiştirildi!")
                    else:
                        await ctx.send("❌ Resim indirilemedi!")
        else:
            await ctx.send("❌ Bir resim URL'si girin! Kullanım: `!bot_banner https://example.com/banner.png`")
    except Exception as e:
        await ctx.send(f"❌ Hata: {e}")

@bot.command(name='bot_durum')
@commands.is_owner()
async def bot_durum(ctx, *, status: str = None):
    """Botun durumunu değiştir (Owner only)"""
    try:
        if status:
            activity = discord.Activity(
                type=discord.ActivityType.playing,
                name=status
            )
            await bot.change_presence(activity=activity)
            await ctx.send(f"✅ Botun durumu değiştirildi: **{status}**")
        else:
            await ctx.send("❌ Bir durum girin! Kullanım: `!bot_durum FiveM`")
    except Exception as e:
        await ctx.send(f"❌ Hata: {e}")

@bot.command(name='load')
@commands.is_owner()
async def load_cog(ctx, extension: str):
    """Load a cog (Owner only)"""
    try:
        await bot.load_extension(f'cogs.{extension}')
        await ctx.send(f'✅ `{extension}` yüklendi!')
    except Exception as e:
        await ctx.send(f'❌ Hata: {e}')

@bot.command(name='unload')
@commands.is_owner()
async def unload_cog(ctx, extension: str):
    """Unload a cog (Owner only)"""
    try:
        await bot.unload_extension(f'cogs.{extension}')
        await ctx.send(f'✅ `{extension}` kaldırıldı!')
    except Exception as e:
        await ctx.send(f'❌ Hata: {e}')

@bot.command(name='reload')
@commands.is_owner()
async def reload_cog(ctx, extension: str):
    """Reload a cog (Owner only)"""
    try:
        await bot.reload_extension(f'cogs.{extension}')
        await ctx.send(f'✅ `{extension}` yeniden yüklendi!')
    except Exception as e:
        await ctx.send(f'❌ Hata: {e}')

@bot.command(name='reloadall')
@commands.is_owner()
async def reload_all_cogs(ctx):
    """Reload all cogs (Owner only)"""
    cogs = [
        'moderation', 'music',
        'fun', 'utility', 'events', 'error_handler', 'help', 'dashboard'
    ]
    
    success = 0
    failed = 0
    
    for cog in cogs:
        try:
            await bot.reload_extension(f'cogs.{cog}')
            success += 1
        except Exception as e:
            logger.error(f'Failed to reload {cog}: {e}')
            failed += 1
    
    await ctx.send(f'🔄 {success} cog yenilendi, {failed} başarısız!')

@bot.command(name='shutdown')
@commands.is_owner()
async def shutdown_bot(ctx):
    """Shutdown the bot (Owner only)"""
    await ctx.send('👋 Bot kapatılıyor...')
    await bot.close()

# Run the bot
if __name__ == '__main__':
    token = get_env('DISCORD_TOKEN')
    if not token:
        logger.error('❌ DISCORD_TOKEN bulunamadi! .env veya ortam degiskenlerini kontrol et.')
        exit(1)

    import traceback

    try:
        bot.run(token, reconnect=True)
    except discord.LoginFailure:
        logger.error('❌ Geçersiz token! DISCORD_TOKEN değerini kontrol et.')
        exit(1)
    except discord.errors.PrivilegedIntentsRequired:
        logger.error('=' * 60)
        logger.error('❌ PRIVILEGED INTENTS KAPALI - Bot çalışamaz!')
        logger.error('=' * 60)
        logger.error('1. https://discord.com/developers/applications')
        logger.error('2. Uygulamanı seç → Bot sekmesi')
        logger.error('3. MESSAGE CONTENT INTENT ve SERVER MEMBERS INTENT → AÇ')
        logger.error('4. Save Changes')
        logger.error('=' * 60)
        exit(1)
    except SystemExit:
        raise
    except Exception as e:
        logger.error('=' * 60)
        logger.error(f'❌ BOT ÇÖKTÜ: {type(e).__name__}')
        logger.error('=' * 60)
        for line in traceback.format_exc().splitlines():
            logger.error(line)
        logger.error('=' * 60)
        exit(1)
