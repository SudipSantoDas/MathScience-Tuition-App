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

def show_login():
    logo_html = ""
    if "logo_b64_str" in globals() and globals().get("logo_b64_str"):
        logo_html = f'<img src="{globals()["logo_b64_str"]}" style="width: 48px; height: 48px; border-radius: 12px; border: 1.5px solid #38bdf8; object-fit: cover;" />'

    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
        {logo_html}
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
            if clean_email == "admin@academy.com" and password_input == "admin123":
                st.session_state.logged_in = True
                st.session_state.user_role = "Admin"
                st.session_state.logged_in_role = "Admin"
                st.session_state.user_email = clean_email
                st.rerun()
            elif clean_email == "parent@academy.com" and password_input == "parent123":
                st.session_state.logged_in = True
                st.session_state.user_role = "Parent"
                st.session_state.logged_in_role = "Parent"
                st.session_state.user_email = clean_email
                st.rerun()
            elif clean_email == "teacher@academy.com" and password_input == "teacher123":
                st.session_state.logged_in = True
                st.session_state.user_role = "Teacher"
                st.session_state.logged_in_role = "Teacher"
                st.session_state.user_email = clean_email
                st.rerun()
            else:
                st.error("Invalid email or password. Please verify credentials.")

        # Global fallback for logo string to prevent NameErrors across functions
if "logo_b64_str" not in globals():
    logo_b64_str = ""

