import streamlit as st
import sqlite3
import hashlib
import secrets
import datetime
import os
import base64

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

# ----------------------------------------------------
# 3. DATABASE LAYER (SQLite — persists on disk, shared across everyone
#    who connects to this app, unlike the old per-browser session_state)
# ----------------------------------------------------

@st.cache_resource
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn

def init_db(conn: sqlite3.Connection):
    conn.executescript("""
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
    """)
    conn.commit()

    # Seed one built-in Admin and one built-in Teacher account if none exist yet.
    if conn.execute("SELECT COUNT(*) FROM users WHERE role='Admin'").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users(email, password_hash, role) VALUES (?,?,?)",
            ("admin@academy.com", hash_password("admin123"), "Admin"),
        )
    if conn.execute("SELECT COUNT(*) FROM users WHERE role='Teacher'").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users(email, password_hash, role) VALUES (?,?,?)",
            ("teacher@academy.com", hash_password("teacher123"), "Teacher"),
        )
    conn.commit()

    # First-run demo data only — two students, each linked to their own parent
    # account, so the parent-portal access control is visible out of the box.
    if conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
        demo_students = [
            ("STU101", "Aarav Sharma", "Class 10", "Science", 1500, "parent1@academy.com"),
            ("STU102", "Rohan Das", "Class 10", "Science", 1500, "parent2@academy.com"),
        ]
        conn.executemany(
            "INSERT INTO students(id, name, grade, subject, fee, parent_email) VALUES (?,?,?,?,?,?)",
            demo_students,
        )
        conn.executemany(
            "INSERT INTO users(email, password_hash, role) VALUES (?,?,?)",
            [
                ("parent1@academy.com", hash_password("parent123"), "Parent"),
                ("parent2@academy.com", hash_password("parent123"), "Parent"),
            ],
        )
        conn.executemany(
            "INSERT INTO financial_records(tx_id, student, date, amount, type, method) VALUES (?,?,?,?,?,?)",
            [
                ("TXN901", "Aarav Sharma", "2026-09-01", 1500, "Tuition Fee", "UPI / Online"),
                ("TXN902", "Rohan Das", "2026-09-03", 1500, "Tuition Fee", "Cash"),
            ],
        )
        conn.execute(
            "INSERT INTO payment_status(student_id, status) VALUES (?,?)",
            ("STU101", "Paid"),
        )
        conn.commit()

# ---- Auth ----

def authenticate(conn, email: str, password: str):
    row = conn.execute("SELECT password_hash, role FROM users WHERE email=?", (email,)).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return row["role"]
    return None

def create_parent_account(conn, email: str, password: str):
    conn.execute(
        "INSERT INTO users(email, password_hash, role) VALUES (?,?,?)",
        (email, hash_password(password), "Parent"),
    )
    conn.commit()

def list_parent_accounts(conn):
    return [dict(r) for r in conn.execute("SELECT email FROM users WHERE role='Parent' ORDER BY email").fetchall()]

def delete_parent_account(conn, email: str):
    conn.execute("DELETE FROM users WHERE email=? AND role='Parent'", (email,))
    conn.execute("UPDATE students SET parent_email=NULL WHERE parent_email=?", (email,))
    conn.commit()

# ---- Students ----

