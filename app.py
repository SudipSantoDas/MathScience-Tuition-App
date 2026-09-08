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
    st.session_state.students_db = []
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

    /* Form Input Fields & Visibility Fix */
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

    /* Expander Header Text Visibility Fix */
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
    # ----------------------------------------------------
    # QUICK CONSOLE NAVIGATION SWITCHER
    # ----------------------------------------------------
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("⬅ Return to Admin Console", use_container_width=True, key="btn_to_admin"):
            st.session_state.current_role = "admin"
            st.rerun()
    with nav_col2:
        if st.button("👨‍👩‍👧 Open Parent Portal", use_container_width=True, key="btn_to_parent"):
            st.session_state.current_role = "parent"
            st.rerun()

    st.write("")  # small spacer

    # 1. Retrieve dynamic academy or teacher name (fallback to a clean universal title)
    academy_name = st.session_state.get("academy_name", "Tuition Operations Console")
    teacher_name = st.session_state.get("user_name", "Teacher Desk")

    # 2. Universal High-Contrast Header
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px; background: rgba(30, 41, 59, 0.7); padding: 12px 16px; border-radius: 14px; border: 1px solid rgba(56, 189, 248, 0.3);">
        <img src="{logo_b64_str}" style="width: 48px; height: 48px; border-radius: 12px; border: 1.5px solid #38bdf8; object-fit: cover;" />
        <div>
            <h2 style="margin: 0; font-size: 20px; font-weight: 700; color: #ffffff;">{academy_name}</h2>
            <p style="margin: 0; color: #38bdf8; font-size: 13px; font-weight: 500;">{teacher_name} • Operations Console</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ----------------------------------------------------
    # 1. DYNAMIC CLASSROOM CREATOR & WORKSPACE SELECTOR
    # ----------------------------------------------------
    if "classrooms" not in st.session_state:
        st.session_state.classrooms = []

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
                    st.session_state.classrooms.append({
                        "title": r_title.strip(),
                        "subject": r_subj.strip(),
                        "section": r_batch.strip() or "Regular",
                        "fee": r_fee
                    })
                    st.success("Classroom created successfully!")
                    st.rerun()
                else:
                    st.warning("Please provide both a Class level and a Subject.")

    # High-contrast active class selector card
    active_room = None
    if st.session_state.classrooms:
        room_labels = [f"{r['title']} — {r['subject']} ({r['section']})" for r in st.session_state.classrooms]
        selected_label = st.selectbox("Select Active Classroom to Manage:", room_labels, key="active_room_picker")
        active_room = st.session_state.classrooms[room_labels.index(selected_label)]

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

    # ----------------------------------------------------
    # 2. SINGLE UNIFIED TAB BAR (No duplicate tabs)
    # ----------------------------------------------------
    tab_students, tab_attendance, tab_financial, tab_notices = st.tabs([
        "👥 Student Management",
        "📅 Attendance Desk",
        "💰 Financial Desk",
        "📢 Notice Board"
    ])

    # ---------------- TAB 1: STUDENT MANAGEMENT ----------------
    with tab_students:
        st.subheader("Academy Student Roster")
        
        if "students_db" in st.session_state and st.session_state.students_db:
            st.dataframe(st.session_state.students_db, use_container_width=True)
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

                if st.form_submit_button("Save Student to Records", use_container_width=True):
                    if stu_name.strip():
                        new_id = f"STU{101 + len(st.session_state.students_db)}"
                        st.session_state.students_db.append({
                            "id": new_id,
                            "name": stu_name.strip(),
                            "grade": stu_grade.strip() or "General",
                            "subject": stu_subject.strip() or "General",
                            "fee": stu_fee
                        })
                        st.success(f"Added {stu_name.strip()} successfully!")
                        st.rerun()
                    else:
                        st.warning("Please enter student name.")

        with st.expander("🗑️ Delete Student from Roster", expanded=False):
            if "students_db" in st.session_state and st.session_state.students_db:
                student_options = [f"{s['name']} ({s['id']})" for s in st.session_state.students_db]
                del_choice = st.selectbox("Select Student to Remove", student_options, key="del_stu_select")
                if st.button("Confirm Delete", type="primary", use_container_width=True):
                    chosen_id = del_choice.split("(")[-1].replace(")", "").strip()
                    st.session_state.students_db = [s for s in st.session_state.students_db if s["id"] != chosen_id]
                    st.success("Student removed.")
                    st.rerun()
            else:
                st.write("No students available to remove.")

    # ---------------- TAB 2: ATTENDANCE DESK ----------------
    with tab_attendance:
        st.subheader("Daily Attendance Register")
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        st.caption(f"Logging Record for: **{today_str}**")

        registered_rooms = sorted(list(set(
            s.get("grade", "").strip() for s in st.session_state.get("students_db", []) if s.get("grade")
        )))

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
            if selected_class == "All Classes":
                active_roster = st.session_state.students_db
            else:
                active_roster = [s for s in st.session_state.students_db if s.get("grade") == selected_class]

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
            if "attendance_logs" not in st.session_state:
                st.session_state.attendance_logs = {}

            present_list = [s["name"] for s in active_roster if attendance_status.get(s["id"])]
            absent_list = [s["name"] for s in active_roster if not attendance_status.get(s["id"])]

            st.session_state.attendance_logs[today_str] = {
                "present": present_list,
                "absent": absent_list,
                "class": selected_class if registered_rooms else "All"
            }
            st.success(f"Attendance recorded! Present: {len(present_list)} | Absent: {len(absent_list)}")

    # ---------------- TAB 3: FINANCIAL DESK ----------------
