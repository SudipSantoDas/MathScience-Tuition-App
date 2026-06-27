import streamlit as st
import pandas as pd
from datetime import datetime
import os
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# 1. PAGE CONFIGURATION & GLOBAL APP SETTINGS
# ==============================================================================
st.set_page_config(
    page_title="MathScience Academy Tracker",
    page_icon="🎓",
    layout="centered"
)

# Core spreadsheet and brand link configurations
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1DhuNCdpfHNpycppJDzv2SfWmLdf76iOgxuSPXEbOnWM/edit?usp=sharing"
WEBSITE_URL = "https://mathscience.in"

# Custom CSS styling injection for green WhatsApp buttons
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 24px !important; font-weight: 700; }
    .whatsapp-btn {
        display: inline-flex; align-items: center; justify-content: center;
        background-color: #25D366; color: white !important; font-weight: bold;
        padding: 6px 14px; border-radius: 8px; text-decoration: none; font-size: 13px;
    }
    .whatsapp-btn:hover { background-color: #128C7E; color: white !important; }
</style>
""", unsafe_allow_html=True)

# Main Screen Header Layout containing your custom logo picture
with st.container():
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=110)
    st.markdown(f"""
    <h1 style="color: #0f172a; font-family: 'Inter', system-ui, sans-serif; font-size: 26px; font-weight: 800; margin-top: 5px; margin-bottom: 0px;">MathScience Tuition App</h1>
    <div style="display: inline-block; margin-top: 5px; margin-bottom: 15px; padding: 4px 12px; background-color: #e0f2fe; border-radius: 20px;">
        <p style="color: #0369a1; font-family: 'Inter', system-ui, sans-serif; font-size: 11px; font-weight: 700; margin: 0; text-transform: uppercase;">📚 PRIVATE TUITION & STUDENT PORTAL</p>
    </div>
    <div style="margin-bottom: 20px;">
        <a href="{WEBSITE_URL}" target="_blank" style="display: inline-block; background: #0f172a; color: #ffffff !important; font-family: 'Inter', system-ui, sans-serif; font-size: 13px; font-weight: 600; padding: 9px 18px; border-radius: 10px; text-decoration: none;">🌐 Visit Academy Portal</a>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. LIVE CLOUD DATABASE STORAGE CONNECTOR (GOOGLE SHEETS)
# ==============================================================================
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 1. Fetch Students Database
    try:
        st.session_state.student_db = conn.read(spreadsheet=GSHEET_URL, worksheet="Students")
        if st.session_state.student_db.empty or "Student Name" not in st.session_state.student_db.columns:
            raise ValueError
    except Exception:
        st.session_state.student_db = pd.DataFrame({
            "Student Name": ["Rudra", "Supratik", "Vivek", "Ananya", "Arup"],
            "Math Score": [85, 92, 78, 95, 88],
            "Monthly Fee (₹)": [1500, 1500, 1500, 1500, 1500],
            "Fee Status": ["Paid", "Pending", "Paid", "Paid", "Pending"]
        })

    # 2. Fetch Attendance Log
    try:
        st.session_state.attendance_db = conn.read(spreadsheet=GSHEET_URL, worksheet="Attendance")
        if st.session_state.attendance_db.empty or "Student Name" not in st.session_state.attendance_db.columns:
            raise ValueError
    except Exception:
        st.session_state.attendance_db = pd.DataFrame(columns=["Date", "Student Name", "Status"])

    # 3. Fetch Announcements
    try:
        st.session_state.announcements = conn.read(spreadsheet=GSHEET_URL, worksheet="Announcements")
        if st.session_state.announcements.empty or "Notice" not in st.session_state.announcements.columns:
            raise ValueError
    except Exception:
        st.session_state.announcements = pd.DataFrame([
            {"Date": datetime.now().strftime("%Y-%m-%d"), "Notice": "Welcome to the new MathScience Academy digital Tuition Portal! 🎉"}
        ])

except Exception as e:
    st.error("Cloud Database Connection Pending. Please verify your Google Sheet sharing link configurations.")
    st.stop()

# Multi-Teacher Verification Dictionary
TEACHER_REGISTRY = {
    "Admin Master": "9999",
    "Sudip Das": "1234",
    "Ananya Sen": "5678",
    "Vivek Sharma": "4321"
}

df = st.session_state.student_db

def render_notice_board():
    notices_df = st.session_state.announcements
    if not notices_df.empty:
        latest_notice = notices_df.iloc[-1]
        with st.container(border=True):
            st.markdown(f"### 📢 Academy Notice Board (`{latest_notice['Date']}`)")
            st.info(f"👉 **Latest Update:** {latest_notice['Notice']}")

# ==============================================================================
# 3. SIDEBAR NAVIGATION CONSOLE & CARD CONTROLS
# ==============================================================================
with st.sidebar:
    st.markdown("## 🧭 Navigation Control")
    portal_mode = st.radio(
        "🔄 Select Portal Mode:", 
        ["Teacher Dashboard", "Student View", "Parent Portal"]
    )

# ------------------------------------------------------------------------------
# MODE MODULE: TEACHER INTERFACE
# ------------------------------------------------------------------------------
if portal_mode == "Teacher Dashboard":
    with st.container(border=True):
        st.markdown("### 🔒 Administrative Multi-User Verification")
        teacher_list = ["-- Select Profile --"] + list(TEACHER_REGISTRY.keys())
        selected_teacher = st.selectbox("Identify Your Teacher Profile:", teacher_list)
        entered_pin = st.text_input("Enter Your Unique Secret PIN:", type="password", placeholder="****")
        
    if selected_teacher != "-- Select Profile --" and entered_pin == TEACHER_REGISTRY.get(selected_teacher):
        st.toast(f"Welcome back, {selected_teacher}! Identity Verified.", icon="🔑")
        
        # Form 1: Broadcast Notice Announcements Desk
        with st.container(border=True):
            st.markdown(f"### 📢 Broadcast Desk (Publisher: {selected_teacher})")
            with st.form("notice_form", clear_on_submit=True):
                notice_text = st.text_area("Type Announcement text here:", placeholder="Enter updates...")
                publish_btn = st.form_submit_button("Publish Announcement to All Portals", use_container_width=True)
                
                if publish_btn and notice_text:
                    signed_notice = f"{notice_text} (Posted by: {selected_teacher})"
                    new_notice_row = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "Notice": signed_notice}])
                    st.session_state.announcements = pd.concat([st.session_state.announcements, new_notice_row], ignore_index=True)
                    
                    # 🌐 Update Cloud Google Sheet instantly
                    conn.update(spreadsheet=GSHEET_URL, worksheet="Announcements", data=st.session_state.announcements)
                    st.success("Announcement updated on cloud Google Sheet successfully!")
                    st.clear_cache()
                    st.rerun()

        # Form 2: Mobile Photo Uploader Profiler
        with st.container(border=True):
            st.markdown("### 📷 Upload Student Photo directly from Phone")
            student_options = ["-- Choose Student --"] + list(df["Student Name"].unique())
            target_pic_student = st.selectbox("Select target student identity:", student_options)
            uploaded_file = st.file_uploader("Take Photo or Choose Gallery file:", type=["jpg", "jpeg", "png"])
            
            if st.button("Save Photo to Profile", use_container_width=True):
                if target_pic_student != "-- Choose Student --" and uploaded_file is not None:
                    os.makedirs("student_pics", exist_ok=True)
                    file_ext = uploaded_file.name.split(".")[-1].lower()
                    save_path = f"student_pics/{target_pic_student.strip()}.{file_ext}"
                    
                    for ext in ["jpg", "jpeg", "png"]:
                        alt_path = f"student_pics/{target_pic_student.strip()}.{ext}"
                        if os.path.exists(alt_path):
                            os.remove(alt_path)
                            
                    with open(save_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.success(f"Successfully linked image asset to {target_pic_student}!")
                    st.rerun()
                else:
                    st.warning("Please specify a student name and attach an image file first.")

        # Section 3: Revenue Analytics Counter
        with st.container(border=True):
            st.markdown("### 📊 Business & Revenue Analytics")
            total_collected = df[df["Fee Status"] == "Paid"]["Monthly Fee (₹)"].sum()
            total_pending = df[df["Fee Status"] == "Pending"]["Monthly Fee (₹)"].sum()
            
            card1, card2 = st.columns(2)
            card1.metric(label="🟢 Total Revenue Collected", value=f"₹{total_collected:,}")
            card2.metric(label="🔴 Total Revenue Pending", value=f"₹{total_pending:,}")

        # Form 4: Attendance Taking Manager Checklist
        with st.container(border=True):
            st.markdown("### 📅 Take Attendance")
            selected_date = st.date_input("Select Date for Attendance:", datetime.now().date())
            date_str = selected_date.strftime("%Y-%m-%d")
            
            st.write("Mark present students:")
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
                old_history = st.session_state.attendance_db
                
                if not old_history.empty and "Date" in old_history.columns:
                    old_history = old_history[old_history["Date"] != date_str]
                    
                st.session_state.attendance_db = pd.concat([old_history, new_att_df], ignore_index=True)
                
                # 🌐 Update Cloud Google Sheet instantly
                conn.update(spreadsheet=GSHEET_URL, worksheet="Attendance", data=st.session_state.attendance_db)
                st.success(f"Attendance cloud log synced for {date_str} successfully!")
                st.clear_cache()
                st.rerun()

        # Section 5: Admin Roster Overview Grid
        with st.container(border=True):
            st.markdown("### 📋 Active Student Roster & Fee Desk")
            st.dataframe(df, use_container_width=True, hide_index=True)

    else:
        if entered_pin != "":
            st.error("Incorrect PIN. Please try again.")
        else:
            st.warning("Please enter your registered Teacher Verification PIN to unlock dashboard options.")

# ==============================================================================
# MODE MODULE: STUDENT & PARENT DISPLAY MODES
# ==============================================================================
else:
    st.markdown(f"## 👤 {portal_mode}")
    render_notice_board()
    
    with st.container(border=True):
        st.markdown("### 📈 Your Academic Performance Profile")
        st.dataframe(df[["Student Name", "Math Score", "Fee Status"]], use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.markdown("### 📅 Verified Historical Attendance Ledger")
        att_history = st.session_state.attendance_db
        if not att_history.empty:
            st.dataframe(att_history, use_container_width=True, hide_index=True)
        else:
            st.info("No historical attendance marks logged in database yet.")

    with st.container(border=True):
        st.markdown("### 💬 Direct Academy Support Desk")
        st.write("Connect with the teaching staff directly via WhatsApp:")
        
        for index, row in df.iterrows():
            student = row["Student Name"]
            score = row["Math Score"]
            status = row["Fee Status"]
            
            text_msg = f"Hello Sir, checking metrics for student: {student}. Score: {score}/100. Fee Status: {status}."
            encoded_msg = text_msg.replace(" ", "%20")
            whatsapp_url = f"https://wa.me/919999999999?text={encoded_msg}"
            
            col_name, col_btn = st.columns([0.4, 0.6])
            with col_name:
                st.markdown(f"👤 **{student}**")
            with col_btn:
                st.markdown(f'<a href="{whatsapp_url}" target="_blank" class="whatsapp-btn">💬 Chat on WhatsApp</a>', unsafe_allow_html=True)