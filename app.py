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
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "owner@platform.com")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "owner123")

# Set SHOW_DEMO_CREDENTIALS=false in production deploys to hide the demo
# login hints on the public login screen (they're handy for local dev only).
SHOW_DEMO_CREDENTIALS = os.environ.get("SHOW_DEMO_CREDENTIALS", "true").strip().lower() != "false"

# Minimum acceptable password length, enforced everywhere a password is set.
MIN_PASSWORD_LENGTH = 8

# ----------------------------------------------------
# 1B. TURSO (REMOTE, PERSISTENT DATABASE) CONFIGURATION
# ----------------------------------------------------
# If these two secrets are set (Streamlit Cloud -> Settings -> Secrets), the
# app stores everything in a real hosted Turso database instead of a local
# SQLite file that can be wiped whenever the container restarts. If they are
# NOT set, the app falls back to the old local-file behavior automatically —
# nothing breaks, it's just not durable across restarts.
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")
USE_TURSO = bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)

# ----------------------------------------------------
# 1C. TURSO COMPATIBILITY LAYER
# ----------------------------------------------------
# Every function in this file was written against the plain sqlite3 API
# (conn.execute(...).fetchone(), row["col"], dict(row), etc). Rather than
# rewrite all of that, these thin wrappers make a remote libSQL connection
# quack like a sqlite3 connection, so nothing below this section needs to
# know or care which backend it's actually talking to.

class _CompatRow:
    """Makes a plain tuple row support row['col'] and dict(row), like sqlite3.Row."""
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
    """Wraps a raw libsql connection so it behaves like sqlite3.Connection
    for every call pattern used elsewhere in this file."""
    def __init__(self, raw_conn):
        self._raw = raw_conn

    def execute(self, sql, params=()):
        cur = self._raw.execute(sql, params)
        return _CompatCursor(cur)

    def executemany(self, sql, seq_of_params):
        for params in seq_of_params:
            self._raw.execute(sql, params)

    def executescript(self, script: str):
        # libSQL's remote client doesn't support multi-statement scripts the
        # way sqlite3 does, so split on ';' and run each statement alone.
        # Safe here because our schema statements never contain a literal
        # semicolon inside a string value.
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self._raw.execute(statement)

    def commit(self):
        try:
            self._raw.commit()
        except Exception as e:
            # Some libsql modes auto-commit and don't support commit() at all —
            # that case is fine to ignore. But a genuine write failure here
            # would otherwise vanish silently, so at least surface it.
            st.warning(f"Database commit warning: {e}")

# ----------------------------------------------------
# 2. PASSWORD HASHING
# ----------------------------------------------------
# PBKDF2-HMAC-SHA256 with a per-user random salt (stdlib only, no extra deps).
# Stored as "<salt_hex>$<hash_hex>".

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
    return bool(password) and len(password) >= MIN_PASSWORD_LENGTH

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def is_valid_email(email: str) -> bool:
    """Deliberately simple check (not a full RFC 5322 validator) — just
    enough to catch obvious typos and junk input at account-creation time."""
    return bool(email) and bool(_EMAIL_PATTERN.match(email))

# ----------------------------------------------------
# 3. DATABASE LAYER (SQLite — persists on disk, shared across everyone
#    who connects to this app, unlike the old per-browser session_state)
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
    """Adds a column to an existing table if it isn't there yet (simple migration helper).
    Wrapped in try/except because PRAGMA support can vary on a remote backend —
    if this can't be checked, we skip rather than crash the whole app."""
    try:
        existing_cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in existing_cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            conn.commit()
    except Exception as e:
        st.warning(f"Could not verify/add column '{column}' on '{table}': {e}")

def _create_schema(conn):
    """Creates every table if it doesn't already exist. Safe to call repeatedly."""
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
    """)
    conn.commit()

def _ensure_multitenancy_columns(conn):
    """Adds the institute_id / is_super_admin columns to every table. Safe to
    call repeatedly (no-op once columns exist). Must run on the TARGET
    database before any row copy that includes these columns — otherwise
    the copy fails because the destination table doesn't have them yet."""
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

