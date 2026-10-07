from plyer import notification
import sqlite3

# Test SQLite
conn = sqlite3.connect("test.db")
conn.execute("CREATE TABLE IF NOT EXISTS demo(id INTEGER PRIMARY KEY, name TEXT)")
conn.close()

# Test notification
notification.notify(
    title="💊 Test Notification",
    message="Python + SQLite + Plyer are working perfectly!",
    timeout=5
)
