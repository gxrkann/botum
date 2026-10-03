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
        self.port = 5000
        self.dashboard_thread = None

    def run_dashboard(self):
        """Run the Flask dashboard in a separate thread"""
        self.app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)

    async def start_dashboard(self):
        """Start the dashboard"""
        self.dashboard_thread = threading.Thread(target=self.run_dashboard, daemon=True)
        self.dashboard_thread.start()
        self.bot.logger.info(f"Dashboard started on http://localhost:{self.port}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Start dashboard when bot is ready"""
        await self.start_dashboard()

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
        commands.append({
            'name': cmd.name,
            'description': cmd.description,
            'type': str(cmd.type),
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

@app.route('/api/guard/<int:guild_id>')
def api_guard(guild_id):
    """Get guard settings"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

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

    if request.method == 'GET':
        return jsonify({
            'status': os.environ.get('BOT_STATUS', 'FiveM'),
            'large_image': os.environ.get('BOT_LARGE_IMAGE', ''),
            'large_text': os.environ.get('BOT_LARGE_TEXT', ''),
            'small_image': os.environ.get('BOT_SMALL_IMAGE', ''),
            'small_text': os.environ.get('BOT_SMALL_TEXT', '')
        })

    elif request.method == 'POST':
        data = request.json
        status = data.get('status')
        large_image = data.get('large_image')
        large_text = data.get('large_text')
        small_image = data.get('small_image')
        small_text = data.get('small_text')

        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name=status or 'FiveM',
            large_image=large_image or None,
            large_text=large_text or None,
            small_image=small_image or None,
            small_text=small_text or None
        )

        async def update_presence():
            await bot.change_presence(activity=activity)

        asyncio.run_coroutine_threadsafe(update_presence(), bot.loop)
        return jsonify({'success': True})

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
    await bot.add_cog(Dashboard(bot))
    app.config['BOT'] = bot
