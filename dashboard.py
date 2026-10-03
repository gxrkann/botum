from flask import Flask, render_template, jsonify, request, redirect, url_for
import discord
from discord.ext import commands
import asyncio
import threading
import os
import json
from datetime import datetime

app = Flask(__name__)

class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.app = app
        self.port = int(os.environ.get('PORT', 5000))
        self.dashboard_thread = None
        self._started = False
        self._lock = threading.Lock()

    def run_dashboard(self):
        """Flask dashboard'i ayri thread'de calistir"""
        try:
            self.app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)
        except Exception as e:
            print(f"[dashboard] Sunucu baslatilamadi: {e}", flush=True)

    async def start_dashboard(self):
        """Dashboard'i baslat (sadece bir kez)"""
        with self._lock:
            if self._started:
                return
            self._started = True

        try:
            self.dashboard_thread = threading.Thread(target=self.run_dashboard, daemon=True)
            self.dashboard_thread.start()
            msg = f"[DASHBOARD] Baslatildi -> http://0.0.0.0:{self.port}"
            print(msg, flush=True)
            self.bot.logger.info(f"Dashboard started on port {self.port}")
        except Exception as e:
            err = f"[DASHBOARD] BASLATILAMADI: {e}"
            print(err, flush=True)
            self.bot.logger.error(f"Dashboard could not start: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.start_dashboard()

# Health check - Pterodactyl/PaaS icin
@app.route('/health')
def health():
    bot = app.config.get('BOT')
    return jsonify({
        'status': 'ok',
        'bot': str(bot.user) if bot and bot.user else 'not connected',
        'guilds': len(bot.guilds) if bot else 0
    }), 200

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def api_stats():
    """Get bot statistics"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    stats = {
        'guilds': len(bot.guilds),
        'users': sum(g.member_count for g in bot.guilds),
        'channels': sum(len(g.channels) for g in bot.guilds),
        'latency': round(bot.latency * 1000),
        'commands': len(bot.tree.get_commands()),
        'uptime': 'N/A',
    }
    return jsonify(stats)

@app.route('/api/guilds')
def api_guilds():
    """Get guild list"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    guilds = []
    for guild in bot.guilds:
        guilds.append({
            'id': guild.id,
            'name': guild.name,
            'member_count': guild.member_count,
            'icon': str(guild.icon.url) if guild.icon else None,
        })
    return jsonify(guilds)

@app.route('/api/guild/<int:guild_id>')
def api_guild(guild_id):
    """Get guild details"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    guild = bot.get_guild(guild_id)
    if not guild:
        return jsonify({'error': 'Guild not found'}), 404

    data = {
        'id': guild.id,
        'name': guild.name,
        'member_count': guild.member_count,
        'channel_count': len(guild.channels),
        'role_count': len(guild.roles),
        'icon': str(guild.icon.url) if guild.icon else None,
        'created_at': guild.created_at.isoformat(),
        'owner': str(guild.owner) if guild.owner else None,
    }
    return jsonify(data)

@app.route('/api/commands')
def api_commands():
    """Get command list"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    commands = []
    for cmd in bot.tree.get_commands():
        # Prefix komutlarinda .type yok - getattr ile guvenli erisim
        commands.append({
            'name': cmd.name,
            'description': cmd.description or 'Aciklama yok',
            'type': str(getattr(cmd, 'type', 'text')),
        })
    return jsonify(commands)

@app.route('/api/logs')
def api_logs():
    """Get recent logs"""
    try:
        with open('bot.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()[-100:]
        return jsonify({'logs': lines})
    except FileNotFoundError:
        return jsonify({'logs': []})

@app.route('/api/backups')
def api_backups():
    """Get backup list"""
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        return jsonify([])

    backups = []
    for filename in os.listdir(backup_dir):
        filepath = os.path.join(backup_dir, filename)
        backups.append({
            'filename': filename,
            'size': os.path.getsize(filepath),
            'created': datetime.fromtimestamp(os.path.getctime(filepath)).isoformat()
        })
    return jsonify(backups)

@app.route('/api/farm/<int:guild_id>')
def api_farm(guild_id):
    """Get farm statistics"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    async def get_farm_stats():
        async with bot.db.connection.execute(
            'SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM farms WHERE guild_id = ?',
            (guild_id,)
        ) as cursor:
            total = await cursor.fetchone()

        async with bot.db.connection.execute(
            '''SELECT user_id, COUNT(*) as farm_count, SUM(amount) as total_amount
               FROM farms WHERE guild_id = ? GROUP BY user_id ORDER BY total_amount DESC LIMIT 10''',
            (guild_id,)
        ) as cursor:
            users = await cursor.fetchall()

        return {
            'total_farms': total[0],
            'total_amount': total[1],
            'users': [{'user_id': u[0], 'count': u[1], 'amount': u[2]} for u in users]
        }

    result = asyncio.run_coroutine_threadsafe(get_farm_stats(), bot.loop).result()
    return jsonify(result)

@app.route('/api/fivem/<int:guild_id>')
def api_fivem(guild_id):
    """Get FiveM weapon statistics"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    async def get_fivem_stats():
        async with bot.db.connection.execute(
            'SELECT COUNT(*), COALESCE(SUM(price), 0) FROM fivem_weapons WHERE guild_id = ?',
            (guild_id,)
        ) as cursor:
            weapons = await cursor.fetchone()

        async with bot.db.connection.execute(
            'SELECT COUNT(*) FROM fivem_weapons_lost WHERE guild_id = ?',
            (guild_id,)
        ) as cursor:
            lost = await cursor.fetchone()

        return {
            'total_weapons': weapons[0],
            'total_value': weapons[1],
            'total_lost': lost[0]
        }

    result = asyncio.run_coroutine_threadsafe(get_fivem_stats(), bot.loop).result()
    return jsonify(result)

@app.route('/api/giveaways')
def api_giveaways():
    """Get active giveaways"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    giveaway_cog = bot.get_cog('Giveaway')
    if not giveaway_cog:
        return jsonify([])

    giveaways = []
    for msg_id, data in giveaway_cog.active_giveaways.items():
        giveaways.append({
            'message_id': msg_id,
            'prize': data['prize'],
            'winners': data['winners'],
            'end_time': data['end_time'].isoformat(),
            'channel_id': data['channel_id']
        })
    return jsonify(giveaways)

@app.route('/api/voice/<int:guild_id>')
def api_voice(guild_id):
    """Get voice statistics"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    voice_cog = bot.get_cog('VoiceTracker')
    if not voice_cog:
        return jsonify({'error': 'Voice tracker not available'}), 500

    guild = bot.get_guild(guild_id)
    if not guild:
        return jsonify({'error': 'Guild not found'}), 404

    voice_data = voice_cog.voice_data.get(str(guild_id), {})
    if not voice_data:
        return jsonify([])

    stats = []
    for user_id, data in voice_data.items():
        member = guild.get_member(int(user_id))
        if member:
            stats.append({
                'user_id': int(user_id),
                'name': member.name,
                'total_seconds': data['total_seconds']
            })

    stats.sort(key=lambda x: x['total_seconds'], reverse=True)
    return jsonify(stats[:10])

@app.route('/api/reload/<cog>')
def api_reload(cog):
    """Reload a cog"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    async def do_reload():
        try:
            await bot.reload_extension(f'cogs.{cog}')
            return True
        except Exception as e:
            return str(e)

    result = asyncio.run_coroutine_threadsafe(do_reload(), bot.loop).result()
    if result is True:
        return jsonify({'success': True})
    return jsonify({'error': result}), 500

@app.route('/api/bot_settings', methods=['GET', 'POST'])
def api_bot_settings():
    """Get or update bot settings"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    config_file = 'bot_config.json'

    def load_config():
        defaults = {
            'status': os.environ.get('BOT_STATUS', 'FiveM'),
            'large_image': os.environ.get('BOT_LARGE_IMAGE', ''),
            'large_text': os.environ.get('BOT_LARGE_TEXT', ''),
            'small_image': os.environ.get('BOT_SMALL_IMAGE', ''),
            'small_text': os.environ.get('BOT_SMALL_TEXT', '')
        }
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            defaults.update({k: v for k, v in saved.items() if v})
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return defaults

    if request.method == 'GET':
        return jsonify(load_config())

    elif request.method == 'POST':
        data = request.json or {}
        config = {
            'status': data.get('status', 'FiveM') or 'FiveM',
            'large_image': data.get('large_image', ''),
            'large_text': data.get('large_text', ''),
            'small_image': data.get('small_image', ''),
            'small_text': data.get('small_text', '')
        }

        # Ayarlari kalici olarak kaydet
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except OSError as e:
            print(f"[dashboard] Ayar kaydedilemedi: {e}", flush=True)

        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name=config['status'],
            large_image=config['large_image'] or None,
            large_text=config['large_text'] or None,
            small_image=config['small_image'] or None,
            small_text=config['small_text'] or None
        )

        async def update_presence():
            await bot.change_presence(activity=activity)

        try:
            asyncio.run_coroutine_threadsafe(update_presence(), bot.loop).result(timeout=10)
            print(f"[dashboard] Durum guncellendi: {config['status']}", flush=True)
            return jsonify({'success': True})
        except Exception as e:
            print(f"[dashboard] Durum guncellenemedi: {e}", flush=True)
            return jsonify({'error': str(e)}), 500

@app.route('/api/guard/<int:guild_id>', methods=['GET', 'POST'])
def api_guard(guild_id):
    """Get or update guard settings"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    if request.method == 'GET':
        async def get_guard():
            async with bot.db.connection.execute(
                'SELECT settings FROM guard_settings WHERE guild_id = ?',
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    import json
                    return json.loads(row[0])
                return None

        result = asyncio.run_coroutine_threadsafe(get_guard(), bot.loop).result()
        return jsonify(result or {'error': 'Guard not configured'})

    elif request.method == 'POST':
        data = request.json
        settings = {
            'enabled': data.get('enabled', True),
            'protections': data.get('protections', []),
            'log_channel_id': data.get('log_channel_id')
        }

        async def update_guard():
            await bot.db.connection.execute(
                '''INSERT OR REPLACE INTO guard_settings (guild_id, settings) VALUES (?, ?)''',
                (guild_id, json.dumps(settings))
            )
            await bot.db.connection.commit()

        asyncio.run_coroutine_threadsafe(update_guard(), bot.loop)
        return jsonify({'success': True})

@app.route('/api/bot_invite')
def api_bot_invite():
    """Get bot invite link"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    invite_url = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    return jsonify({'invite_url': invite_url})

@app.route('/api/bot_add/<int:guild_id>')
def api_bot_add(guild_id):
    """Generate bot invite link for specific guild"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    guild = bot.get_guild(guild_id)
    if not guild:
        return jsonify({'error': 'Guild not found'}), 404

    invite_url = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands&guild_id={guild_id}"
    return jsonify({'invite_url': invite_url, 'guild_name': guild.name})

async def setup(bot):
    print("[DASHBOARD] Cog yukleniyor...", flush=True)
    app.config['BOT'] = bot
    cog = Dashboard(bot)
    await bot.add_cog(cog)
    print(f"[DASHBOARD] Port: {cog.port}, Bot hazir mi: {bot.is_ready()}", flush=True)

    # Bot cog yuklenmeden once hazirlandiysa on_ready tetiklenmez,
    # bu yuzden elle kontrol edip dashboard'u hemen baslat.
    if bot.is_ready():
        await asyncio.sleep(0.5)
        await cog.start_dashboard()
