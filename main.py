import discord
from discord.ext import commands
import asyncio
import os
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

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('discord_bot')

# Bot configuration
class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
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
            'cogs.economy',
            'cogs.levels',
            'cogs.fun',
            'cogs.utility',
            'cogs.events',
            'cogs.error_handler',
            'cogs.help',
            'dashboard'
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f'Loaded: {cog}')
            except Exception as e:
                logger.error(f'Failed to load {cog}: {e}')
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f'Synced {len(synced)} slash commands')
        except Exception as e:
            logger.error(f'Failed to sync slash commands: {e}')

    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f'{len(self.guilds)} sunucu | /help'
        )
        await self.change_presence(activity=activity)

    async def close(self):
        await self.db.close()
        await super().close()

# Create bot instance
bot = Bot()

# Owner-only commands
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
        'moderation', 'music', 'economy', 'levels',
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
        logger.error('DISCORD_TOKEN not found in environment variables!')
        exit(1)
    
    try:
        bot.run(token, reconnect=True)
    except discord.LoginFailure:
        logger.error('Invalid token! Please check your DISCORD_TOKEN.')
    except Exception as e:
        logger.error(f'Bot crashed: {e}')
