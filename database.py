import sqlite3
import time

conn = sqlite3.connect('t11.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS memory
             (user_id INTEGER, message TEXT, timestamp REAL, respect INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS reports
             (type TEXT, count INTEGER, timestamp REAL)''')
conn.commit()

def save_message(user_id, message):
    c.execute("INSERT INTO memory VALUES (?,?,?,?)", (user_id, message, time.time(), get_respect(user_id)))
    conn.commit()

def get_respect(user_id):
    c.execute("SELECT respect FROM memory WHERE user_id=? ORDER BY timestamp DESC LIMIT 1", (user_id,))
    res = c.fetchone()
    return res[0] if res else 100

def update_respect(user_id, points):
    new = max(0, min(100, get_respect(user_id) + points))
    c.execute("INSERT INTO memory VALUES (?,?,?,?)", (user_id, "SYSTEM", time.time(), new))
    conn.commit()
    return new

def get_history(user_id, limit=10):
    c.execute("SELECT message FROM memory WHERE user_id=? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
    return [row[0] for row in c.fetchall()]

def last_seen(user_id):
    c.execute("SELECT MAX(timestamp) FROM memory WHERE user_id=?", (user_id,))
    res = c.fetchone()[0]
    return time.time() - res if res else 999

def is_banned(user_id):
    c.execute("SELECT timestamp FROM memory WHERE user_id=? AND message='BANNED' ORDER BY timestamp DESC LIMIT 1", (user_id,))
    res = c.fetchone()
    return res and time.time() - res[0] < 3600

def ban_user(user_id):
    c.execute("INSERT INTO memory VALUES (?,?,?,?)", (user_id, "BANNED", time.time(), 0))
    add_report("ban")
    conn.commit()

def add_report(r_type):
    c.execute("INSERT INTO reports VALUES (?,?,?)", (r_type, 1, time.time()))
    conn.commit()

def get_report():
    day = time.time() - 86400
    c.execute("SELECT type, COUNT(*) FROM reports WHERE timestamp > ? GROUP BY type", (day,))
    return dict(c.fetchall())
