import streamlit as st
import sqlite3
import hashlib
import secrets
import datetime
import os
import base64
import html
import csv
import io
import re
import json
import urllib.request
import urllib.error

# ----------------------------------------------------
# 1. PAGE CONFIGURATION
# ----------------------------------------------------
st.set_page_config(
    page_title="MathScience Tuition Academy",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "academy.db")

# Free-tier student cap. Institutes above this need to be flipped to Premium
# (manually, via the Super Admin console, until online billing is wired up).
FREE_STUDENT_LIMIT = 15

# Super Admin (platform owner) credentials — only used the very first time the
# app runs against a brand-new database, to seed the account. Set these as
# environment variables on Streamlit Cloud (Settings -> Secrets) BEFORE first
# deploy so the seeded account isn't the public default. After that first run,
# use the in-app "Change Password" form in the Super Admin console instead —
# these env vars won't touch an already-seeded account on later restarts.
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "").strip().lower()
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")

# Set SHOW_DEMO_CREDENTIALS=false in production deploys to hide the demo
# login hints on the public login screen (they're handy for local dev only).
SHOW_DEMO_CREDENTIALS = os.environ.get("SHOW_DEMO_CREDENTIALS", "false").strip().lower() == "true"
DEMO_MODE = os.environ.get("DEMO_MODE", "false").strip().lower() == "true"

# Minimum acceptable password length, enforced everywhere a password is set.
MIN_PASSWORD_LENGTH = 8

# ----------------------------------------------------
# 1B2. RAZORPAY CONFIGURATION (self-serve Premium upgrade)
# ----------------------------------------------------
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
PREMIUM_UPGRADE_AMOUNT_INR = int(os.environ.get("PREMIUM_UPGRADE_AMOUNT_INR", "999"))

def razorpay_configured() -> bool:
    return bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)

def _razorpay_request(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"https://api.razorpay.com/v1{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    auth = base64.b64encode(f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
            msg = body.get("error", {}).get("description", str(e))
        except Exception:
            msg = str(e)
        raise RuntimeError(f"Razorpay error: {msg}")
    except Exception as e:
        raise RuntimeError(f"Could not reach Razorpay: {e}")

# ----------------------------------------------------
# 1B. TURSO (REMOTE, PERSISTENT DATABASE) CONFIGURATION
# ----------------------------------------------------
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")
USE_TURSO = bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)

# ----------------------------------------------------
# 1C. TURSO COMPATIBILITY LAYER
# ----------------------------------------------------
class _CompatRow:
    def __init__(self, columns, values):
        self._columns = columns
        self._values = list(values)

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._values[self._columns.index(key)]
        return self._values[key]

    def get(self, key, default=None):
        try:
            return self[key]
        except (ValueError, IndexError):
            return default

    def keys(self):
        return list(self._columns)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

class _CompatCursor:
    def __init__(self, raw_cursor):
        self._raw = raw_cursor

    def _columns(self):
        desc = getattr(self._raw, "description", None)
        return [d[0] for d in desc] if desc else []

    def _wrap(self, row):
        if row is None:
            return None
        return _CompatRow(self._columns(), row)

    def fetchone(self):
        row = self._raw.fetchone()
        return self._wrap(row)

    def fetchall(self):
        return [self._wrap(r) for r in self._raw.fetchall()]

class _TursoConnWrapper:
    def __init__(self, raw_conn):
        self._raw = raw_conn

    def execute(self, sql, params=()):
        cur = self._raw.execute(sql, params)
        return _CompatCursor(cur)

    def executemany(self, sql, seq_of_params):
        for params in seq_of_params:
            self._raw.execute(sql, params)

    def executescript(self, script: str):
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self._raw.execute(statement)

    def commit(self):
        try:
            self._raw.commit()
        except Exception as e:
            st.warning(f"Database commit warning: {e}")

# ----------------------------------------------------
# 2. PASSWORD HASHING
# ----------------------------------------------------
def hash_password(password: str, salt_hex: str | None = None) -> str:
    if salt_hex is None:
        salt_hex = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 100_000)
    return f"{salt_hex}${dk.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, _ = stored.split("$")
    except ValueError:
        return False
    return secrets.compare_digest(hash_password(password, salt_hex), stored)

def is_password_strong_enough(password: str) -> bool:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return False
    return (
        any(c.islower() for c in password)
        and any(c.isupper() for c in password)
        and any(c.isdigit() for c in password)
        and any(not c.isalnum() for c in password)
    )

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def is_valid_email(email: str) -> bool:
    return bool(email) and bool(_EMAIL_PATTERN.match(email))

# ----------------------------------------------------
# 3. DATABASE LAYER
# ----------------------------------------------------
@st.cache_resource
def get_connection():
    if USE_TURSO:
        import libsql
        raw_conn = libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
        conn = _TursoConnWrapper(raw_conn)
        _create_schema(conn)
        _ensure_multitenancy_columns(conn)
        _migrate_local_file_into_turso_if_needed(conn)
    else:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _create_schema(conn)
    init_db(conn)
    return conn

def _ensure_column(conn, table: str, column: str, coltype: str):
    try:
        existing_cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in existing_cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            conn.commit()
    except Exception as e:
        st.warning(f"Could not verify/add column '{column}' on '{table}': {e}")

def _create_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS institutes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        owner_email TEXT,
        plan TEXT DEFAULT 'Free',
        student_limit INTEGER DEFAULT 15,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('Admin','Teacher','Parent'))
    );
    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        grade TEXT,
        subject TEXT,
        fee INTEGER DEFAULT 0,
        parent_email TEXT
    );
    CREATE TABLE IF NOT EXISTS classrooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        subject TEXT,
        section TEXT,
        fee INTEGER
    );
    CREATE TABLE IF NOT EXISTS attendance (
        date TEXT,
        student_id TEXT,
        status TEXT,
        class_name TEXT,
        PRIMARY KEY (date, student_id)
    );
    CREATE TABLE IF NOT EXISTS payment_status (
        student_id TEXT PRIMARY KEY,
        status TEXT
    );
    CREATE TABLE IF NOT EXISTS financial_records (
        tx_id TEXT PRIMARY KEY,
        student TEXT,
        student_id TEXT,
        date TEXT,
        amount INTEGER,
        type TEXT,
        method TEXT
    );
    CREATE TABLE IF NOT EXISTS notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        body TEXT,
        priority TEXT,
        date TEXT
    );
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        actor_email TEXT,
        action TEXT,
        details TEXT,
        institute_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS login_attempts (
        email TEXT PRIMARY KEY,
        failed_count INTEGER DEFAULT 0,
        locked_until TEXT
    );
    CREATE TABLE IF NOT EXISTS signup_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT
    );
    CREATE TABLE IF NOT EXISTS premium_payment_links (
        link_id TEXT PRIMARY KEY,
        institute_id INTEGER,
        amount INTEGER,
        short_url TEXT,
        status TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS fee_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        institute_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        billing_month TEXT NOT NULL,
        amount INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'Unpaid',
        paid_date TEXT,
        method TEXT,
        reference TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(institute_id, student_id, billing_month)
    );
    """)
    conn.commit()

def _ensure_multitenancy_columns(conn):
    _ensure_column(conn, "financial_records", "student_id", "TEXT")
    _ensure_column(conn, "users", "institute_id", "INTEGER")
    _ensure_column(conn, "users", "is_super_admin", "INTEGER DEFAULT 0")
    _ensure_column(conn, "students", "institute_id", "INTEGER")
    _ensure_column(conn, "classrooms", "institute_id", "INTEGER")
    _ensure_column(conn, "attendance", "institute_id", "INTEGER")
    _ensure_column(conn, "payment_status", "institute_id", "INTEGER")
    _ensure_column(conn, "financial_records", "institute_id", "INTEGER")
    _ensure_column(conn, "notices", "institute_id", "INTEGER")
    _ensure_column(conn, "notices", "target_grade", "TEXT")
    _ensure_column(conn, "students", "is_deleted", "INTEGER DEFAULT 0")
    _ensure_column(conn, "financial_records", "billing_month", "TEXT")
    _ensure_column(conn, "financial_records", "reference", "TEXT")
    _ensure_column(conn, "financial_records", "actor_email", "TEXT")
    _ensure_column(conn, "users", "must_change_password", "INTEGER DEFAULT 0")

def _migrate_local_file_into_turso_if_needed(turso_conn):
    if not os.path.exists(DB_PATH):
        return
    try:
        existing = turso_conn.execute("SELECT COUNT(*) FROM institutes").fetchone()
        if existing and existing[0] > 0:
            return
    except Exception:
        pass
    try:
        local = sqlite3.connect(DB_PATH)
        local.row_factory = sqlite3.Row
    except Exception:
        return
    tables = ["institutes", "users", "students", "classrooms", "attendance",
              "payment_status", "financial_records", "notices"]
    copied_any = False
    for table in tables:
        try:
            cols_info = local.execute(f"PRAGMA table_info({table})").fetchall()
            if not cols_info:
                continue
            col_names = [c["name"] for c in cols_info]
            rows = local.execute(f"SELECT * FROM {table}").fetchall()
            placeholders = ",".join("?" for _ in col_names)
            col_list = ",".join(col_names)
            for row in rows:
                values = tuple(row[c] for c in col_names)
                turso_conn.execute(
                    f"INSERT OR IGNORE INTO {table}({col_list}) VALUES ({placeholders})",
                    values,
                )
                copied_any = True
        except Exception as e:
            st.warning(f"Could not migrate table '{table}' to Turso: {e}")
    turso_conn.commit()
    local.close()
    if copied_any:
        st.success("✅ Existing local data was migrated into your Turso database.")

def _last_insert_id(conn) -> int:
    row = conn.execute("SELECT last_insert_rowid()").fetchone()
    return row[0] if row else None

def log_audit_event(conn, actor_email: str, action: str, details: str = "", institute_id: int | None = None):
    try:
        conn.execute(
            "INSERT INTO audit_log(timestamp, actor_email, action, details, institute_id) VALUES (?,?,?,?,?)",
            (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), actor_email, action, details, institute_id),
        )
        conn.commit()
    except Exception as e:
        st.warning(f"Could not record audit log entry: {e}")

def list_audit_log(conn, institute_id: int | None = None, limit: int = 200):
    if institute_id is not None:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE institute_id=? ORDER BY id DESC LIMIT ?",
            (institute_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

def init_db(conn):
    _ensure_multitenancy_columns(conn)

    legacy_users = conn.execute(
        "SELECT COUNT(*) FROM users WHERE institute_id IS NULL AND (is_super_admin IS NULL OR is_super_admin=0)"
    ).fetchone()[0]
    legacy_students = conn.execute(
        "SELECT COUNT(*) FROM students WHERE institute_id IS NULL"
    ).fetchone()[0]

    if legacy_users > 0 or legacy_students > 0:
        admin_row = conn.execute(
            "SELECT email FROM users WHERE role='Admin' AND institute_id IS NULL ORDER BY email LIMIT 1"
        ).fetchone()
        owner_email = admin_row["email"] if admin_row else "admin@academy.com"

        existing_institute = conn.execute(
            "SELECT id FROM institutes WHERE owner_email=?", (owner_email,)
        ).fetchone()
        if existing_institute:
            legacy_institute_id = existing_institute["id"]
        else:
            cur = conn.execute(
                "INSERT INTO institutes(name, owner_email, plan, student_limit, created_at) VALUES (?,?,?,?,?)",
                ("My Academy", owner_email, "Premium", 999999, datetime.date.today().strftime("%Y-%m-%d")),
            )
            legacy_institute_id = _last_insert_id(conn)

        conn.execute(
            "UPDATE users SET institute_id=? WHERE institute_id IS NULL AND (is_super_admin IS NULL OR is_super_admin=0)",
            (legacy_institute_id,),
        )
        for table in ["students", "classrooms", "attendance", "payment_status", "financial_records", "notices"]:
            conn.execute(f"UPDATE {table} SET institute_id=? WHERE institute_id IS NULL", (legacy_institute_id,))
        conn.commit()

    if DEMO_MODE and conn.execute("SELECT COUNT(*) FROM institutes").fetchone()[0] == 0:
        cur = conn.execute(
            "INSERT INTO institutes(name, owner_email, plan, student_limit, created_at) VALUES (?,?,?,?,?)",
            ("Demo Academy", "admin@academy.com", "Premium", 999999, datetime.date.today().strftime("%Y-%m-%d")),
        )
        demo_institute_id = _last_insert_id(conn)

        conn.execute(
            "INSERT INTO users(email, password_hash, role, institute_id, is_super_admin) VALUES (?,?,?,?,0)",
            ("admin@academy.com", hash_password("admin123"), "Admin", demo_institute_id),
        )
        conn.execute(
            "INSERT INTO users(email, password_hash, role, institute_id, is_super_admin) VALUES (?,?,?,?,0)",
            ("teacher@academy.com", hash_password("teacher123"), "Teacher", demo_institute_id),
        )

        demo_students = [
            ("STU101", "Aarav Sharma", "Class 10", "Science", 1500, "parent1@academy.com"),
            ("STU102", "Rohan Das", "Class 10", "Science", 1500, "parent2@academy.com"),
        ]
        conn.executemany(
            "INSERT INTO students(id, name, grade, subject, fee, parent_email, institute_id) VALUES (?,?,?,?,?,?,?)",
            [s + (demo_institute_id,) for s in demo_students],
        )
        conn.executemany(
            "INSERT INTO users(email, password_hash, role, institute_id, is_super_admin) VALUES (?,?,?,?,0)",
            [
                ("parent1@academy.com", hash_password("parent123"), "Parent", demo_institute_id),
                ("parent2@academy.com", hash_password("parent123"), "Parent", demo_institute_id),
            ],
        )
        conn.executemany(
            "INSERT INTO financial_records(tx_id, student, student_id, date, amount, type, method, institute_id) VALUES (?,?,?,?,?,?,?,?)",
            [
                ("TXN901", "Aarav Sharma", "STU101", "2026-09-01", 1500, "Tuition Fee", "UPI / Online", demo_institute_id),
                ("TXN902", "Rohan Das", "STU102", "2026-09-03", 1500, "Tuition Fee", "Cash", demo_institute_id),
            ],
        )
        conn.execute(
            "INSERT INTO payment_status(student_id, status, institute_id) VALUES (?,?,?)",
            ("STU101", "Paid", demo_institute_id),
        )
        conn.commit()

    # One-time migration of legacy Paid/Unpaid flags into the current billing cycle.
    for inst_row in conn.execute("SELECT id FROM institutes").fetchall():
        inst_id = inst_row["id"]
        legacy_rows = conn.execute("SELECT student_id, status FROM payment_status WHERE institute_id=?", (inst_id,)).fetchall()
        for legacy in legacy_rows:
            student = get_student(conn, inst_id, legacy["student_id"]) if "get_student" in globals() else None
            if not student:
                continue
            exists = conn.execute("SELECT 1 FROM fee_payments WHERE institute_id=? AND student_id=? AND billing_month=?", (inst_id, legacy["student_id"], current_billing_month())).fetchone()
            if not exists:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute("INSERT INTO fee_payments(institute_id, student_id, billing_month, amount, status, paid_date, method, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (inst_id, legacy["student_id"], current_billing_month(), int(student.get("fee") or 0), legacy["status"], datetime.date.today().strftime("%Y-%m-%d") if legacy["status"] == "Paid" else None, "Legacy Fee Status" if legacy["status"] == "Paid" else None, now, now))
    conn.commit()

    if conn.execute("SELECT COUNT(*) FROM users WHERE is_super_admin=1").fetchone()[0] == 0:
        if not SUPER_ADMIN_EMAIL or not SUPER_ADMIN_PASSWORD:
            if conn.execute("SELECT COUNT(*) FROM institutes").fetchone()[0] == 0:
                # A fresh production deployment can still start so the owner can configure secrets.
                st.warning("SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD are not configured. Set them in Streamlit Secrets before creating the first platform-owner account.")
            else:
                st.warning("No Super Admin exists. Configure SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD, then restart the app.")
        elif not is_valid_email(SUPER_ADMIN_EMAIL) or not is_password_strong_enough(SUPER_ADMIN_PASSWORD):
            raise RuntimeError("SUPER_ADMIN_EMAIL must be valid and SUPER_ADMIN_PASSWORD must be 8+ chars with upper/lowercase, number and special character.")
        else:
            conn.execute(
                "INSERT INTO users(email, password_hash, role, institute_id, is_super_admin) VALUES (?,?,?,?,1)",
                (SUPER_ADMIN_EMAIL, hash_password(SUPER_ADMIN_PASSWORD), "Admin", None),
            )
            conn.commit()

# ---- Auth ----
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15
SIGNUP_MAX_PER_HOUR = 10

def _ensure_signup_log_table(conn):
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS signup_log (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT)")
        conn.commit()
    except Exception:
        pass

def check_signup_rate_limit(conn):
    try:
        _ensure_signup_log_table(conn)
        one_hour_ago = (datetime.datetime.now() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        row = conn.execute("SELECT COUNT(*) FROM signup_log WHERE timestamp > ?", (one_hour_ago,)).fetchone()
        count = row[0] if row else 0
        if count >= SIGNUP_MAX_PER_HOUR:
            return False, "A lot of new academies have signed up in the last hour. Please try again shortly."
        return True, None
    except Exception:
        return True, None

def record_signup_attempt(conn):
    try:
        _ensure_signup_log_table(conn)
        conn.execute(
            "INSERT INTO signup_log(timestamp) VALUES (?)",
            (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),),
        )
        conn.commit()
    except Exception:
        pass

def _ensure_login_attempts_table(conn):
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS login_attempts (
            email TEXT PRIMARY KEY, failed_count INTEGER DEFAULT 0, locked_until TEXT
        )""")
        conn.commit()
    except Exception:
        pass

