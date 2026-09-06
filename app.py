import streamlit as st
import pandas as pd
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

# ----------------------------------------------------
# 2. SESSION STATE MANAGEMENT (DATA PERSISTENCE)
# ----------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

# Student Roster Database
if "students_db" not in st.session_state:
    st.session_state.students_db = [
        {"id": "STU101", "name": "Aarav Sharma", "grade": "Class 9 Science", "subject": "Science", "fee_status": "Paid", "fee_amount": 1500, "attendance": "94%"},
        {"id": "STU102", "name": "Diya Patel", "grade": "Class 7 Olympiad", "subject": "Mathematics", "fee_status": "Pending", "fee_amount": 1200, "attendance": "98%"},
        {"id": "STU103", "name": "Rohan Das", "grade": "Class 9 Science", "subject": "Science", "fee_status": "Paid", "fee_amount": 1500, "attendance": "89%"},
    ]

# Financial / Fee Ledger Transactions
if "financial_records" not in st.session_state:
    st.session_state.financial_records = [
        {"tx_id": "TXN901", "student": "Aarav Sharma", "date": "2026-09-01", "amount": 1500, "type": "Tuition Fee", "method": "UPI / Online"},
        {"tx_id": "TXN902", "student": "Rohan Das", "date": "2026-09-03", "amount": 1500, "type": "Tuition Fee", "method": "Cash"},
    ]

# Academy Notices
if "notice_board" not in st.session_state:
    st.session_state.notice_board = [
        {"date": "2026-09-06", "title": "Academy Portal Launch", "content": "Welcome to the official MathScience Academy digital portal!"},
        {"date": "2026-09-04", "title": "Class 9 Science Mock Test", "content": "Physics & Chemistry chapter tests scheduled for coming Sunday."},
    ]

# ----------------------------------------------------
# 3. STATIC ASSETS (LOGO RESOLUTION)
# ----------------------------------------------------
logo_b64_str = ""
if os.path.exists("logo.jpg"):
    with open("logo.jpg", "rb") as img_file:
        logo_b64_str = f"data:image/jpeg;base64,{base64.b64encode(img_file.read()).decode()}"
else:
    logo_b64_str = "https://mathscience.in/logo.jpg"

