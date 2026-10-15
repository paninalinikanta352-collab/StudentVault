import os
import json
import hmac
import hashlib
import base64
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()
_RAW_DB_URL = os.getenv("DATABASE_URL", "sqlite:///./studyvault.db")
DB_PATH = _RAW_DB_URL.replace("sqlite:///", "") or "studyvault.db"
SECRET = os.getenv("JWT_SECRET", "change-me-studyvault")


def db():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


@contextmanager
def db_session():
    c = db()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()


def check_pw(password: str, salt: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_pw(password, salt), hashed)


def make_token(email: str) -> str:
    h = b64e(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    p = b64e(json.dumps({
        "sub": email,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
    }).encode())
    s = b64e(hmac.new(SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest())
    return f"{h}.{p}.{s}"


def read_token(token: str):
    try:
        parts = token.split(".")
        h, p, s = parts
        exp = b64e(hmac.new(SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(exp, s):
            return None
        data = json.loads(b64d(p))
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if data.get("exp", 0) < now_ts:
            return None
        return data
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def now():
    return datetime.now(timezone.utc).isoformat()


def init():
    with db_session() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT UNIQUE, pw TEXT, branch TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT, subject TEXT, title TEXT,
            content TEXT, tags TEXT, upvotes INTEGER DEFAULT 0,
            created TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS votes(
            email TEXT, note_id INTEGER,
            PRIMARY KEY(email, note_id))""")
        n_notes = c.execute("SELECT COUNT(*) c FROM notes").fetchone()["c"]
        if n_notes == 0:
            seeds = [
                ("admin@studyvault.test", "DSA", "Binary Search Template",
                 "lo=0 hi=n-1 while lo<=hi: mid=(lo+hi)//2 ...", "dsa,python"),
                ("admin@studyvault.test", "DBMS", "Normalization in 5 lines",
                 "1NF atomic, 2NF no partial, 3NF no transitive ...", "dbms,theory"),
                ("admin@studyvault.test", "OS", "Deadlock 4 conditions",
                 "mutual exclusion, hold-wait, no preemption, circular wait ...", "os,theory"),
            ]
            for owner, subject, title, content, tags in seeds:
                c.execute(
                    "INSERT INTO notes(owner,subject,title,content,tags,upvotes,created) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (owner, subject, title, content, tags, 5, now()),
                )
        n_admin = c.execute(
            "SELECT COUNT(*) c FROM users WHERE email='admin@studyvault.test'"
        ).fetchone()["c"]
        if n_admin == 0:
            c.execute("INSERT INTO users(name,email,pw,branch) VALUES(?,?,?,?)",
                      ("Demo", "admin@studyvault.test",
                       hash_pw("admin123", "admin@studyvault.test"), "CSE"))