def check_login_lock(conn, email: str):
    try:
        _ensure_login_attempts_table(conn)
        row = conn.execute("SELECT locked_until FROM login_attempts WHERE email=?", (email,)).fetchone()
    except Exception:
        return False, 0
    if not row or not row["locked_until"]:
        return False, 0
    try:
        locked_until = datetime.datetime.strptime(row["locked_until"], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return False, 0
    now = datetime.datetime.now()
    if now < locked_until:
        return True, int((locked_until - now).total_seconds())
    return False, 0

def record_failed_login(conn, email: str):
    try:
        _ensure_login_attempts_table(conn)
        row = conn.execute("SELECT failed_count FROM login_attempts WHERE email=?", (email,)).fetchone()
        failed_count = (row["failed_count"] if row else 0) + 1
        locked_until = None
        if failed_count >= LOGIN_MAX_ATTEMPTS:
            locked_until = (datetime.datetime.now() + datetime.timedelta(minutes=LOGIN_LOCKOUT_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
            failed_count = 0
        conn.execute(
            """INSERT INTO login_attempts(email, failed_count, locked_until) VALUES (?,?,?)
               ON CONFLICT(email) DO UPDATE SET failed_count=excluded.failed_count, locked_until=excluded.locked_until""",
            (email, failed_count, locked_until),
        )
        conn.commit()
    except Exception:
        pass

def clear_failed_login(conn, email: str):
    try:
        _ensure_login_attempts_table(conn)
        conn.execute("DELETE FROM login_attempts WHERE email=?", (email,))
        conn.commit()
    except Exception:
        pass

def update_password(conn, email: str, new_password: str, force_change: bool = False):
    conn.execute("UPDATE users SET password_hash=? WHERE email=?", (hash_password(new_password), email))
    try:
        conn.execute(
            "UPDATE users SET must_change_password=? WHERE email=?",
            (1 if force_change else 0, email),
        )
    except Exception:
        # Keep password changes working with older databases that lack the
        # optional migration column.
        pass
    conn.commit()

def authenticate(conn, email: str, password: str):
    # Backward-compatible login: older databases do not necessarily have
    # the newer must_change_password column. Login must never depend on it.
    row = conn.execute(
        "SELECT password_hash, role, institute_id, is_super_admin FROM users WHERE email=?",
        (email,),
    ).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return {
            "role": row["role"],
            "institute_id": row["institute_id"],
            "is_super_admin": bool(row.get("is_super_admin", 0)),
            "must_change_password": bool(row.get("must_change_password", 0)),
        }
    return None

def create_user_account(conn, institute_id: int, email: str, password: str, role: str):
    conn.execute(
        "INSERT INTO users(email, password_hash, role, institute_id, is_super_admin) VALUES (?,?,?,?,0)",
        (email, hash_password(password), role, institute_id),
    )
    try:
        conn.execute("UPDATE users SET must_change_password=1 WHERE email=?", (email,))
    except Exception:
        pass
    conn.commit()

def list_accounts_by_role(conn, institute_id: int, role: str):
    return [dict(r) for r in conn.execute(
        "SELECT email FROM users WHERE role=? AND institute_id=? ORDER BY email", (role, institute_id)
    ).fetchall()]

def delete_account(conn, institute_id: int, email: str, role: str):
    conn.execute("DELETE FROM users WHERE email=? AND role=? AND institute_id=?", (email, role, institute_id))
    if role == "Parent":
        conn.execute("UPDATE students SET parent_email=NULL WHERE parent_email=? AND institute_id=?", (email, institute_id))
    conn.commit()

def create_parent_account(conn, institute_id: int, email: str, password: str):
    create_user_account(conn, institute_id, email, password, "Parent")

def list_parent_accounts(conn, institute_id: int):
    return list_accounts_by_role(conn, institute_id, "Parent")

def delete_parent_account(conn, institute_id: int, email: str):
    delete_account(conn, institute_id, email, "Parent")

def list_teacher_accounts(conn, institute_id: int):
    return list_accounts_by_role(conn, institute_id, "Teacher")

def create_teacher_account(conn, institute_id: int, email: str, password: str):
    create_user_account(conn, institute_id, email, password, "Teacher")

def delete_teacher_account(conn, institute_id: int, email: str):
    delete_account(conn, institute_id, email, "Teacher")

# ---- Institutes (multi-tenancy) ----
def create_institute_and_admin(conn, institute_name: str, owner_email: str, password: str):
    existing = conn.execute("SELECT 1 FROM users WHERE email=?", (owner_email,)).fetchone()
    if existing:
        raise ValueError("An account with that email already exists.")
    cur = conn.execute(
        "INSERT INTO institutes(name, owner_email, plan, student_limit, created_at) VALUES (?,?,?,?,?)",
        (institute_name, owner_email, "Free", FREE_STUDENT_LIMIT, datetime.date.today().strftime("%Y-%m-%d")),
    )
    institute_id = _last_insert_id(conn)
    try:
        conn.execute(
            "INSERT INTO users(email, password_hash, role, institute_id, is_super_admin) VALUES (?,?,?,?,0)",
            (owner_email, hash_password(password), "Admin", institute_id),
        )
    except Exception:
        conn.execute("DELETE FROM institutes WHERE id=?", (institute_id,))
        conn.commit()
        raise ValueError("An account with that email already exists.")
    conn.commit()
    return institute_id

def get_institute(conn, institute_id: int):
    row = conn.execute("SELECT * FROM institutes WHERE id=?", (institute_id,)).fetchone()
    return dict(row) if row else None

def list_institutes(conn):
    rows = conn.execute("SELECT * FROM institutes ORDER BY id").fetchall()
    count_rows = conn.execute(
        "SELECT institute_id, COUNT(*) as cnt FROM students WHERE (is_deleted IS NULL OR is_deleted=0) GROUP BY institute_id"
    ).fetchall()
    counts_by_institute = {r["institute_id"]: r["cnt"] for r in count_rows}
    result = []
    for r in rows:
        d = dict(r)
        d["student_count"] = counts_by_institute.get(d["id"], 0)
        result.append(d)
    return result

def set_institute_plan(conn, institute_id: int, plan: str, student_limit: int, actor_email: str = ""):
    conn.execute(
        "UPDATE institutes SET plan=?, student_limit=? WHERE id=?", (plan, student_limit, institute_id)
    )
    conn.commit()
    log_audit_event(conn, actor_email, "plan_change", f"Set plan to {plan} (limit {student_limit})", institute_id)

def get_or_create_premium_payment_link(conn, institute_id: int, institute_name: str, admin_email: str, force_new: bool = False) -> dict:
    if not force_new:
        existing = conn.execute(
            "SELECT * FROM premium_payment_links WHERE institute_id=? AND status='created' ORDER BY created_at DESC LIMIT 1",
            (institute_id,),
        ).fetchone()
        if existing:
            return dict(existing)
    else:
        conn.execute(
            "UPDATE premium_payment_links SET status='superseded' WHERE institute_id=? AND status='created'",
            (institute_id,),
        )
        conn.commit()

    payload = {
        "amount": PREMIUM_UPGRADE_AMOUNT_INR * 100,
        "currency": "INR",
        "description": f"Premium upgrade — {institute_name}",
        "reference_id": f"premium-{institute_id}-{int(datetime.datetime.now().timestamp())}",
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
    }
    if admin_email:
        payload["customer"] = {"email": admin_email}

    result = _razorpay_request("POST", "/payment_links", payload)
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO premium_payment_links(link_id, institute_id, amount, short_url, status, created_at) VALUES (?,?,?,?,?,?)",
        (result["id"], institute_id, PREMIUM_UPGRADE_AMOUNT_INR, result["short_url"], result.get("status", "created"), created_at),
    )
    conn.commit()
    return {
        "link_id": result["id"], "institute_id": institute_id, "amount": PREMIUM_UPGRADE_AMOUNT_INR,
        "short_url": result["short_url"], "status": result.get("status", "created"), "created_at": created_at,
    }

def refresh_premium_payment_link_status(conn, institute_id: int, link_id: str, actor_email: str) -> str:
    result = _razorpay_request("GET", f"/payment_links/{link_id}")
    status = result.get("status", "created")
    conn.execute("UPDATE premium_payment_links SET status=? WHERE link_id=?", (status, link_id))
    conn.commit()
    if status == "paid":
        set_institute_plan(conn, institute_id, "Premium", 999999, actor_email=actor_email)
        log_audit_event(conn, actor_email, "premium_self_upgrade", f"Paid via Razorpay link {link_id}", institute_id)
    return status

def count_students(conn, institute_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM students WHERE institute_id=? AND (is_deleted IS NULL OR is_deleted=0)", (institute_id,)
    ).fetchone()[0]

def can_add_student(conn, institute_id: int):
    plan = st.session_state.get("institute_plan", "Free")
    if plan == "Premium":
        return True, None
    limit = st.session_state.get("student_limit", FREE_STUDENT_LIMIT)
    current = count_students(conn, institute_id)
    if current >= limit:
        return False, (
            f"You've reached the Free plan limit of {limit} students. "
            f"Ask the platform owner to upgrade your institute to Premium to add more."
        )
    return True, None

# ---- Students ----
def list_students(conn, institute_id: int, parent_email: str | None = None):
    if parent_email:
        rows = conn.execute(
            "SELECT * FROM students WHERE institute_id=? AND parent_email=? AND (is_deleted IS NULL OR is_deleted=0) ORDER BY name",
            (institute_id, parent_email),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM students WHERE institute_id=? AND (is_deleted IS NULL OR is_deleted=0) ORDER BY name", (institute_id,)
        ).fetchall()
    return [dict(r) for r in rows]

def _student_id_prefix(institute_id: int) -> str:
    return f"STU{institute_id}-"

def add_student(conn, institute_id: int, name, grade, subject, fee, parent_email=None):
    prefix = _student_id_prefix(institute_id)
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(id, ?) AS INTEGER)) FROM students WHERE id LIKE ? AND institute_id=?",
        (len(prefix) + 1, prefix + "%", institute_id),
    ).fetchone()
    highest = row[0] if row and row[0] is not None else 100
    new_id = f"{prefix}{highest + 1}"
    conn.execute(
        "INSERT INTO students(id, name, grade, subject, fee, parent_email, institute_id) VALUES (?,?,?,?,?,?,?)",
        (new_id, name, grade, subject, fee, parent_email or None, institute_id),
    )
    conn.commit()
    return new_id