def _migrate_local_file_into_turso_if_needed(turso_conn):
    """One-time safety net: if this is the first time we're connecting to
    Turso and a real local academy.db file exists on this machine (from
    before the Turso switch), copy every row across so nothing is lost.
    Does nothing if Turso already has institutes (already migrated), or if
    there's no local file to copy from."""
    if not os.path.exists(DB_PATH):
        return

    try:
        existing = turso_conn.execute("SELECT COUNT(*) FROM institutes").fetchone()
        if existing and existing[0] > 0:
            return  # Turso already has data — never overwrite it
    except Exception:
        pass  # institutes table may not exist yet on a brand new Turso db; continue

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
    """Works the same whether conn is a plain sqlite3 connection or the Turso
    wrapper — avoids relying on cursor.lastrowid, which the Turso wrapper's
    cursor doesn't provide."""
    row = conn.execute("SELECT last_insert_rowid()").fetchone()
    return row[0] if row else None

def log_audit_event(conn, actor_email: str, action: str, details: str = "", institute_id: int | None = None):
    """Records a Super-Admin-level action (plan change, password reset, etc.)
    so there's a record of who did what and when if it's ever disputed.
    Best-effort: an audit-log failure should never block the underlying
    action, so this swallows its own errors rather than raising."""
    try:
        conn.execute(
            "INSERT INTO audit_log(timestamp, actor_email, action, details, institute_id) VALUES (?,?,?,?,?)",
            (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), actor_email, action, details, institute_id),
        )
        conn.commit()
    except Exception as e:
        st.warning(f"Could not record audit log entry: {e}")

def list_audit_log(conn, institute_id: int | None = None, limit: int = 200):
    """institute_id=None returns the full platform-wide log (Super Admin view).
    Pass an institute_id to scope it to just that institute's own actions."""
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

    # ---- Safety net: if this is an existing single-academy database (rows
    # exist with institute_id still NULL), fold ALL of that real data into
    # one grandfathered "legacy" institute instead of treating it as demo
    # data or leaving it orphaned/invisible. This runs at most once per DB. ----
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

    # ---- Brand-new install (no institutes at all yet): seed one demo
    # institute with the original demo accounts/students, exactly like before. ----
    if conn.execute("SELECT COUNT(*) FROM institutes").fetchone()[0] == 0:
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

    # ---- Ensure a Super Admin (platform owner) account always exists.
    # Not tied to any institute — this is you, managing the whole platform. ----
    if conn.execute("SELECT COUNT(*) FROM users WHERE is_super_admin=1").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users(email, password_hash, role, institute_id, is_super_admin) VALUES (?,?,?,?,1)",
            (SUPER_ADMIN_EMAIL, hash_password(SUPER_ADMIN_PASSWORD), "Admin", None),
        )
        conn.commit()

# ---- Auth ----

# After this many failed attempts for one email, block further tries for
# LOGIN_LOCKOUT_MINUTES. Keyed by email (not IP, which Streamlit doesn't
# expose) so it stops repeated guessing against one account, not a general
# rate limit on the login page itself.
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15

