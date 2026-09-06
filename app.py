import streamlit as st
import pandas as pd
import datetime
import os
import base64

# ----------------------------------------------------
# 1. PAGE CONFIGURATION (MUST BE FIRST STREAMLIT CALL)
# ----------------------------------------------------
st.set_page_config(
    page_title="MathScience Tuition",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------
# 2. SESSION STATE MANAGEMENT
# ----------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

# Shared student roster dataset
if "students_db" not in st.session_state:
    st.session_state.students_db = [
        {"id": "STU101", "name": "Aarav Sharma", "grade": "Class 9 Science", "subject": "Science", "attendance": "94%"},
        {"id": "STU102", "name": "Diya Patel", "grade": "Class 7 Olympiad", "subject": "Mathematics", "attendance": "98%"},
        {"id": "STU103", "name": "Rohan Das", "grade": "Class 9 Science", "subject": "Science", "attendance": "89%"},
    ]

# ----------------------------------------------------
# 3. LOGO ENCODING & STATIC ASSETS
# ----------------------------------------------------
logo_b64_str = ""
if os.path.exists("logo.jpg"):
    with open("logo.jpg", "rb") as img_file:
        logo_b64_str = f"data:image/jpeg;base64,{base64.b64encode(img_file.read()).decode()}"
else:
    logo_b64_str = "https://mathscience.in/logo.jpg"

# ----------------------------------------------------
# 4. MASTER HIGH-CONTRAST CSS STYLING ENGINE
# ----------------------------------------------------
st.markdown(f"""
<style>
    /* 1. App Background */
    .stApp {{
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%) !important;
        background-attachment: fixed !important;
    }}

    /* 2. Global Text Legibility */
    p, span, label, .stMarkdown p, [data-testid="stMarkdownContainer"] p {{
        color: #e2e8f0 !important;
    }}

    /* 3. Streamlit Header & Visible Toggle Chevron */
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

    /* Floating toggle support on mobile screens */
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

    /* 4. High-Contrast Sidebar */
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

    /* 5. Dropdown Menus & Selectboxes (High Contrast Popup Fix) */
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

    /* 6. Typography & Headings */
    h1, h2, h3, h4, h5, h6 {{
        color: #ffffff !important;
        font-weight: 700 !important;
    }}

    /* 7. Form Action Buttons */
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

    /* 8. Navigation Tabs */
    button[data-baseweb="tab"] {{
        color: #94a3b8 !important;
        font-weight: 600 !important;
        font-size: 15px !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: #38bdf8 !important;
        font-weight: 700 !important;
    }}

    /* 9. Glass Cards & Expanders */
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

    /* 10. Clean View & Balanced Padding */
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
            <p style="color: #cbd5e1; font-size: 14px; margin: 0;">Welcome! Please log in to securely manage your digital tuition roster.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input("Registered Email Address", placeholder="name@academy.com")
            password = st.text_input("Account Password", type="password")
            submit = st.form_submit_button("Access Dashboard")

            if submit:
                clean_email = email.strip().lower()
                # Direct Role Allocation (No Dropdowns Needed)
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
        <img src="{logo_b64_str}" style="width: 50px; height: 50px; border-radius: 12px; border: 1.5px solid #38bdf8;" />
        <div>
            <h2 style="margin: 0; font-size: 24px;">MathScience Tuition</h2>
            <p style="margin: 0; color: #94a3b8; font-size: 13px;">Instructor Console • Active Session</p>
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

    tab1, tab2, tab3 = st.tabs(["👥 Student Management", "📅 Attendance Desk", "📢 Notice Board"])

    with tab1:
        st.subheader("Academy Student Management Console")
        df = pd.DataFrame(st.session_state.students_db)
        st.dataframe(df, use_container_width=True)

        with st.expander("➕ Add New Student to Roster"):
            s_name = st.text_input("Student Full Name")
            s_grade = st.selectbox("Grade / Batch", ["Class 7 Olympiad", "Class 9 Science", "Class 10 Board Prep"])
            s_subject = st.text_input("Assigned Subject", value="Science")
            
            if st.button("Save Student", key="btn_save_student"):
                if s_name.strip():
                    st.session_state.students_db.append({
                        "id": f"STU{len(st.session_state.students_db)+101}",
                        "name": s_name.strip(),
                        "grade": s_grade,
                        "subject": s_subject.strip(),
                        "attendance": "100%"
                    })
                    st.success(f"Added {s_name} to student records.")
                    st.rerun()
                else:
                    st.warning("Please enter a valid student name.")

    with tab2:
        st.subheader("Daily Attendance Register")
        today = datetime.date.today().strftime("%Y-%m-%d")
        st.write(f"Logging Record for: **{today}**")
        
        for student in st.session_state.students_db:
            st.checkbox(f"{student['name']} ({student['grade']})", value=True, key=f"chk_{student['id']}")
            
        if st.button("Submit Attendance", key="btn_submit_attendance"):
            st.success("Attendance synced successfully!")

    with tab3:
        st.subheader("Notice Board")
        st.info("📢 Welcome to the new MathScience Academy digital Tuition Portal! Track student rosters, monitor test cycles, and register daily attendance seamlessly.")

def show_admin_dashboard():
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
        <img src="{logo_b64_str}" style="width: 50px; height: 50px; border-radius: 12px; border: 1.5px solid #38bdf8;" />
        <div>
            <h2 style="margin: 0; font-size: 24px;">Academy Master Console</h2>
            <p style="margin: 0; color: #94a3b8; font-size: 13px;">Administrator Access • Full Permissions</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Enrolled Students", len(st.session_state.students_db))
    col2.metric("Active Batches", "3")
    col3.metric("System Health", "Operational")

    st.subheader("All Student Records")
    df = pd.DataFrame(st.session_state.students_db)
    st.dataframe(df, use_container_width=True)

def show_parent_dashboard():
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
        <img src="{logo_b64_str}" style="width: 50px; height: 50px; border-radius: 12px; border: 1.5px solid #38bdf8;" />
        <div>
            <h2 style="margin: 0; font-size: 24px;">Parent Access Portal</h2>
            <p style="margin: 0; color: #94a3b8; font-size: 13px;">Viewing: Aarav Sharma (Class 9 Science)</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="glass-card">
        <h3 style="margin-top:0; color:#38bdf8;">Academic Status Overview</h3>
        <p><strong>Student Name:</strong> Aarav Sharma</p>
        <p><strong>Overall Attendance:</strong> 94%</p>
        <p><strong>Upcoming Assessment:</strong> Physics Mid-Term (Next Week)</p>
        <p><strong>Monthly Performance:</strong> Excellent (Grade A)</p>
    </div>
    """, unsafe_allow_html=True)

# ----------------------------------------------------
# 6. ROUTER & SIDEBAR CONTROLS
# ----------------------------------------------------
if not st.session_state.logged_in:
    show_login_page()
else:
    role = st.session_state.user_role

    # Persistent Left Sidebar
    with st.sidebar:
        st.markdown(f"""
        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 14px; padding: 16px; margin-bottom: 20px; text-align: center;">
            <div style="display: inline-block; background: linear-gradient(135deg, #0284c7 0%, #06b6d4 100%); color: #ffffff; padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; margin-bottom: 8px;">
                {role} Mode
            </div>
            <p style="color: #cbd5e1; font-size: 13px; margin: 0; font-weight: 500;">{st.session_state.user_email}</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🚪 Logout", key="sidebar_logout_btn", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_role = None
            st.session_state.user_email = ""
            st.rerun()

    # Route automatically to the user's specific page
    if role == "Teacher":
        show_teacher_dashboard()
    elif role == "Admin":
        show_admin_dashboard()
    elif role == "Parent":
        show_parent_dashboard()
    else:
        st.error("Unknown user role.")
        if st.button("Return to Login"):
            st.session_state.clear()
            st.rerun()
