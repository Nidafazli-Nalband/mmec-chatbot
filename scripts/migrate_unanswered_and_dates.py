#!/usr/bin/env python3
"""
Migration script to backfill unanswered queries from chat_logs.json and to set missing user registration dates.
Run from project root: python scripts/migrate_unanswered_and_dates.py
"""
import os, json, sqlite3, datetime
ROOT = os.path.dirname(os.path.dirname(__file__)) if os.path.basename(__file__)=='migrate_unanswered_and_dates.py' else os.getcwd()
CHAT_LOG = os.path.join(ROOT, 'chat_logs.json')
DB = os.path.join(ROOT, 'data', 'mmec.db')
USERS_DB = os.path.join(ROOT, 'data', 'users.db')

# Backfill unanswered queries
if os.path.exists(CHAT_LOG) and os.path.exists(DB):
    print('Backfilling unanswered queries from chat_logs.json...')
    try:
        with open(CHAT_LOG, 'r', encoding='utf-8') as f:
            logs = json.load(f)
    except Exception as e:
        print('Failed to load chat_logs.json:', e)
        logs = []
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS unanswered_queries (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, answer TEXT, answered INTEGER DEFAULT 0, answered_at TEXT, answered_by TEXT)''')
    inserted = 0
    for entry in logs:
        try:
            user = entry.get('user')
            q = entry.get('user_msg') or entry.get('user')
            bot = entry.get('bot_msg') or ''
            # Treat unanswered if no bot_msg or bot_msg empty after strip
            if not q:
                continue
            if not bot or str(bot).strip()=='' or 'not found' in str(bot).lower() or 'found relevant data' in str(bot).lower():
                # avoid duplicates
                cur.execute('SELECT id FROM unanswered_queries WHERE question=?', (q,))
                if cur.fetchone():
                    continue
                cur.execute('INSERT INTO unanswered_queries (question, timestamp) VALUES (?, ?)', (q, entry.get('ts') or datetime.datetime.utcnow().isoformat()+'Z'))
                inserted += 1
        except Exception:
            continue
    conn.commit()
    conn.close()
    print(f'Inserted {inserted} unanswered queries.')
else:
    print('Skipping unanswered backfill: chat_logs.json or database not found.')

# Set missing created_at in users.db to 2025-11-22 if any
if os.path.exists(USERS_DB):
    print('Backfilling missing user created_at in users.db...')
    conn = sqlite3.connect(USERS_DB)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
    except Exception:
        pass
    # Set created_at to 2025-11-22T00:00:00Z for rows where created_at is null or empty
    cutoff = '2025-11-22T00:00:00Z'
    cur.execute("UPDATE users SET created_at=? WHERE created_at IS NULL OR created_at=''", (cutoff,))
    updated = cur.rowcount
    conn.commit()
    conn.close()
    print(f'Updated {updated} user rows with default created_at {cutoff}.')
else:
    print('users.db not found, skipping user date backfill.')

print('Migration finished.')
