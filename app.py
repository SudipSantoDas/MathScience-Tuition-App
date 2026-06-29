import streamlit as st
import pandas as pd
from datetime import datetime
import os
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# 1. PAGE CONFIGURATION & PREMIUM DESIGN THEMING (CSS TEXT RE-CONTRAST)
# ==============================================================================
st.set_page_config(
    page_title="MathScience Academy Tracker",
    page_icon="🎓",
    layout="centered"
)

# Core spreadsheet and brand link configurations
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1DhuNCdpfHNpycppJDzv2SfWmLdf76iOgxuSPXEbOnWM/edit?usp=sharing"
WEBSITE_URL = "https://mathscience.in"

# 🎨 Premium UI Custom Engine Styling (Text Visibility & High Contrast Fix)
st.markdown(f"""
<style>
    /* Global App Canvas Soft Gradient Background */
    .stApp {{
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%) !important;
        background-attachment: fixed !important;
    }}
    
    /* ⚡ Same-Line Flex Header Layout Wrapper */
    .header-flex-container {{
        display: flex;
        align-items: center;
        gap: 15px;
        margin-top: -10px;
        margin-bottom: 20px;
        animation: fadeIn 1s ease-out;
    }}
    
    /* Centerpiece Logo Premium Small Glow Filter for Same-Line Grid */
    .logo-container img {{
        border-radius: 20%;
        box-shadow: 0 0 20px rgba(6, 182, 212, 0.4);
    }}
    
    /* ✨ Stunning Gradient Text Styling for Title */
    .gradient-title {{
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 28px;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin: 0;
        background: linear-gradient(135deg, #ffffff 30%, #38bdf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    
    /* Frosted Glass Container Layout Card */
    .glass-card {{
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 24px;
        padding: 25px 20px;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        margin-bottom: 25px;
        animation: fadeIn 1s ease-out;
    }}
    
    /* 🔒 High-Contrast Form Text Corrections */
    h3, .stMarkdown h3 p, [data-testid="stMarkdownContainer"] h3 {{
        color: #f8fafc !important;
        font-weight: 700 !important;
    }}
    
    /* Force Streamlit input labels to be bright and legible */
    label, [data-testid="stWidgetLabel"] p {{
        color: #cbd5e1 !important;
        font-weight: 600 !important;
        font-size: 14px !important;
    }}
    
    /* Customize the sub-warning banner color tone */
    .stAlert {{
        background-color: rgba(234, 179, 8, 0.1) !important;
        border: 1px solid rgba(234, 179, 8, 0.3) !important;
        color: #fde047 !important;
    }}
    
    /* Vibrant Blue Gradient Portal Action Button */
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
        transition: all 0.3s ease;
        letter-spacing: 0.5px;
    }}
    .portal-btn:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(6, 182, 212, 0.5);
    }}
    
    /* Premium Metrics Adjustments */
    [data-testid="stMetricValue"] {{ font-size: 26px !important; font-weight: 800; color: #06b6d4 !important; }}
    [data-testid="stMetricLabel"] {{ color: #94a3b8 !important; }}
    
    .whatsapp-btn {{
        display: inline-flex; align-items: center; justify-content: center;
        background: linear-gradient(135deg, #25D366 0%, #128C7E 100%); color: white !important; font-weight: bold;
        padding: 8px 16px; border-radius: 10px; text-decoration: none; font-size: 13px;
        box-shadow: 0 4px 12px rgba(37, 211, 102, 0.2); transition: all 0.2s ease;
    }}
    .whatsapp-btn:hover {{ transform: translateY(-1px); box-shadow: 0 6px 16px rgba(37, 211, 102, 0.4); }}
    
    h1, h2, h3, p, span {{ font-family: 'Inter', system-ui, sans-serif; }}
    
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(10px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
</style>
""", unsafe_allow_html=True)
# ==============================================================================
# 2. UPDATED HEADER INTERFACE DESIGN (LOGO AND GRADIENT TITLE ON SAME LINE)
# ==============================================================================
with st.container():
    # We combine the logo and text into a unified horizontal layout
    col_logo, col_text = st.columns([0.22, 0.78], vertical_alignment="center")
    
    with col_logo:
        if os.path.exists("logo.jpg"):
            st.markdown('<div class="logo-container">', unsafe_allow_html=True)
            st.image("logo.jpg", width=75)
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col_text:
        st.markdown('<h1 class="gradient-title">MathScience Tuition</h1>', unsafe_allow_html=True)
        
    # Sub-action sub-header info elements inside the clean card
    st.markdown(f"""
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
# 3. LIVE CLOUD DATABASE STORAGE CONNECTOR (GOOGLE SHEETS)
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
        st.markdown(f"""
        <div style="background: rgba(2, 132, 199, 0.1); border-left: 4px solid #0284c7; padding: 15px; border-radius: 12px; margin-bottom: 20px;">
            <h4 style="margin: 0 0 5px 0; color: #38bdf8; font-size: 16px;">📢 Academy Notice Board ({latest_notice['Date']})</h4>
            <p style="margin: 0; color: #cbd5e1; font-size: 14px;">{latest_notice['Notice']}</p>
        </div>
        """, unsafe_allow_html=True)

# ==============================================================================
# 4. SIDEBAR NAVIGATION CONSOLE & CARD CONTROLS
# ==============================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#f8fafc; font-size:20px; font-weight:700; margin-bottom:15px;'>🧭 Navigation Control</h2>", unsafe_allow_html=True)
    portal_mode = st.radio(
        "🔄 Select Portal Mode:", 
        ["Teacher Dashboard", "Student View", "Parent Portal"]
    )

# ------------------------------------------------------------------------------
# MODE MODULE: TEACHER INTERFACE
# ------------------------------------------------------------------------------
if portal_mode == "Teacher Dashboard":
    with st.container(border=True):
        st.markdown("### 🔒 Administrative Verification")
        teacher_list = ["-- Select Profile --"] + list(TEACHER_REGISTRY.keys())
        selected_teacher = st.selectbox("Identify Your Teacher Profile:", teacher_list)
        entered_pin = st.text_input("Enter Your Unique Secret PIN:", type="password", placeholder="****")
        
    if selected_teacher != "-- Select Profile --" and entered_pin == TEACHER_REGISTRY.get(selected_teacher):
        st.toast(f"Welcome back, {selected_teacher}!", icon="🔑")
        
        # Form 1: Broadcast Notice Announcements Desk
        with st.container(border=True):
            st.markdown(f"### 📢 Broadcast Desk (Publisher: {selected_teacher})")
            with st.form("notice_form", clear_on_submit=True):
                notice_text = st.text_area("Type Announcement text here:", placeholder="Enter updates...")
                publish_btn = st.form_submit_button("Publish Announcement Live", use_container_width=True)
                
                if publish_btn and notice_text:
                    signed_notice = f"{notice_text} (Posted by: {selected_teacher})"
                    new_notice_row = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "Notice": signed_notice}])
                    st.session_state.announcements = pd.concat([st.session_state.announcements, new_notice_row], ignore_index=True)
                    
                    conn.update(spreadsheet=GSHEET_URL, worksheet="Announcements", data=st.session_state.announcements)
                    st.success("Announcement updated on cloud Google Sheet successfully!")
                    st.clear_cache()
                    st.rerun()

        # Form 2: Mobile Photo Uploader Profiler
        with st.container(border=True):
            st.markdown("### 📷 Upload Student Photo")
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

        # Section 3: Revenue Analytics Counter
        with st.container(border=True):
            st.markdown("### 📊 Business Analytics")
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
                
                conn.update(spreadsheet=GSHEET_URL, worksheet="Attendance", data=st.session_state.attendance_db)
                st.success(f"Attendance cloud log synced successfully!")
                st.clear_cache()
                st.rerun()

        # Section 5: Admin Roster Overview Grid
        with st.container(border=True):
            st.markdown("### 📋 Student Roster & Fee Desk")
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        if entered_pin != "":
            st.error("Incorrect PIN. Please try again.")
        else:
            st.warning("Please enter your Verification PIN to unlock dashboard options.")

# ------------------------------------------------------------------------------
# MODE MODULE: STUDENT & PARENT DISPLAY MODES
# ------------------------------------------------------------------------------
else:
    st.markdown(f"<h2 style='color: #ffffff; font-weight:700; font-size:22px; margin-bottom:15px;'>👤 {portal_mode}</h2>", unsafe_allow_html=True)
    render_notice_board()
    
    with st.container(border=True):
        st.markdown("### 📈 Your Academic Performance Profile")
        st.dataframe(df[["Student Name", "Math Score", "Fee Status"]], use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.markdown("### 📅 Historical Attendance Ledger")
        att_history = st.session_state.attendance_db
        if not att_history.empty:
            st.dataframe(att_history, use_container_width=True, hide_index=True)
        else:
            st.info("No historical attendance marks logged yet.")

    with st.container(border=True):
        st.markdown("### 💬 Direct Academy Support Desk")
        st.write("Connect with staff via WhatsApp:")
        
        for index, row in df.iterrows():
            student = row["Student Name"]
            score = row["Math Score"]
            status = row["Fee Status"]
            
            text_msg = f"Hello Sir, checking metrics for student: {student}. Score: {score}/100. Fee Status: {status}."
            encoded_msg = text_msg.replace(" ", "%20")
            whatsapp_url = f"https://wa.me/919999999999?text={encoded_msg}"
            
            col_name, col_btn = st.columns([0.4, 0.6])
            with col_name:
                st.markdown(f"<p style='color: #e2e8f0; margin-top:5px;'>👤 <b>{student}</b></p>", unsafe_allow_html=True)
            with col_btn:
                st.markdown(f'<a href="{whatsapp_url}" target="_blank" class="whatsapp-btn">💬 Chat on WhatsApp</a>', unsafe_allow_html=True)