def _ensure_login_attempts_table(conn):
    """Self-healing: (re)creates login_attempts on the fly if it's ever
    missing on the active backend (seen in practice on Turso — a schema
    statement can occasionally not land on first connect). Safe to call
    on every login-lockout check; it's a no-op once the table exists."""
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS login_attempts (
            email TEXT PRIMARY KEY, failed_count INTEGER DEFAULT 0, locked_until TEXT
        )""")
        conn.commit()
    except Exception:
        pass

def check_login_lock(conn, email: str):
    """Returns (is_locked: bool, seconds_remaining: int). This is a
    nice-to-have anti-brute-force check, not core to login working at all —
    so any problem reaching login_attempts (missing table, a flaky remote
    connection) must never crash the login page. On any error, this fails
    OPEN (treats the account as not locked) rather than blocking everyone
    from logging in."""
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
    """Best-effort: if this fails (e.g. the table momentarily isn't
    reachable), the failed attempt just isn't counted — it must never
    prevent the 'Invalid email or password' message from showing."""
    try:
        _ensure_login_attempts_table(conn)
        row = conn.execute("SELECT failed_count FROM login_attempts WHERE email=?", (email,)).fetchone()
        failed_count = (row["failed_count"] if row else 0) + 1
        locked_until = None
        if failed_count >= LOGIN_MAX_ATTEMPTS:
            locked_until = (datetime.datetime.now() + datetime.timedelta(minutes=LOGIN_LOCKOUT_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
            failed_count = 0  # reset the counter once locked, so the next window starts fresh
        conn.execute(
            """INSERT INTO login_attempts(email, failed_count, locked_until) VALUES (?,?,?)
               ON CONFLICT(email) DO UPDATE SET failed_count=excluded.failed_count, locked_until=excluded.locked_until""",
            (email, failed_count, locked_until),
        )
        conn.commit()
    except Exception:
        pass

def clear_failed_login(conn, email: str):
    """Best-effort cleanup after a successful login — a failure here must
    never block the person from actually reaching their dashboard."""
    try:
        _ensure_login_attempts_table(conn)
        conn.execute("DELETE FROM login_attempts WHERE email=?", (email,))
        conn.commit()
    except Exception:
        pass

def update_password(conn, email: str, new_password: str):
    conn.execute(
        "UPDATE users SET password_hash=? WHERE email=?", (hash_password(new_password), email)
    )
    conn.commit()

def authenticate(conn, email: str, password: str):
    row = conn.execute(
        "SELECT password_hash, role, institute_id, is_super_admin FROM users WHERE email=?", (email,)
    ).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return {
            "role": row["role"],
            "institute_id": row["institute_id"],
            "is_super_admin": bool(row["is_super_admin"]),
        }
    return None

def create_user_account(conn, institute_id: int, email: str, password: str, role: str):
    conn.execute(
        "INSERT INTO users(email, password_hash, role, institute_id, is_super_admin) VALUES (?,?,?,?,0)",
        (email, hash_password(password), role, institute_id),
    )
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
    """Raises sqlite3.IntegrityError (or the Turso backend's equivalent) if
    owner_email is already registered — callers must catch broadly, since the
    remote Turso client does not necessarily raise sqlite3.IntegrityError."""
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
        # Someone else's signup won the race between our check and this
        # insert — roll back the orphaned institute row we just created.
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
    result = []
    for r in rows:
        d = dict(r)
        d["student_count"] = conn.execute(
            "SELECT COUNT(*) FROM students WHERE institute_id=? AND (is_deleted IS NULL OR is_deleted=0)", (d["id"],)
        ).fetchone()[0]
        result.append(d)
    return result

def set_institute_plan(conn, institute_id: int, plan: str, student_limit: int, actor_email: str = ""):
    conn.execute(
        "UPDATE institutes SET plan=?, student_limit=? WHERE id=?", (plan, student_limit, institute_id)
    )
    conn.commit()
    log_audit_event(conn, actor_email, "plan_change", f"Set plan to {plan} (limit {student_limit})", institute_id)

def count_students(conn, institute_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM students WHERE institute_id=? AND (is_deleted IS NULL OR is_deleted=0)", (institute_id,)
    ).fetchone()[0]

def can_add_student(conn, institute_id: int):
    """Returns (allowed: bool, message: str|None). Premium institutes have no cap."""
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
    """Every institute's student IDs are scoped and separated by a dash
    (STU<institute_id>-<sequence>) so the numeric suffix used for 'what's
    the next ID' can never be confused with the institute_id itself."""
    return f"STU{institute_id}-"

def add_student(conn, institute_id: int, name, grade, subject, fee, parent_email=None):
    # Base the next ID on the highest sequence number ever used WITHIN THIS
    # INSTITUTE, not the current row count (COUNT(*) breaks after a delete)
    # and not a global platform-wide MAX (which would leak one institute's
    # growth into another's numbering and force a full-table scan as the
    # platform grows). The STU<id>- prefix keeps the institute_id and the
    # sequence number unambiguous so re-reading "the highest number used"
    # never re-absorbs the institute_id into the count.
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
    """Inserts many students in one pass for CSV import. Each row needs at
    least a 'name'; grade/subject/fee/parent_email are optional and default
    the same way the single-add form does. Computes the starting ID once and
    increments locally instead of re-querying MAX() per row, then commits
    once at the end — much cheaper than calling add_student() in a loop,
    especially over the network on Turso. Returns the number of rows inserted."""
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
    """Soft-deletes the student: hides them from every roster/attendance/fee
    view, but keeps the underlying row (and their attendance + payment
    history) in the database rather than permanently erasing it. This means
    an accidental delete — or a parent later disputing a past fee — doesn't
    destroy the record it would take to sort things out."""
    student = get_student(conn, institute_id, student_id)
    conn.execute("UPDATE students SET is_deleted=1 WHERE id=? AND institute_id=?", (student_id, institute_id))
    conn.commit()
    student_name = student["name"] if student else student_id
    log_audit_event(conn, actor_email, "student_deleted", f"Removed {student_name} ({student_id})", institute_id)

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
    """entries: [{student_id, status, class_name}, ...]"""
    for e in entries:
        conn.execute(
            """INSERT INTO attendance(date, student_id, status, class_name, institute_id) VALUES (?,?,?,?,?)
               ON CONFLICT(date, student_id) DO UPDATE SET status=excluded.status, class_name=excluded.class_name""",
            (date_str, e["student_id"], e["status"], e["class_name"], institute_id),
        )
    conn.commit()

def attendance_for_date(conn, institute_id: int, date_str: str) -> dict:
    """Returns {student_id: status} for whatever was already recorded on this
    date, so re-opening a past date shows what's actually saved instead of
    always defaulting back to all-present."""
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

def get_payment_status(conn, institute_id: int, student_id: str) -> str:
    row = conn.execute(
        "SELECT status FROM payment_status WHERE student_id=? AND institute_id=?", (student_id, institute_id)
    ).fetchone()
    return row["status"] if row else "Unpaid"

def _next_tx_id(conn, institute_id: int) -> str:
    # Same "highest number used, not row count" logic as student IDs — scoped
    # per institute (for the same "avoid leaking growth across institutes /
    # avoid a full-table scan" reasons) and separated with a dash so the
    # institute_id and the sequence number can never be confused when read
    # back via SUBSTR — the same bug class the student-ID scheme had to avoid.
    prefix = f"TXN{institute_id}-"
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(tx_id, ?) AS INTEGER)) FROM financial_records WHERE tx_id LIKE ? AND institute_id=?",
        (len(prefix) + 1, prefix + "%", institute_id),
    ).fetchone()
    highest = row[0] if row and row[0] is not None else 900
    return f"{prefix}{highest + 1}"

