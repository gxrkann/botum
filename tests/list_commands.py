"""
Tum slash komutlarini gercek bot agacindan okur ve listeler.
Discord'e baglanmaz, sadece cog'lari yukler.
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from discord.ext import commands as dpy
from discord import app_commands
from discord.utils import MISSING

COGS = [
    'cogs.moderation', 'cogs.music', 'cogs.fun', 'cogs.utility',
    'cogs.events', 'cogs.error_handler', 'cogs.help', 'cogs.farm',
    'cogs.fivem', 'cogs.giveaway', 'cogs.voice_tracker',
    'cogs.voice_manager', 'cogs.owner_protect', 'cogs.guard',
    'cogs.announcement', 'dashboard',
]


def param_str(cmd):
    out = []
    for p in cmd.parameters:
        inp = getattr(p, 'input', None)
        if inp is None:
            inp = getattr(p, 'annotation', str)
        if isinstance(inp, app_commands.Choice):
            t = f"[{len(inp.choices)} sec.]"
        elif getattr(inp, '__name__', '') == 'Mentionable':
            t = 'uye/rol'
        elif isinstance(inp, type):
            t = inp.__name__
        else:
            t = type(inp).__name__
        req = '' if getattr(p, 'required', True) else '?'
        out.append(f'{p.name}{req}:{t}')
    return ', '.join(out)


async def go():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.voice_states = True

    bot = dpy.Bot(command_prefix='!', intents=intents, help_command=None)

    for cog in COGS:
        try:
            await bot.load_extension(cog)
        except Exception as e:
            print(f'HATA [{cog}]: {type(e).__name__}: {e}', file=sys.stderr)

    cmds = sorted(bot.tree.get_commands(), key=lambda c: c.name)

    print(f'{"COG":<15} {"KOMUT":<22} {"ACIKLAMA":<52} PARAMETRELER')
    print('=' * 148)
    for c in cmds:
        cog = c.module.split('.')[-1] if c.module else '-'
        desc = (c.description or '')[:50]
        print(f'{cog:<15} /{c.name:<21} {desc:<52} {param_str(c)}')

    print('=' * 148)
    print(f'TOPLAM: {len(cmds)} komut   (Discord siniri: 100 | Kalan: {100 - len(cmds)})')

    print('\nCOG BAZLI DAGILIM')
    from collections import Counter
    for cog, n in sorted(Counter(
        c.module.split('.')[-1] if c.module else '-' for c in cmds
    ).items(), key=lambda x: -x[1]):
        print(f'  {cog:<16}{n:>4}')

    await bot.close()


asyncio.run(go())