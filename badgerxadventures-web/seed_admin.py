"""Create (or reset the password for) the admin account.
Usage: python3 seed_admin.py you@example.com yourpassword
"""
import sys
import db
import auth

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 seed_admin.py <email> <password>")
        sys.exit(1)
    email, password = sys.argv[1].strip().lower(), sys.argv[2]
    db.init_db()
    conn = db.get_db()
    pw_hash = auth.hash_password(password)
    existing = conn.execute("SELECT id FROM admins WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.execute("UPDATE admins SET password_hash = ? WHERE email = ?", (pw_hash, email))
        print(f"Updated password for admin {email}")
    else:
        conn.execute("INSERT INTO admins (email, password_hash) VALUES (?, ?)", (email, pw_hash))
        print(f"Created admin {email}")
    conn.commit()
    conn.close()