# ---------------- TAB 3: FINANCIAL DESK ----------------
    with tab_financial:
        st.subheader("Tuition Fee Management")

        if "payment_status" not in st.session_state:
            st.session_state.payment_status = {}

        if "students_db" in st.session_state and st.session_state.students_db:
            # 1. Summary Metrics
            total_expected = sum(s.get("fee", 0) for s in st.session_state.students_db)
            total_collected = sum(
                s.get("fee", 0) for s in st.session_state.students_db
                if st.session_state.payment_status.get(s["id"], "Unpaid") == "Paid"
            )
            total_due = total_expected - total_collected

            col_rev1, col_rev2 = st.columns(2)
            with col_rev1:
                st.metric("Total Collected", f"₹{total_collected:,}")
            with col_rev2:
                st.metric("Pending / Due", f"₹{total_due:,}")

            st.write("---")
            st.markdown("### Update Student Payment Status")

            # 2. Form with explicit save button
            with st.form("fee_status_form"):
                new_statuses = {}
                for student in st.session_state.students_db:
                    s_id = student["id"]
                    current_val = st.session_state.payment_status.get(s_id, "Unpaid")

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
                        st.session_state.payment_status[sid] = stat
                    st.success("Payment records updated!")
                    st.rerun()

            st.write("---")

            # 3. Defaulters Alert
            unpaid_students = [
                s for s in st.session_state.students_db
                if st.session_state.payment_status.get(s["id"], "Unpaid") == "Unpaid"
            ]

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

    # ---------------- TAB 4: NOTICE BOARD ----------------
    with tab_notices:
        st.subheader("Academy Notices & Announcements")
        st.info("Broadcast channel active for students and parents.")
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

    # Quick Navigation Switchers
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("🧑‍🏫 Open Teacher Desk", use_container_width=True, key="admin_to_teacher"):
            st.session_state.user_role = "Teacher"
            st.rerun()
    with col_nav2:
        if st.button("👨‍👩‍👧 Open Parent Portal", use_container_width=True, key="admin_to_parent"):
            st.session_state.user_role = "Parent"
            st.rerun()

    st.write("---")

    # Dynamic Live Metrics Calculation
    students = st.session_state.get("students_db", [])
    enrolled_count = len(students)
    total_revenue = sum(int(s.get("fee", 0)) for s in students)

    st.metric("Enrolled Students", enrolled_count)
    st.metric("Total Revenue", f"₹{total_revenue:,}")
    st.metric("System Health", "Operational")

    st.write("---")

    # Master Student Records Table (hide_index prevents cut-off on mobile)
    st.subheader("Master Student Records")
    if students:
        st.dataframe(students, use_container_width=True, hide_index=True)
    else:
        st.info("No student records found.")

    st.write("---")

    # Master Financial Ledger Table
    st.subheader("Master Financial Ledger")
    if students:
        st.dataframe(students, use_container_width=True, hide_index=True)
    else:
        st.info("No ledger entries available.")
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