def bulk_add_students(conn, institute_id: int, rows: list[dict]) -> int:
    if not rows:
        return 0
    prefix = _student_id_prefix(institute_id)
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(id, ?) AS INTEGER)) FROM students WHERE id LIKE ? AND institute_id=?",
        (len(prefix) + 1, prefix + "%", institute_id),
    ).fetchone()
    next_num = (row[0] if row and row[0] is not None else 100) + 1
    inserted = 0
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        new_id = f"{prefix}{next_num}"
        next_num += 1
        try:
            fee_val = int(float(r.get("fee") or 0))
        except (ValueError, TypeError):
            fee_val = 0
        conn.execute(
            "INSERT INTO students(id, name, grade, subject, fee, parent_email, institute_id) VALUES (?,?,?,?,?,?,?)",
            (
                new_id,
                name,
                (r.get("grade") or "General").strip() or "General",
                (r.get("subject") or "General").strip() or "General",
                fee_val,
                (r.get("parent_email") or "").strip().lower() or None,
                institute_id,
            ),
        )
        inserted += 1
    conn.commit()
    return inserted

def delete_student(conn, institute_id: int, student_id: str, actor_email: str = ""):
    student = get_student(conn, institute_id, student_id)
    conn.execute("UPDATE students SET is_deleted=1 WHERE id=? AND institute_id=?", (student_id, institute_id))
    conn.commit()
    student_name = student["name"] if student else student_id
    log_audit_event(conn, actor_email, "student_deleted", f"Archived {student_name} ({student_id})", institute_id)

def restore_student(conn, institute_id: int, student_id: str, actor_email: str = ""):
    student = conn.execute("SELECT name FROM students WHERE id=? AND institute_id=?", (student_id, institute_id)).fetchone()
    conn.execute("UPDATE students SET is_deleted=0 WHERE id=? AND institute_id=?", (student_id, institute_id))
    conn.commit()
    student_name = student["name"] if student else student_id
    log_audit_event(conn, actor_email, "student_restored", f"Restored {student_name} ({student_id})", institute_id)

def list_archived_students(conn, institute_id: int):
    return [dict(r) for r in conn.execute("SELECT * FROM students WHERE institute_id=? AND is_deleted=1 ORDER BY name", (institute_id,)).fetchall()]

def update_student_parent_email(conn, institute_id: int, student_id: str, parent_email: str | None):
    conn.execute(
        "UPDATE students SET parent_email=? WHERE id=? AND institute_id=?",
        (parent_email or None, student_id, institute_id),
    )
    conn.commit()

def update_student(conn, institute_id: int, student_id: str, name: str, grade: str, subject: str, fee: int):
    conn.execute(
        "UPDATE students SET name=?, grade=?, subject=?, fee=? WHERE id=? AND institute_id=?",
        (name, grade, subject, fee, student_id, institute_id),
    )
    conn.commit()

def get_student(conn, institute_id: int, student_id: str):
    row = conn.execute(
        "SELECT * FROM students WHERE id=? AND institute_id=?", (student_id, institute_id)
    ).fetchone()
    return dict(row) if row else None

# ---- Classrooms ----
def list_classrooms(conn, institute_id: int):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM classrooms WHERE institute_id=? ORDER BY id", (institute_id,)
    ).fetchall()]

def add_classroom(conn, institute_id: int, title, subject, section, fee):
    conn.execute(
        "INSERT INTO classrooms(title, subject, section, fee, institute_id) VALUES (?,?,?,?,?)",
        (title, subject, section, fee, institute_id),
    )
    conn.commit()

# ---- Attendance ----
def save_attendance(conn, institute_id: int, date_str: str, entries: list[dict]):
    for e in entries:
        conn.execute(
            """INSERT INTO attendance(date, student_id, status, class_name, institute_id) VALUES (?,?,?,?,?)
               ON CONFLICT(date, student_id) DO UPDATE SET status=excluded.status, class_name=excluded.class_name""",
            (date_str, e["student_id"], e["status"], e["class_name"], institute_id),
        )
    conn.commit()

def attendance_for_date(conn, institute_id: int, date_str: str) -> dict:
    rows = conn.execute(
        "SELECT student_id, status FROM attendance WHERE institute_id=? AND date=?",
        (institute_id, date_str),
    ).fetchall()
    return {r["student_id"]: r["status"] for r in rows}

def attendance_history(conn, institute_id: int, student_id: str):
    rows = conn.execute(
        "SELECT date, status FROM attendance WHERE student_id=? AND institute_id=? ORDER BY date DESC",
        (student_id, institute_id),
    ).fetchall()
    return [(r["date"], r["status"]) for r in rows]

# ---- Fees ----
def current_billing_month() -> str:
    return datetime.date.today().strftime("%Y-%m")

