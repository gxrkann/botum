# Discord Bot

Kapsamlı Discord botu - Python + discord.py

## Özellikler

### 🛡️ Moderasyon
- Ban, Kick, Mute, Unmute
- Warn sistemi
- Slowmode, Lock/Unlock
- Mesaj temizleme
- Rol yönetimi
- Takma ad değiştirme

### 🎵 Müzik
- YouTube/Spotify çalma
- Sıra yönetimi
- Tekrar modu (off/one/all)
- Ses kontrolü
- Duraklat/Devam et/Atla

### 💰 Ekonomi
- Günlük ödül
- Banka sistemi (yatır/çek)
- Para transferi
- Çalışma sistemi
- Soygunluk
- Zenginlik sıralaması

### 📊 Seviye
- XP sistemi
- Seviye atlama
- Sıralama
- Seviye kartı

### 🎉 Eğlence
- Yazı tura, Zar, 8-Ball
- Taş kağıt makas
- Sayı tahmin oyunu
- Anket oluşturma
- Şaka, Meme
- Ship, Gaylik, Simp, Hotrate

### 🔧 Yardımcı
- Hatırlatma sistemi
- Geri sayım
- Ping ölçümü
- Bot istatistikleri
- QR kod oluşturma
- Sunucu/Kullanıcı bilgileri

### 📋 Event Sistemi
- Hoş geldin/Görüşürüz mesajları
- Otomatik rol
- Log sistemi (mesaj silme/düzenleme, ses kanalı, rol değişikliği)

### 🌐 Dashboard
- Web tabanlı kontrol paneli
- Canlı istatistikler
- Sunucu yönetimi
- Log görüntüleme
- Komut listesi

## Kurulum

### 1. Bağımlılıkları Yükle
```bash
pip install -r requirements.txt
```

### 2. Environment Ayarları
`.env.example` dosyasını `.env` olarak kopyala ve doldur:
```bash
cp .env.example .env
```

### 3. Bot Token'ı Al
1. [Discord Developer Portal](https://discord.com/developers/applications) git
2. Yeni uygulama oluştur
3. Bot sekmesinden token al
4. `.env` dosyasına ekle

### 4. Botu Çalıştır
```bash
python main.py
```

## Dashboard
Bot çalıştığında dashboard otomatik olarak başlar:
- **URL:** http://localhost:5000
- **Port:** 5000 (değiştirilebilir)

## Komutlar

Tüm komutlar slash command olarak çalışır (`/komut`).

### Moderasyon
| Komut | Açıklama |
|-------|----------|
| `/ban` | Üye yasakla |
| `/kick` | Üye at |
| `/mute` | Üye sustur |
| `/unmute` | Susturmayı kaldır |
| `/warn` | Uyarı ver |
| `/warnings` | Uyarıları gör |
| `/clear` | Mesaj sil |
| `/slowmode` | Yavaş mod |
| `/lock` | Kanal kilitle |
| `/unlock` | Kanal aç |
| `/nick` | Takma ad değiştir |
| `/role_add` | Rol ekle |
| `/role_remove` | Rol kaldır |

### Müzik
| Komut | Açıklama |
|-------|----------|
| `/play` | Müzik çal |
| `/skip` | Şarkı atla |
| `/pause` | Duraklat |
| `/resume` | Devam et |
| `/stop` | Durdur |
| `/queue` | Sırayı göster |
| `/loop` | Tekrar modu |
| `/volume` | Ses seviyesi |
| `/nowplaying` | Şimdi çalan |
| `/disconnect` | Botu ayır |

### Ekonomi
| Komut | Açıklama |
|-------|----------|
| `/balance` | Bakiyeni gör |
| `/daily` | Günlük ödül |
| `/deposit` | Banka yatır |
| `/withdraw` | Bankadan çek |
| `/transfer` | Para gönder |
| `/work` | Çalış |
| `/rob` | Soy |
| `/leaderboard` | Sıralama |

### Seviye
| Komut | Açıklama |
|-------|----------|
| `/rank` | Seviye kartı |
| `/leaderboard` | Sıralama |

### Eğlence
| Komut | Açıklama |
|-------|----------|
| `/yazitura` | Yazı tura |
| `/zar` | Zar at |
| `/8ball` | 8-Ball |
| `/meme` | Meme |
| `/avatar` | Avatar |
| `/servericon` | Sunucu ikonu |
| `/serverinfo` | Sunucu bilgisi |
| `/userinfo` | Kullanıcı bilgisi |
| `/poll` | Anket |
| `/guess` | Sayı tahmin |
| `/rps` | Taş kağıt makas |
| `/joke` | Şaka |
| `/ship` | Eşleştir |

### Yardımcı
| Komut | Açıklama |
|-------|----------|
| `/remind` | Hatırlatma |
| `/timer` | Geri sayım |
| `/ping` | Gecikme |
| `/invite` | Davet linki |
| `/support` | Destek |
| `/vote` | Oy ver |
| `/stats` | İstatistik |
| `/uptime` | Çalışma süresi |
| `/qr` | QR kod |

## Yapılandırma

### Environment Değişkenleri
| Değişken | Açıklama | Zorunlu |
|----------|----------|---------|
| `DISCORD_TOKEN` | Bot token | Evet |
| `PREFIX` | Komut prefix'i | Hayır (varsayılan: !) |
| `DATABASE_URL` | Veritabanı URL | Hayır (varsayılan: sqlite:///bot.db) |
| `SPOTIFY_CLIENT_ID` | Spotify API ID | Hayır |
| `SPOTIFY_CLIENT_SECRET` | Spotify API Secret | Hayır |
| `YOUTUBE_API_KEY` | YouTube API Key | Hayır |
| `OWNER_ID` | Bot sahibi ID | Hayır |

## Veritabanı
SQLite kullanılır. Tablolar otomatik oluşturulur:
- `economy` - Ekonomi verileri
- `levels` - Seviye verileri
- `warnings` - Uyarılar
- `mutes` - Susturmalar
- `settings` - Sunucu ayarları
- `music_queue` - Müzik sırası
- `giveaways` - Çekilişler
- `reminders` - Hatırmalar

## Güvenlik
- Token'ı asla paylaşma
- `.env` dosyasını `.gitignore`'a ekle
- Yetki kontrollerini düzgün ayarla
- Rate limit'e dikkat et

## Lisans
MIT
