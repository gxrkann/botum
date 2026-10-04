"""
FiveM Silah Katalogu

Her silah icin: marka, alt marka, kategori ve fiyat.
Discord'da yazi olarak gosterilir, veritabaninda marka ile saklanir.

Kategoriler:
  Tabanca, Pompali, Tabanca-MAK, Tufek, Keskin-Nisan, Agir-Silah
"""

# model -> {marka, alt, kategori, fiyat}
SILAH_KATALOG = {
    # ---------- TABANCALAR ----------
    "Glock-18": {"marka": "Glock", "alt": "Seri 1", "kategori": "Tabanca", "fiyat": 1500},
    "Glock-45": {"marka": "Glock", "alt": "Seri 2", "kategori": "Tabanca", "fiyat": 2200},
    "Deagle": {"marka": "Desert Eagle", "alt": "50 AE", "kategori": "Tabanca", "fiyat": 9000},
    "USP-S": {"marka": "USP", "alt": "Silah", "kategori": "Tabanca", "fiyat": 1800},
    "P250": {"marka": "Pistol", "alt": "250", "kategori": "Tabanca", "fiyat": 1600},
    "Revolver": {"marka": "Revolver", "alt": "357", "kategori": "Tabanca", "fiyat": 3200},
    "Taser": {"marka": "Taser", "alt": "X26", "kategori": "Tabanca", "fiyat": 800},
    "Stungun": {"marka": "Stungun", "alt": "Seri 1", "kategori": "Tabanca", "fiyat": 500},

    # ---------- POMPALI ----------
    "Pump-Action": {"marka": "Pompali", "alt": "12 Kalibre", "kategori": "Pompali", "fiyat": 6500},
    "Saiga-12": {"marka": "Saiga", "alt": "12 Kalibre", "kategori": "Pompali", "fiyat": 8500},
    "Pistol-Sgk": {"marka": "Seri", "alt": "Pompali", "kategori": "Pompali", "fiyat": 7200},

    # ---------- MAK ----------
    "MP5": {"marka": "Heckler & Koch", "alt": "MP5", "kategori": "Mak", "fiyat": 12000},
    "MP7": {"marka": "Heckler & Koch", "alt": "MP7", "kategori": "Mak", "fiyat": 14000},
    "MP9": {"marka": "Heckler & Koch", "alt": "MP9", "kategori": "Mak", "fiyat": 13500},
    "MAC-10": {"marka": "MAC", "alt": "10", "kategori": "Mak", "fiyat": 9000},
    "Uzi": {"marka": "Uzi", "alt": "Micro", "kategori": "Mak", "fiyat": 7500},
    "Micro-SMG": {"marka": "Micro", "alt": "SMG", "kategori": "Mak", "fiyat": 8000},
    "MP40": {"marka": "Bergmann", "alt": "MP40", "kategori": "Mak", "fiyat": 11000},

    # ---------- TUFEL ----------
    "AK-47": {"marka": "Kalashnikov", "alt": "AK-47", "kategori": "Tufek", "fiyat": 25000},
    "AK-74": {"marka": "Kalashnikov", "alt": "AK-74", "kategori": "Tufek", "fiyat": 28000},
    "M4A1": {"marka": "Colt", "alt": "M4A1", "kategori": "Tufek", "fiyat": 30000},
    "M16A4": {"marka": "Colt", "alt": "M16A4", "kategori": "Tufek", "fiyat": 32000},
    "SCAR-L": {"marka": "FN", "alt": "SCAR-L", "kategori": "Tufek", "fiyat": 38000},
    "SCAR-H": {"marka": "FN", "alt": "SCAR-H", "kategori": "Tufek", "fiyat": 42000},
    "FAMAS": {"marka": "FAMAS", "alt": "F3", "kategori": "Tufek", "fiyat": 33000},
    "G3": {"marka": "Heckler & Koch", "alt": "G3", "kategori": "Tufek", "fiyat": 31000},
    "Galil": {"marka": "IMI", "alt": "Galil", "kategori": "Tufek", "fiyat": 29000},
    "M14": {"marka": "M14", "alt": "EBR", "kategori": "Tufek", "fiyat": 35000},

    # ---------- KESKIN NISAN ----------
    "AWP": {"marka": "Accuracy International", "alt": "AWP", "kategori": "Keskin", "fiyat": 120000},
    "Kar98k": {"marka": "Mauser", "alt": "Kar98k", "kategori": "Keskin", "fiyat": 65000},
    "MK2": {"marka": "Remington", "alt": "MK2", "kategori": "Keskin", "fiyat": 58000},
    "M24": {"marka": "M24", "alt": "SWS", "kategori": "Keskin", "fiyat": 70000},
    "SR-25": {"marka": "SR-25", "alt": "Keskin", "kategori": "Keskin", "fiyat": 85000},
    "VSS": {"marka": "VSS", "alt": "Vintovka", "kategori": "Keskin", "fiyat": 40000},
    "Crossbow": {"marka": "Crossbow", "alt": "Balista", "kategori": "Keskin", "fiyat": 25000},

    # ---------- AGIR SILAH ----------
    "M249": {"marka": "FN", "alt": "M249", "kategori": "Agir", "fiyat": 150000},
    "MG3": {"marka": "Rheinmetall", "alt": "MG3", "kategori": "Agir", "fiyat": 130000},
    "RPK": {"marka": "RPK", "alt": "Silah", "kategori": "Agir", "fiyat": 55000},
    "Minigun": {"marka": "M134", "alt": "Minigun", "kategori": "Agir", "fiyat": 350000},
}

# Katalog disi silahlar icin genel deger
VARSAYILAN = {"marka": "Bilinmiyor", "alt": "-", "kategori": "Diger", "fiyat": 0}


def _normalize(s: str) -> str:
    """Bosluk, tire ve alt cizgi farklarini yok eder: 'AK 47' == 'ak-47'"""
    return (s or '').strip().lower().replace(' ', '').replace('-', '').replace('_', '')


def silah_bilgi(model: str):
    """Modele gore bilgi doner, bulunamazsa varsayilan"""
    if not model:
        return dict(VARSAYILAN)

    m = model.strip().lower()

    # Tam eslesme
    if m in SILAH_KATALOG:
        return dict(SILAH_KATALOG[m])

    norm = _normalize(m)

    # Normalize eslesme (AK 47 / ak_47 / ak-47)
    for k, v in SILAH_KATALOG.items():
        if _normalize(k) == norm:
            return dict(v)

    # Marka adiyla tam eslesme
    for k, v in SILAH_KATALOG.items():
        if m == v['marka'].lower():
            return dict(v)

    # Marka adi normalize eslesme
    for k, v in SILAH_KATALOG.items():
        if norm and _normalize(v['marka']) == norm:
            return dict(v)

    # Kismi eslesme
    if norm:
        for k, v in SILAH_KATALOG.items():
            if _normalize(k) in norm or norm in _normalize(k):
                return dict(v)

    sonuc = dict(VARSAYILAN)
    sonuc['marka'] = model.strip() or 'Bilinmiyor'
    return sonuc


def markalar():
    """Marka -> [modeller]"""
    sonuc = {}
    for model, bilgi in SILAH_KATALOG.items():
        sonuc.setdefault(bilgi['marka'], []).append((model, bilgi))
    return sonuc


def kategoriler():
    """Kategori -> [modeller]"""
    sonuc = {}
    for model, bilgi in SILAH_KATALOG.items():
        sonuc.setdefault(bilgi['kategori'], []).append((model, bilgi))
    return sonuc


def model_listesi():
    return sorted(SILAH_KATALOG.keys())