# ----------------------------------------------------
# 4. MASTER HIGH-CONTRAST CSS STYLING
# ----------------------------------------------------
st.markdown(f"""
<style>
    /* Base Mobile Container */
    .stApp {{
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%) !important;
        background-attachment: fixed !important;
    }}

    /* Global High Contrast Text */
    p, span, label, .stMarkdown p, [data-testid="stMarkdownContainer"] p {{
        color: #e2e8f0 !important;
    }}

    /* Header & Mobile Sidebar Toggle */
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

    /* High-Contrast Mobile Sidebar */
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

    /* Dropdown Menus & Selectboxes Contrast Fix */
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

    /* Headings & Text Weights */
    h1, h2, h3, h4, h5, h6 {{
        color: #ffffff !important;
        font-weight: 700 !important;
    }}

    /* Buttons */
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

    /* Delete / Destructive Action Button Style */
    button[kind="secondary"] {{
        background: #ef4444 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
    }}

    /* Navigation Tabs */
    button[data-baseweb="tab"] {{
        color: #94a3b8 !important;
        font-weight: 600 !important;
        font-size: 15px !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: #38bdf8 !important;
        font-weight: 700 !important;
    }}

    /* Cards & Expanders */
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

    /* Streamlit Metric Counters */
    [data-testid="stMetricValue"] {{ 
        font-size: 26px !important; 
        font-weight: 800; 
        color: #06b6d4 !important; 
    }}
    [data-testid="stMetricLabel"] {{ 
        color: #94a3b8 !important; 
    }}

    /* Clutter cleanup */
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
# 5. VIEW CONTROLLERS
# ----------------------------------------------------
def show_login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 24px;">
            <img src="{logo_b64_str}" style="width: 72px; height: 72px; border-radius: 18px; margin-bottom: 12px; border: 2px solid #38bdf8;" />
            <h1 style="font-size: 26px; margin: 0 0 8px 0;">MathScience Academy</h1>
            <p style="color: #cbd5e1; font-size: 14px; margin: 0;">Welcome! Please log in to securely access your portal.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input("Registered Email Address", placeholder="name@academy.com")
            password = st.text_input("Account Password", type="password")
            submit = st.form_submit_button("Access Dashboard")

            if submit:
                clean_email = email.strip().lower()
                # Unified Authentication Credentials
                if clean_email == "teacher1@gmail.com" and password == "123456":
                    st.session_state.logged_in = True
                    st.session_state.user_role = "Teacher"
                    st.session_state.user_email = clean_email
                    st.rerun()
                elif clean_email == "admin@academy.com" and password == "admin123":
                    st.session_state.logged_in = True
                    st.session_state.user_role = "Admin"
                    st.session_state.user_email = clean_email
                    st.rerun()
                elif clean_email == "parent@academy.com" and password == "parent123":
                    st.session_state.logged_in = True
                    st.session_state.user_role = "Parent"
                    st.session_state.user_email = clean_email
                    st.rerun()
                else:
                    st.error("Invalid email or password. Please verify credentials.")

def show_teacher_dashboard():
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
        <img src="{logo_b64_str}" style="width: 48px; height: 48px; border-radius: 12px; border: 1.5px solid #38bdf8;" />
        <div>
            <h2 style="margin: 0; font-size: 22px;">MathScience Tuition</h2>
            <p style="margin: 0; color: #94a3b8; font-size: 13px;">Teacher Desk • Operations Console</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="glass-card" style="text-align: center;">
        <span style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.35); color: #38bdf8; padding: 4px 14px; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;">PREMIUM PRIVATE PORTAL</span>
        <div style="margin-top: 14px;">
            <a href="https://mathscience.in" target="_blank" class="portal-btn">🌐 Visit Academy Portal</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["👥 Student Management", "💰 Financial Desk", "📅 Attendance Desk", "📢 Notice Board"])

    # --- TAB 1: STUDENT MANAGEMENT (ADD & DELETE) ---
    with tab1:
        st.subheader("Academy Student Roster")
        if st.session_state.students_db:
            df = pd.DataFrame(st.session_state.students_db)
            st.dataframe(df[["id", "name", "grade", "subject", "fee_status", "attendance"]], use_container_width=True)
        else:
            st.info("No active students found in roster.")

        # Expandable: Add Student
        with st.expander("➕ Add New Student to Roster"):
            with st.form("add_student_form"):
                s_name = st.text_input("Full Name")
                s_grade = st.selectbox("Grade / Batch", ["Class 7 Olympiad", "Class 9 Science", "Class 10 Board Prep"])
                s_subject = st.text_input("Assigned Subject", value="Science")
                s_fee = st.number_input("Monthly Fee Amount (₹)", min_value=500, max_value=20000, value=1500, step=100)
                add_btn = st.form_submit_button("Save Student to Records")

                if add_btn:
                    if s_name.strip():
                        new_id = f"STU{len(st.session_state.students_db) + 101}"
                        st.session_state.students_db.append({
                            "id": new_id,
                            "name": s_name.strip(),
                            "grade": s_grade,
                            "subject": s_subject.strip(),
                            "fee_status": "Pending",
                            "fee_amount": int(s_fee),
                            "attendance": "100%"
                        })
                        st.success(f"Enrolled {s_name} (ID: {new_id}) successfully!")
                        st.rerun()
                    else:
                        st.warning("Please provide a valid student name.")

        # Expandable: Delete Student
        with st.expander("🗑️ Delete Student from Roster"):
            if st.session_state.students_db:
                student_options = {f"{s['name']} ({s['id']})": s["id"] for s in st.session_state.students_db}
                selected_label = st.selectbox("Select Student to Remove", list(student_options.keys()))
                
                col_del_1, col_del_2 = st.columns([2, 1])
                with col_del_2:
                    if st.button("Confirm Deletion", type="secondary", use_container_width=True):
                        target_id = student_options[selected_label]
                        st.session_state.students_db = [s for s in st.session_state.students_db if s["id"] != target_id]
                        st.success(f"Removed student record successfully!")
                        st.rerun()
            else:
                st.write("No students available to delete.")

    # --- TAB 2: FINANCIAL SECTION (FEES & PAYMENTS) ---
    with tab2:
        st.subheader("Tuition Fee Management & Records")
        
        # Financial metric summary cards
        total_collected = sum(tx["amount"] for tx in st.session_state.financial_records)
        pending_students = [s for s in st.session_state.students_db if s.get("fee_status") == "Pending"]
        total_pending = sum(s.get("fee_amount", 1500) for s in pending_students)

        col_f1, col_f2 = st.columns(2)
        col_f1.metric("Total Fees Collected", f"₹{total_collected:,}")
        col_f2.metric("Outstanding Due", f"₹{total_pending:,}")

        st.markdown("#### Record Payment Collection")
        with st.form("fee_payment_form"):
            payer = st.selectbox("Select Student", [s["name"] for s in st.session_state.students_db])
            amount_paid = st.number_input("Amount Paid (₹)", min_value=100, max_value=50000, value=1500, step=100)
            pay_method = st.selectbox("Payment Mode", ["UPI / GPay / PhonePe", "Cash", "Bank Transfer", "Cheque"])
            pay_notes = st.text_input("Transaction Note / Reference ID", value="Monthly Tuition Fee")
            record_pay_btn = st.form_submit_button("Confirm Payment Receipt")

            if record_pay_btn:
                today_str = datetime.date.today().strftime("%Y-%m-%d")
                new_tx = {
                    "tx_id": f"TXN{len(st.session_state.financial_records)+901}",
                    "student": payer,
                    "date": today_str,
                    "amount": int(amount_paid),
                    "type": pay_notes,
                    "method": pay_method
                }
                st.session_state.financial_records.append(new_tx)

                # Update student fee status to Paid
                for s in st.session_state.students_db:
                    if s["name"] == payer:
                        s["fee_status"] = "Paid"

                st.success(f"Recorded ₹{amount_paid} payment for {payer}!")
                st.rerun()

        st.markdown("#### Transaction Log")
        if st.session_state.financial_records:
            tx_df = pd.DataFrame(st.session_state.financial_records)
            st.dataframe(tx_df, use_container_width=True)

    # --- TAB 3: ATTENDANCE DESK ---
    with tab2 if False else tab3:
        st.subheader("Daily Attendance Register")
        today = datetime.date.today().strftime("%Y-%m-%d")
        st.write(f"Logging Record for: **{today}**")

        if st.session_state.students_db:
            for s in st.session_state.students_db:
                st.checkbox(f"{s['name']} — {s['grade']} ({s['subject']})", value=True, key=f"att_chk_{s['id']}")
            if st.button("Submit Attendance Register", key="btn_sub_att"):
                st.success("Attendance submitted and synced with portal!")
        else:
            st.info("Enroll students in Tab 1 to track attendance.")

    # --- TAB 4: NOTICE BOARD ---
    with tab4:
        st.subheader("Academy Notices")
        for n in st.session_state.notice_board:
            st.markdown(f"""
            <div class="glass-card" style="padding: 16px; margin-bottom: 12px;">
                <span style="color: #38bdf8; font-size: 12px; font-weight: 700;">{n['date']}</span>
                <h4 style="margin: 4px 0 8px 0; font-size: 17px;">{n['title']}</h4>
                <p style="margin: 0; color: #cbd5e1; font-size: 14px;">{n['content']}</p>
            </div>
            """, unsafe_allow_html=True)

        with st.expander("📢 Broadcast New Notice"):
            n_title = st.text_input("Notice Headline")
            n_body = st.text_area("Notice Message")
            if st.button("Post Announcement"):
                if n_title.strip() and n_body.strip():
                    st.session_state.notice_board.insert(0, {
                        "date": datetime.date.today().strftime("%Y-%m-%d"),
                        "title": n_title.strip(),
                        "content": n_body.strip()
                    })
                    st.success("Announcement published to notice board!")
                    st.rerun()
def show_admin_dashboard():
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
        <img src="{logo_b64_str}" style="width: 48px; height: 48px; border-radius: 12px; border: 1.5px solid #38bdf8;" />
        <div>
            <h2 style="margin: 0; font-size: 22px;">Admin Master Console</h2>
            <p style="margin: 0; color: #94a3b8; font-size: 13px;">Executive Management • Full Academy Controls</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1-Tap Perspective Switcher for Admin
    c1, c2 = st.columns(2)
    with c1:
        if st.button("👨‍🏫 Open Teacher Desk", key="btn_switch_to_teacher", use_container_width=True):
            st.session_state.active_view = "Teacher"
            st.rerun()
    with c2:
        if st.button("👨‍👩‍👦 Open Parent Portal", key="btn_switch_to_parent", use_container_width=True):
            st.session_state.active_view = "Parent"
            st.rerun()

    st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

    total_revenue = sum(tx["amount"] for tx in st.session_state.financial_records)
    c1, c2, c3 = st.columns(3)
    c1.metric("Enrolled Students", len(st.session_state.students_db))
    c2.metric("Total Revenue", f"₹{total_revenue:,}")
    c3.metric("System Health", "Operational")

    st.subheader("Master Student Records")
    st.dataframe(pd.DataFrame(st.session_state.students_db), use_container_width=True)

    st.subheader("Master Financial Ledger")
    st.dataframe(pd.DataFrame(st.session_state.financial_records), use_container_width=True)

def show_parent_dashboard():
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
        <img src="{logo_b64_str}" style="width: 48px; height: 48px; border-radius: 12px; border: 1.5px solid #38bdf8;" />
        <div>
            <h2 style="margin: 0; font-size: 22px;">Parent Portal</h2>
            <p style="margin: 0; color: #94a3b8; font-size: 13px;">Viewing Student Profile: Aarav Sharma</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="glass-card">
        <h3 style="margin-top:0; color:#38bdf8;">Academic & Tuition Status</h3>
        <p><strong>Student Name:</strong> Aarav Sharma</p>
        <p><strong>Batch:</strong> Class 9 Science</p>
        <p><strong>Attendance Percentage:</strong> 94%</p>
        <p><strong>Monthly Fee Status:</strong> <span style="color:#4ade80; font-weight:700;">Paid (September 2026)</span></p>
        <p><strong>Next Assessment:</strong> Physics Mid-Term (Next Week)</p>
    </div>
    """, unsafe_allow_html=True)

