"""
Guard Tehdit Motoru - Wick/Beni benzeri detayli guvenlik sistemi.

Ozellikler:
  * Her supheli olaya puan verir, toplam tehdit seviyesi uretir
  * Tehdit zamanla azalir (decay)
  * Hizli toplu katilim tespiti -> Raid modu
  * Sete gore kullanici tehdit takibi
  * Tum aksiyonlar veritabaninda saklanir (kim / ne / ne zaman / engellendi mi)
"""

# Olay -> puan (ne kadar yuksek o kadar tehlikeli)
THREAT_WEIGHTS = {
    'bot_eklendi': 50,
    'admin_verildi': 30,
    'yetki_verildi': 12,
    'webhook_olusturuldu': 10,
    'toplu_dm': 20,
    'toplu_rol': 15,
    'toplu_ban': 12,
    'toplu_mesaj_silme': 8,
    'yetkili_rol_olusturuldu': 14,
    'yetkili_rol_silindi': 8,
    'kanal_silindi': 5,
    'kanal_olusturuldu': 3,
    'rol_olusturuldu': 3,
    'rol_silindi': 4,
    'uye_atildi': 5,
    'uye_yasaklandi': 8,
    'sunucu_guncellendi': 25,
    'rol_degisti': 1,
    'hizli_giris': 8,
}

# Seviye etiketleri (Wick'ten)
THREAT_LEVELS = [
    (20,  'İmkânsız',      'İmkânsız',      0x2ECC71),   # yesil
    (40,  'Olası Değil',   'Olası Değil',   0x27AE60),   # yesil
    (60,  'Mümkün',        'Mümkün',        0xF1C40F),   # sari
    (80,  'Muhtemel',      'Muhtemel',      0xE67E22),   # turuncu
    (100, 'Kesin',         'Kesin',         0xE74C3C),   # kirmizi
]

# Puanin yarisi bu surede bir azalir (dakika)
DECAY_MINUTES = 30


def threat_level(score: int):
    """Puan -> (etiket, renk)"""
    score = max(0, min(100, int(score)))
    for limit, label, _, color in THREAT_LEVELS:
        if score <= limit:
            return label, color
    return 'Kesin', 0xE74C3C


def decay_score(score: int, minutes_passed: float) -> int:
    """Zaman gectikce tehdit azalir"""
    if minutes_passed <= 0:
        return score
    steps = int(minutes_passed // DECAY_MINUTES)
    if steps <= 0:
        return score
    # Her 30 dakikada yaridan fazla azalir
    factor = 0.6 ** steps
    return int(score * factor)


def add_score(score: int, action_type: str) -> int:
    """Olay tipine gore puan ekle"""
    weight = THREAT_WEIGHTS.get(action_type, 1)
    return max(0, min(100, score + weight))


def action_info(action_type: str):
    """Olay tipi -> (baslik, emoji, aciklama)"""
    data = {
        'bot_eklendi': ('🤖 Bot Eklendi', 'Bot eklendi'),
        'admin_verildi': ('👑 Admin Yetkisi', 'Yönetici yetkisi verildi'),
        'yetki_verildi': ('⚠️ Yetki Verildi', 'Tehlikeli yetki verildi'),
        'webhook_olusturuldu': ('🪝 Webhook Oluşturuldu', 'Webhook oluşturuldu'),
        'toplu_dm': ('📨 Toplu DM', 'Toplu DM gönderildi'),
        'toplu_rol': ('🎭 Toplu Rol', 'Toplu rol verildi'),
        'toplu_ban': ('🔨 Toplu Ban', 'Toplu yasaklama yapildi'),
        'toplu_mesaj_silme': ('🗑️ Toplu Mesaj Silme', 'Toplu mesaj silindi'),
        'yetkili_rol_olusturuldu': ('🎖️ Yetkili Rol Oluşturuldu', 'Yetkili rol oluşturuldu'),
        'yetkili_rol_silindi': ('🗑️ Yetkili Rol Silindi', 'Yetkili rol silindi'),
        'kanal_silindi': ('🗑️ Kanal Silindi', 'Kanal silindi'),
        'kanal_olusturuldu': ('📺 Kanal Oluşturuldu', 'Kanal oluşturuldu'),
        'rol_olusturuldu': ('🎭 Rol Oluşturuldu', 'Rol oluşturuldu'),
        'rol_silindi': ('🗑️ Rol Silindi', 'Rol silindi'),
        'uye_atildi': ('👢 Üye Atıldı', 'Üye atıldı'),
        'uye_yasaklandi': ('🔨 Üye Yasaklandı', 'Üye yasaklandi'),
        'sunucu_guncellendi': ('🏠 Sunucu Güncellendi', 'Sunucu ayarlari degisti'),
        'rol_degisti': ('🎭 Rol Değişti', 'Rol değişikliği'),
        'hizli_giris': ('⚡ Hızlı Giriş', 'Hizli toplu katilim'),
    }
    return data.get(action_type, ('⚠️ Olay', 'Bilinmeyen olay'))