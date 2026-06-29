import streamlit as st
import pandas as pd
from datetime import datetime
import os
import urllib.parse
import requests

# ==============================================================================
# 1. PAGE CONFIGURATION & PREMIUM DESIGN THEMING
# ==============================================================================
st.set_page_config(
    page_title="MathScience Academy Tracker",
    page_icon="🎓",
    layout="centered"
)

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
    [data-testid="stSidebar"] {{
        background-color: #0f172a !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
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
        color: #94a3b8 !important;
        font-weight: 600 !important;
        font-size: 15px !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: #38bdf8 !important;
        font-weight: 700 !important;
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
    .whatsapp-btn {{
        display: inline-flex; align-items: center; justify-content: center;
        background: linear-gradient(135deg, #25D366 0%, #128C7E 100%); color: white !important; font-weight: bold;
        padding: 8px 16px; border-radius: 10px; text-decoration: none; font-size: 13px;
    }}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. HEADER INTERFACE DESIGN
# ==============================================================================
with st.container():
    import base64
    logo_html = ""
    if os.path.exists("logo.jpg"):
        with open("logo.jpg", "rb") as image_file:
            encoded_logo = base64.b64encode(image_file.read()).decode()
            logo_html = f'<img src="data:image/jpeg;base64,{encoded_logo}" style="width: 60px; height: 60px; border-radius: 20%; box-shadow: 0 0 20px rgba(6, 182, 212, 0.4); flex-shrink: 0;">'

    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 15px; margin-top: -10px; margin-bottom: 20px;">
        {logo_html}
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

# ==============================================================================
# 3. RELIABLE CLOUD DATA FETCHING LOGIC
# ==============================================================================
# Helper to read from sheets securely via CSV endpoints
def fetch_cloud_sheet(sheet_name, fallback_df):
    try:
        url = GSHEET_URL + urllib.parse.quote(sheet_name)
        data = pd.read_csv(url)
        if data.empty:
            return fallback_df
        return data
    except Exception:
        return fallback_df

if 'student_db' not in st.session_state:
    st.session_state.student_db = fetch_cloud_sheet("Students", pd.DataFrame({
        "Student Name": ["Rudra", "Supratik", "Vivek", "Ananya", "Arup"],
        "Math Score": [85, 92, 78, 95, 88],
        "Monthly Fee (₹)": [1500, 1500, 1500, 1500, 1500],
        "Fee Status": ["Paid", "Pending", "Paid", "Paid", "Pending"]
    }))

if 'attendance_db' not in st.session_state:
    st.session_state.attendance_db = fetch_cloud_sheet("Attendance", pd.DataFrame(columns=["Date", "Student Name", "Status"]))

if 'announcements' not in st.session_state:
    st.session_state.announcements = fetch_cloud_sheet("Announcements", pd.DataFrame([
        {"Date": datetime.now().strftime("%Y-%m-%d"), "Notice": "Welcome to the new MathScience Academy digital Tuition Portal! 🎉"}
    ]))

TEACHER_REGISTRY = {"Admin Master": "9999", "Sudip Das": "1234"}
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
# 4. SIDEBAR NAVIGATION CONSOLE
# ==============================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#f8fafc; font-size:20px; font-weight:700;'>🧭 Navigation Control</h2>", unsafe_allow_html=True)
    portal_mode = st.radio("🔄 Select Portal Mode:", ["Teacher Dashboard", "Student View", "Parent Portal"])

if portal_mode == "Teacher Dashboard":
    with st.container(border=True):
        st.markdown("### 🔒 Administrative Verification")
        teacher_list = ["-- Select Profile --"] + list(TEACHER_REGISTRY.keys())
        selected_teacher = st.selectbox("Identify Your Teacher Profile:", teacher_list)
        entered_pin = st.text_input("Enter PIN:", type="password", placeholder="****")
        
    if selected_teacher != "-- Select Profile --" and entered_pin == TEACHER_REGISTRY.get(selected_teacher):
        st.toast(f"Welcome back, {selected_teacher}!", icon="🔑")
        
        admin_tab1, admin_tab2, admin_tab3, admin_tab4 = st.tabs([
            "👥 Student Management", "📅 Attendance Desk", "📢 Broadcast Desk", "📊 Financial Analytics"
        ])

        with admin_tab1:
            st.markdown("### 🛠️ Academy Student Management Console")
            
            with st.expander("➕ Add New Student to Roster", expanded=False):
                with st.form("add_student_form", clear_on_submit=True):
                    new_student_name = st.text_input("Full Student Name:")
                    initial_math_score = st.number_input("Initial Math Score:", min_value=0, max_value=100, value=0)
                    assigned_monthly_fee = st.number_input("Assigned Monthly Fee (₹):", min_value=0, value=1500)
                    initial_fee_status = st.selectbox("Current Fee Status:", ["Pending", "Paid"])
                    submit_new_student = st.form_submit_button("Create Student Account")
                    
                    if submit_new_student and new_student_name.strip() != "":
                        new_row = pd.DataFrame([{
                            "Student Name": new_student_name.strip(),
                            "Math Score": int(initial_math_score),
                            "Monthly Fee (₹)": int(assigned_monthly_fee),
                            "Fee Status": initial_fee_status
                        }])
                        st.session_state.student_db = pd.concat([st.session_state.student_db, new_row], ignore_index=True)
                        st.success(f"Registered {new_student_name} to local session. (For continuous multi-device syncing, copy updates to your primary Google Sheet layout).")
                        st.rerun()

            with st.expander("📝 Update Fees, Status, or Math Scores", expanded=False):
                student_to_edit = st.selectbox("Select Student to Modify:", ["-- Choose Student --"] + list(df["Student Name"].unique()))
                if student_to_edit != "-- Choose Student --":
                    student_data = df[df["Student Name"] == student_to_edit].iloc[0]
                    with st.form("edit_student_form"):
                        updated_score = st.number_input("Update Math Score:", min_value=0, max_value=100, value=int(student_data["Math Score"]))
                        updated_fee = st.number_input("Modify Monthly Fee (₹):", min_value=0, value=int(student_data["Monthly Fee (₹)"]))
                        updated_status = st.selectbox("Update Fee Status:", ["Pending", "Paid"], index=["Pending", "Paid"].index(student_data["Fee Status"]))
                        save_edits = st.form_submit_button("Save Changes")
                        
                        if save_edits:
                            idx = st.session_state.student_db[st.session_state.student_db["Student Name"] == student_to_edit].index[0]
                            st.session_state.student_db.at[idx, "Math Score"] = int(updated_score)
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
                    signed_notice = f"{notice_text} (Posted by: {selected_teacher})"
                    new_notice_row = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "Notice": signed_notice}])
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
    else:
        if entered_pin != "": st.error("Incorrect PIN.")
        else: st.warning("Please enter your Verification PIN to unlock dashboard options.")

else:
    st.markdown(f"## 👤 {portal_mode}")
    render_notice_board()
    st.dataframe(df[["Student Name", "Math Score", "Fee Status"]], use_container_width=True, hide_index=True)