# ----------------------------------------------------
# ----------------------------------------------------
# 6. CORE APP ROUTER & SIDEBAR CONTROLLER
# ----------------------------------------------------
if not st.session_state.get("logged_in", False):
    show_login_page()
else:
    role = st.session_state.get("user_role")

    # Set default view if not already selected
    if "active_view" not in st.session_state or st.session_state.active_view is None:
        st.session_state.active_view = role

    # Dedicated Left Sidebar
    with st.sidebar:
        st.markdown(f"""
        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 14px; padding: 16px; margin-bottom: 20px; text-align: center;">
            <div style="display: inline-block; background: linear-gradient(135deg, #0284c7 0%, #06b6d4 100%); color: #ffffff; padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; margin-bottom: 8px;">
                {role} Mode
            </div>
            <p style="color: #cbd5e1; font-size: 13px; margin: 0; font-weight: 500;">{st.session_state.get('user_email', '')}</p>
        </div>
        """, unsafe_allow_html=True)

    # Admin-exclusive sidebar switcher
        if role == "Admin":
            st.markdown("### 🛠️ Admin Navigation")
            pages = ["Admin", "Teacher", "Parent"]
            
            # Keep sidebar selectbox synced with button clicks
            if st.session_state.get("active_view") not in pages:
                st.session_state.active_view = "Admin"

            def sync_sidebar_desk():
                st.session_state.active_view = st.session_state.admin_sidebar_nav

            current_idx = pages.index(st.session_state.active_view)
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

    # Determine view to render
    current_view = st.session_state.get("active_view", "Admin") if role == "Admin" else role

    # Admin return header if inspecting another desk
    if role == "Admin" and current_view != "Admin":
        if st.button("⬅️ Return to Admin Master Console", key="admin_top_return_btn", use_container_width=True):
            st.session_state.active_view = "Admin"
            st.rerun()

    # Strict single-dashboard rendering
    if current_view == "Teacher":
        show_teacher_dashboard()
    elif current_view == "Parent":
        show_parent_dashboard()
    else:
        show_admin_dashboard()
