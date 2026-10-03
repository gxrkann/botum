from flask import Flask, render_template, jsonify, request, redirect, url_for
import discord
from discord.ext import commands
import asyncio
import threading
import os
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
        'uptime': 'N/A',  # You'd track this
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

@app.route('/api/eval', methods=['POST'])
def api_eval():
    """Evaluate code (DANGEROUS - Owner only)"""
    # This is a placeholder - implement proper authentication
    return jsonify({'error': 'Not implemented'}), 501

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

async def setup(bot):
    await bot.add_cog(Dashboard(bot))
    app.config['BOT'] = bot