def show_teacher_dashboard():
    # Fix the top red navigation buttons for Admin / Parent role switching
    if st.session_state.get("logged_in_role") == "Admin" or st.session_state.get("user_role") == "Admin":
        nav_col1, nav_col2 = st.columns(2)
        with nav_col1:
            if st.button("⬅ Return to Admin Console", use_container_width=True, key="btn_to_admin"):
                st.session_state.user_role = "Admin"
                st.session_state.active_view = "Admin"
                st.rerun()
        with nav_col2:
            if st.button("👨‍👩‍👧 Open Parent Portal", use_container_width=True, key="btn_to_parent"):
                st.session_state.user_role = "Parent"
                st.session_state.active_view = "Parent"
                st.rerun()
        st.write("---")

    academy_name = st.session_state.get("academy_name", "Tuition Operations Console")
    teacher_name = st.session_state.get("user_name", "Teacher Desk")

    # Safe logo rendering
    logo_html = ""
    if "logo_b64_str" in globals() and globals().get("logo_b64_str"):
        logo_html = f'<img src="{globals()["logo_b64_str"]}" style="width: 48px; height: 48px; border-radius: 12px; border: 1.5px solid #38bdf8; object-fit: cover;" />'

    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px; background: rgba(30, 41, 59, 0.7); padding: 12px 16px; border-radius: 14px; border: 1px solid rgba(56, 189, 248, 0.3);">
        {logo_html}
        <div>
            <h2 style="margin: 0; font-size: 20px; font-weight: 700; color: #ffffff;">{academy_name}</h2>
            <p style="margin: 0; color: #38bdf8; font-size: 13px; font-weight: 500;">{teacher_name} • Operations Console</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if "classrooms" not in st.session_state:
        st.session_state.classrooms = []

    with st.expander("➕ Create New Classroom / Batch", expanded=False):
        with st.form("create_room_form_unique", clear_on_submit=True):
            r_col1, r_col2 = st.columns(2)
            with r_col1:
                r_title = st.text_input("Grade / Class Level", placeholder="e.g., Class 10")
            with r_col2:
                r_subj = st.text_input("Subject", placeholder="e.g., Science")

            r_col3, r_col4 = st.columns(2)
            with r_col3:
                r_batch = st.text_input("Batch / Section", placeholder="e.g., 4:30 pm")
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
                    st.warning("Please provide both Class Level and Subject.")

    active_room = None
    if st.session_state.classrooms:
        room_labels = [f"{r['title']} — {r['subject']} ({r['section']})" for r in st.session_state.classrooms]
        selected_label = st.selectbox("Select Active Classroom to Manage:", options=room_labels, key="unique_classroom_selector_main")
        active_room = st.session_state.classrooms[room_labels.index(selected_label)]

        st.markdown(f"""
        <div style="background-color: #1e293b; border: 1.5px solid #38bdf8; border-radius: 12px; padding: 12px 18px; margin: 10px 0 20px 0;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                <div>
                    <span style="color: #38bdf8; font-weight: 700; font-size: 14px; text-transform: uppercase;">Active Class:</span>
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

    # All 4 Operations Tabs (Including Tab 3 Financial Desk with OK Confirmation Button)
    tab_students, tab_attendance, tab_financial, tab_notices = st.tabs([
        "🎓 Student Management", 
        "📅 Attendance Desk", 
        "💰 Financial Desk", 
        "📢 Notice Board"
    ])

    with tab_students:
        st.subheader("Academy Student Roster")
        students_list = st.session_state.get("students_db", [])
        if students_list:
            st.dataframe(students_list, use_container_width=True, hide_index=True)
        else:
            st.info("No students added yet. Use the form below to register your first student.")

        with st.expander("➕ Add New Student to Roster", expanded=False):
            with st.form("new_student_form_roster", clear_on_submit=True):
                stu_name = st.text_input("Full Name", placeholder="e.g., Aarav Sharma")
                default_grade = active_room["title"] if active_room else ""
                default_subject = active_room["subject"] if active_room else ""
                
                s_col1, s_col2 = st.columns(2)
                with s_col1:
                    stu_grade = st.text_input("Grade", value=default_grade)
                with s_col2:
                    stu_subj = st.text_input("Subject", value=default_subject)
                
                stu_fee = st.number_input("Monthly Fee (₹)", min_value=0, value=active_room.get("fee", 2500) if active_room else 2500, step=100)

                if st.form_submit_button("Register Student", use_container_width=True):
                    if stu_name.strip():
                        if "students_db" not in st.session_state:
                            st.session_state.students_db = []
                        new_id = f"STU{101 + len(st.session_state.students_db)}"
                        st.session_state.students_db.append({
                            "id": new_id,
                            "name": stu_name.strip(),
                            "grade": stu_grade.strip() or "General",
                            "subject": stu_subj.strip() or "General",
                            "fee": stu_fee
                        })
                        st.success(f"Student {stu_name} registered successfully!")
                        st.rerun()
                    else:
                        st.warning("Please enter a student name.")

        with st.expander("🗑️ Delete Student from Roster", expanded=False):
            if students_list:
                student_names = [f"{s['name']} ({s.get('grade', '')})" for s in students_list]
                del_choice = st.selectbox("Select Student to Delete", options=student_names, key="unique_delete_student_selectbox")
                if st.button("Confirm Deletion", type="primary", use_container_width=True):
                    idx_to_del = student_names.index(del_choice)
                    removed = st.session_state.students_db.pop(idx_to_del)
                    st.success(f"Removed {removed['name']} from roster.")
                    st.rerun()
            else:
                st.info("No students available to delete.")

    with tab_attendance:
        st.subheader("Attendance Tracking")
        st.info("Mark and review daily attendance logs for active batches.")

    with tab_financial:
        st.subheader("Tuition Fee Management")

        if "payment_status" not in st.session_state:
            st.session_state.payment_status = {}

        total_collected = 0
        total_pending = 0
        students_list = st.session_state.get("students_db", [])

        for student in students_list:
            s_id = student.get("id", student.get("name"))
            fee_amt = student.get("fee", 2500)
            status = st.session_state.get("payment_status", {}).get(s_id, "Unpaid")
            if status == "Paid":
                total_collected += fee_amt
            else:
                total_pending += fee_amt

        col_fin1, col_fin2 = st.columns(2)
        with col_fin1:
            st.caption("Total Collected")
            st.markdown(f"<h3 style='color: #4ade80; margin-top: -6px;'>₹{total_collected:,}</h3>", unsafe_allow_html=True)
        with col_fin2:
            st.caption("Pending / Due")
            st.markdown(f"<h3 style='color: #f87171; margin-top: -6px;'>₹{total_pending:,}</h3>", unsafe_allow_html=True)

        st.write("---")
        st.markdown("#### Update Student Payment Status")

        if students_list:
            with st.form("financial_update_form"):
                updated_statuses = {}
                for idx, student in enumerate(students_list):
                    s_id = student.get("id", student.get("name"))
                    s_name = student.get("name")
                    s_grade = student.get("grade")
                    s_fee = student.get("fee", 2500)

                    current_status = st.session_state.get("payment_status", {}).get(s_id, "Unpaid")
                    
                    st.markdown(f"**{s_name}** ({s_grade}) • Fee: ₹{s_fee:,}")
                    new_status = st.selectbox(
                        "Status", 
                        ["Unpaid", "Paid"], 
                        index=0 if current_status == "Unpaid" else 1, 
                        key=f"pay_status_{s_id}_{idx}"
                    )
                    updated_statuses[s_id] = new_status
                    st.write("")

                submitted = st.form_submit_button("💾 Confirm & Save Payment Status", use_container_width=True)
                if submitted:
                    st.session_state.payment_status = updated_statuses
                    st.success("Payment statuses updated successfully!")
                    st.rerun()
        else:
            st.info("No students available for fee tracking.")

    with tab_notices:
        st.subheader("Academy Notice Board")
        st.info("Broadcast announcements and urgent notices to student/parent portals.")

    def show_parent_dashboard():
        if st.session_state.get("logged_in_role") == "Admin":
            p_nav1, p_nav2 = st.columns(2)
            with p_nav1:
                if st.button("⬅ Return to Admin Console", use_container_width=True, key="parent_to_admin"):
                    st.session_state.user_role = "Admin"
                    st.rerun()
            with p_nav2:
                if st.button("🧑‍🏫 Open Teacher Desk", use_container_width=True, key="parent_to_teacher"):
                    st.session_state.user_role = "Teacher"
                    st.rerun()
            st.write("---")
    
        students = st.session_state.get("students_db", [])
        if not students:
            st.info("No registered students found in the academy roster.")
            return
    
        child_names = [s["name"] for s in students]
        selected_name = st.selectbox("Select Student Profile:", child_names, index=0, key="parent_child_select")
        
        child = next((s for s in students if s["name"] == selected_name), students[0])
        child_id = child.get("id", "")
    
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
            <img src="{logo_b64_str}" style="width: 48px; height: 48px; border-radius: 12px; border: 1.5px solid #38bdf8; object-fit: cover;" />
            <div>
                <h2 style="margin: 0; font-size: 22px; color: #ffffff;">Parent Portal</h2>
                <p style="margin: 0; color: #94a3b8; font-size: 13px;">Viewing Student Profile: <strong style="color: #38bdf8;">{child.get('name')}</strong></p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
        payment_map = st.session_state.get("payment_status", {})
        fee_status = payment_map.get(child_id, "Unpaid")
        status_badge_color = "#4ade80" if fee_status == "Paid" else "#f87171"
    
        attendance_logs = st.session_state.get("attendance_logs", {})
        total_days = 0
        present_days = 0
        for day_record in attendance_logs.values():
            total_days += 1
            if child["name"] in day_record.get("present", []):
                present_days += 1
    
        attendance_pct = int((present_days / total_days) * 100) if total_days > 0 else 100
    
        st.markdown(f"""
        <div style="background-color: #1e293b; border: 1.5px solid #334155; border-radius: 14px; padding: 18px; margin-top: 10px;">
            <h3 style="color: #ffffff; margin-top: 0; font-size: 18px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
                Academic & Tuition Status
            </h3>
            <p style="color: #cbd5e1; margin: 10px 0; font-size: 15px;">
                Student Name: <strong style="color: #ffffff;">{child.get('name')}</strong>
            </p>
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
    
        st.write("---")
        if st.button("🚪 Log Out", use_container_width=True, key="parent_logout_btn"):
            st.session_state.clear()
            st.rerun()
    
    def show_admin_dashboard():
        if "students_db" not in st.session_state:
            st.session_state.students_db = []
        if "payment_status" not in st.session_state:
            st.session_state.payment_status = {}
    
        logo_html = f'<img src="{logo_b64_str}" style="width: 48px; height: 48px; border-radius: 12px; border: 1.5px solid #38bdf8; object-fit: cover;" />' if logo_b64_str else ''
    
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
            {logo_html}
            <div>
                <h2 style="margin: 0; font-size: 22px; color: #ffffff;">Admin Master Console</h2>
                <p style="margin: 0; color: #94a3b8; font-size: 13px;">Executive Management • Full Academy Controls</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
        col_nav1, col_nav2 = st.columns(2)
        with col_nav1:
            if st.button("🧑‍🏫 Open Teacher Desk", use_container_width=True, key="admin_to_teacher_btn"):
                st.session_state.active_view = "Teacher"
                st.rerun()
        with col_nav2:
            if st.button("👨‍👩‍👧 Open Parent Portal", use_container_width=True, key="admin_to_parent_btn"):
                st.session_state.active_view = "Parent"
                st.rerun()
    
        st.write("---")
    
        students = st.session_state.students_db
        enrolled_count = len(students)
        total_rev = sum(s.get("fee", 0) for s in students)
    
        st.caption("Enrolled Students")
        st.markdown(f"<h2 style='color: #ffffff; margin-top: -8px;'>{enrolled_count}</h2>", unsafe_allow_html=True)
    
        st.caption("Total Revenue")
        st.markdown(f"<h2 style='color: #ffffff; margin-top: -8px;'>₹{total_rev:,}</h2>", unsafe_allow_html=True)
    
        st.write("---")
        st.subheader("Master Student Records")
        if students:
            st.dataframe(students, use_container_width=True, hide_index=True)
        else:
            st.info("No student records available.")
    
    # ----------------------------------------------------
    # 6. CORE APP ROUTER & SIDEBAR CONTROLLER
    # ----------------------------------------------------
    if not st.session_state.get("logged_in", False):
        show_login()
    else:
        logged_role = st.session_state.get("logged_in_role", "Teacher")
        active_view = st.session_state.get("active_view", logged_role)
    
        if logged_role != "Admin":
            active_view = logged_role
    
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
                
                if st.session_state.get("active_view") not in pages:
                    st.session_state.active_view = "Admin"
    
                def sync_sidebar_desk():
                    st.session_state.active_view = st.session_state.admin_sidebar_nav
    
                current_idx = pages.index(st.session_state.get("active_view", "Admin"))
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
    
        current_active_view = st.session_state.get("active_view", "Admin")
        active_dashboard_func = dashboard_routes.get(current_active_view, show_admin_dashboard)
        active_dashboard_func()
