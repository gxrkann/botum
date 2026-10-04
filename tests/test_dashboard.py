"""
Dashboard endpoint testi - production mimarisini taklit eder.
Event loop ayri thread'de calisir, endpoint'ler main thread'den cagrilir.
"""
import concurrent.futures
import os
import sys
import threading
import time

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DISCORD_TOKEN', 'x')
os.environ.setdefault('ENABLE_MEMBERS_INTENT', 'false')

import asyncio

import discord
from discord.ext import commands as dpy_commands

LOOP_BOX = {}


class FakeMember:
    def __init__(self, uid, name='Uye'):
        self.id = uid
        self.name = name
        self.mention = f'<@{uid}>'
        self.bot = False


class FakeGuild:
    id = 100
    name = 'Test Sunucu'
    icon = type('I', (), {'url': 'http://x/icon.png'})()
    member_count = 42
    channels = []
    roles = []
    created_at = None
    owner = None

    def get_member(self, uid): return FakeMember(uid)


class FakeChannel:
    def __init__(self, cid, name='kanal'):
        self.id = cid
        self.name = name
        self.mention = f'<#{cid}>'


class FakeUser:
    id = 999
    name = 'TestBot'
    display_avatar = type('A', (), {'url': 'http://x/avatar.png'})()
    banner = None


class FakeCommand:
    def __init__(self, name, desc, type_='slash'):
        self.name = name
        self.description = desc
        self.type = type_


class FakeTree:
    def get_commands(self):
        return [FakeCommand('help', 'Yardim'), FakeCommand('ban', 'Yasakla')]


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows or []
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def fetchone(self): return self._rows[0] if self._rows else None
    async def fetchall(self): return self._rows
    def __await__(self):
        async def _self():
            return self
        return _self().__await__()


class FakeConn:
    # aiosqlite gibi: execute() dogrudan async CM dondurur (coroutine degil)
    def execute(self, sql, params=None):
        return FakeCursor([])
    async def commit(self): pass


class FakeDB:
    def __init__(self):
        self.connection = FakeConn()

    async def get_settings(self, guild_id):
        return {'guard_log_channel_id': None, 'log_channel_id': None, 'farm_log_channel_id': None}


class FakeBot(dpy_commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=discord.Intents.default(), help_command=None)
        self.db = FakeDB()
        self.logger = type('L', (), {'info': lambda *a: None, 'error': lambda *a: None})()
        self._user = FakeUser()
        self._guilds = [FakeGuild()]

    async def setup_hook(self): pass

    @property
    def user(self): return self._user
    @property
    def guilds(self): return self._guilds
    @property
    def tree(self): return FakeTree()
    @property
    def latency(self): return 0.05

    def get_guild(self, gid): return self._guilds[0] if gid == 100 else None
    def get_user(self, uid): return self._user if uid == 999 else FakeMember(uid)
    def get_channel(self, cid): return FakeChannel(cid)
    async def change_presence(self, activity=None):
        FakeBot.last_activity = activity


def run_loop():
    """Event loop'u ayri thread'de calistir"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    LOOP_BOX['loop'] = loop

    bot = FakeBot()
    LOOP_BOX['bot'] = bot

    loop.run_until_complete(bot.load_extension('dashboard'))
    # Loop calismaya devam etmeli (production'daki gibi)
    loop.run_forever()


ENDPOINTS = [
    ('GET', '/', None),
    ('GET', '/health', None),
    ('GET', '/api/stats', None),
    ('GET', '/api/guilds', None),
    ('GET', '/api/guild/100', None),
    ('GET', '/api/guild/999', None),
    ('GET', '/api/commands', None),
    ('GET', '/api/logs', None),
    ('GET', '/api/backups', None),
    ('GET', '/api/farm/100', None),
    ('GET', '/api/fivem/100', None),
    ('GET', '/api/giveaways', None),
    ('GET', '/api/voice/100', None),
    ('GET', '/api/bot_settings', None),
    ('GET', '/api/bot_invite', None),
    ('GET', '/api/bot_profile', None),
    ('GET', '/api/dashboard_theme', None),
    ('GET', '/api/guard/100', None),
    ('GET', '/api/bot_add/100', None),
    ('POST', '/api/dashboard_theme', {'title': 'Test Panel', 'accent_color': '#ff0000',
                                      'bg_color': '#101010', 'refresh_interval': 45}),
    ('POST', '/api/bot_settings', {'status': 'FiveM', 'large_image': '', 'large_text': 'RP'}),
    ('POST', '/api/guard/100', {'enabled': True, 'protections': ['ban', 'raid']}),
]


def main():
    t = threading.Thread(target=run_loop, daemon=True)
    t.start()
    time.sleep(3)

    dash = sys.modules['dashboard']
    dash.app.config['PROPAGATE_EXCEPTIONS'] = True
    dash.app.config['TESTING'] = True

    print('=' * 76)
    print(f'{"MET":<6}{"ENDPOINT":<26}{"SONUC":<9}DETAY')
    print('=' * 76)

    basarili = 0
    hatalar = []
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    for method, path, payload in ENDPOINTS:
        def call(method=method, path=path, payload=payload):
            app = dash.app
            with app.test_client() as c:
                if method == 'GET':
                    res = c.get(path)
                else:
                    res = c.post(path, json=payload)
                return res.status_code, res.get_data(as_text=True)

        try:
            code, text = pool.submit(call).result(timeout=30)
            if code < 400:
                basarili += 1
                print(f'{method:<6}{path:<26}{"OK":<9}')
            else:
                kısa = text[:200].replace('\n', ' ')
                hatalar.append((path, code, kısa))
                # Traceback satirlarini cikar
                import re as _re
                tb = _re.findall(r'File &quot;([^&]+)&quot;, line \d+.*?&#10;([^&]*\n){0,1}', text)
                sonuc = ''
                for f, _ in tb[-2:]:
                    sonuc += f' | {f}'
                print(f'{method:<6}{path:<26}{"HATA":<9}{sonuc}')
        except Exception as e:
            hatalar.append((path, 'EXC', str(e)))
            print(f'{method:<6}{path:<26}{"PATLADI":<9}{type(e).__name__}: {e}')

    print()
    print('=' * 76)
    print(f'DASHBOARD TESTI: {basarili}/{len(ENDPOINTS)} basarili')
    print('=' * 76)

    if hatalar:
        print('\HATALI ENDPOINTLER:')
        for path, code, detail in hatalar:
            print(f'  {path} [{code}]')
            print(f'    {detail}')


main()