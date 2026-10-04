from flask import Flask, render_template, jsonify, request, redirect, url_for
import discord
from discord.ext import commands
import asyncio
import threading
import time
import os
import json
from datetime import datetime

app = Flask(__name__)


def resolve_guild(bot, raw_id):
    """
    Guild ID'sini cozer.

    Discord snowflake ID'leri 2^53'ten buyuk oldugu icin JSON'da sayi olarak
    gonderilirse JavaScript bunu yuvarlar ve ID bozulur. API'lerimiz ID'leri
    string donduruyor ama yine de bozulmus bir ID gelirse (eski arayuz, onbellek)
    asagidaki toleransli eslestirmeyle kurtarmaya calisir.

    JavaScript double hassasiyeti 1.5e17 civarinda en fazla ~16 sapma yapar.
    """
    try:
        gid = int(raw_id)
    except (TypeError, ValueError):
        return None

    guild = bot.get_guild(gid)
    if guild:
        return guild

    # Bozuk ID olabilir - yakin bir guild var mi bak
    for g in bot.guilds:
        if abs(g.id - gid) <= 64:
            return g
    return None

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
            # Discord snowflake ID'leri 2^53'ten buyuk. JSON'da sayi olarak
            # gonderilirse JavaScript (IEEE 754) bozar ve sunucu bulunamaz.
            # Her zaman string gonderiyoruz.
            'id': str(guild.id),
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
        'id': str(guild.id),
        'name': guild.name,
        'member_count': guild.member_count or 0,
        'channel_count': len(guild.channels),
        'role_count': len(guild.roles),
        'icon': str(guild.icon.url) if guild.icon else None,
        'created_at': guild.created_at.isoformat() if guild.created_at else None,
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
            total = await cursor.fetchone() or (0, 0)

        async with bot.db.connection.execute(
            '''SELECT user_id, COUNT(*) as farm_count, SUM(amount) as total_amount
               FROM farms WHERE guild_id = ? GROUP BY user_id ORDER BY total_amount DESC LIMIT 10''',
            (guild_id,)
        ) as cursor:
            users = await cursor.fetchall() or []

        return {
            'total_farms': total[0] or 0,
            'total_amount': total[1] or 0,
            'users': [{'user_id': str(u[0]), 'count': u[1], 'amount': u[2]} for u in users]
        }

    result = run_async(get_farm_stats())
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
            weapons = await cursor.fetchone() or (0, 0)

        async with bot.db.connection.execute(
            'SELECT COUNT(*) FROM fivem_weapons_lost WHERE guild_id = ?',
            (guild_id,)
        ) as cursor:
            lost = await cursor.fetchone() or (0,)

        return {
            'total_weapons': weapons[0] or 0,
            'total_value': weapons[1] or 0,
            'total_lost': lost[0] or 0
        }

    result = run_async(get_fivem_stats())
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
                'user_id': str(user_id),
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

    result = run_async(do_reload())
    if result is True:
        return jsonify({'success': True})
    return jsonify({'error': result}), 500