def list_students(conn, parent_email: str | None = None):
    if parent_email:
        rows = conn.execute(
            "SELECT * FROM students WHERE parent_email=? ORDER BY name", (parent_email,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM students ORDER BY name").fetchall()
    return [dict(r) for r in rows]

def add_student(conn, name, grade, subject, fee, parent_email=None):
    count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    new_id = f"STU{101 + count}"
    conn.execute(
        "INSERT INTO students(id, name, grade, subject, fee, parent_email) VALUES (?,?,?,?,?,?)",
        (new_id, name, grade, subject, fee, parent_email or None),
    )
    conn.commit()
    return new_id

def delete_student(conn, student_id: str):
    conn.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.execute("DELETE FROM payment_status WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM attendance WHERE student_id=?", (student_id,))
    conn.commit()

def update_student_parent_email(conn, student_id: str, parent_email: str | None):
    conn.execute("UPDATE students SET parent_email=? WHERE id=?", (parent_email or None, student_id))
    conn.commit()

def update_student(conn, student_id: str, name: str, grade: str, subject: str, fee: int):
    conn.execute(
        "UPDATE students SET name=?, grade=?, subject=?, fee=? WHERE id=?",
        (name, grade, subject, fee, student_id),
    )
    conn.commit()

def get_student(conn, student_id: str):
    row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    return dict(row) if row else None

# ---- Classrooms ----

def list_classrooms(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM classrooms ORDER BY id").fetchall()]

def add_classroom(conn, title, subject, section, fee):
    conn.execute(
        "INSERT INTO classrooms(title, subject, section, fee) VALUES (?,?,?,?)",
        (title, subject, section, fee),
    )
    conn.commit()

# ---- Attendance ----

def save_attendance(conn, date_str: str, entries: list[dict]):
    """entries: [{student_id, status, class_name}, ...]"""
    for e in entries:
        conn.execute(
            """INSERT INTO attendance(date, student_id, status, class_name) VALUES (?,?,?,?)
               ON CONFLICT(date, student_id) DO UPDATE SET status=excluded.status, class_name=excluded.class_name""",
            (date_str, e["student_id"], e["status"], e["class_name"]),
        )
    conn.commit()

def attendance_history(conn, student_id: str):
    rows = conn.execute(
        "SELECT date, status FROM attendance WHERE student_id=? ORDER BY date DESC", (student_id,)
    ).fetchall()
    return [(r["date"], r["status"]) for r in rows]

# ---- Fees ----

def get_payment_status(conn, student_id: str) -> str:
    row = conn.execute("SELECT status FROM payment_status WHERE student_id=?", (student_id,)).fetchone()
    return row["status"] if row else "Unpaid"

def set_payment_status(conn, student_id: str, status: str):
    conn.execute(
        """INSERT INTO payment_status(student_id, status) VALUES (?,?)
           ON CONFLICT(student_id) DO UPDATE SET status=excluded.status""",
        (student_id, status),
    )
    conn.commit()

def list_financial_records(conn, student_name: str | None = None):
    if student_name:
        rows = conn.execute(
            "SELECT * FROM financial_records WHERE student=? ORDER BY date DESC", (student_name,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM financial_records ORDER BY date DESC").fetchall()
    return [dict(r) for r in rows]

# ---- Notices ----

def list_notices(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM notices ORDER BY id DESC").fetchall()]

def add_notice(conn, title, body, priority, date_str):
    conn.execute(
        "INSERT INTO notices(title, body, priority, date) VALUES (?,?,?,?)",
        (title, body, priority, date_str),
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
            <h2 style="margin: 0; font-size: 20px; font-weight: 700; color: #ffffff;">{title}</h2>
            <p style="margin: 0; color: #38bdf8; font-size: 13px; font-weight: 500;">{subtitle}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_admin_quick_nav(current: str):
    if st.session_state.get("logged_in_role") != "Admin":
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
                go_to(target)
                st.rerun()
    st.write("---")

def logout_button(key: str):
    st.write("---")
    if st.button("🚪 Log Out", use_container_width=True, key=key):
        st.session_state.clear()
        st.rerun()

# ----------------------------------------------------
# 8. VIEW: LOGIN
# ----------------------------------------------------

def show_login():
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
        {logo_img_tag()}
        <div>
            <h2 style="margin: 0; font-size: 22px; color: #ffffff;">MathScience Academy</h2>
            <p style="margin: 0; color: #94a3b8; font-size: 13px;">Secure Portal Authentication</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("Welcome! Please log in to securely access your portal.")

    with st.form("login_form"):
        email_input = st.text_input("Registered Email Address", placeholder="name@academy.com")
        password_input = st.text_input("Account Password", type="password", placeholder="••••••••")
        submit_btn = st.form_submit_button("Access Dashboard", use_container_width=True)

        if submit_btn:
            clean_email = email_input.strip().lower()
            role = authenticate(conn, clean_email, password_input)
            if role:
                st.session_state.logged_in = True
                st.session_state.logged_in_role = role
                st.session_state.user_email = clean_email
                st.session_state.active_view = role
                st.rerun()
            else:
                st.error("Invalid email or password. Please verify credentials.")

    with st.expander("Demo credentials", expanded=False):
        st.caption(
            "Admin: admin@academy.com / admin123  \n"
            "Teacher: teacher@academy.com / teacher123  \n"
            "Parent (Aarav's family): parent1@academy.com / parent123  \n"
            "Parent (Rohan's family): parent2@academy.com / parent123"
        )

# ----------------------------------------------------
# 9. VIEW: TEACHER DASHBOARD
# ----------------------------------------------------

def show_teacher_dashboard():
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
                    add_classroom(conn, r_title.strip(), r_subj.strip(), r_batch.strip() or "Regular", r_fee)
                    st.success("Classroom created successfully!")
                    st.rerun()
                else:
                    st.warning("Please provide both a Class level and a Subject.")

    classrooms = list_classrooms(conn)
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
                    <span style="color: #ffffff; font-weight: 700; font-size: 16px; margin-left: 6px;">{active_room['title']}</span>
                </div>
                <div style="color: #cbd5e1; font-size: 14px;">
                    Subject: <strong style="color: #38bdf8;">{active_room['subject']}</strong>
                    <span style="color: #64748b; margin: 0 6px;">•</span>
                    Batch: <strong style="color: #f1f5f9;">{active_room['section']}</strong>
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

    # ---------------- TAB 1: STUDENT MANAGEMENT ----------------
    with tab_students:
        st.subheader("Academy Student Roster")
        all_students = list_students(conn)

        if all_students:
            st.dataframe(all_students, use_container_width=True, hide_index=True)
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
                        add_student(
                            conn,
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
                    update_student_parent_email(conn, chosen["id"], new_parent_email.strip().lower() or None)
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
                    delete_student(conn, chosen_id)
                    st.success("Student removed.")
                    st.rerun()
            else:
                st.write("No students available to remove.")

    # ---------------- TAB 2: ATTENDANCE DESK ----------------
    with tab_attendance:
        st.subheader("Daily Attendance Register")
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        st.caption(f"Logging Record for: **{today_str}**")

        all_students = list_students(conn)
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
            mark_all = st.button("✅ Mark All Present", use_container_width=True, key="mark_all_btn")
        with col_b:
            clear_all = st.button("⭕ Clear All", use_container_width=True, key="clear_all_btn")

        attendance_status = {}
        st.write("---")
        for s in active_roster:
            s_id = s["id"]
            default_val = False if clear_all else True
            attendance_status[s_id] = st.checkbox(
                f"{s['name']} — {s['grade']} ({s.get('subject', 'General')})",
                value=default_val,
                key=f"att_check_{s_id}_{today_str}"
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
            save_attendance(conn, today_str, entries)
            present_count = sum(1 for e in entries if e["status"] == "Present")
            st.success(f"Attendance recorded! Present: {present_count} | Absent: {len(entries) - present_count}")

    # ---------------- TAB 3: FINANCIAL DESK ----------------
    with tab_financial:
        st.subheader("Tuition Fee Management")
        all_students = list_students(conn)

        if all_students:
            total_expected = sum(s.get("fee", 0) for s in all_students)
            total_collected = sum(
                s.get("fee", 0) for s in all_students if get_payment_status(conn, s["id"]) == "Paid"
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
                    current_val = get_payment_status(conn, s_id)

                    f_col1, f_col2 = st.columns([3, 2])
                    with f_col1:
                        badge = "🟢 Paid" if current_val == "Paid" else "🔴 Unpaid"
                        st.markdown(
                            f"**{student['name']}** ({student['grade']})<br>"
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
                    for sid, stat in new_statuses.items():
                        set_payment_status(conn, sid, stat)
                    st.success("Payment records updated!")
                    st.rerun()

            st.write("---")

            unpaid_students = [s for s in all_students if get_payment_status(conn, s["id"]) == "Unpaid"]
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
        records = list_financial_records(conn)
        if records:
            st.dataframe(records, use_container_width=True, hide_index=True)
        else:
            st.info("No transactions recorded yet.")

    # ---------------- TAB 4: NOTICE BOARD ----------------
    with tab_notices:
        st.subheader("📢 Academy Notice Board")

        with st.expander("➕ Broadcast New Announcement", expanded=False):
            with st.form("new_notice_form", clear_on_submit=True):
                n_title = st.text_input("Announcement Title", placeholder="e.g., Weekly Test Schedule / Holiday")
                n_body = st.text_area("Message / Details", placeholder="Write the announcement details here...")
                n_priority = st.selectbox("Priority Level", ["Normal", "Urgent", "Exam/Test"])

                if st.form_submit_button("Publish Announcement", use_container_width=True):
                    if n_title.strip() and n_body.strip():
                        add_notice(conn, n_title.strip(), n_body.strip(), n_priority, datetime.date.today().strftime("%d %b %Y"))
                        st.success("Notice published successfully!")
                        st.rerun()
                    else:
                        st.warning("Please provide both a title and details.")

        notices = list_notices(conn)
        if notices:
            for notice in notices:
                border_color = "#ef4444" if notice["priority"] == "Urgent" else ("#f59e0b" if notice["priority"] == "Exam/Test" else "#38bdf8")
                st.markdown(f"""
                <div style="background-color: #1e293b; border-left: 4px solid {border_color}; border-radius: 8px; padding: 12px 16px; margin: 10px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="color: #ffffff; font-size: 16px;">{notice['title']}</strong>
                        <span style="color: #94a3b8; font-size: 12px;">{notice['date']}</span>
                    </div>
                    <p style="color: #cbd5e1; font-size: 14px; margin: 8px 0 0 0; line-height: 1.4;">{notice['body']}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No notices posted yet. Use the form above to broadcast an update.")

    if st.session_state.get("logged_in_role") == "Teacher":
        logout_button("teacher_logout_btn")

# ----------------------------------------------------
# 10. VIEW: PARENT DASHBOARD
# ----------------------------------------------------

def render_child_card(child: dict):
    child_id = child.get("id", "")
    child_name = child.get("name", "")

    fee_status = get_payment_status(conn, child_id)
    status_badge_color = "#4ade80" if fee_status == "Paid" else "#f87171"

    history_rows = attendance_history(conn, child_id)
    total_days = len(history_rows)
    present_days = sum(1 for _, status in history_rows if status == "Present")
    attendance_pct = int((present_days / total_days) * 100) if total_days > 0 else 100

    st.markdown(f"""
    <div style="background-color: #1e293b; border: 1.5px solid #334155; border-radius: 14px; padding: 18px; margin-top: 10px;">
        <h3 style="color: #ffffff; margin-top: 0; font-size: 18px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
            {child_name} — Academic & Tuition Status
        </h3>
        <p style="color: #cbd5e1; margin: 10px 0; font-size: 15px;">
            Batch / Grade: <strong style="color: #38bdf8;">{child.get('grade')}</strong>
            <span style="color: #64748b;">({child.get('subject', 'General')})</span>
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
            tx_list = list_financial_records(conn, child_name)
            if tx_list:
                st.dataframe(tx_list, use_container_width=True, hide_index=True)
            else:
                st.info("No recorded transactions yet for this student.")

    with st.expander(f"📢 Notices for {child.get('grade', 'this class')}", expanded=False):
        # Notice board isn't tagged by class today, so this shows all academy
        # notices for now — swap in a grade filter once notices carry one.
        notices = list_notices(conn)
        if notices:
            for n in notices:
                border_color = "#ef4444" if n["priority"] == "Urgent" else ("#f59e0b" if n["priority"] == "Exam/Test" else "#38bdf8")
                st.markdown(f"""
                <div style="background-color: #0f172a; border-left: 4px solid {border_color}; border-radius: 8px; padding: 10px 14px; margin: 8px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="color: #ffffff; font-size: 14px;">{n['title']}</strong>
                        <span style="color: #94a3b8; font-size: 11px;">{n['date']}</span>
                    </div>
                    <p style="color: #cbd5e1; font-size: 13px; margin: 6px 0 0 0; line-height: 1.4;">{n['body']}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No notices posted yet.")

def show_parent_dashboard():
    render_admin_quick_nav("Parent")

    is_admin_viewing = st.session_state.get("logged_in_role") == "Admin"
    parent_email = st.session_state.get("user_email", "")

    if is_admin_viewing:
        parent_accounts = list_parent_accounts(conn)
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

    my_children = list_students(conn, parent_email=parent_email)

    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
        {logo_img_tag()}
        <div>
            <h2 style="margin: 0; font-size: 22px; color: #ffffff;">Parent Portal</h2>
            <p style="margin: 0; color: #94a3b8; font-size: 13px;">
                {'Previewing as' if is_admin_viewing else 'Signed in as'} <strong style="color: #38bdf8;">{parent_email}</strong>
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
            render_child_card(child)

    if st.session_state.get("logged_in_role") == "Parent":
        logout_button("parent_logout_btn")

# ----------------------------------------------------
# 11. VIEW: ADMIN DASHBOARD
# ----------------------------------------------------

def show_admin_dashboard():
    render_header("Admin Master Console", "Executive Management • Full Academy Controls")

    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("🧑‍🏫 Open Teacher Desk", use_container_width=True, key="admin_to_teacher_btn"):
            go_to("Teacher")
            st.rerun()
    with col_nav2:
        if st.button("👨‍👩‍👧 Open Parent Portal", use_container_width=True, key="admin_to_parent_btn"):
            go_to("Parent")
            st.rerun()

    st.write("---")

    all_students = list_students(conn)
    enrolled_count = len(all_students)
    total_rev = sum(s.get("fee", 0) for s in all_students)
    total_collected = sum(s.get("fee", 0) for s in all_students if get_payment_status(conn, s["id"]) == "Paid")

    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        st.metric("Enrolled Students", enrolled_count)
    with m_col2:
        st.metric("Expected Revenue", f"₹{total_rev:,}")
    with m_col3:
        st.metric("Collected So Far", f"₹{total_collected:,}")

    st.write("---")
    st.subheader("🧑‍🎓 Manage Students")

    if all_students:
        st.dataframe(all_students, use_container_width=True, hide_index=True)
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
                    add_student(
                        conn,
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
                    update_student(conn, editing["id"], e_name.strip(), e_grade.strip() or "General", e_subject.strip() or "General", e_fee)
                    update_student_parent_email(conn, editing["id"], e_parent_email.strip().lower() or None)
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
                delete_student(conn, chosen_id)
                st.success("Student removed.")
                st.rerun()
        else:
            st.write("No students available to remove.")

    st.write("---")
    st.subheader("Master Financial Ledger")
    records = list_financial_records(conn)
    if records:
        st.dataframe(records, use_container_width=True, hide_index=True)
    else:
        st.info("No ledger entries available.")

    st.write("---")
    st.subheader("👪 Parent Accounts")
    st.caption("Each parent account only sees the student(s) linked to it here.")

    with st.expander("➕ Create Parent Account", expanded=False):
        with st.form("create_parent_form", clear_on_submit=True):
            p_email = st.text_input("Parent Email", placeholder="parent@example.com")
            p_pass = st.text_input("Temporary Password", type="password")
            p_children = st.multiselect(
                "Link to Student(s)",
                options=[s["name"] for s in all_students],
                help="You can also link/relink students later from the Teacher Desk."
            )
            if st.form_submit_button("Create Account", use_container_width=True):
                clean_email = p_email.strip().lower()
                if clean_email and p_pass.strip():
                    try:
                        create_parent_account(conn, clean_email, p_pass)
                        for name in p_children:
                            match = next((s for s in all_students if s["name"] == name), None)
                            if match:
                                update_student_parent_email(conn, match["id"], clean_email)
                        st.success(f"Parent account created for {clean_email}.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("An account with that email already exists.")
                else:
                    st.warning("Email and password are required.")

    parent_accounts = list_parent_accounts(conn)
    if parent_accounts:
        for pr in parent_accounts:
            linked_names = [s["name"] for s in all_students if s.get("parent_email") == pr["email"]]
            p_col1, p_col2 = st.columns([4, 1])
            with p_col1:
                linked_text = ", ".join(linked_names) if linked_names else "_no students linked_"
                st.markdown(f"**{pr['email']}** — linked to: {linked_text}")
            with p_col2:
                if st.button("Remove", key=f"del_parent_{pr['email']}", use_container_width=True):
                    delete_parent_account(conn, pr["email"])
                    st.rerun()
    else:
        st.info("No parent accounts yet — create one above.")

    logout_button("admin_logout_btn")

# ----------------------------------------------------
# 12. CORE APP ROUTER & SIDEBAR CONTROLLER
# ----------------------------------------------------
if not st.session_state.get("logged_in", False):
    show_login()
else:
    logged_role = st.session_state.get("logged_in_role", "Teacher")

    if logged_role != "Admin":
        st.session_state.active_view = logged_role
    elif st.session_state.get("active_view") not in ("Admin", "Teacher", "Parent"):
        st.session_state.active_view = "Admin"

    with st.sidebar:
        st.markdown(f"""
        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 14px; padding: 16px; margin-bottom: 20px; text-align: center;">
            <div style="display: inline-block; background: linear-gradient(135deg, #0284c7 0%, #06b6d4 100%); color: #ffffff; padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; margin-bottom: 8px;">
                {logged_role} Mode
            </div>
            <p style="color: #cbd5e1; font-size: 13px; margin: 0; font-weight: 500;">{st.session_state.get('user_email', '')}</p>
        </div>
        """, unsafe_allow_html=True)

        if logged_role == "Admin":
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
            st.session_state.clear()
            st.rerun()

    dashboard_routes = {
        "Admin": show_admin_dashboard,
        "Teacher": show_teacher_dashboard,
        "Parent": show_parent_dashboard
    }
    dashboard_routes.get(st.session_state.active_view, show_admin_dashboard)()
