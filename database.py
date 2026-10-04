import aiosqlite
import os
from datetime import datetime

class Database:
    def __init__(self):
        db_url = os.environ.get('DATABASE_URL', 'sqlite:///bot.db')
        if db_url.startswith('sqlite:///'):
            self.db_path = db_url.replace('sqlite:///', '', 1)
        else:
            self.db_path = 'bot.db'
        self.connection = None

    def _resolve_path(self):
        """Veritabanı yazılabilir değilse çalışma dizinine düş"""
        if os.path.dirname(self.db_path):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        return self.db_path

    async def connect(self):
        """Connect to the database and create tables"""
        try:
            self.connection = await aiosqlite.connect(self._resolve_path())
        except (OSError, PermissionError) as e:
            # Yazma izni yoksa geçici dizin kullan
            import tempfile
            fallback = os.path.join(tempfile.gettempdir(), 'bot.db')
            print(f"[!] Veritabanı yazılamadı ({e}), geçici dizin kullanılıyor: {fallback}")
            self.connection = await aiosqlite.connect(fallback)
        await self.create_tables()

    async def close(self):
        """Close the database connection"""
        if self.connection:
            await self.connection.close()

    async def create_tables(self):
        """Create all necessary tables"""
        # Economy table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                guild_id INTEGER,
                balance INTEGER DEFAULT 1000,
                bank INTEGER DEFAULT 0,
                daily_streak INTEGER DEFAULT 0,
                last_daily TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Levels table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS levels (
                user_id INTEGER,
                guild_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                messages INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')

        # Warnings table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Mutes table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS mutes (
                user_id INTEGER,
                guild_id INTEGER,
                mute_role_id INTEGER,
                reason TEXT,
                muted_at TEXT,
                unmute_at TEXT,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')

        # Settings table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER PRIMARY KEY,
                prefix TEXT DEFAULT '!',
                welcome_channel_id INTEGER,
                welcome_message TEXT,
                leave_channel_id INTEGER,
                leave_message TEXT,
                log_channel_id INTEGER,
                mute_role_id INTEGER,
                autorole_id INTEGER,
                levelup_channel_id INTEGER,
                levelup_message TEXT,
                rol_log_channel_id INTEGER,
                dm_giris_acik INTEGER DEFAULT 0,
                dm_giris_mesaj TEXT,
                dm_cikis_acik INTEGER DEFAULT 0,
                dm_cikis_mesaj TEXT,
                uyari_rolleri TEXT
            )
        ''')

        # FiveM sunucu giris kayitlari
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS fivem_servers (
                guild_id INTEGER NOT NULL,
                server_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                host TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS fivem_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                server_id INTEGER,
                user_id INTEGER,
                server_name TEXT,
                player_name TEXT,
                steam_id TEXT,
                license_id TEXT,
                ip TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await self.connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_fivem_conn ON fivem_connections(guild_id, id DESC)'
        )
        await self.connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_fivem_conn_user ON fivem_connections(guild_id, user_id)'
        )

        # Guard - Wick tarzi tehdit/aksiyon takibi
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS guard_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                action_type TEXT,
                severity INTEGER DEFAULT 0,
                description TEXT,
                executor_id INTEGER,
                executor_name TEXT,
                target_name TEXT,
                blocked INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS guard_threat (
                guild_id INTEGER PRIMARY KEY,
                score INTEGER DEFAULT 0,
                raid_mode INTEGER DEFAULT 0,
                last_raid_join TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS guard_user_threat (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                score INTEGER DEFAULT 0,
                action_count INTEGER DEFAULT 0,
                last_seen TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')

        # Indexler - hizli sorgu icin
        await self.connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_guard_actions_guild ON guard_actions(guild_id, id DESC)'
        )
        await self.connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_guard_threat_users ON guard_user_threat(guild_id, score DESC)'
        )

        # Music queue table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS music_queue (
                guild_id INTEGER PRIMARY KEY,
                current_song TEXT,
                queue TEXT,
                volume INTEGER DEFAULT 100,
                loop_mode TEXT DEFAULT 'off'
            )
        ''')

        # Giveaways table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                prize TEXT,
                winners INTEGER,
                end_time TEXT,
                host_id INTEGER,
                ended INTEGER DEFAULT 0
            )
        ''')

        # Reminders table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                reminder TEXT,
                remind_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Farms table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS farms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                amount INTEGER,
                farm_type TEXT DEFAULT 'Belirtilmedi',
                reason TEXT,
                moderator_id INTEGER,
                created_at TEXT
            )
        ''')

        # FiveM weapons table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS fivem_weapons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                weapon_name TEXT,
                price INTEGER,
                moderator_id INTEGER,
                created_at TEXT
            )
        ''')

        # FiveM weapons lost table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS fivem_weapons_lost (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                weapon_name TEXT,
                reason TEXT,
                moderator_id INTEGER,
                created_at TEXT
            )
        ''')

        # Guard settings table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS guard_settings (
                guild_id INTEGER PRIMARY KEY,
                settings TEXT
            )
        ''')

        # Quarantines table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS quarantines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                reason TEXT,
                moderator_id INTEGER,
                created_at TEXT,
                expires_at TEXT
            )
        ''')

        # Server quarantines table
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS server_quarantines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                reason TEXT,
                moderator_id INTEGER,
                created_at TEXT,
                expires_at TEXT
            )
        ''')

        await self.connection.commit()

        await self._migrate_settings()
        await self._migrate_farms()

    async def _migrate_farms(self):
        """farms tablosuna eksik kolonlari ekle"""
        try:
            async with self.connection.execute("PRAGMA table_info(farms)") as cursor:
                rows = await cursor.fetchall()

            if not rows:
                return

            existing = {row[1] for row in rows}

            if 'farm_type' not in existing:
                await self.connection.execute(
                    "ALTER TABLE farms ADD COLUMN farm_type TEXT DEFAULT 'Belirtilmedi'"
                )
                print("[db] farms.farm_type kolonu eklendi", flush=True)

            await self.connection.commit()
        except Exception as e:
            print(f"[db] farms migration hatasi: {e}", flush=True)

    async def _migrate_settings(self):
        """Eksik settings kolonlarini ekle (eski veritabanlari icin)"""
        log_columns = [
            'guard_log_channel_id',
            'mod_log_channel_id',
            'message_log_channel_id',
            'voice_log_channel_id',
            'member_log_channel_id',
            'rol_log_channel_id',
            'silah_katlanan_log_channel_id',
            'silah_kaybedilen_log_channel_id',
            'farm_log_channel_id',
        ]

        # Giris/cikis DM ayarlari (metin + anahtar kolonlari)
        dm_columns = [
            ('dm_giris_acik', 'INTEGER DEFAULT 0'),
            ('dm_giris_mesaj', 'TEXT'),
            ('dm_cikis_acik', 'INTEGER DEFAULT 0'),
            ('dm_cikis_mesaj', 'TEXT'),
            ('uyari_rolleri', 'TEXT'),
        ]

        try:
            async with self.connection.execute("PRAGMA table_info(settings)") as cursor:
                rows = await cursor.fetchall()

            if not rows:
                return

            existing = {row[1] for row in rows}

            for col in log_columns:
                if col not in existing:
                    await self.connection.execute(
                        f'ALTER TABLE settings ADD COLUMN {col} INTEGER'
                    )
                    print(f"[db] Yeni kolon eklendi: {col}", flush=True)

            for col, coltype in dm_columns:
                if col not in existing:
                    await self.connection.execute(
                        f'ALTER TABLE settings ADD COLUMN {col} {coltype}'
                    )
                    print(f"[db] Yeni kolon eklendi: {col}", flush=True)

            await self.connection.commit()
        except Exception as e:
            print(f"[db] Migration hatasi: {e}", flush=True)

    # Economy methods
    async def get_balance(self, user_id: int, guild_id: int):
        async with self.connection.execute(
            'SELECT balance, bank FROM economy WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {'balance': row[0], 'bank': row[1]}
            return None

    async def create_user(self, user_id: int, guild_id: int):
        await self.connection.execute(
            'INSERT OR IGNORE INTO economy (user_id, guild_id) VALUES (?, ?)',
            (user_id, guild_id)
        )
        await self.connection.commit()

    async def update_balance(self, user_id: int, guild_id: int, amount: int):
        await self.create_user(user_id, guild_id)
        await self.connection.execute(
            'UPDATE economy SET balance = balance + ? WHERE user_id = ? AND guild_id = ?',
            (amount, user_id, guild_id)
        )
        await self.connection.commit()

    async def update_bank(self, user_id: int, guild_id: int, amount: int):
        await self.create_user(user_id, guild_id)
        await self.connection.execute(
            'UPDATE economy SET bank = bank + ? WHERE user_id = ? AND guild_id = ?',
            (amount, user_id, guild_id)
        )
        await self.connection.commit()

    # Levels methods
    async def get_level(self, user_id: int, guild_id: int):
        async with self.connection.execute(
            'SELECT xp, level, messages FROM levels WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {'xp': row[0], 'level': row[1], 'messages': row[2]}
            return None

    async def update_xp(self, user_id: int, guild_id: int, xp: int):
        await self.connection.execute(
            '''INSERT INTO levels (user_id, guild_id, xp, messages) 
               VALUES (?, ?, ?, 1)
               ON CONFLICT(user_id, guild_id) 
               DO UPDATE SET xp = xp + ?, messages = messages + 1''',
            (user_id, guild_id, xp, xp)
        )
        await self.connection.commit()

    async def set_level(self, user_id: int, guild_id: int, level: int):
        await self.connection.execute(
            'UPDATE levels SET level = ? WHERE user_id = ? AND guild_id = ?',
            (level, user_id, guild_id)
        )
        await self.connection.commit()

    # Warnings methods
    async def add_warning(self, user_id: int, guild_id: int, moderator_id: int, reason: str):
        await self.connection.execute(
            'INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?, ?, ?, ?)',
            (user_id, guild_id, moderator_id, reason)
        )
        await self.connection.commit()

    async def get_warnings(self, user_id: int, guild_id: int):
        async with self.connection.execute(
            'SELECT * FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY created_at DESC',
            (user_id, guild_id)
        ) as cursor:
            return await cursor.fetchall()

    async def remove_warning(self, warning_id: int):
        await self.connection.execute(
            'DELETE FROM warnings WHERE id = ?',
            (warning_id,)
        )
        await self.connection.commit()

    async def clear_warnings(self, user_id: int, guild_id: int):
        """Uyenin tum uyari gecmisini siler"""
        await self.connection.execute(
            'DELETE FROM warnings WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        )
        await self.connection.commit()

    # Settings methods
    async def get_settings(self, guild_id: int):
        async with self.connection.execute(
            'SELECT * FROM settings WHERE guild_id = ?',
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            # Sutun adlarini ve degerleri eslestir - yeni log kolonlari otomatik gelir
            async with self.connection.execute('PRAGMA table_info(settings)') as pcur:
                columns = [r[1] for r in await pcur.fetchall()]

            data = {}
            for idx, col in enumerate(columns):
                if idx < len(row):
                    data[col] = row[idx]

            # Eski sabit anahtarlarla uyumluluk
            data['prefix'] = data.get('prefix') or '!'
            data['welcome_channel_id'] = data.get('welcome_channel_id')
            data['welcome_message'] = data.get('welcome_message')
            data['leave_channel_id'] = data.get('leave_channel_id')
            data['leave_message'] = data.get('leave_message')
            data['log_channel_id'] = data.get('log_channel_id')
            data['mute_role_id'] = data.get('mute_role_id')
            data['autorole_id'] = data.get('autorole_id')

            # DM giris/cikis ayarlari (eski satirlarda olmayabilir)
            data['dm_giris_acik'] = bool(data.get('dm_giris_acik'))
            data['dm_giris_mesaj'] = data.get('dm_giris_mesaj') or ''
            data['dm_cikis_acik'] = bool(data.get('dm_cikis_acik'))
            data['dm_cikis_mesaj'] = data.get('dm_cikis_mesaj') or ''

            return data

    async def update_setting(self, guild_id: int, key: str, value):
        await self.connection.execute(
            'INSERT OR IGNORE INTO settings (guild_id) VALUES (?)',
            (guild_id,)
        )
        await self.connection.execute(
            f'UPDATE settings SET {key} = ? WHERE guild_id = ?',
            (value, guild_id)
        )
        await self.connection.commit()

    # Reminders methods
    async def add_reminder(self, user_id: int, guild_id: int, reminder: str, remind_at: str):
        await self.connection.execute(
            'INSERT INTO reminders (user_id, guild_id, reminder, remind_at) VALUES (?, ?, ?, ?)',
            (user_id, guild_id, reminder, remind_at)
        )
        await self.connection.commit()

    async def get_reminders(self, user_id: int):
        async with self.connection.execute(
            'SELECT * FROM reminders WHERE user_id = ? AND remind_at <= ?',
            (user_id, datetime.now().isoformat())
        ) as cursor:
            return await cursor.fetchall()

    async def remove_reminder(self, reminder_id: int):
        await self.connection.execute(
            'DELETE FROM reminders WHERE id = ?',
            (reminder_id,)
        )
        await self.connection.commit()
