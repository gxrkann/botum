"""
Slash komut adlarini Turkceye cevirir.
Discord sadece a-z 0-9 - _ kabul eder, bu yuzden Turkce harfler kullanilmaz.

Sadece @app_commands.command(name='...') satirini degistirir,
Python fonksiyon adlari ve diger referanslar oldugu gibi kalir.
"""
import io
import os
import sys

# dosya -> {eski: yeni}
MAP = {
    'cogs/moderation.py': {
        'ban': 'yasakla',
        'kick': 'at',
        'mute': 'sustur',
        'unmute': 'susturma_kaldir',
        'clear': 'temizle',
        'slowmode': 'yavas_mod',
        'lock': 'kilitle',
        'unlock': 'kilit_ac',
        'nick': 'takma_ad',
        'role_add': 'rol_ekle',
        'role_remove': 'rol_kaldir',
    },
    'cogs/music.py': {
        'play': 'cal',
        'skip': 'atla',
        'pause': 'duraklat',
        'resume': 'devam_et',
        'stop': 'durdur',
        'queue': 'sira',
        'loop': 'tekrar',
        'volume': 'ses_seviye',
        'nowplaying': 'suregi_cal',
    },
    'cogs/utility.py': {
        'remind': 'hatirlat',
        'timer': 'geri_sayim',
        'ping': 'gecikme',
        'invite': 'davet',
        'support': 'destek',
        'vote': 'oy_ver',
        'stats': 'istatistik',
        'uptime': 'calisma_suresi',
        'weather': 'hava_durumu',
        'translate': 'ceviri',
        'shorten': 'link_kisit',
        'qr': 'qr_kod',
        'screenshot': 'ekran_goruntu',
        'bitcoin': 'btc_fiyat',
        'github': 'github_bilgi',
        'npm': 'npm_bilgi',
        'urban': 'sozluk',
    },
    'cogs/help.py': {
        'help': 'yardim',
    },
}

for path, mapping in MAP.items():
    with io.open(path, encoding='utf-8') as f:
        lines = f.readlines()

    changed = []
    for i, line in enumerate(lines):
        if '@app_commands.command(' not in line:
            continue
        for old, new in mapping.items():
            marker = "name='%s'" % old
            if marker in line:
                lines[i] = line.replace(marker, "name='%s'" % new)
                changed.append('%s -> %s' % (old, new))
                break

    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        f.writelines(lines)

    print('%s: %d komut' % (path, len(changed)))
    for c in changed:
        print('    ' + c)