def ensure_fee_payment(conn, institute_id: int, student: dict, billing_month: str | None = None):
    month = billing_month or current_billing_month()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO fee_payments(institute_id, student_id, billing_month, amount, status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(institute_id, student_id, billing_month) DO UPDATE SET amount=excluded.amount, updated_at=excluded.updated_at""",
        (institute_id, student["id"], month, int(student.get("fee") or 0), "Unpaid", now, now),
    )
    conn.commit()

def get_payment_status(conn, institute_id: int, student_id: str, billing_month: str | None = None) -> str:
    month = billing_month or current_billing_month()
    row = conn.execute(
        "SELECT status FROM fee_payments WHERE student_id=? AND institute_id=? AND billing_month=?",
        (student_id, institute_id, month),
    ).fetchone()
    if row:
        return row["status"]
    return "Unpaid"

def get_payment_statuses_bulk(conn, institute_id: int, billing_month: str | None = None) -> dict:
    month = billing_month or current_billing_month()
    rows = conn.execute(
        "SELECT student_id, status FROM fee_payments WHERE institute_id=? AND billing_month=?",
        (institute_id, month),
    ).fetchall()
    result = {r["student_id"]: r["status"] for r in rows}
    return result

def _next_tx_id(conn, institute_id: int) -> str:
    prefix = f"TXN{institute_id}-"
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(tx_id, ?) AS INTEGER)) FROM financial_records WHERE tx_id LIKE ? AND institute_id=?",
        (len(prefix) + 1, prefix + "%", institute_id),
    ).fetchone()
    highest = row[0] if row and row[0] is not None else 900
    return f"{prefix}{highest + 1}"

def set_payment_status(conn, institute_id: int, student_id: str, status: str, billing_month: str | None = None, method: str = "Marked Paid (Fee Desk)", reference: str = "", actor_email: str = ""):
    if status not in {"Paid", "Unpaid"}:
        raise ValueError("Invalid payment status")
    month = billing_month or current_billing_month()
    student = get_student(conn, institute_id, student_id)
    if not student:
        raise ValueError("Student not found")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    previous = get_payment_status(conn, institute_id, student_id, month)
    conn.execute(
        """INSERT INTO fee_payments(institute_id, student_id, billing_month, amount, status, paid_date, method, reference, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(institute_id, student_id, billing_month) DO UPDATE SET
             amount=excluded.amount, status=excluded.status, paid_date=excluded.paid_date,
             method=excluded.method, reference=excluded.reference, updated_at=excluded.updated_at""",
        (institute_id, student_id, month, int(student.get("fee") or 0), status, datetime.date.today().strftime("%Y-%m-%d") if status == "Paid" else None, method if status == "Paid" else None, reference or None, now, now),
    )
    conn.execute(
        """INSERT INTO payment_status(student_id, status, institute_id) VALUES (?,?,?)
           ON CONFLICT(student_id) DO UPDATE SET status=excluded.status""",
        (student_id, status, institute_id),
    )
    if status == "Paid" and previous != "Paid":
        existing = conn.execute(
            "SELECT tx_id FROM financial_records WHERE institute_id=? AND student_id=? AND billing_month=? AND type='Tuition Fee'",
            (institute_id, student_id, month),
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO financial_records(tx_id, student, student_id, date, amount, type, method, institute_id, billing_month, reference, actor_email)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (_next_tx_id(conn, institute_id), student["name"], student_id, datetime.date.today().strftime("%Y-%m-%d"), int(student.get("fee") or 0), "Tuition Fee", method, institute_id, month, reference or None, actor_email or None),
            )
    conn.commit()

def list_financial_records(conn, institute_id: int, student_id: str | None = None, student_name: str | None = None):
    if student_id or student_name:
        rows = conn.execute(
            """SELECT * FROM financial_records WHERE institute_id=? AND ((student_id IS NOT NULL AND student_id=?) OR (student_id IS NULL AND student=?)) ORDER BY date DESC""",
            (institute_id, student_id, student_name),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM financial_records WHERE institute_id=? ORDER BY date DESC", (institute_id,)).fetchall()
    return [dict(r) for r in rows]

def list_fee_payments(conn, institute_id: int, billing_month: str | None = None):
    month = billing_month or current_billing_month()
    rows = conn.execute(
        """SELECT fp.*, s.name, s.grade, s.fee FROM fee_payments fp
           JOIN students s ON s.id=fp.student_id AND s.institute_id=fp.institute_id
           WHERE fp.institute_id=? AND fp.billing_month=? ORDER BY s.name""",
        (institute_id, month),
    ).fetchall()
    return [dict(r) for r in rows]

# ---- Notices ----
def list_notices(conn, institute_id: int, grade: str | None = None):
    if grade:
        rows = conn.execute(
            """SELECT * FROM notices
               WHERE institute_id=? AND (target_grade IS NULL OR target_grade='' OR target_grade=?)
               ORDER BY id DESC""",
            (institute_id, grade),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM notices WHERE institute_id=? ORDER BY id DESC", (institute_id,)
        ).fetchall()
    return [dict(r) for r in rows]

def add_notice(conn, institute_id: int, title, body, priority, date_str, target_grade: str | None = None):
    conn.execute(
        "INSERT INTO notices(title, body, priority, date, institute_id, target_grade) VALUES (?,?,?,?,?,?)",
        (title, body, priority, date_str, institute_id, target_grade or None),
    )
    conn.commit()

conn = get_connection()

# ----------------------------------------------------
# 4. SESSION STATE
# ----------------------------------------------------
for key, default in {
    "logged_in": False,
    "logged_in_role": None,
    "user_email": "",
    "active_view": None,
    "institute_id": None,
    "institute_name": None,
    "institute_plan": "Free",
    "student_limit": FREE_STUDENT_LIMIT,
    "is_super_admin": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ----------------------------------------------------
# 5. STATIC ASSETS
# ----------------------------------------------------
if os.path.exists("logo.jpg"):
    with open("logo.jpg", "rb") as img_file:
        logo_b64_str = f"data:image/jpeg;base64,{base64.b64encode(img_file.read()).decode()}"
else:
    logo_b64_str = "https://mathscience.in/logo.jpg"

def logo_img_tag(size=48):
    return (
        f'<img src="{logo_b64_str}" '
        f'style="width: {size}px; height: {size}px; border-radius: 12px; '
        f'border: 1.5px solid #38bdf8; object-fit: cover;" />'
    )

def filter_students(students: list[dict], query: str) -> list[dict]:
    q = (query or "").strip().lower()
    if not q:
        return students
    return [
        s for s in students
        if q in str(s.get("name", "")).lower()
        or q in str(s.get("id", "")).lower()
        or q in str(s.get("grade", "")).lower()
        or q in str(s.get("subject", "")).lower()
        or q in str(s.get("parent_email", "") or "").lower()
    ]

def rows_to_csv_bytes(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")

def esc(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)

# ----------------------------------------------------
# 6. MASTER HIGH-CONTRAST CSS STYLING
# ----------------------------------------------------
st.markdown(f"""
<style>
    .stApp {{
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%) !important;
        background-attachment: fixed !important;
    }}
    p, span, label, .stMarkdown p, [data-testid="stMarkdownContainer"] p {{
        color: #e2e8f0 !important;
    }}
    header[data-testid="stHeader"] {{
        background: transparent !important;
        z-index: 999991 !important;
    }}
    header[data-testid="stHeader"] button {{
        background: rgba(15, 23, 42, 0.85) !important;
        border: 1.5px solid #38bdf8 !important;
        border-radius: 8px !important;
        color: #38bdf8 !important;
        visibility: visible !important;
        margin-left: 8px !important;
        margin-top: 4px !important;
    }}
    header[data-testid="stHeader"] button svg {{
        fill: #38bdf8 !important;
        color: #38bdf8 !important;
    }}
    [data-testid="collapsedControl"] {{
        display: flex !important;
        visibility: visible !important;
        position: fixed !important;
        top: 12px !important;
        left: 12px !important;
        z-index: 999999 !important;
    }}
    [data-testid="collapsedControl"] button {{
        background: #0284c7 !important;
        border: 2px solid #38bdf8 !important;
        border-radius: 50% !important;
        width: 42px !important;
        height: 42px !important;
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.6) !important;
    }}
    [data-testid="collapsedControl"] svg {{
        fill: #ffffff !important;
        stroke: #ffffff !important;
        width: 22px !important;
        height: 22px !important;
    }}
    section[data-testid="stSidebar"] {{
        background-color: #0b1329 !important;
        background: linear-gradient(180deg, #091426 0%, #030a16 100%) !important;
        border-right: 2px solid #38bdf8 !important;
        box-shadow: 6px 0 25px rgba(0, 0, 0, 0.8) !important;
    }}
    section[data-testid="stSidebar"] * {{
        color: #f1f5f9 !important;
    }}
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h2 span {{
        color: #ffffff !important;
        font-weight: 700 !important;
    }}
    div[data-baseweb="select"] > div {{
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #ffffff !important;
    }}
    ul[data-baseweb="menu"],
    ul[data-baseweb="menu"] li,
    ul[data-baseweb="menu"] li div,
    ul[data-baseweb="menu"] li span {{
        background-color: #ffffff !important;
        color: #0f172a !important;
        font-weight: 700 !important;
    }}
    ul[data-baseweb="menu"] li:hover,
    ul[data-baseweb="menu"] li[aria-selected="true"] {{
        background-color: #e0f2fe !important;
        color: #0284c7 !important;
    }}
    div[data-baseweb="input"] > div,
    input.st-bc,
    input[type="text"],
    input[type="number"] {{
        background-color: #0f172a !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border: 1.5px solid #334155 !important;
        font-weight: 600 !important;
    }}
    input::placeholder {{
        color: #94a3b8 !important;
        -webkit-text-fill-color: #94a3b8 !important;
        opacity: 1 !important;
    }}
    div[data-testid="stNumberInput"] button {{
        background-color: #1e293b !important;
        color: #38bdf8 !important;
        border: 1px solid #334155 !important;
    }}
    [data-testid="stExpander"] summary {{
        background: #1e293b !important;
        border-radius: 12px 12px 0 0 !important;
    }}
    [data-testid="stExpander"] summary * {{
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 16px !important;
    }}
    [data-testid="stExpander"] summary svg {{
        fill: #38bdf8 !important;
    }}
    h1, h2, h3, h4, h5, h6 {{
        color: #ffffff !important;
        font-weight: 700 !important;
    }}
    div[data-testid="stFormSubmitButton"] button,
    .stButton button,
    button[kind="primaryFormSubmit"] {{
        background: linear-gradient(135deg, #0284c7 0%, #06b6d4 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 10px 20px !important;
        box-shadow: 0 4px 15px rgba(2, 132, 199, 0.3) !important;
        width: 100% !important;
    }}
    button[kind="secondary"] {{
        background: #ef4444 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
    }}
    button[data-baseweb="tab"] {{
        color: #94a3b8 !important;
        font-weight: 600 !important;
        font-size: 15px !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: #38bdf8 !important;
        font-weight: 700 !important;
    }}
    [data-testid="stExpander"] {{
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
    }}
    .glass-card {{
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        padding: 22px;
        margin-bottom: 20px;
    }}
    .portal-btn {{
        display: inline-block;
        background: linear-gradient(135deg, #0284c7 0%, #06b6d4 100%);
        color: #ffffff !important;
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 13px;
        font-weight: 700;
        padding: 10px 22px;
        border-radius: 12px;
        text-decoration: none;
        box-shadow: 0 4px 15px rgba(2, 132, 199, 0.3);
    }}
    [data-testid="stMetricValue"] {{
        font-size: 26px !important;
        font-weight: 800;
        color: #06b6d4 !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: #94a3b8 !important;
    }}
    div[data-testid="stToolbar"] {{ display: none !important; }}
    footer {{ display: none !important; }}
    div[class*="viewerBadge"] {{ display: none !important; }}
    div[data-testid="stStatusWidget"] {{
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        position: fixed !important;
        top: 10px !important;
        right: 12px !important;
        z-index: 999999 !important;
        background: rgba(2, 132, 199, 0.9) !important;
        border-radius: 20px !important;
        padding: 4px 10px !important;
    }}
    div[data-testid="stStatusWidget"] * {{
        color: #ffffff !important;
    }}
    div[data-testid="stToast"] {{
        background-color: #1e293b !important;
        border: 1.5px solid #38bdf8 !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5) !important;
    }}
    div[data-testid="stToast"] * {{
        color: #ffffff !important;
        opacity: 1 !important;
    }}
    input[type="password"],
    input[type="date"] {{
        background-color: #0f172a !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border: 1.5px solid #334155 !important;
        font-weight: 600 !important;
        color-scheme: dark;
    }}
    input[type="date"]::-webkit-calendar-picker-indicator {{
        filter: invert(1);
        opacity: 0.8;
    }}
    .stButton button:active,
    div[data-testid="stFormSubmitButton"] button:active {{
        transform: scale(0.97) !important;
        opacity: 0.85 !important;
        transition: transform 0.05s ease, opacity 0.05s ease !important;
    }}
    /* Login-page role guidance boxes — colored border per role so the two
       paths (existing login vs new academy signup) are visually distinct
       at a glance, not just via tab labels. */
    .login-guide-box {{
        background: rgba(56, 189, 248, 0.08);
        border: 1.5px solid #38bdf8;
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 16px;
    }}
    .login-guide-box.signup {{
        background: rgba(74, 222, 128, 0.08);
        border-color: #4ade80;
    }}
    .block-container {{
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }}
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 7. SHARED HELPERS
# ----------------------------------------------------
def go_to(view: str):
    st.session_state.active_view = view

def render_header(title: str, subtitle: str, size: int = 48):
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px; background: rgba(30, 41, 59, 0.7); padding: 12px 16px; border-radius: 14px; border: 1px solid rgba(56, 189, 248, 0.3);">
        {logo_img_tag(size)}
        <div>
            <h2 style="margin: 0; font-size: 20px; font-weight: 700; color: #ffffff;">{esc(title)}</h2>
            <p style="margin: 0; color: #38bdf8; font-size: 13px; font-weight: 500;">{esc(subtitle)}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_admin_quick_nav(current: str):
    if st.session_state.get("logged_in_role") != "Admin" or st.session_state.get("is_super_admin"):
        return
    labels = {
        "Admin": "⬅ Return to Admin Console",
        "Teacher": "🧑‍🏫 Open Teacher Desk",
        "Parent": "👨‍👩‍👧 Open Parent Portal",
    }
    others = [(key, label) for key, label in labels.items() if key != current]
    cols = st.columns(len(others))
    for col, (target, label) in zip(cols, others):
        with col:
            if st.button(label, use_container_width=True, key=f"nav_{current}_to_{target}"):
                st.toast(f"Opening {target} desk…", icon="🔄")
                go_to(target)
                st.rerun()
    st.write("---")

def logout_button(key: str):
    st.write("---")
    if st.button("🚪 Log Out", use_container_width=True, key=key):
        st.toast("Logging out…", icon="👋")
        st.session_state.clear()
        st.rerun()

def render_plan_banner(institute_id: int):
    plan = st.session_state.get("institute_plan", "Free")
    if plan == "Premium":
        return
    limit = st.session_state.get("student_limit", FREE_STUDENT_LIMIT)
    used = count_students(conn, institute_id)
    st.markdown(f"""
    <div style="background: rgba(56, 189, 248, 0.1); border: 1px solid #38bdf8; border-radius: 12px; padding: 14px 18px; margin-bottom: 18px;">
        <strong style="color: #38bdf8;">Free Plan</strong>
        <span style="color: #e2e8f0;"> — {used}/{limit} students used.</span>
        <span style="color: #94a3b8;"> Need more? Pay the platform owner directly (UPI/bank transfer) and ask to be upgraded to Premium — it's a manual flip on their end, usually same-day.</span>
    </div>
    """, unsafe_allow_html=True)

def render_premium_upgrade_widget(institute_id: int, institute_name: str, admin_email: str):
    plan = st.session_state.get("institute_plan", "Free")
    if plan == "Premium" or not razorpay_configured():
        return

    st.markdown(f"#### 💳 Upgrade to Premium — pay online (₹{PREMIUM_UPGRADE_AMOUNT_INR})")
    st.caption("Unlocks unlimited students immediately once your payment clears.")

    pending = conn.execute(
        "SELECT * FROM premium_payment_links WHERE institute_id=? AND status='created' ORDER BY created_at DESC LIMIT 1",
        (institute_id,),
    ).fetchone()

    col1, col2 = st.columns(2)
    with col1:
        button_label = "🔄 Get New Payment Link" if pending else "💳 Generate Payment Link"
        if st.button(button_label, use_container_width=True, key="gen_premium_link"):
            try:
                st.toast("Creating payment link…", icon="⏳")
                with st.spinner("Creating payment link…"):
                    get_or_create_premium_payment_link(conn, institute_id, institute_name, admin_email, force_new=bool(pending))
                st.rerun()
            except RuntimeError as e:
                st.error(str(e))
    with col2:
        if pending and st.button("✅ I've Paid — Check Status", use_container_width=True, key="check_premium_link"):
            try:
                st.toast("Checking with Razorpay…", icon="⏳")
                with st.spinner("Checking with Razorpay…"):
                    status = refresh_premium_payment_link_status(conn, institute_id, pending["link_id"], admin_email)
                if status == "paid":
                    st.success("Payment confirmed! You're now on Premium.")
                    st.rerun()
                else:
                    st.info(f"Not received yet (status: {status}). Complete the payment, then check again.")
            except RuntimeError as e:
                st.error(str(e))

    if pending:
        st.markdown(f"[👉 Click here to pay ₹{pending['amount']}]({pending['short_url']})")
        if pending["amount"] != PREMIUM_UPGRADE_AMOUNT_INR:
            st.caption(
                f"⚠️ This link was created at the old price (₹{pending['amount']}). "
                f"The current price is ₹{PREMIUM_UPGRADE_AMOUNT_INR} — click '🔄 Get New Payment Link' above for a link at the new price."
            )

    st.write("---")

def refresh_institute_session(institute_id: int):
    if not institute_id:
        return
    inst = get_institute(conn, institute_id)
    if inst:
        st.session_state.institute_name = inst["name"]
        st.session_state.institute_plan = inst["plan"]
        st.session_state.student_limit = inst["student_limit"]

def render_csv_import_widget(institute_id: int, key_prefix: str):
    st.caption("CSV columns: **name** (required), grade, subject, fee, parent_email (all optional).")
    uploaded = st.file_uploader("Choose a CSV file", type=["csv"], key=f"{key_prefix}_csv_uploader")
    if not uploaded:
        return

    try:
        text = uploaded.getvalue().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        parsed_rows = []
        for raw_row in reader:
            norm_row = {(k or "").strip().lower(): v for k, v in raw_row.items()}
            parsed_rows.append(norm_row)
    except Exception as e:
        st.error(f"Couldn't read that CSV: {e}")
        return

    valid_rows = [r for r in parsed_rows if (r.get("name") or "").strip()]
    skipped = len(parsed_rows) - len(valid_rows)

    if not valid_rows:
        st.warning("No valid rows found — make sure the CSV has a 'name' column.")
        return

    st.write(f"Found **{len(valid_rows)}** student(s) to import" + (f" ({skipped} row(s) skipped — missing name)" if skipped else "") + ":")
    st.dataframe(valid_rows[:20], use_container_width=True, hide_index=True)
    if len(valid_rows) > 20:
        st.caption(f"…and {len(valid_rows) - 20} more.")

    plan = st.session_state.get("institute_plan", "Free")
    if plan != "Premium":
        limit = st.session_state.get("student_limit", FREE_STUDENT_LIMIT)
        current = count_students(conn, institute_id)
        if current + len(valid_rows) > limit:
            st.error(
                f"This import would bring you to {current + len(valid_rows)} students, "
                f"over the Free plan limit of {limit}. Ask the platform owner to upgrade to Premium first, "
                f"or trim the CSV."
            )
            return

    if st.button(f"✅ Import {len(valid_rows)} Student(s)", use_container_width=True, key=f"{key_prefix}_confirm_import"):
        st.toast(f"Importing {len(valid_rows)} student(s)…", icon="⏳")
        with st.spinner(f"Importing {len(valid_rows)} student(s)…"):
            inserted = bulk_add_students(conn, institute_id, valid_rows)
            log_audit_event(conn, st.session_state.get("user_email", ""), "bulk_import", f"Imported {inserted} students via CSV", institute_id)
        st.success(f"Imported {inserted} student(s) successfully!")
        st.rerun()

# ----------------------------------------------------
# 8. VIEW: LOGIN / SIGNUP  (rewritten for clarity — see change note below)
# ----------------------------------------------------
# CHANGE: the two tabs were not obviously distinct enough — real users
# (institute Admins, Teachers, Parents) weren't sure which tab was for them.
# Fixed by: (1) a clear "Which one am I?" box right above the tabs that
# names all three roles explicitly, (2) more explicit tab labels, (3) a
# matching colored guidance box repeated INSIDE each tab, so whichever one
# someone lands on, they immediately see confirmation they're in the right
# place or a pointer to switch.

def show_login():
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
        {logo_img_tag()}
        <div>
            <h2 style="margin: 0; font-size: 22px; color: #ffffff;">Tuition Academy Platform</h2>
            <p style="margin: 0; color: #94a3b8; font-size: 13px;">Secure Portal Authentication</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="login-guide-box">
        <strong style="color: #38bdf8;">👋 Which one am I?</strong>
        <p style="color: #e2e8f0; margin: 8px 0 0 0; font-size: 14px; line-height: 1.6;">
            🧑‍🏫 <strong>Teacher</strong> or 👨‍👩‍👧 <strong>Parent</strong> — your academy's Admin already created your login.
            Use the email &amp; password they gave you in the <strong>"🔑 I Already Have a Login"</strong> tab below.<br>
            🏫 <strong>Starting a brand-new tuition academy?</strong> — you don't have a login yet.
            Use the <strong>"🆕 New Academy? Start Free"</strong> tab to create one — you'll become its Admin.
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["🔑 I Already Have a Login", "🆕 New Academy? Start Free"])

    with tab_login:
        st.markdown("""
        <div class="login-guide-box">
            <span style="color: #e2e8f0; font-size: 14px;">
                ✅ Use this tab if you're an <strong>Admin, Teacher, or Parent</strong> who already has an email &amp; password
                for this platform.
            </span>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            email_input = st.text_input("Registered Email Address", placeholder="name@academy.com")
            password_input = st.text_input("Account Password", type="password", placeholder="••••••••")
            submit_btn = st.form_submit_button("Access Dashboard", use_container_width=True)

            if submit_btn:
                clean_email = email_input.strip().lower()
                is_locked, seconds_left = check_login_lock(conn, clean_email)
                if is_locked:
                    minutes_left = max(1, seconds_left // 60)
                    st.error(f"Too many failed attempts for this account. Try again in about {minutes_left} minute(s).")
                else:
                    st.toast("Checking credentials…", icon="⏳")
                    with st.spinner("Checking credentials…"):
                        result = authenticate(conn, clean_email, password_input)
                    if result:
                        clear_failed_login(conn, clean_email)
                        st.session_state.logged_in = True
                        st.session_state.logged_in_role = result["role"]
                        st.session_state.user_email = clean_email
                        st.session_state.is_super_admin = result["is_super_admin"]
                        st.session_state.institute_id = result["institute_id"]

                        if result["institute_id"]:
                            inst = get_institute(conn, result["institute_id"])
                            if inst:
                                st.session_state.institute_name = inst["name"]
                                st.session_state.institute_plan = inst["plan"]
                                st.session_state.student_limit = inst["student_limit"]

                        st.session_state.active_view = "SuperAdmin" if result["is_super_admin"] else result["role"]
                        must_change = bool(result.get("must_change_password"))
                        st.session_state.must_change_password = must_change
                        st.rerun()
                    else:
                        record_failed_login(conn, clean_email)
                        st.error(
                            "Invalid email or password. If you're a Teacher or Parent, double-check with your "
                            "academy Admin — they're the ones who created your account."
                        )

        if SHOW_DEMO_CREDENTIALS:
            with st.expander("Demo credentials (for testing only)", expanded=False):
                st.caption(
                    "Admin: admin@academy.com / admin123  \n"
                    "Teacher: teacher@academy.com / teacher123  \n"
                    "Parent (Aarav's family): parent1@academy.com / parent123  \n"
                    "Parent (Rohan's family): parent2@academy.com / parent123"
                )

    with tab_signup:
        st.markdown("""
        <div class="login-guide-box signup">
            <span style="color: #e2e8f0; font-size: 14px;">
                🏫 Use this tab ONLY if you're starting a <strong>brand-new tuition academy</strong> on this platform.
                You'll become that academy's <strong>Admin</strong> and can then create Teacher and Parent logins
                for your staff and students' families from your Admin Console.
            </span>
        </div>
        """, unsafe_allow_html=True)

        st.caption(f"Free plan includes up to {FREE_STUDENT_LIMIT} students, no credit card needed. Upgrade any time.")

        if "signup_captcha_a" not in st.session_state:
            st.session_state.signup_captcha_a = secrets.randbelow(9) + 1
            st.session_state.signup_captcha_b = secrets.randbelow(9) + 1

        with st.form("signup_form", clear_on_submit=True):
            s_institute = st.text_input("Institute / Academy Name", placeholder="e.g., Bright Minds Tuition")
            s_email = st.text_input("Your Email (this becomes your Admin login)", placeholder="owner@myacademy.com")
            s_pass = st.text_input("Create Password", type="password", help=f"Use {MIN_PASSWORD_LENGTH}+ characters with uppercase, lowercase, number and special character.")
            s_honeypot = st.text_input(
                "Leave this field empty",
                key="signup_honeypot",
                help="Spam protection — please leave this blank."
            )
            captcha_answer = st.number_input(
                f"Quick check — what is {st.session_state.signup_captcha_a} + {st.session_state.signup_captcha_b}?",
                step=1, value=0, key="signup_captcha_answer"
            )

            if st.form_submit_button("Create My Academy Account", use_container_width=True):
                clean_s_email = s_email.strip().lower()
                correct_answer = st.session_state.signup_captcha_a + st.session_state.signup_captcha_b

                if s_honeypot.strip():
                    st.error("Something went wrong. Please try again.")
                elif captcha_answer != correct_answer:
                    st.warning("That answer isn't quite right — please try the math check again.")
                    st.session_state.signup_captcha_a = secrets.randbelow(9) + 1
                    st.session_state.signup_captcha_b = secrets.randbelow(9) + 1
                elif s_institute.strip() and clean_s_email and s_pass.strip():
                    if not is_valid_email(clean_s_email):
                        st.warning("Please enter a valid email address.")
                    elif not is_password_strong_enough(s_pass):
                        st.warning(f"Password must be {MIN_PASSWORD_LENGTH}+ characters and include uppercase, lowercase, number and special character.")
                    else:
                        allowed, rate_msg = check_signup_rate_limit(conn)
                        if not allowed:
                            st.error(rate_msg)
                        else:
                            try:
                                st.toast("Creating your academy…", icon="⏳")
                                with st.spinner("Creating your academy…"):
                                    create_institute_and_admin(conn, s_institute.strip(), clean_s_email, s_pass)
                                    record_signup_attempt(conn)
                                st.success(
                                    f"Account created! '{s_institute.strip()}' is live on the Free plan "
                                    f"(up to {FREE_STUDENT_LIMIT} students). Switch to the "
                                    f"'🔑 I Already Have a Login' tab above to log in."
                                )
                                st.session_state.signup_captcha_a = secrets.randbelow(9) + 1
                                st.session_state.signup_captcha_b = secrets.randbelow(9) + 1
                            except (ValueError, sqlite3.IntegrityError):
                                st.error("An account with that email already exists. Please log in instead.")
                else:
                    st.warning("Please fill in all fields.")

# ----------------------------------------------------
# 9. VIEW: TEACHER DASHBOARD
# ----------------------------------------------------
def show_teacher_dashboard():
    institute_id = st.session_state.get("institute_id")
    refresh_institute_session(institute_id)
    render_admin_quick_nav("Teacher")
    render_header("Tuition Operations Console", "Teacher Desk • Operations Console")

    with st.expander("➕ Create New Classroom / Batch", expanded=False):
        with st.form("create_room_form", clear_on_submit=True):
            r_col1, r_col2 = st.columns(2)
            with r_col1:
                r_title = st.text_input("Grade / Class Level", placeholder="e.g., Class 11, Grade 8, AP Physics")
            with r_col2:
                r_subj = st.text_input("Subject", placeholder="e.g., Physics, Calculus, Chemistry")

            r_col3, r_col4 = st.columns(2)
            with r_col3:
                r_batch = st.text_input("Batch / Section", placeholder="e.g., Batch A, Room 102, Weekend")
            with r_col4:
                r_fee = st.number_input("Standard Monthly Fee (₹)", min_value=0, value=2500, step=100)

            if st.form_submit_button("Save Classroom", use_container_width=True):
                if r_title.strip() and r_subj.strip():
                    st.toast("Saving classroom…", icon="⏳")
                    with st.spinner("Saving classroom…"):
                        add_classroom(conn, institute_id, r_title.strip(), r_subj.strip(), r_batch.strip() or "Regular", r_fee)
                    st.success("Classroom created successfully!")
                    st.rerun()
                else:
                    st.warning("Please provide both a Class level and a Subject.")

    classrooms = list_classrooms(conn, institute_id)
    active_room = None
    if classrooms:
        room_labels = [f"{r['title']} — {r['subject']} ({r['section']})" for r in classrooms]
        selected_label = st.selectbox("Select Active Classroom to Manage:", room_labels, key="active_room_picker")
        active_room = classrooms[room_labels.index(selected_label)]

        st.markdown(f"""
        <div style="background-color: #1e293b; border: 1.5px solid #38bdf8; border-radius: 12px; padding: 12px 18px; margin: 10px 0 20px 0;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                <div>
                    <span style="color: #38bdf8; font-weight: 700; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;">Active Class:</span>
                    <span style="color: #ffffff; font-weight: 700; font-size: 16px; margin-left: 6px;">{esc(active_room['title'])}</span>
                </div>
                <div style="color: #cbd5e1; font-size: 14px;">
                    Subject: <strong style="color: #38bdf8;">{esc(active_room['subject'])}</strong>
                    <span style="color: #64748b; margin: 0 6px;">•</span>
                    Batch: <strong style="color: #f1f5f9;">{esc(active_room['section'])}</strong>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    tab_students, tab_attendance, tab_financial, tab_notices = st.tabs([
        "👥 Student Management",
        "📅 Attendance Desk",
        "💰 Financial Desk",
        "📢 Notice Board"
    ])

    all_students = list_students(conn, institute_id)

    with tab_students:
        st.subheader("Academy Student Roster")

        roster_search = st.text_input(
            "🔎 Search roster", placeholder="Search by name, ID, grade, subject, or parent email…",
            key="teacher_roster_search"
        )
        displayed_students = filter_students(all_students, roster_search)

        if all_students:
            if roster_search and not displayed_students:
                st.warning("No students match that search.")
            elif displayed_students:
                st.dataframe(displayed_students, use_container_width=True, hide_index=True)
                st.download_button(
                    "⬇️ Export Roster (CSV)", rows_to_csv_bytes(displayed_students),
                    file_name="roster.csv", mime="text/csv", key="teacher_export_roster"
                )
        else:
            st.info("No students added yet. Use the form below to register your first student.")

        with st.expander("➕ Add New Student to Roster", expanded=False):
            with st.form("new_student_form", clear_on_submit=True):
                stu_name = st.text_input("Full Name", placeholder="e.g., Aarav Sharma")

                default_grade = active_room["title"] if active_room else ""
                default_subject = active_room["subject"] if active_room else ""
                default_fee = int(active_room["fee"]) if active_room else 2500

                stu_grade = st.text_input("Grade / Batch / Room", value=default_grade, placeholder="e.g., Class 11 Physics")
                stu_subject = st.text_input("Assigned Subject", value=default_subject, placeholder="e.g., Physics")
                stu_fee = st.number_input("Monthly Fee Amount (₹)", min_value=0, value=default_fee, step=100)
                stu_parent_email = st.text_input(
                    "Parent Email (optional)",
                    placeholder="parent@example.com",
                    help="Links this student to a parent account so only that family can see their fees, attendance and notices."
                )

                if st.form_submit_button("Save Student to Records", use_container_width=True):
                    if stu_name.strip():
                        allowed, limit_msg = can_add_student(conn, institute_id)
                        if not allowed:
                            st.error(limit_msg)
                        else:
                            st.toast("Saving student…", icon="⏳")
                            with st.spinner("Saving student…"):
                                add_student(
                                    conn,
                                    institute_id,
                                    stu_name.strip(),
                                    stu_grade.strip() or "General",
                                    stu_subject.strip() or "General",
                                    stu_fee,
                                    stu_parent_email.strip().lower() or None,
                                )
                            st.success(f"Added {stu_name.strip()} successfully!")
                            st.rerun()
                    else:
                        st.warning("Please enter student name.")

        with st.expander("📥 Bulk Import Students (CSV)", expanded=False):
            render_csv_import_widget(institute_id, key_prefix="teacher")

        with st.expander("🔗 Link / Update Parent Email", expanded=False):
            if all_students:
                link_options = [f"{s['name']} ({s['id']})" for s in all_students]
                link_choice = st.selectbox("Select Student", link_options, key="link_parent_select")
                chosen = all_students[link_options.index(link_choice)]
                st.caption(f"Currently linked to: **{chosen.get('parent_email') or 'no parent account'}**")
                new_parent_email = st.text_input(
                    "New Parent Email (leave blank to unlink)",
                    value=chosen.get("parent_email") or "",
                    key="new_parent_email_input"
                )
                if st.button("Update Link", use_container_width=True, key="update_parent_link_btn"):
                    st.toast("Updating…", icon="⏳")
                    with st.spinner("Updating…"):
                        update_student_parent_email(conn, institute_id, chosen["id"], new_parent_email.strip().lower() or None)
                    st.success("Parent link updated.")
                    st.rerun()
            else:
                st.write("No students available yet.")

        with st.expander("🗑️ Delete Student from Roster", expanded=False):
            if all_students:
                student_options = [f"{s['name']} ({s['id']})" for s in all_students]
                del_choice = st.selectbox("Select Student to Remove", student_options, key="del_stu_select")
                if st.button("Confirm Delete", type="primary", use_container_width=True):
                    chosen_id = del_choice.split("(")[-1].replace(")", "").strip()
                    st.toast("Removing student…", icon="⏳")
                    with st.spinner("Removing student…"):
                        delete_student(conn, institute_id, chosen_id, actor_email=st.session_state.get("user_email", ""))
                    st.success("Student removed.")
                    st.rerun()
            else:
                st.write("No students available to remove.")

    with tab_attendance:
        st.subheader("Daily Attendance Register")
        selected_date = st.date_input(
            "Attendance Date",
            value=datetime.date.today(),
            max_value=datetime.date.today(),
            key="att_desk_date_picker",
            help="Pick a past date to correct or fill in attendance you missed logging that day."
        )
        today_str = selected_date.strftime("%Y-%m-%d")
        existing_for_date = attendance_for_date(conn, institute_id, today_str)
        st.caption(f"Logging Record for: **{today_str}**" + (" _(editing a saved record)_" if existing_for_date else ""))

        registered_rooms = sorted(list(set(s.get("grade", "").strip() for s in all_students if s.get("grade"))))

        if not registered_rooms:
            st.info("No student rooms registered yet. Add students under Student Management first.")
            active_roster = []
        else:
            selected_class = st.selectbox(
                "Select Class / Room to Mark",
                options=["All Classes"] + registered_rooms,
                index=0,
                key="att_desk_room_selector"
            )
            active_roster = all_students if selected_class == "All Classes" else \
                [s for s in all_students if s.get("grade") == selected_class]

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("✅ Mark All Present", use_container_width=True, key="mark_all_btn"):
                st.toast("Marking everyone present…", icon="✅")
                st.session_state.att_mark_default = True
                st.session_state.att_bulk_override = {s["id"]: True for s in active_roster}
                st.session_state.att_batch_stamp = st.session_state.get("att_batch_stamp", 0) + 1
        with col_b:
            if st.button("⭕ Clear All", use_container_width=True, key="clear_all_btn"):
                st.toast("Clearing all…", icon="⭕")
                st.session_state.att_mark_default = False
                st.session_state.att_bulk_override = {s["id"]: False for s in active_roster}
                st.session_state.att_batch_stamp = st.session_state.get("att_batch_stamp", 0) + 1

        if "att_mark_default" not in st.session_state:
            st.session_state.att_mark_default = True
        if "att_bulk_override" not in st.session_state:
            st.session_state.att_bulk_override = {}
        batch_stamp = st.session_state.get("att_batch_stamp", 0)

        attendance_status = {}
        st.write("---")
        for s in active_roster:
            s_id = s["id"]
            if s_id in st.session_state.att_bulk_override:
                default_checked = bool(st.session_state.att_bulk_override[s_id])
            elif s_id in existing_for_date:
                default_checked = existing_for_date[s_id] == "Present"
            else:
                default_checked = st.session_state.att_mark_default
            attendance_status[s_id] = st.checkbox(
                f"{s['name']} — {s['grade']} ({s.get('subject', 'General')})",
                value=default_checked,
                key=f"att_check_{s_id}_{today_str}_{batch_stamp}"
            )

        if st.button("Submit Attendance Register", use_container_width=True, key="submit_att_btn"):
            entries = [
                {
                    "student_id": s["id"],
                    "status": "Present" if attendance_status.get(s["id"]) else "Absent",
                    "class_name": s.get("grade", "General"),
                }
                for s in active_roster
            ]
            st.toast("Saving attendance…", icon="⏳")
            with st.spinner("Saving attendance…"):
                save_attendance(conn, institute_id, today_str, entries)
            present_count = sum(1 for e in entries if e["status"] == "Present")
            st.success(f"Attendance recorded for {today_str}! Present: {present_count} | Absent: {len(entries) - present_count}")

    with tab_financial:
        st.subheader("🔒 Financial Desk — Admin Only")
        st.info("Teachers can manage students, attendance and notices. Fee records and financial ledgers are restricted to Academy Admins.")

    with tab_notices:
        st.subheader("📢 Academy Notice Board")

        registered_grades_for_notices = sorted(list(set(
            s.get("grade", "").strip() for s in all_students if s.get("grade")
        )))

        with st.expander("➕ Broadcast New Announcement", expanded=False):
            with st.form("new_notice_form", clear_on_submit=True):
                n_title = st.text_input("Announcement Title", placeholder="e.g., Weekly Test Schedule / Holiday")
                n_body = st.text_area("Message / Details", placeholder="Write the announcement details here...")
                n_priority = st.selectbox("Priority Level", ["Normal", "Urgent", "Exam/Test"])
                n_target_grade = st.selectbox(
                    "Send To",
                    options=["All Classes"] + registered_grades_for_notices,
                    help="Pick a specific class so only students (and their parents) in that class see it, or leave as All Classes."
                )

                if st.form_submit_button("Publish Announcement", use_container_width=True):
                    if n_title.strip() and n_body.strip():
                        target = None if n_target_grade == "All Classes" else n_target_grade
                        st.toast("Publishing notice…", icon="⏳")
                        with st.spinner("Publishing notice…"):
                            add_notice(conn, institute_id, n_title.strip(), n_body.strip(), n_priority, datetime.date.today().strftime("%d %b %Y"), target)
                        st.success("Notice published successfully!")
                        st.rerun()
                    else:
                        st.warning("Please provide both a title and details.")

        notices = list_notices(conn, institute_id)
        if notices:
            for notice in notices:
                border_color = "#ef4444" if notice["priority"] == "Urgent" else ("#f59e0b" if notice["priority"] == "Exam/Test" else "#38bdf8")
                target_label = notice.get("target_grade") or "All Classes"
                st.markdown(f"""
                <div style="background-color: #1e293b; border-left: 4px solid {border_color}; border-radius: 8px; padding: 12px 16px; margin: 10px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="color: #ffffff; font-size: 16px;">{esc(notice['title'])}</strong>
                        <span style="color: #94a3b8; font-size: 12px;">{esc(notice['date'])}</span>
                    </div>
                    <p style="color: #cbd5e1; font-size: 14px; margin: 8px 0 0 0; line-height: 1.4;">{esc(notice['body'])}</p>
                    <span style="display: inline-block; margin-top: 8px; background: rgba(56,189,248,0.15); color: #38bdf8; font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 10px;">{esc(target_label)}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No notices posted yet. Use the form above to broadcast an update.")

    if st.session_state.get("logged_in_role") == "Teacher":
        logout_button("teacher_logout_btn")

# ----------------------------------------------------
# 10. VIEW: PARENT DASHBOARD
# ----------------------------------------------------
def render_child_card(child: dict, institute_id: int):
    child_id = child.get("id", "")
    child_name = child.get("name", "")

    fee_status = get_payment_status(conn, institute_id, child_id)
    status_badge_color = "#4ade80" if fee_status == "Paid" else "#f87171"

    history_rows = attendance_history(conn, institute_id, child_id)
    total_days = len(history_rows)
    present_days = sum(1 for _, status in history_rows if status == "Present")
    attendance_pct = int((present_days / total_days) * 100) if total_days > 0 else 100

    st.markdown(f"""
    <div style="background-color: #1e293b; border: 1.5px solid #334155; border-radius: 14px; padding: 18px; margin-top: 10px;">
        <h3 style="color: #ffffff; margin-top: 0; font-size: 18px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
            {esc(child_name)} — Academic & Tuition Status
        </h3>
        <p style="color: #cbd5e1; margin: 10px 0; font-size: 15px;">
            Batch / Grade: <strong style="color: #38bdf8;">{esc(child.get('grade'))}</strong>
            <span style="color: #64748b;">({esc(child.get('subject', 'General'))})</span>
        </p>
        <p style="color: #cbd5e1; margin: 10px 0; font-size: 15px;">
            Attendance Record: <strong style="color: #38bdf8;">{attendance_pct}%</strong>
            <span style="color: #94a3b8; font-size: 13px;">({present_days}/{total_days} sessions attended)</span>
        </p>
        <p style="color: #cbd5e1; margin: 10px 0; font-size: 15px;">
            Monthly Tuition Fee: <strong style="color: #ffffff;">₹{child.get('fee', 2500):,}</strong>
        </p>
        <p style="color: #cbd5e1; margin: 10px 0; font-size: 15px;">
            Fee Status: <strong style="color: {status_badge_color};">{fee_status}</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    detail_col1, detail_col2 = st.columns(2)

    with detail_col1:
        with st.expander(f"📅 Attendance History — {child_name}", expanded=False):
            if history_rows:
                st.dataframe(
                    [{"Date": d, "Status": s} for d, s in history_rows],
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("No attendance sessions logged yet for this student.")

    with detail_col2:
        with st.expander(f"💳 Payment History — {child_name}", expanded=False):
            tx_list = list_financial_records(conn, institute_id, student_id=child_id, student_name=child_name)
            if tx_list:
                st.dataframe(tx_list, use_container_width=True, hide_index=True)
            else:
                st.info("No recorded transactions yet for this student.")

    with st.expander(f"📢 Notices for {child.get('grade', 'this class')}", expanded=False):
        notices = list_notices(conn, institute_id, grade=child.get("grade"))
        if notices:
            for n in notices:
                border_color = "#ef4444" if n["priority"] == "Urgent" else ("#f59e0b" if n["priority"] == "Exam/Test" else "#38bdf8")
                st.markdown(f"""
                <div style="background-color: #0f172a; border-left: 4px solid {border_color}; border-radius: 8px; padding: 10px 14px; margin: 8px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="color: #ffffff; font-size: 14px;">{esc(n['title'])}</strong>
                        <span style="color: #94a3b8; font-size: 11px;">{esc(n['date'])}</span>
                    </div>
                    <p style="color: #cbd5e1; font-size: 13px; margin: 6px 0 0 0; line-height: 1.4;">{esc(n['body'])}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No notices posted yet.")

def show_parent_dashboard():
    institute_id = st.session_state.get("institute_id")
    render_admin_quick_nav("Parent")

    is_admin_viewing = st.session_state.get("logged_in_role") == "Admin" and not st.session_state.get("is_super_admin")
    parent_email = st.session_state.get("user_email", "")

    if is_admin_viewing:
        parent_accounts = list_parent_accounts(conn, institute_id)
        parent_emails = [p["email"] for p in parent_accounts]
        if parent_emails:
            chosen = st.selectbox(
                "🔎 View Parent Portal as:",
                options=parent_emails,
                key="admin_view_as_parent"
            )
            parent_email = chosen
        else:
            st.info("No parent accounts exist yet — create one from the Admin Console.")
            return

    my_children = list_students(conn, institute_id, parent_email=parent_email)

    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
        {logo_img_tag()}
        <div>
            <h2 style="margin: 0; font-size: 22px; color: #ffffff;">Parent Portal</h2>
            <p style="margin: 0; color: #94a3b8; font-size: 13px;">
                {'Previewing as' if is_admin_viewing else 'Signed in as'} <strong style="color: #38bdf8;">{esc(parent_email)}</strong>
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not my_children:
        st.info(
            "No students are linked to this account yet. Ask the academy admin to link "
            "your child's profile to this email address."
        )
    else:
        for child in my_children:
            render_child_card(child, institute_id)

    if st.session_state.get("logged_in_role") == "Parent":
        logout_button("parent_logout_btn")

# ----------------------------------------------------
# 11. VIEW: ADMIN DASHBOARD
# ----------------------------------------------------
def show_admin_dashboard():
    institute_id = st.session_state.get("institute_id")
    refresh_institute_session(institute_id)
    institute_name = st.session_state.get("institute_name") or "Your Academy"
    render_header("Admin Master Console", f"{institute_name} • Executive Management")

    render_plan_banner(institute_id)
    render_premium_upgrade_widget(institute_id, institute_name, st.session_state.get("user_email", ""))

    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("🧑‍🏫 Open Teacher Desk", use_container_width=True, key="admin_to_teacher_btn"):
            st.toast("Opening Teacher Desk…", icon="🔄")
            go_to("Teacher")
            st.rerun()
    with col_nav2:
        if st.button("👨‍👩‍👧 Open Parent Portal", use_container_width=True, key="admin_to_parent_btn"):
            st.toast("Opening Parent Portal…", icon="🔄")
            go_to("Parent")
            st.rerun()

    st.write("---")

    all_students = list_students(conn, institute_id)
    enrolled_count = len(all_students)
    total_rev = sum(s.get("fee", 0) for s in all_students)
    admin_payment_statuses = get_payment_statuses_bulk(conn, institute_id)
    total_collected = sum(s.get("fee", 0) for s in all_students if admin_payment_statuses.get(s["id"], "Unpaid") == "Paid")

    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        st.metric("Enrolled Students", enrolled_count)
    with m_col2:
        st.metric("Expected Revenue", f"₹{total_rev:,}")
    with m_col3:
        st.metric("Collected So Far", f"₹{total_collected:,}")

    st.write("---")
    st.subheader("🧑‍🎓 Manage Students")

    admin_roster_search = st.text_input(
        "🔎 Search roster", placeholder="Search by name, ID, grade, subject, or parent email…",
        key="admin_roster_search"
    )
    admin_displayed_students = filter_students(all_students, admin_roster_search)

    if all_students:
        if admin_roster_search and not admin_displayed_students:
            st.warning("No students match that search.")
        elif admin_displayed_students:
            st.dataframe(admin_displayed_students, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Export Roster (CSV)", rows_to_csv_bytes(admin_displayed_students),
                file_name=f"{institute_name}_roster.csv", mime="text/csv", key="admin_export_roster"
            )
    else:
        st.info("No student records available.")

    with st.expander("➕ Add New Student", expanded=False):
        with st.form("admin_new_student_form", clear_on_submit=True):
            a_name = st.text_input("Full Name", placeholder="e.g., Aarav Sharma")
            a_grade = st.text_input("Grade / Batch / Room", placeholder="e.g., Class 11 Physics")
            a_subject = st.text_input("Assigned Subject", placeholder="e.g., Physics")
            a_fee = st.number_input("Monthly Fee Amount (₹)", min_value=0, value=2500, step=100)
            a_parent_email = st.text_input(
                "Parent Email (optional)",
                placeholder="parent@example.com",
                help="Links this student to a parent account so only that family can see their fees, attendance and notices."
            )
            if st.form_submit_button("Save Student", use_container_width=True):
                if a_name.strip():
                    allowed, limit_msg = can_add_student(conn, institute_id)
                    if not allowed:
                        st.error(limit_msg)
                    else:
                        st.toast("Saving student…", icon="⏳")
                        with st.spinner("Saving student…"):
                            add_student(
                                conn,
                                institute_id,
                                a_name.strip(),
                                a_grade.strip() or "General",
                                a_subject.strip() or "General",
                                a_fee,
                                a_parent_email.strip().lower() or None,
                            )
                        st.success(f"Added {a_name.strip()} successfully!")
                        st.rerun()
                else:
                    st.warning("Please enter student name.")

    with st.expander("📥 Bulk Import Students (CSV)", expanded=False):
        render_csv_import_widget(institute_id, key_prefix="admin")

    with st.expander("✏️ Edit Student", expanded=False):
        if all_students:
            edit_options = [f"{s['name']} ({s['id']})" for s in all_students]
            edit_choice = st.selectbox("Select Student to Edit", edit_options, key="admin_edit_stu_select")
            editing = all_students[edit_options.index(edit_choice)]

            with st.form("admin_edit_student_form"):
                e_name = st.text_input("Full Name", value=editing["name"])
                e_grade = st.text_input("Grade / Batch / Room", value=editing.get("grade", ""))
                e_subject = st.text_input("Assigned Subject", value=editing.get("subject", ""))
                e_fee = st.number_input("Monthly Fee Amount (₹)", min_value=0, value=int(editing.get("fee", 0)), step=100)
                e_parent_email = st.text_input(
                    "Parent Email (leave blank to unlink)",
                    value=editing.get("parent_email") or ""
                )
                if st.form_submit_button("Save Changes", use_container_width=True):
                    st.toast("Saving changes…", icon="⏳")
                    with st.spinner("Saving changes…"):
                        update_student(conn, institute_id, editing["id"], e_name.strip(), e_grade.strip() or "General", e_subject.strip() or "General", e_fee)
                        update_student_parent_email(conn, institute_id, editing["id"], e_parent_email.strip().lower() or None)
                    st.success("Student record updated.")
                    st.rerun()
        else:
            st.write("No students available to edit.")

    with st.expander("🗑️ Delete Student", expanded=False):
        if all_students:
            del_options = [f"{s['name']} ({s['id']})" for s in all_students]
            del_choice = st.selectbox("Select Student to Remove", del_options, key="admin_del_stu_select")
            if st.button("Confirm Delete", type="primary", use_container_width=True, key="admin_del_stu_btn"):
                chosen_id = del_choice.split("(")[-1].replace(")", "").strip()
                st.toast("Removing student…", icon="⏳")
                with st.spinner("Removing student…"):
                    delete_student(conn, institute_id, chosen_id, actor_email=st.session_state.get("user_email", ""))
                st.success("Student removed.")
                st.rerun()
        else:
            st.write("No students available to remove.")

    with st.expander("♻️ Archived Students / Restore", expanded=False):
        archived = list_archived_students(conn, institute_id)
        if archived:
            restore_options = [f"{s['name']} ({s['id']})" for s in archived]
            restore_choice = st.selectbox("Select Student to Restore", restore_options, key="admin_restore_stu_select")
            if st.button("♻️ Restore Student", use_container_width=True, key="admin_restore_stu_btn"):
                chosen_id = restore_choice.split("(")[-1].replace(")", "").strip()
                restore_student(conn, institute_id, chosen_id, actor_email=st.session_state.get("user_email", ""))
                st.success("Student restored successfully.")
                st.rerun()
        else:
            st.info("No archived students.")

    st.write("---")
    st.subheader("Master Financial Ledger")
    records = list_financial_records(conn, institute_id)
    if records:
        st.dataframe(records, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Export Ledger (CSV)", rows_to_csv_bytes(records),
            file_name=f"{institute_name}_ledger.csv", mime="text/csv", key="admin_export_ledger"
        )
    else:
        st.info("No ledger entries available.")

    st.write("---")
    st.subheader("👪 Parent Accounts")
    st.caption("Each parent account only sees the student(s) linked to it here.")

    with st.expander("➕ Create Parent Account", expanded=False):
        with st.form("create_parent_form", clear_on_submit=True):
            p_email = st.text_input("Parent Email", placeholder="parent@example.com")
            p_pass = st.text_input("Temporary Password", type="password", help=f"Use {MIN_PASSWORD_LENGTH}+ characters with uppercase, lowercase, number and special character.")
            p_children = st.multiselect(
                "Link to Student(s)",
                options=[f"{s['name']} ({s['id']})" for s in all_students],
                help="Students are selected by unique student ID so duplicate names cannot be linked accidentally."
            )
            if st.form_submit_button("Create Account", use_container_width=True):
                clean_email = p_email.strip().lower()
                if clean_email and p_pass.strip():
                    if not is_valid_email(clean_email):
                        st.warning("Please enter a valid email address.")
                    elif not is_password_strong_enough(p_pass):
                        st.warning(f"Password must be {MIN_PASSWORD_LENGTH}+ characters and include uppercase, lowercase, number and special character.")
                    else:
                        try:
                            st.toast("Creating parent account…", icon="⏳")
                            with st.spinner("Creating parent account…"):
                                create_parent_account(conn, institute_id, clean_email, p_pass)
                                for selected in p_children:
                                    match = next((s for s in all_students if selected.endswith(f"({s['id']})")), None)
                                    if match:
                                        update_student_parent_email(conn, institute_id, match["id"], clean_email)
                            st.success(f"Parent account created for {clean_email}. Give them this email + the password you set, and tell them to use the 'I Already Have a Login' tab.")
                            st.rerun()
                        except Exception:
                            st.error("An account with that email already exists.")
                else:
                    st.warning("Email and password are required.")

    parent_accounts = list_parent_accounts(conn, institute_id)
    if parent_accounts:
        for pr in parent_accounts:
            linked_names = [s["name"] for s in all_students if s.get("parent_email") == pr["email"]]
            p_col1, p_col2 = st.columns([4, 1])
            with p_col1:
                linked_text = ", ".join(linked_names) if linked_names else "_no students linked_"
                st.markdown(f"**{pr['email']}** — linked to: {linked_text}")
            with p_col2:
                if st.button("Remove", key=f"del_parent_{pr['email']}", use_container_width=True):
                    st.toast("Removing…", icon="⏳")
                    with st.spinner("Removing…"):
                        delete_parent_account(conn, institute_id, pr["email"])
                    st.rerun()
    else:
        st.info("No parent accounts yet — create one above.")

    st.write("---")
    st.subheader("🧑‍🏫 Teacher Accounts")
    st.caption("Give each real teacher their own login instead of sharing one account.")

    with st.expander("➕ Create Teacher Account", expanded=False):
        with st.form("create_teacher_form", clear_on_submit=True):
            t_email = st.text_input("Teacher Email", placeholder="teacher.name@academy.com")
            t_pass = st.text_input("Temporary Password", type="password", key="new_teacher_pass", help=f"Use {MIN_PASSWORD_LENGTH}+ characters with uppercase, lowercase, number and special character.")
            if st.form_submit_button("Create Account", use_container_width=True):
                clean_t_email = t_email.strip().lower()
                if clean_t_email and t_pass.strip():
                    if not is_valid_email(clean_t_email):
                        st.warning("Please enter a valid email address.")
                    elif not is_password_strong_enough(t_pass):
                        st.warning(f"Password must be {MIN_PASSWORD_LENGTH}+ characters and include uppercase, lowercase, number and special character.")
                    else:
                        try:
                            st.toast("Creating teacher account…", icon="⏳")
                            with st.spinner("Creating teacher account…"):
                                create_teacher_account(conn, institute_id, clean_t_email, t_pass)
                            st.success(f"Teacher account created for {clean_t_email}. Give them this email + the password you set, and tell them to use the 'I Already Have a Login' tab.")
                            st.rerun()
                        except Exception:
                            st.error("An account with that email already exists.")
                else:
                    st.warning("Email and password are required.")

    teacher_accounts = list_teacher_accounts(conn, institute_id)
    if teacher_accounts:
        for tr in teacher_accounts:
            t_col1, t_col2 = st.columns([4, 1])
            with t_col1:
                st.markdown(f"**{tr['email']}**")
            with t_col2:
                if st.button("Remove", key=f"del_teacher_{tr['email']}", use_container_width=True):
                    st.toast("Removing…", icon="⏳")
                    with st.spinner("Removing…"):
                        delete_teacher_account(conn, institute_id, tr["email"])
                    st.rerun()
    else:
        st.info("No teacher accounts yet — create one above.")

    logout_button("admin_logout_btn")

# ----------------------------------------------------
# 12. VIEW: SUPER ADMIN DASHBOARD
# ----------------------------------------------------
def show_super_admin_dashboard():
    render_header("Super Admin Console", "Platform Owner • Manage every institute")

    institutes = list_institutes(conn)
    total_institutes = len(institutes)
    premium_count = sum(1 for i in institutes if i["plan"] == "Premium")
    free_count = total_institutes - premium_count

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Institutes", total_institutes)
    with c2:
        st.metric("Premium", premium_count)
    with c3:
        st.metric("Free", free_count)

    st.write("---")
    st.subheader("All Institutes")
    st.caption("Flip an institute to Premium once they've paid you manually (UPI/bank transfer).")

    if institutes:
        for inst in institutes:
            limit_display = "Unlimited" if inst["plan"] == "Premium" else inst["student_limit"]
            with st.expander(f"{inst['name']} — {inst['owner_email']}  ({inst['plan']})", expanded=False):
                i_col1, i_col2, i_col3 = st.columns(3)
                with i_col1:
                    st.metric("Students", inst["student_count"])
                with i_col2:
                    st.write(f"**Plan:** {inst['plan']}")
                    st.write(f"**Limit:** {limit_display}")
                with i_col3:
                    st.write(f"**Created:** {inst.get('created_at', '—')}")

                new_plan = st.selectbox(
                    "Change Plan",
                    ["Free", "Premium"],
                    index=0 if inst["plan"] == "Free" else 1,
                    key=f"plan_select_{inst['id']}"
                )
                if st.button("💾 Save Plan", key=f"save_plan_{inst['id']}", use_container_width=True):
                    new_limit = FREE_STUDENT_LIMIT if new_plan == "Free" else 999999
                    st.toast("Updating plan…", icon="⏳")
                    with st.spinner("Updating plan…"):
                        set_institute_plan(conn, inst["id"], new_plan, new_limit, actor_email=st.session_state.get("user_email", ""))
                    st.success(f"{inst['name']} is now on the {new_plan} plan. They'll see it reflected next time they log in.")
                    st.rerun()
    else:
        st.info("No institutes have signed up yet.")

    st.write("---")
    st.subheader("🔓 Reset a User's Password")
    st.caption("For when an Admin, Teacher, or Parent gets locked out and can't reset it themselves.")

    with st.form("reset_user_pw_form", clear_on_submit=True):
        target_email = st.text_input("Their Email", placeholder="someone@example.com")
        target_new_pw = st.text_input("New Password for Them", type="password")

        if st.form_submit_button("Reset Password", use_container_width=True):
            clean_target = target_email.strip().lower()
            user_row = conn.execute(
                "SELECT email, role, is_super_admin, institute_id FROM users WHERE email=?", (clean_target,)
            ).fetchone()
            if not clean_target or not target_new_pw:
                st.warning("Email and new password are both required.")
            elif not user_row:
                st.error("No account found with that email.")
            elif not is_password_strong_enough(target_new_pw):
                st.warning(f"New password must be {MIN_PASSWORD_LENGTH}+ characters and include uppercase, lowercase, number and special character.")
            else:
                st.toast("Resetting password…", icon="⏳")
                with st.spinner("Resetting password…"):
                    update_password(conn, clean_target, target_new_pw, force_change=True)
                    log_audit_event(
                        conn, st.session_state.get("user_email", ""), "password_reset",
                        f"Reset password for {clean_target}", user_row["institute_id"],
                    )
                role_label = "Super Admin" if user_row["is_super_admin"] else user_row["role"]
                st.success(f"Password reset for {clean_target} ({role_label}). Share the new password with them directly.")

    st.write("---")
    st.subheader("🔑 Change Your Password")
    st.caption("Do this now if you're still on the default seeded password.")

    with st.form("super_admin_change_pw_form", clear_on_submit=True):
        current_pw = st.text_input("Current Password", type="password")
        new_pw = st.text_input("New Password", type="password")
        confirm_pw = st.text_input("Confirm New Password", type="password")

        if st.form_submit_button("Update Password", use_container_width=True):
            my_email = st.session_state.get("user_email", "")
            if not verify_password(current_pw, conn.execute(
                "SELECT password_hash FROM users WHERE email=?", (my_email,)
            ).fetchone()["password_hash"]):
                st.error("Current password is incorrect.")
            elif not is_password_strong_enough(new_pw):
                st.warning(f"New password must be {MIN_PASSWORD_LENGTH}+ characters and include uppercase, lowercase, number and special character.")
            elif new_pw != confirm_pw:
                st.warning("New password and confirmation don't match.")
            else:
                st.toast("Updating password…", icon="⏳")
                with st.spinner("Updating password…"):
                    update_password(conn, my_email, new_pw)
                st.success("Password updated. Use it next time you log in.")

    st.write("---")
    st.subheader("📜 Audit Log")
    st.caption("Recent platform-wide actions: plan changes, password resets, and student deletions.")
    audit_entries = list_audit_log(conn)
    if audit_entries:
        st.dataframe(
            [{"When": e["timestamp"], "Actor": e["actor_email"], "Action": e["action"], "Details": e["details"]} for e in audit_entries],
            use_container_width=True, hide_index=True
        )
    else:
        st.info("No audit events recorded yet.")

    logout_button("superadmin_logout_btn")

# ----------------------------------------------------
# 13. CORE APP ROUTER & SIDEBAR CONTROLLER
# ----------------------------------------------------
if not st.session_state.get("logged_in", False):
    show_login()
else:
    if st.session_state.get("must_change_password"):
        st.title("🔐 Password Change Required")
        st.info("Your account was created or reset with a temporary password. Please choose a new password before continuing.")
        with st.form("forced_password_change_form", clear_on_submit=True):
            new_pw = st.text_input("New Password", type="password", help=f"Use {MIN_PASSWORD_LENGTH}+ characters with uppercase, lowercase, number and special character.")
            confirm_pw = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Set New Password", use_container_width=True, type="primary"):
                if not is_password_strong_enough(new_pw):
                    st.error(f"Password must be {MIN_PASSWORD_LENGTH}+ characters and include uppercase, lowercase, number and special character.")
                elif new_pw != confirm_pw:
                    st.error("Passwords do not match.")
                else:
                    update_password(conn, st.session_state.get("user_email", ""), new_pw, force_change=False)
                    st.session_state.must_change_password = False
                    log_audit_event(conn, st.session_state.get("user_email", ""), "password_changed_after_reset", "Temporary password replaced", st.session_state.get("institute_id"))
                    st.success("Password updated successfully.")
                    st.rerun()
        st.stop()

    logged_role = st.session_state.get("logged_in_role", "Teacher")
    is_super = bool(st.session_state.get("is_super_admin"))

    if is_super:
        st.session_state.active_view = "SuperAdmin"
    elif logged_role != "Admin":
        st.session_state.active_view = logged_role
    elif st.session_state.get("active_view") not in ("Admin", "Teacher", "Parent"):
        st.session_state.active_view = "Admin"

    with st.sidebar:
        role_label = "Super Admin" if is_super else logged_role
        st.markdown(f"""
        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 14px; padding: 16px; margin-bottom: 20px; text-align: center;">
            <div style="display: inline-block; background: linear-gradient(135deg, #0284c7 0%, #06b6d4 100%); color: #ffffff; padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; margin-bottom: 8px;">
                {esc(role_label)} Mode
            </div>
            <p style="color: #cbd5e1; font-size: 13px; margin: 0; font-weight: 500;">{esc(st.session_state.get('user_email', ''))}</p>
        </div>
        """, unsafe_allow_html=True)

        if not is_super and st.session_state.get("institute_name"):
            st.caption(f"🏫 {st.session_state.get('institute_name')} • {st.session_state.get('institute_plan', 'Free')} Plan")

        if logged_role == "Admin" and not is_super:
            st.markdown("### 🛠️ Admin Navigation")
            pages = ["Admin", "Teacher", "Parent"]
            current_idx = pages.index(st.session_state.active_view)

            def sync_sidebar_desk():
                st.session_state.active_view = st.session_state.admin_sidebar_nav

            st.selectbox(
                "Go to Desk:",
                pages,
                index=current_idx,
                key="admin_sidebar_nav",
                on_change=sync_sidebar_desk
            )

        if st.button("🚪 Logout", key="sidebar_logout_btn", use_container_width=True):
            st.toast("Logging out…", icon="👋")
            st.session_state.clear()
            st.rerun()

    dashboard_routes = {
        "Admin": show_admin_dashboard,
        "Teacher": show_teacher_dashboard,
        "Parent": show_parent_dashboard,
        "SuperAdmin": show_super_admin_dashboard,
    }
    dashboard_routes.get(st.session_state.active_view, show_admin_dashboard)()