@app.route('/api/guard_threat', methods=['GET', 'POST'])
def api_guard_threat():
    """Guard tehdit seviyesi, olaylar, supheli kullanicilar"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    guard = bot.get_cog('Guard')
    if not guard:
        return jsonify({'error': 'Guard cog yuklenmedi'}), 500

    guild_id = (request.json or {}).get('guild_id') if request.method == 'POST' \
        else request.args.get('guild_id')
    if not guild_id:
        return jsonify({'error': 'Sunucu secilmedi'}), 400

    guild_id = int(guild_id)

    try:
        async def collect():
            threat = await guard.get_threat(guild_id)
            actions = await guard.get_actions(guild_id, 30)
            users = await guard.get_threat_users(guild_id, 8)

            async with bot.db.connection.execute(
                'SELECT settings FROM guard_settings WHERE guild_id = ?', (guild_id,)
            ) as cur:
                row = await cur.fetchone()
            cfg = json.loads(row[0]) if row else {'enabled': False, 'protections': []}

            # Son 24 saat istatistigi
            async with bot.db.connection.execute(
                '''SELECT COUNT(*), COALESCE(SUM(blocked), 0)
                   FROM guard_actions
                   WHERE guild_id = ? AND created_at >= datetime('now','-1 day')''',
                (guild_id,)
            ) as cur:
                day = await cur.fetchone()

            return {
                'threat': {
                    'score': threat['score'],
                    'label': threat['label'],
                    'raid_mode': bool(threat['raid_mode']),
                },
                'enabled': cfg.get('enabled', False),
                'protections': cfg.get('protections', []),
                'total_actions': len(actions),
                'last_24h': {'total': day[0] or 0, 'blocked': day[1] or 0},
                'actions': [
                    {
                        'type': r[0],
                        'severity': r[1] or 0,
                        'description': r[2],
                        'executor_id': str(r[3]) if r[3] else None,
                        'executor': r[4],
                        'target': r[5],
                        'blocked': bool(r[6]),
                        'time': str(r[7]) if r[7] else '',
                    }
                    for r in actions
                ],
                'suspects': [
                    {
                        'user_id': str(u[0]),
                        'score': u[1] or 0,
                        'count': u[2] or 0,
                        'last_seen': str(u[3]) if u[3] else '',
                        'mention': f"<@{u[0]}>",
                    }
                    for u in users
                ],
            }

        return jsonify(run_async(collect()))

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/hizli_ayar', methods=['GET', 'POST'])
def api_hizli_ayar():
    """Giris/cikis DM mesajlari - hizli ayar"""
    bot = app.config.get('BOT')
    if not bot:
        return jsonify({'error': 'Bot not available'}), 500

    if request.method == 'POST':
        data = request.json or {}
        guild_id = data.get('guild_id')
        if not guild_id:
            return jsonify({'error': 'Sunucu secilmedi'}), 400

        giris_mesaj = (data.get('dm_giris_mesaj') or '')[:2000]
        cikis_mesaj = (data.get('dm_cikis_mesaj') or '')[:2000]
        giris_acik = 1 if data.get('dm_giris_acik') else 0
        cikis_acik = 1 if data.get('dm_cikis_acik') else 0

        async def save():
            for key, val in (
                ('dm_giris_acik', giris_acik),
                ('dm_giris_mesaj', giris_mesaj),
                ('dm_cikis_acik', cikis_acik),
                ('dm_cikis_mesaj', cikis_mesaj),
            ):
                await bot.db.update_setting(int(guild_id), key, val)

        try:
            run_async(save())
        except Exception as e:
            return jsonify({'error': f'Kaydedilemedi: {e}'}), 500

        return jsonify({'success': True, 'message': 'Ayar kaydedildi'})

    # GET
    guild_id = request.args.get('guild_id')
    if not guild_id:
        return jsonify({'error': 'Sunucu secilmedi'}), 400

    async def load():
        s = await bot.db.get_settings(int(guild_id)) or {}
        return {
            'dm_giris_acik': bool(s.get('dm_giris_acik')),
            'dm_giris_mesaj': s.get('dm_giris_mesaj') or '',
            'dm_cikis_acik': bool(s.get('dm_cikis_acik')),
            'dm_cikis_mesaj': s.get('dm_cikis_mesaj') or '',
        }

    try:
        return jsonify(run_async(load()))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            run_async(update_presence(), timeout=10)
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

        result = run_async(get_guard())
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

        run_async(update_guard())
        return jsonify({'success': True})

@app.route('/api/bot_profile', methods=['GET', 'POST'])
def api_bot_profile():
    """Bot avatar / banner guncelle"""
    bot = app.config.get('BOT')
    if not bot or not bot.user:
        return jsonify({'error': 'Bot not available'}), 500

    if request.method == 'GET':
        return jsonify({
            'avatar_url': str(bot.user.display_avatar.url) if bot.user.display_avatar else None,
            'banner_url': str(bot.user.banner.url) if bot.user.banner else None,
            'name': bot.user.name
        })

    data = request.json or {}

    # Guvenli resim adresleri - Discord CDN + yaygin resim hostlari
    ALLOWED_HOSTS = (
        'cdn.discordapp.com',
        'media.discordapp.net',
        'images-ext-1.discordapp.net',
        'images-ext-2.discordapp.net',
        'i.imgur.com',
        'imgur.com',
        'cdn.discord.com',
        'discordapp.com',
        'discordapp.net',
        'pbs.twimg.com',
        'i.redd.it',
        'redd.it',
        'github.com',
        'raw.githubusercontent.com',
        'media.githubusercontent.com',
        'gitlab.com',
    )
    ALLOWED_SCHEMES = ('http://', 'https://')

    # Tehlikeli/ozel ag adresleri (SSRF korumasi)
    BLOCKED_HOSTS = (
        'localhost', '127.0.0.1', '0.0.0.0', '::1',
        '169.254.169.254',  # AWS metadata
        'metadata.google.internal',
    )

    def validate_url(url):
        """Guvenli resim adresi mi kontrol et"""
        from urllib.parse import urlparse
        import ipaddress

        url = url.strip()
        if not url:
            return False, 'Adres bos'

        if not url.lower().startswith(ALLOWED_SCHEMES):
            return False, 'Sadece http:// veya https:// ile baslayan adres kabul edilir'

        try:
            parsed = urlparse(url)
        except ValueError:
            return False, 'Gecersiz adres'

        host = (parsed.hostname or '').lower()
        if not host:
            return False, 'Adres yazilmis degil'

        if host in BLOCKED_HOSTS:
            return False, 'Bu adres guvenlik nedeniyle engellendi'

        # Ozel IP araliklari engellenir
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False, 'Ozel ag adresleri guvenlik nedeniyle engellendi'
        except ValueError:
            pass  # IP degil, domain - devam et

        # Bilinen host veya tum alt domain'lere izin ver
        allowed = any(
            host == h or host.endswith('.' + h)
            for h in ALLOWED_HOSTS
        )

        if not allowed:
            return False, ('Bu adres kabul edilmiyor. Discord CDN veya bilinen '
                          'resim hostlari (imgur, redd.it, github, twitter) kullanin')

        return True, None

    errors = []
    for kind in ('avatar', 'banner'):
        url = (data.get(kind) or '').strip()
        if url:
            ok, err = validate_url(url)
            if not ok:
                errors.append(f'{kind}: {err}')

    if errors:
        return jsonify({'error': ' | '.join(errors)}), 400

    # Ayni URL tekrar gonderiliyorsa guncelleme yapma
    if not errors and not (data.get('avatar') or '').strip() and not (data.get('banner') or '').strip():
        return jsonify({'error': 'Profil Resmi veya Banner URL adresi giriniz'}), 400

    async def apply_profile():
        avatar_bytes = None
        banner_bytes = None

        for kind in ('avatar', 'banner'):
            url = (data.get(kind) or '').strip()
            if not url:
                continue
            try:
                async with bot.http.session.get(url) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        if len(content) > 8 * 1024 * 1024:
                            errors.append(f'{kind}: Resim 8 MB dan buyuk')
                            continue
                        if kind == 'avatar':
                            avatar_bytes = content
                        else:
                            banner_bytes = content
                    else:
                        msg = f'{kind}: Discord CDN adresi dondu (HTTP {resp.status}). Linkin sonu gecersiz olabilir.'
                        errors.append(msg)
                        print(f"[dashboard] {msg}", flush=True)
            except Exception as e:
                msg = f'{kind}: Indirme hatasi ({type(e).__name__})'
                errors.append(msg)
                print(f"[dashboard] {msg}: {e}", flush=True)

        kwargs = {}
        if avatar_bytes:
            kwargs['avatar'] = avatar_bytes
        if banner_bytes:
            kwargs['banner'] = banner_bytes

        if not kwargs:
            if errors:
                return False, errors
            # Hicbir URL girilmemis
            return False, ['Profil Resmi veya Banner URL adresi giriniz']

        try:
            await bot.user.edit(**kwargs)
            return True, list(kwargs.keys())
        except discord.Forbidden:
            return False, ['Discord bu degisiklige izin vermedi (bot yetkisi yetersiz)']
        except discord.HTTPException as e:
            return False, [f'Discord reddetti (HTTP {e.status}): {e.text}']

    try:
        ok, result = run_async(apply_profile(), timeout=25)

        if ok:
            print(f"[dashboard] Guncellendi: {result}", flush=True)
            return jsonify({'success': True, 'changed': result})
        return jsonify({'error': ' | '.join(result)}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/voice_control', methods=['GET', 'POST'])
def api_voice_control():
    """Bot ses kontrolu: kanallari listele, katil, ayril"""
    bot = app.config.get('BOT')
    if not bot or not bot.is_ready():
        return jsonify({'error': 'Bot henuz hazir degil'}), 503

    # GET - kanallari ve durumu listele
    if request.method == 'GET':
        guild_id = request.args.get('guild_id')
        if not guild_id:
            # Bot yeni baglandiginda guild cache'i birkac saniye bos kalabilir.
            # Dashboard acilir acilmez sorgu gelirse 0 sunucu donuyordu -> kisa sure bekle.
            waited = 0.0
            while not bot.guilds and waited < 5.0:
                time.sleep(0.25)
                waited += 0.25

            guilds = [{'id': str(g.id), 'name': g.name} for g in bot.guilds]
            if not guilds:
                return jsonify({
                    'guilds': [],
                    'error': 'Bot sunucuya baglanmadi - 5 saniye icinde baglanmadi'
                }), 503
            return jsonify({'guilds': guilds})

        try:
            guild = resolve_guild(bot, guild_id)
        except (ValueError, TypeError):
            return jsonify({'error': 'Gecersiz sunucu numarasi'}), 400

        if not guild:
            return jsonify({'error': 'Sunucu bulunamadi - bot o sunucuda degil'}), 404

        channels = [
            {
                'id': str(ch.id),
                'name': ch.name,
                'members': len(ch.members),
                'user_limit': ch.user_limit or 0
            }
            for ch in guild.voice_channels
        ]

        current = None
        for vc in bot.voice_clients:
            if vc.guild.id == guild.id:
                current = {
                    'channel_id': str(vc.channel.id) if vc.channel else None,
                    'channel_name': vc.channel.name if vc.channel else None
                }
                break

        return jsonify({
            'channels': channels,
            'current': current,
            'guild_name': guild.name
        })

    # POST - katil / ayril / tasin
    data = request.json or {}
    action = data.get('action')
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')

    guild = bot.get_guild(int(guild_id)) if guild_id else None
    if not guild:
        return jsonify({'error': 'Sunucu bulunamadi'}), 404

    async def do_action():
        # Mevcut baglantiyi bul
        vc = None
        for c in bot.voice_clients:
            if c.guild.id == guild.id:
                vc = c
                break

        if action == 'leave':
            if vc:
                await vc.disconnect(force=True)
                return True, 'Ses kanalindan ayrildi'
            return False, 'Bot zaten ses kanalinda degil'

        if action == 'join' or action == 'move':
            if not channel_id:
                return False, 'Kanal secilmedi'

            channel = guild.get_channel(int(channel_id))
            if not channel:
                return False, 'Kanal bulunamadi'

            if vc:
                await vc.move_to(channel)
                return True, f'{channel.name} kanalina tasindi'

            await channel.connect()
            return True, f'{channel.name} kanalina baglandi'

        return False, 'Bilinmeyen islem'

    try:
        ok, msg = run_async(do_action(), timeout=25)
        if ok:
            print(f"[dashboard] Ses: {msg}", flush=True)
            return jsonify({'success': True, 'message': msg})
        return jsonify({'error': msg}), 400
    except Exception as e:
        return jsonify({'error': f'{type(e).__name__}: {e}'}), 500


@app.route('/api/bot_profile_upload', methods=['POST'])
def api_bot_profile_upload():
    """Bot avatar / banner dosya yukleme"""
    bot = app.config.get('BOT')
    if not bot or not bot.user:
        return jsonify({'error': 'Bot not available'}), 500

    avatar_file = request.files.get('avatar')
    banner_file = request.files.get('banner')

    if not avatar_file and not banner_file:
        return jsonify({'error': 'Avatar veya banner dosyasi seciniz'}), 400

    MAX_SIZE = 8 * 1024 * 1024
    ALLOWED_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

    def read_image(fileobj, label):
        if not fileobj or not fileobj.filename:
            return None, None

        ext = os.path.splitext(fileobj.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            return None, f'{label}: Format desteklenmiyor ({ext or "belirsiz"}). PNG, JPG, GIF, WebP kullanin'

        data = fileobj.read()
        if len(data) > MAX_SIZE:
            return None, f'{label}: Dosya 8 MB dan buyuk'
        if len(data) < 100:
            return None, f'{label}: Dosya bos veya gecersiz'
        return data, None

    avatar_bytes, err = read_image(avatar_file, 'avatar')
    if err:
        return jsonify({'error': err}), 400

    banner_bytes, err = read_image(banner_file, 'banner')
    if err:
        return jsonify({'error': err}), 400

    async def apply_upload():
        kwargs = {}
        if avatar_bytes:
            kwargs['avatar'] = avatar_bytes
        if banner_bytes:
            kwargs['banner'] = banner_bytes
        try:
            await bot.user.edit(**kwargs)
            return True, list(kwargs.keys())
        except discord.Forbidden:
            return False, ['Discord bu degisiklige izin vermedi']
        except discord.HTTPException as e:
            return False, [f'Discord reddetti (HTTP {e.status}): {e.text}']

    try:
        ok, result = run_async(apply_upload(), timeout=25)
        if ok:
            print(f"[dashboard] Dosya yuklendi: {result}", flush=True)
            return jsonify({'success': True, 'changed': result})
        return jsonify({'error': ' | '.join(result)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/activity_image', methods=['POST'])
def api_activity_image():
    """Oyun durumu gorseli dosya yukleme (Rich Presence icin)"""
    if not app.config.get('BOT'):
        return jsonify({'error': 'Bot not available'}), 500

    kind = request.form.get('kind', 'large')
    fileobj = request.files.get('image')

    if not fileobj or not fileobj.filename:
        return jsonify({'error': 'Resim dosyasi seciniz'}), 400

    if kind not in ('large', 'small'):
        return jsonify({'error': 'Gecersiz tur'}), 400

    ext = os.path.splitext(fileobj.filename)[1].lower()
    if ext not in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}:
        return jsonify({'error': f'Format desteklenmiyor: {ext}'}), 400

    data = fileobj.read()
    if len(data) > 2 * 1024 * 1024:
        return jsonify({'error': 'Dosya 2 MB dan buyuk'}), 400

    os.makedirs('activity_images', exist_ok=True)
    safe_name = f'activity_images/{kind}.png'
    with open(safe_name, 'wb') as f:
        f.write(data)

    import base64
    b64 = base64.b64encode(data).decode()

    return jsonify({
        'success': True,
        'file': safe_name,
        'size': len(data),
        'data_url': f'data:image/png;base64,{b64}',
        'note': 'Discord Rich Presence gorselleri API ile yuklenemez. '
                'Bu dosya onizleme icin saklandi - gercek gorsel icin Developer Portal > '
                'Rich Presence > Art Assets bolumune yukleyip Asset ID kullanin.'
    })


@app.route('/api/dashboard_theme', methods=['GET', 'POST'])
def api_dashboard_theme():
    """Dashboard tema/ozellestirme ayarlari"""
    config_file = 'dashboard_theme.json'

    DEFAULTS = {
        'title': 'Discord Bot Dashboard',
        'subtitle': 'Bot kontrol paneli',
        'accent_color': '#00d4ff',
        'accent_color_2': '#7b2cbf',
        'bg_color': '#1a1a2e',
        'bg_color_2': '#16213e',
        'card_bg': 'rgba(255,255,255,0.05)',
        'font_family': "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
        'refresh_interval': 30,
        'hide_tabs': [],
        'show_stats': True,
        'rounded_corners': 12
    }

    def load():
        cfg = dict(DEFAULTS)
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k in DEFAULTS and v is not None:
                    cfg[k] = v
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return cfg

    if request.method == 'GET':
        return jsonify(load())

    data = request.json or {}
    cfg = load()

    # Renk dogrulama (sadece hex)
    import re
    hex_pattern = re.compile(r'^#[0-9a-fA-F]{6}$')

    for key in ('accent_color', 'accent_color_2', 'bg_color', 'bg_color_2'):
        val = data.get(key)
        if val and hex_pattern.match(val.strip()):
            cfg[key] = val.strip()

    if 'title' in data and data['title'].strip():
        cfg['title'] = data['title'].strip()[:60]
    if 'subtitle' in data and data['subtitle'].strip():
        cfg['subtitle'] = data['subtitle'].strip()[:120]
    if 'font_family' in data and data['font_family'].strip():
        cfg['font_family'] = data['font_family'].strip()[:100]

    try:
        interval = int(data.get('refresh_interval', cfg['refresh_interval']))
        if 5 <= interval <= 600:
            cfg['refresh_interval'] = interval
    except (TypeError, ValueError):
        pass

    try:
        corners = int(data.get('rounded_corners', cfg['rounded_corners']))
        cfg['rounded_corners'] = max(0, min(30, corners))
    except (TypeError, ValueError):
        pass

    if 'show_stats' in data:
        cfg['show_stats'] = bool(data['show_stats'])

    if 'hide_tabs' in data and isinstance(data['hide_tabs'], list):
        valid = {'commands', 'logs', 'backups', 'farm', 'fivem',
                 'giveaways', 'voice', 'guard', 'settings'}
        cfg['hide_tabs'] = [t for t in data['hide_tabs'] if t in valid]

    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print("[dashboard] Tema guncellendi", flush=True)
    except OSError as e:
        return jsonify({'error': str(e)}), 500

    return jsonify(cfg)


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

    # bot.loop sadece async context icinde okunabilir.
    # Flask ayri thread'de calistigi icin loop referansini simdiden saklayalim.
    try:
        app.config['BOT_LOOP'] = asyncio.get_running_loop()
    except RuntimeError:
        app.config['BOT_LOOP'] = None

    cog = Dashboard(bot)
    await bot.add_cog(cog)
    print(f"[DASHBOARD] Port: {cog.port}, Bot hazir mi: {bot.is_ready()}", flush=True)

    # Bot cog yuklenmeden once hazirlandiysa on_ready tetiklenmez,
    # bu yuzden elle kontrol edip dashboard'u hemen baslat.
    if bot.is_ready():
        await asyncio.sleep(0.5)
        await cog.start_dashboard()


def run_async(coro, timeout=15):
    """Flask thread'inden bot loop'una coroutine calistirir"""
    loop = app.config.get('BOT_LOOP')
    if loop is None or loop.is_closed():
        raise RuntimeError('Bot loopu erisilebilir degil')

    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)
