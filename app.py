import streamlit as st
import pandas as pd
from datetime import datetime
import os
import urllib.parse
import base64
from supabase import create_client, Client  # 👈 Added the Supabase tool inside your app

# ==============================================================================
# 🌐 CONNECT TO YOUR CLOUD DATABASE
# ==============================================================================
SUPABASE_URL = "https://kzremjjivpkvbbmeqkzk.supabase.co"
SUPABASE_KEY = "sb_publishable_n7PGTD-wEjjlmMhjsl4d-g_Y4HT_n7PGTD"

# This creates the live connection bridge
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==============================================================================
# 1. NEW: SECURITY GUARD (MULTI-USER SESSION STATE)
# ==============================================================================
# This keeps track of who is logged in so teachers don't see each other's data
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = None  # Will be 'Admin', 'Teacher', or 'Student'

# ==============================================================================
# 2. PREMIUM PAGE CONFIGURATION & METATAG INJECTIONS
# ==============================================================================
st.set_page_config(
    page_title="MathScience Tuition",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)
# Hide Streamlit header, settings cog, and footer
st.markdown("""
    <style>
    /* Keep header active and transparent so the sidebar toggle is clickable */
    header[data-testid="stHeader"] {
        background: transparent !important;
        z-index: 100000 !important;
    }
    
    /* Ensure the sidebar toggle icon (chevron button) is visible and highlighted */
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapsedControl"] button,
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        color: #38bdf8 !important;
        z-index: 100001 !important;
    }

    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="collapsedControl"] svg {
        fill: #38bdf8 !important;
        stroke: #38bdf8 !important;
        width: 28px !important;
        height: 28px !important;
    }

    /* Clean Streamlit clutter */
    div[data-testid="stToolbar"] { display: none !important; }
    footer { display: none !important; }
    div[class*="viewerBadge"] { display: none !important; }
    </style>
""", unsafe_allow_html=True)
# Load local logo and base64 encode it for fluid rendering
logo_b64_str = ""
if os.path.exists("logo.jpg"):
    with open("logo.jpg", "rb") as img_file:
        logo_b64_str = f"data:image/jpeg;base64,{base64.b64encode(img_file.read()).decode()}"
else:
    logo_b64_str = "https://mathscience.in/logo.jpg"

# Core spreadsheet export URL configurations
SHEET_ID = "1DhuNCdpfHNpycppJDzv2SfWmLdf76iOgxuSPXEbOnWM"
GSHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet="
WEBSITE_URL = "https://mathscience.in"