def set_payment_status(conn, institute_id: int, student_id: str, status: str):
    previous_status = get_payment_status(conn, institute_id, student_id)

    conn.execute(
        """INSERT INTO payment_status(student_id, status, institute_id) VALUES (?,?,?)
           ON CONFLICT(student_id) DO UPDATE SET status=excluded.status""",
        (student_id, status, institute_id),
    )

    # Auto-log a transaction the moment a student flips Unpaid -> Paid, so the
    # ledger and "Fee Status: Paid" never disagree. Re-saving an already-Paid
    # status (no change) does NOT create a duplicate entry.
    if status == "Paid" and previous_status != "Paid":
        student = get_student(conn, institute_id, student_id)
        if student:
            conn.execute(
                "INSERT INTO financial_records(tx_id, student, student_id, date, amount, type, method, institute_id) VALUES (?,?,?,?,?,?,?,?)",
                (
                    _next_tx_id(conn, institute_id),
                    student["name"],
                    student_id,
                    datetime.date.today().strftime("%Y-%m-%d"),
                    student.get("fee", 0),
                    "Tuition Fee",
                    "Marked Paid (Fee Desk)",
                    institute_id,
                ),
            )

    conn.commit()

def list_financial_records(conn, institute_id: int, student_id: str | None = None, student_name: str | None = None):
    if student_id or student_name:
        # Match by student_id when present (new records); fall back to matching
        # by name for older rows recorded before student_id was tracked.
        rows = conn.execute(
            """SELECT * FROM financial_records
               WHERE institute_id=? AND (
                     (student_id IS NOT NULL AND student_id=?)
                  OR (student_id IS NULL AND student=?)
               )
               ORDER BY date DESC""",
            (institute_id, student_id, student_name),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM financial_records WHERE institute_id=? ORDER BY date DESC", (institute_id,)
        ).fetchall()
    return [dict(r) for r in rows]

# ---- Notices ----

