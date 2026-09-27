import sqlite3

def patch():
    conn = sqlite3.connect("destifc.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS global_drafts (
            id INTEGER PRIMARY KEY,
            draft_number INTEGER,
            pool_a TEXT,
            pool_b TEXT,
            pool_c TEXT,
            expires_at TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("Database patched.")

if __name__ == "__main__":
    patch()
