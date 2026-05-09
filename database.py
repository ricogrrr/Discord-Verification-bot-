import sqlite3
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path='bot_settings.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    prefix TEXT DEFAULT '!',
                    verified_role_name TEXT DEFAULT 'Verified',
                    unverified_role_name TEXT DEFAULT 'Unverified',
                    verification_channel_id INTEGER,
                    log_channel_id INTEGER,
                    verification_type TEXT DEFAULT 'custom_captcha',
                    auto_role_on_join BOOLEAN DEFAULT 1,
                    delete_verification_messages BOOLEAN DEFAULT 0,
                    verification_timeout_minutes INTEGER DEFAULT 5,
                    max_captcha_attempts INTEGER DEFAULT 3
                )
            ''')
            conn.commit()

    def get_settings(self, guild_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM guild_settings WHERE guild_id = ?', (guild_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_settings(self, guild_id, **kwargs):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if exists
            cursor.execute('SELECT 1 FROM guild_settings WHERE guild_id = ?', (guild_id,))
            exists = cursor.fetchone()

            if not exists:
                # Insert default values first
                cursor.execute('INSERT INTO guild_settings (guild_id) VALUES (?)', (guild_id,))

            if kwargs:
                columns = ', '.join([f"{k} = ?" for k in kwargs.keys()])
                values = list(kwargs.values()) + [guild_id]
                cursor.execute(f'UPDATE guild_settings SET {columns} WHERE guild_id = ?', values)

            conn.commit()

    def delete_guild(self, guild_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM guild_settings WHERE guild_id = ?', (guild_id,))
            conn.commit()