def list_notices(conn, institute_id: int, grade: str | None = None):
    """If grade is given, returns notices aimed at that grade PLUS any
    'All Classes' notices (target_grade IS NULL/empty). If grade is None,
    returns everything (used on the Teacher's own Notice Board view)."""
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
# 4. SESSION STATE (login/navigation only — everything durable lives in SQLite now)
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
# 5. STATIC ASSETS (LOGO RESOLUTION)
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
    """Case-insensitive substring match across name, ID, grade, subject, and
    parent email — good enough for finding one kid in a roster of hundreds
    without needing a real search index."""
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
    """Turns a list of dicts (as returned by list_students / list_financial_records)
    into CSV bytes for st.download_button. Uses the stdlib csv module rather
    than pandas so it doesn't add a dependency just for this."""
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")

def esc(value) -> str:
    """Escapes a value for safe interpolation into an unsafe_allow_html
    string. Everything that ultimately comes from user input (student names,
    notice titles/bodies, institute names, emails, grades, subjects, etc.)
    must be passed through this before being dropped into an HTML template —
    otherwise a value like '<img src=x onerror=alert(1)>' typed as a student
    name or notice body would execute for whoever views that card."""
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
    /* Keep the built-in "running" indicator visible and easy to notice —
       without this, hiding the toolbar above can make it feel like nothing
       happened when you tap a button, especially with Turso adding network
       latency to every action. */
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
    /* Toast notifications (st.toast) need their own explicit background AND
       text color set together — the global "p, span, label" rule above only
       forces light text, and without a matching dark background here that
       text can end up light-on-light and effectively invisible. */
    div[data-testid="stToast"] {{
        background-color: #1e293b !important;
        border: 1.5px solid #38bdf8 !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5) !important;
    }}
    div[data-testid="stToast"] * {{
        color: #ffffff !important;
        opacity: 1 !important;
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
    """Shows Free-plan usage + manual-upgrade instructions on the Admin console."""
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

def refresh_institute_session(institute_id: int):
    """Re-reads plan/limit from the DB into session_state on every dashboard
    load, so a Super Admin flipping someone to Premium takes effect on their
    very next click instead of requiring them to log out and back in."""
    if not institute_id:
        return
    inst = get_institute(conn, institute_id)
    if inst:
        st.session_state.institute_name = inst["name"]
        st.session_state.institute_plan = inst["plan"]
        st.session_state.student_limit = inst["student_limit"]

def render_csv_import_widget(institute_id: int, key_prefix: str):
    """Shared bulk-import widget used from both the Teacher Desk and Admin
    Console. Expects a CSV with a 'name' column (required) and optional
    'grade', 'subject', 'fee', 'parent_email' columns — same fields as the
    single-student form, just many rows at once. Shows a preview and the
    Free-plan capacity check before anything is actually inserted."""
    st.caption("CSV columns: **name** (required), grade, subject, fee, parent_email (all optional).")
    uploaded = st.file_uploader("Choose a CSV file", type=["csv"], key=f"{key_prefix}_csv_uploader")
    if not uploaded:
        return

    try:
        text = uploaded.getvalue().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        # Normalize header names (case/whitespace-insensitive) so "Name" or
        # " Fee " in someone's spreadsheet export still matches.
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
# 8. VIEW: LOGIN / SIGNUP
# ----------------------------------------------------

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

    tab_login, tab_signup = st.tabs(["🔐 Log In", "🏫 Create Institute Account"])

    with tab_login:
        st.markdown("Welcome! Please log in to securely access your portal.")

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
                        st.rerun()
                    else:
                        record_failed_login(conn, clean_email)
                        st.error("Invalid email or password. Please verify credentials.")

        if SHOW_DEMO_CREDENTIALS:
            with st.expander("Demo credentials", expanded=False):
                st.caption(
                    "Admin: admin@academy.com / admin123  \n"
                    "Teacher: teacher@academy.com / teacher123  \n"
                    "Parent (Aarav's family): parent1@academy.com / parent123  \n"
                    "Parent (Rohan's family): parent2@academy.com / parent123"
                )

    with tab_signup:
        st.markdown("### Start your own tuition academy on this platform")
        st.caption(f"Free plan includes up to {FREE_STUDENT_LIMIT} students, no credit card needed. Upgrade any time by contacting the platform owner.")

        with st.form("signup_form", clear_on_submit=True):
            s_institute = st.text_input("Institute / Academy Name", placeholder="e.g., Bright Minds Tuition")
            s_email = st.text_input("Your Email (this becomes your Admin login)", placeholder="owner@myacademy.com")
            s_pass = st.text_input("Create Password", type="password", help=f"At least {MIN_PASSWORD_LENGTH} characters.")

            if st.form_submit_button("Create My Academy Account", use_container_width=True):
                clean_s_email = s_email.strip().lower()
                if s_institute.strip() and clean_s_email and s_pass.strip():
                    if not is_valid_email(clean_s_email):
                        st.warning("Please enter a valid email address.")
                    elif not is_password_strong_enough(s_pass):
                        st.warning(f"Password should be at least {MIN_PASSWORD_LENGTH} characters.")
                    else:
                        try:
                            st.toast("Creating your academy…", icon="⏳")
                            with st.spinner("Creating your academy…"):
                                create_institute_and_admin(conn, s_institute.strip(), clean_s_email, s_pass)
                            st.success(
                                f"Account created! '{s_institute.strip()}' is live on the Free plan "
                                f"(up to {FREE_STUDENT_LIMIT} students). Please log in above."
                            )
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

    # Fetched ONCE here and reused across all four tabs below — Streamlit
    # renders every tab's code on every single rerun (not just the visible
    # one), so calling list_students() separately per tab meant every click
    # anywhere on this page triggered 4 separate Turso round-trips for the
    # same roster before your click was even acknowledged.
    all_students = list_students(conn, institute_id)

    # ---------------- TAB 1: STUDENT MANAGEMENT ----------------
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

    # ---------------- TAB 2: ATTENDANCE DESK ----------------
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
                st.session_state.att_batch_stamp = st.session_state.get("att_batch_stamp", 0) + 1
        with col_b:
            if st.button("⭕ Clear All", use_container_width=True, key="clear_all_btn"):
                st.toast("Clearing all…", icon="⭕")
                st.session_state.att_mark_default = False
                st.session_state.att_batch_stamp = st.session_state.get("att_batch_stamp", 0) + 1

        if "att_mark_default" not in st.session_state:
            st.session_state.att_mark_default = True
        batch_stamp = st.session_state.get("att_batch_stamp", 0)

        attendance_status = {}
        st.write("---")
        for s in active_roster:
            s_id = s["id"]
            # Prefill from whatever's already saved for this date; fall back
            # to the Mark All/Clear All default for students with no record
            # yet on this date. Including batch_stamp and the date in the key
            # forces a brand-new checkbox widget whenever the date changes or
            # Mark All/Clear All is clicked — otherwise Streamlit remembers
            # the checkbox's own prior state and ignores the value= we pass in.
            default_checked = existing_for_date.get(s_id, None)
            default_checked = (default_checked == "Present") if default_checked is not None else st.session_state.att_mark_default
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

    # ---------------- TAB 3: FINANCIAL DESK ----------------
    with tab_financial:
        st.subheader("Tuition Fee Management")

        if all_students:
            total_expected = sum(s.get("fee", 0) for s in all_students)
            total_collected = sum(
                s.get("fee", 0) for s in all_students if get_payment_status(conn, institute_id, s["id"]) == "Paid"
            )
            total_due = total_expected - total_collected

            col_rev1, col_rev2 = st.columns(2)
            with col_rev1:
                st.metric("Total Collected", f"₹{total_collected:,}")
            with col_rev2:
                st.metric("Pending / Due", f"₹{total_due:,}")

            st.write("---")
            st.markdown("### Update Student Payment Status")

            with st.form("fee_status_form"):
                new_statuses = {}
                for student in all_students:
                    s_id = student["id"]
                    current_val = get_payment_status(conn, institute_id, s_id)

                    f_col1, f_col2 = st.columns([3, 2])
                    with f_col1:
                        badge = "🟢 Paid" if current_val == "Paid" else "🔴 Unpaid"
                        st.markdown(
                            f"**{esc(student['name'])}** ({esc(student['grade'])})<br>"
                            f"<span style='color:#94a3b8;'>Fee: ₹{student['fee']:,} • Status: {badge}</span>",
                            unsafe_allow_html=True
                        )
                    with f_col2:
                        new_statuses[s_id] = st.selectbox(
                            "Status",
                            options=["Unpaid", "Paid"],
                            index=1 if current_val == "Paid" else 0,
                            key=f"select_fee_{s_id}",
                            label_visibility="collapsed"
                        )

                st.write("")
                submit_fee_update = st.form_submit_button("💾 Save Payment Statuses", use_container_width=True, type="primary")

                if submit_fee_update:
                    st.toast("Saving payment statuses…", icon="⏳")
                    with st.spinner("Saving payment statuses…"):
                        for sid, stat in new_statuses.items():
                            set_payment_status(conn, institute_id, sid, stat)
                    st.success("Payment records updated!")
                    st.rerun()

            st.write("---")

            unpaid_students = [s for s in all_students if get_payment_status(conn, institute_id, s["id"]) == "Unpaid"]
            if unpaid_students:
                st.markdown(f"""
                <div style="background-color: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 10px; padding: 12px 16px;">
                    <strong style="color: #ef4444; font-size: 15px;">⚠️ Pending Fee Reminders:</strong>
                    <p style="color: #fecaca; font-size: 13px; margin: 4px 0 0 0;">
                        {len(unpaid_students)} student(s) have unpaid balances totaling <strong>₹{total_due:,}</strong>.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.success("🎉 All students have paid their dues for this cycle!")
        else:
            st.info("No students enrolled yet to track fees.")

        st.write("---")
        st.markdown("### Raw Transaction Ledger")
        records = list_financial_records(conn, institute_id)
        if records:
            st.dataframe(records, use_container_width=True, hide_index=True)
        else:
            st.info("No transactions recorded yet.")

    # ---------------- TAB 4: NOTICE BOARD ----------------
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
    total_collected = sum(s.get("fee", 0) for s in all_students if get_payment_status(conn, institute_id, s["id"]) == "Paid")

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
            p_pass = st.text_input("Temporary Password", type="password", help=f"At least {MIN_PASSWORD_LENGTH} characters.")
            p_children = st.multiselect(
                "Link to Student(s)",
                options=[s["name"] for s in all_students],
                help="You can also link/relink students later from the Teacher Desk."
            )
            if st.form_submit_button("Create Account", use_container_width=True):
                clean_email = p_email.strip().lower()
                if clean_email and p_pass.strip():
                    if not is_valid_email(clean_email):
                        st.warning("Please enter a valid email address.")
                    elif not is_password_strong_enough(p_pass):
                        st.warning(f"Password should be at least {MIN_PASSWORD_LENGTH} characters.")
                    else:
                        try:
                            st.toast("Creating parent account…", icon="⏳")
                            with st.spinner("Creating parent account…"):
                                create_parent_account(conn, institute_id, clean_email, p_pass)
                                for name in p_children:
                                    match = next((s for s in all_students if s["name"] == name), None)
                                    if match:
                                        update_student_parent_email(conn, institute_id, match["id"], clean_email)
                            st.success(f"Parent account created for {clean_email}.")
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
            t_pass = st.text_input("Temporary Password", type="password", key="new_teacher_pass", help=f"At least {MIN_PASSWORD_LENGTH} characters.")
            if st.form_submit_button("Create Account", use_container_width=True):
                clean_t_email = t_email.strip().lower()
                if clean_t_email and t_pass.strip():
                    if not is_valid_email(clean_t_email):
                        st.warning("Please enter a valid email address.")
                    elif not is_password_strong_enough(t_pass):
                        st.warning(f"Password should be at least {MIN_PASSWORD_LENGTH} characters.")
                    else:
                        try:
                            st.toast("Creating teacher account…", icon="⏳")
                            with st.spinner("Creating teacher account…"):
                                create_teacher_account(conn, institute_id, clean_t_email, t_pass)
                            st.success(f"Teacher account created for {clean_t_email}.")
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
# 12. VIEW: SUPER ADMIN DASHBOARD (platform owner — you)
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
                st.warning(f"New password should be at least {MIN_PASSWORD_LENGTH} characters.")
            else:
                st.toast("Resetting password…", icon="⏳")
                with st.spinner("Resetting password…"):
                    update_password(conn, clean_target, target_new_pw)
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
                st.warning(f"New password should be at least {MIN_PASSWORD_LENGTH} characters.")
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