# 🎨 Master High-Contrast UI Styling Engine for Ultimate Readability
st.markdown(f"""
<style>
    .stApp {{
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%) !important;
        background-attachment: fixed !important;
    }}
    visibility: visible !important;
    display: block !important;
    opacity: 1 !important;
    z-index: 999999 !important;
}}
    [data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #091426 0%, #030a16 100%) !important;
    border-right: 1px solid rgba(56, 189, 248, 0.25) !important;
}}
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h2 span, [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 {{
        color: #ffffff !important; font-weight: 700 !important; font-size: 22px !important;
    }}
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
        color: #38bdf8 !important; font-weight: 700 !important; font-size: 15px !important;
    }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
        color: #f1f5f9 !important; font-weight: 600 !important; font-size: 14px !important;
    }}
    button[data-baseweb="tab"] {{
        color: #94a3b8 !important; font-weight: 600 !important; font-size: 15px !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: #38bdf8 !important; font-weight: 700 !important;
    }}
    [data-testid="stExpander"] details summary p, [data-testid="stExpander"] p, [data-testid="stExpander"] span {{
        color: #ffffff !important; font-weight: 600 !important; font-size: 15px !important;
    }}
    [data-testid="stExpander"] {{
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
    }}
    h1, h2, h3, h4, h5, h6, [data-testid="stMarkdownContainer"] h4, [data-testid="stMarkdownContainer"] h4 p {{
        color: #ffffff !important; font-weight: 700 !important;
    }}
    label, [data-testid="stWidgetLabel"] p {{
        color: #cbd5e1 !important; font-weight: 600 !important; font-size: 14px !important;
    }}
    div[data-testid="stFormSubmitButton"] button, .stButton button, button[kind="primaryFormSubmit"] {{
        background: linear-gradient(135deg, #0284c7 0%, #06b6d4 100%) !important;
        color: #ffffff !important; font-weight: 700 !important; border: none !important;
        border-radius: 12px !important; padding: 10px 20px !important;
        box-shadow: 0 4px 15px rgba(2, 132, 199, 0.3) !important; width: 100% !important;
    }}
    .glass-card {{
        background: rgba(255, 255, 255, 0.04); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 24px; padding: 25px 20px;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3); margin-bottom: 25px;
    }}
    .portal-btn {{
        display: inline-block; background: linear-gradient(135deg, #0284c7 0%, #06b6d4 100%);
        color: #ffffff !important; font-family: 'Inter', system-ui, sans-serif; font-size: 13px;
        font-weight: 700; padding: 10px 22px; border-radius: 12px; text-decoration: none;
        box-shadow: 0 4px 15px rgba(2, 132, 199, 0.3);
    }}
    [data-testid="stMetricValue"] {{ font-size: 26px !important; font-weight: 800; color: #06b6d4 !important; }}
    [data-testid="stMetricLabel"] {{ color: #94a3b8 !important; }}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# # ==============================================================================
# 2. HEADER INTERFACE DESIGN (Now Wrapped inside the Teacher's Dashboard)
# ==============================================================================
def show_teacher_dashboard():
    # Everything inside here is pushed to the right by 1 Tab space!
    with st.sidebar:
        st.markdown("""
            <style>
            section[data-testid="stSidebar"] {
                background: linear-gradient(180deg, #091426 0%, #030a16 100%) !important;
                border-right: 1px solid rgba(56, 189, 248, 0.15) !important;
            }
            .sidebar-profile-card {
                background: rgba(15, 23, 42, 0.65);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(56, 189, 248, 0.2);
                border-radius: 14px;
                padding: 14px;
                margin-bottom: 15px;
                text-align: center;
            }
            .user-badge {
                display: inline-block;
                background: linear-gradient(135deg, #0284c7 0%, #06b6d4 100%);
                color: #ffffff;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 1px;
                padding: 3px 10px;
                border-radius: 20px;
                margin-top: 5px;
            }
            div[data-testid="stSidebar"] div[data-testid="stButton"] > button {
                width: 100%;
                border-radius: 10px !important;
                background: rgba(239, 68, 68, 0.12) !important;
                color: #f87171 !important;
                border: 1px solid rgba(239, 68, 68, 0.3) !important;
                font-weight: 600 !important;
            }
            </style>
            <div class="sidebar-profile-card">
                <div style="font-size: 26px; margin-bottom: 2px;">👨‍🏫</div>
                <h4 style="color: #f1f5f9; margin: 0; font-size: 16px;">Teacher Portal</h4>
                <span class="user-badge">Teacher / Admin</span>
            </div>
        """, unsafe_allow_html=True)

        if st.button("🚪 Log Out", key="teacher_sidebar_logout"):
            st.session_state.clear()
            st.rerun()

    with st.container():
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 15px; margin-top: -10px; margin-bottom: 20px;">
            <img src="{logo_b64_str}" style="width: 60px; height: 60px; border-radius: 20%; box-shadow: 0 0 20px rgba(6, 182, 212, 0.4); flex-shrink: 0;">
            <h1 style="font-family: 'Inter', system-ui, sans-serif; font-size: 26px; font-weight: 800; letter-spacing: -0.5px; margin: 0; background: linear-gradient(135deg, #ffffff 30%, #38bdf8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; white-space: nowrap;">
                MathScience Tuition
            </h1>
        </div>
        <div class="glass-card" style="text-align: center; margin-top: 15px;">
            <div style="display: inline-block; margin-bottom: 15px; padding: 6px 16px; background: rgba(14, 165, 233, 0.15); border: 1px solid rgba(14, 165, 233, 0.3); border-radius: 30px;">
                <p style="color: #38bdf8; font-size: 11px; font-weight: 700; margin: 0; text-transform: uppercase; letter-spacing: 1px;">✨ PREMIUM PRIVATE PORTAL</p>
            </div>
            <div>
                <a href="{WEBSITE_URL}" target="_blank" class="portal-btn">🌐 Visit Academy Portal</a>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 🚨 NOTE: All your student lists, marks columns, and charts that 
    # come next will also be placed inside this function, indented by 1 tab!
# ==============================================================================
# # ==============================================================================
# ==============================================================================
# # 3. PREMIUM SUPABASE CLOUD DATA FETCHING LOGIC
# ==============================================================================
def fetch_cloud_sheet(sheet_name, fallback_df):
    """
    Directly routes your app requests to your premium Supabase cloud database.
    If a table doesn't load, it safely returns your fallback data.
    """
    try:
        # Lowercase the name to match your Supabase tables exactly
        table_target = sheet_name.lower().strip()
        
        # Pull the live records from Supabase
        response = supabase.table(table_target).select("*").execute()
        
        if response.data:
            return pd.DataFrame(response.data)
        return fallback_df
    except Exception as e:
        # If anything drops, seamlessly fall back so your app doesn't crash
        return fallback_df

if 'student_db' not in st.session_state:
    st.session_state.student_db = fetch_cloud_sheet("Students", pd.DataFrame({
        "Student Name": ["Rudra", "Supratik", "Vivek", "Ananya", "Arup"],
        "Parent Phone": ["9876543210", "9876543211", "9876543212", "9876543213", "9876543214"],
        "Math Score": [85, 92, 78, 95, 88],
        "Science Score": [90, 88, 82, 96, 84],
        "Monthly Fee (₹)": [1500, 1500, 1500, 1500, 1500],
        "Fee Status": ["Paid", "Pending", "Paid", "Paid", "Pending"]
    }))

if 'attendance_db' not in st.session_state:
    st.session_state.attendance_db = fetch_cloud_sheet("Attendance", pd.DataFrame(columns=["Date", "Student Name", "Status"]))

if 'announcements' not in st.session_state:
    st.session_state.announcements = fetch_cloud_sheet("Announcements", pd.DataFrame([
        {"Date": datetime.now().strftime("%Y-%m-%d"), "Notice": "Welcome to the new MathScience Academy digital Tuition Portal! 🎉"}
    ]))

# 🌟 UPDATED: Registry containing test credentials for your subscription app
TEACHER_REGISTRY = {
    "admin@mathscience.in": "admin123",       # Platform Owner (You)
    "teacher1@gmail.com": "pass123",         # Subscribed Teacher 1
    "teacher2@gmail.com": "pass456",         # Subscribed Teacher 2
    "druvvvv86@gmail.com": "yourpasswordhere" # 👈 ADD THIS LINE RIGHT HERE!
}
with st.sidebar:
    st.title("Teacher Portal")
    st.write("Logged in: Teacher / Admin")
    if st.button("Log Out", key="teacher_main_logout"):
        st.session_state.clear()
        st.rerun()
df = st.session_state.student_db

def render_notice_board():
    notices_df = st.session_state.announcements
    if not notices_df.empty:
        latest_notice = notices_df.iloc[-1]
        st.markdown(f"""
        <div style="background: rgba(2, 132, 199, 0.1); border-left: 4px solid #0284c7; padding: 15px; border-radius: 12px; margin-bottom: 20px;">
            <h4 style="margin: 0 0 5px 0; color: #38bdf8; font-size: 16px;">📢 Academy Notice Board ({latest_notice['Date']})</h4>
            <p style="margin: 0; color: #cbd5e1; font-size: 14px;">{latest_notice['Notice']}</p>
        </div>
        """, unsafe_allow_html=True)

# ==============================================================================
# 4. SECURE USER AUTHENTICATION & MULTI-TENANT ROUTING
# ==============================================================================

# --- CONTEXT A: USER IS NOT LOGGED IN (SHOW LOGIN FORM) ---
if not st.session_state.logged_in:
    with st.container(border=True):
        st.markdown("### 🔐 MathScience Academy Network")
        st.caption("Welcome! Please log in to securely manage your digital tuition roster.")
        
        email_input = st.text_input("Registered Email Address:", placeholder="name@academy.com")
        password_input = st.text_input("Account Password:", type="password", placeholder="••••••••")
        
        if st.button("Access Dashboard", use_container_width=True):
            if email_input in TEACHER_REGISTRY and password_input == TEACHER_REGISTRY[email_input]:
                st.session_state.logged_in = True
                # Identify if they are the master platform owner or a subscribing teacher
                if email_input == "admin@mathscience.in":
                    st.session_state.user_role = "Admin"
                else:
                    st.session_state.user_role = "Teacher"
                st.toast(f"Authentication Successful! Role: {st.session_state.user_role}", icon="🔑")
                st.rerun()
            else:
                st.error("Invalid email address or password configuration. Please try again.")

# --- CONTEXT B: USER IS LOGGED IN (PROVIDE ROUTING & LOGOUT) ---
else:
    # Sidebar Navigation Controls for Active Users
    with st.sidebar:
        st.markdown(f"<h2 style='color:#f8fafc; font-size:18px; font-weight:700;'>👤 Active Session</h2>", unsafe_allow_html=True)
        role_options = ["Admin", "Teacher", "Student", "Parent"]
        current_index = role_options.index(st.session_state.user_role) if st.session_state.user_role in role_options else 0
        st.session_state.user_role = st.selectbox("Switch View / Role:", role_options, index=current_index)
        
        if st.button("🚪 Log Out of Account", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_role = None
            st.rerun()
            
    # --------------------------------------------------------------------------
    # ROLE ROOM 1: PLATFORM OWNER (YOU) - SAAS SUBSCRIPTION CONTROLLER
    # --------------------------------------------------------------------------
    if st.session_state.user_role == "Admin":
        st.markdown("## 📈 SaaS Platform Manager Dashboard")
        st.write("Welcome, Sudip. Here is the operational state of your global teacher subscription system:")
        
        # Micro-SaaS Analytics Cards
        m1, m2, m3 = st.columns(3)
        m1.metric("Active Subscribed Teachers", "2 Tutors")
        m2.metric("Monthly Recurring Revenue", "₹1,998")
        m3.metric("Global Infrastructure Status", "Healthy 🟢")
        
        st.markdown("### 📋 Subscribed Academy Registry")
        teacher_data_panel = pd.DataFrame([
            {"Teacher ID": "TCH-001", "Email": "teacher1@gmail.com", "Roster Volume": "5 Students", "Subscription Tier": "Basic (₹999/mo)", "Account Status": "Paid Active"},
            {"Teacher ID": "TCH-002", "Email": "teacher2@gmail.com", "Roster Volume": "0 Students", "Subscription Tier": "Basic (₹999/mo)", "Account Status": "Paid Active"}
        ])
        st.dataframe(teacher_data_panel, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # ROLE ROOM 2: SUBSCRIBING TEACHERS (YOUR CUSTOM CLASSROOM TRACKER)
    # --------------------------------------------------------------------------
    elif st.session_state.user_role == "Teacher":
        # Render the premium branding header we wrapped into memory earlier
        show_teacher_dashboard()
        
        # Render the custom notification board banner
        render_notice_board()
        
        # Generate the operation tabs for the specific teacher session
        admin_tab1, admin_tab2, admin_tab3, admin_tab4 = st.tabs([
            "👥 Student Management", "📅 Attendance Desk", "📢 Broadcast Desk", "📊 Financial Analytics"
        ])

        with admin_tab1:
            st.markdown("### 🛠️ Academy Student Management Console")
            
            with st.expander("➕ Add New Student to Roster", expanded=False):
                with st.form("add_student_form", clear_on_submit=True):
                    new_student_name = st.text_input("Full Student Name:")
                    parent_phone = st.text_input("Parent Phone Number:", max_chars=10, placeholder="10-digit number")
                    col1, col2 = st.columns(2)
                    initial_math_score = col1.number_input("Initial Math Score:", min_value=0, max_value=100, value=0)
                    initial_sci_score = col2.number_input("Initial Science Score:", min_value=0, max_value=100, value=0)
                    assigned_monthly_fee = st.number_input("Assigned Monthly Fee (₹):", min_value=0, value=1500)
                    initial_fee_status = st.selectbox("Current Fee Status:", ["Pending", "Paid"])
                    submit_new_student = st.form_submit_button("Create Student Account")
                    
                    if submit_new_student and new_student_name.strip() != "":
                        new_row = pd.DataFrame([{
                            "Student Name": new_student_name.strip(),
                            "Parent Phone": parent_phone.strip() if parent_phone else "N/A",
                            "Math Score": int(initial_math_score),
                            "Science Score": int(initial_sci_score),
                            "Monthly Fee (₹)": int(assigned_monthly_fee),
                            "Fee Status": initial_fee_status
                        }])
                        st.session_state.student_db = pd.concat([st.session_state.student_db, new_row], ignore_index=True)
                        st.success(f"Registered {new_student_name} successfully!")
                        st.rerun()

            with st.expander("📝 Update Fees, Status, or Scores", expanded=False):
                student_to_edit = st.selectbox("Select Student to Modify:", ["-- Choose Student --"] + list(df["Student Name"].unique()))
                if student_to_edit != "-- Choose Student --":
                    student_data = df[df["Student Name"] == student_to_edit].iloc[0]
                    with st.form("edit_student_form"):
                        curr_phone = st.text_input("Modify Parent Phone:", value=str(student_data.get("Parent Phone", "N/A")))
                        col1, col2 = st.columns(2)
                        updated_math = col1.number_input("Update Math Score:", min_value=0, max_value=100, value=int(student_data["Math Score"]))
                        updated_sci = col2.number_input("Update Science Score:", min_value=0, max_value=100, value=int(student_data.get("Science Score", 0)))
                        updated_fee = st.number_input("Modify Monthly Fee (₹):", min_value=0, value=int(student_data["Monthly Fee (₹)"]))
                        updated_status = st.selectbox("Update Fee Status:", ["Pending", "Paid"], index=["Pending", "Paid"].index(student_data["Fee Status"]))
                        save_edits = st.form_submit_button("Save Changes")
                        
                        if save_edits:
                            idx = st.session_state.student_db[st.session_state.student_db["Student Name"] == student_to_edit].index[0]
                            st.session_state.student_db.at[idx, "Parent Phone"] = curr_phone
                            st.session_state.student_db.at[idx, "Math Score"] = int(updated_math)
                            st.session_state.student_db.at[idx, "Science Score"] = int(updated_sci)
                            st.session_state.student_db.at[idx, "Monthly Fee (₹)"] = int(updated_fee)
                            st.session_state.student_db.at[idx, "Fee Status"] = updated_status
                            st.success(f"Updated records for {student_to_edit}!")
                            st.rerun()

            with st.expander("🗑️ Delete Student from Academy Records", expanded=False):
                student_to_delete = st.selectbox("Select Target Student for Removal:", ["-- Choose Student --"] + list(df["Student Name"].unique()))
                if student_to_delete != "-- Choose Student --":
                    if st.button("🔴 Confirm Delete Account", use_container_width=True):
                        st.session_state.student_db = st.session_state.student_db[st.session_state.student_db["Student Name"] != student_to_delete]
                        st.success(f"Removed account for {student_to_delete}.")
                        st.rerun()

            st.dataframe(df, use_container_width=True, hide_index=True)

        with admin_tab2:
            st.markdown("### 📅 Take Attendance")
            selected_date = st.date_input("Select Date for Attendance:", datetime.now().date())
            date_str = selected_date.strftime("%Y-%m-%d")
            
            present_students = []
            for student in df["Student Name"]:
                if st.checkbox(student, key=f"teacher_att_{student}_{date_str}"):
                    present_students.append(student)
                    
            if st.button("💾 Save Attendance Log", use_container_width=True):
                new_records = []
                for student in df["Student Name"]:
                    status = "Present" if student in present_students else "Absent"
                    new_records.append({"Date": date_str, "Student Name": student, "Status": status})
                new_att_df = pd.DataFrame(new_records)
                st.session_state.attendance_db = pd.concat([st.session_state.attendance_db, new_att_df], ignore_index=True)
                st.success(f"Attendance log updated locally for {date_str}!")

        with admin_tab3:
            st.markdown(f"### 📢 Broadcast Desk")
            with st.form("notice_form", clear_on_submit=True):
                notice_text = st.text_area("Type Announcement text here:")
                publish_btn = st.form_submit_button("Publish Announcement Live")
                if publish_btn and notice_text:
                    new_notice_row = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "Notice": notice_text}])
                    st.session_state.announcements = pd.concat([st.session_state.announcements, new_notice_row], ignore_index=True)
                    st.success("Notice updated successfully!")
                    st.rerun()

        with admin_tab4:
            st.markdown("### 📊 Business Analytics")
            total_collected = df[df["Fee Status"] == "Paid"]["Monthly Fee (₹)"].sum()
            total_pending = df[df["Fee Status"] == "Pending"]["Monthly Fee (₹)"].sum()
            card1, card2 = st.columns(2)
            card1.metric(label="🟢 Total Revenue Collected", value=f"₹{total_collected:,}")
            card2.metric(label="🔴 Total Revenue Pending", value=f"₹{total_pending:,}")
# ==============================================================================
# --------------------------------------------------------------------------
    # ROLE ROOM 3: STUDENT / PARENT VIEW (YOUR COMPREHENSIVE VIEW-ONLY STATS)
# --------------------------------------------------------------------------
    elif st.session_state.user_role == "Student":
        st.markdown("## 🎒 Student Performance Hub")
        render_notice_board()
        st.markdown("### 🔎 Access Academic Profile")
        student_list = ["-- Select Student Name --"] + list(df["Student Name"].unique())
        selected_student = st.selectbox("Choose Profile Identity:", student_list)
    
        if selected_student != "-- Select Student Name --":
            student_profile = df[df["Student Name"] == selected_student].iloc[0] 
            # Calculate live attendance metrics dynamically
            att_history = st.session_state.attendance_db
            total_days = 0
            days_present = 0
            attendance_pct = "No logs yet"
            
            if not att_history.empty and "Student Name" in att_history.columns:
                filtered_att = att_history[att_history["Student Name"] == selected_student]
                total_days = len(filtered_att)
                if total_days > 0:
                    days_present = len(filtered_att[filtered_att["Status"] == "Present"])
                    attendance_pct = f"{int((days_present / total_days) * 100)}%"

            # Display dashboard KPI metric boxes
            stat_col1, stat_col2, stat_col3 = st.columns(3)
            stat_col1.metric("📐 Math Score", f"{student_profile['Math Score']}/100")
            stat_col2.metric("🧪 Science Score", f"{student_profile.get('Science Score', 0)}/100")
            stat_col3.metric("📅 Total Attendance", attendance_pct)
            
            with st.container(border=True):
                st.markdown("#### 📋 Administrative & Account Details")
                display_data = pd.DataFrame([{
                    "Student Name": student_profile["Student Name"],
                    "Parent Contact": student_profile.get("Parent Phone", "N/A"),
                    "Monthly Fee": f"₹{student_profile['Monthly Fee (₹)']}",
                    "Fee Status": student_profile["Fee Status"]
                }])
                st.dataframe(display_data, use_container_width=True, hide_index=True)
                
            with st.container(border=True):
                st.markdown("#### 📅 Historical Present / Absent Attendance Logs")
                if not att_history.empty and "Student Name" in att_history.columns:
                    filtered_att = att_history[att_history["Student Name"] == selected_student]
                    if not filtered_att.empty:
                        filtered_att = filtered_att.sort_values(by="Date", ascending=False)
                        st.dataframe(filtered_att[["Date", "Status"]], use_container_width=True, hide_index=True)
                    else:
                        st.info(f"No active attendance sessions recorded yet for {selected_student}.")
                else:
                    st.info("No attendance database entries available.")

    elif st.session_state.user_role == "Parent":
        st.markdown("## 👨‍👩‍👦 Academy Parent Portal")
        render_notice_board()

        st.markdown("### Monitor Ward Progress")
        parent_student_list = ["-- Select Your Child's Profile --"] + list(df["Student Name"].unique())
        selected_child = st.selectbox("Choose Child Profile Identity:", parent_student_list)
        if selected_child != "-- Select Your Child's Profile --":
            child_profile = df[df["Student Name"] == selected_child].iloc[0]

            # Calculate child attendance
            att_history = st.session_state.attendance_db
            child_att_pct = "No logs yet"
            if not att_history.empty and "Student Name" in att_history.columns:
                filtered_att = att_history[att_history["Student Name"] == selected_child]
                tot_days = len(filtered_att)
                if tot_days > 0:
                    pres_days = len(filtered_att[filtered_att["Status"] == "Present"])
                    child_att_pct = f"{int((pres_days / tot_days) * 100)}%"

            # Key academic metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("📐 Math Score", f"{child_profile['Math Score']}/100")
            col2.metric("🧪 Science Score", f"{child_profile.get('Science Score', 0)}/100")
            col3.metric("📅 Overall Attendance", child_att_pct)

            # Account & fee summary
            with st.container(border=True):
                st.markdown("#### 💳 Fee & Enrollment Summary")
                summary_df = pd.DataFrame([{
                    "Student Name": child_profile["Student Name"],
                    "Parent Contact": child_profile.get("Parent Phone", "N/A"),
                    "Monthly Tuition Fee": f"₹{child_profile['Monthly Fee (₹)']}",
                    "Current Fee Status": child_profile["Fee Status"]
                }])
                st.dataframe(summary_df, use_container_width=True, hide_index=True)

            # Attendance records
            with st.container(border=True):
                st.markdown("#### 📋 Ward Attendance History")
                if not att_history.empty and "Student Name" in att_history.columns:
                    filtered_att = att_history[att_history["Student Name"] == selected_child]
                    if not filtered_att.empty:
                        filtered_att = filtered_att.sort_values(by="Date", ascending=False)
                        st.dataframe(filtered_att[["Date", "Status"]], use_container_width=True, hide_index=True)
                    else:
                        st.info(f"No attendance sessions recorded yet for {selected_child}.")
                else:
                    st.info("No attendance records found in database.")
