import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# 🌐 Establish secure connection to your Google Sheets database
conn = st.connection("gsheets", type=GSheetsConnection)

# 📋 Load your data tables directly from the spreadsheet tabs
try:
    student_df = conn.read(worksheet="student_database")
    attendance_df = conn.read(worksheet="attendance_log")
    announcements_df = conn.read(worksheet="announcements")
except Exception as e:
    st.error("Database connection configuration initializing... Please verify your sheet tab names match precisely.")

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

# Custom CSS styling injection for high-fidelity interactive green buttons
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 24px !important; font-weight: 700; }
    .whatsapp-btn {
        display: inline-flex; align-items: center; justify-content: center;
        background-color: #25D366; color: white !important; font-weight: bold;
        padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: 14px;
        margin-top: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .whatsapp-btn:hover { background-color: #128C7E; color: white !important; text-decoration: none; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# PREMIUM ALIGNED HEADER LAYOUT
# ==============================================================================
with st.container():
    # Verify image presence
    logo_exists = os.path.exists("logo.jpg")
    
    # Title row with image inline
    st.markdown(f"""
    <div style="display: flex; align-items: center; justify-content: flex-start; gap: 12px; margin-bottom: 12px; padding-top: 5px;">
        {"<img src='data:image/jpeg;base64," + __import__("base64").b64encode(open("logo.jpg", "rb").read()).decode() + "' style='width: 48px; height: 48px; border-radius: 10px; object-fit: cover;' />" if logo_exists else ""}
        <h1 style="color: #0f172a; font-family: 'Inter', system-ui, sans-serif; font-size: 26px; font-weight: 800; margin: 0px; padding: 0px; letter-spacing: -0.5px;">MathScience Tuition App</h1>
    </div>
    """, unsafe_allow_html=True)
        
    # Badges and link row directly underneath
    st.markdown(f"""
    <div style="margin-bottom: 25px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
        <div style="display: inline-block; padding: 5px 14px; background-color: #e0f2fe; border-radius: 20px; vertical-align: middle;">
            <p style="color: #0369a1; font-family: 'Inter', system-ui, sans-serif; font-size: 11px; font-weight: 700; margin: 0; text-transform: uppercase; letter-spacing: 0.3px;">📚 PRIVATE TUITION & STUDENT PORTAL</p>
        </div>
        <a href="{WEBSITE_URL}" target="_blank" style="display: inline-block; background: #0f172a; color: #ffffff !important; font-family: 'Inter', system-ui, sans-serif; font-size: 12px; font-weight: 600; padding: 6px 14px; border-radius: 8px; text-decoration: none; box-shadow: 0 2px 4px rgba(0,0,0,0.05); vertical-align: middle;">🌐 Visit Academy Portal</a>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. CLOUD CONNECTOR READ PIPELINES & HARD DISK LOCAL CSV FALLBACKS
# ==============================================================================
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # [DATAFRAME PIPELINE 1]: STABLE STUDENTS DATA MANAGEMENT LAYER
    try:
        st.session_state.student_db = conn.read(spreadsheet=GSHEET_URL, worksheet="Students")
        if st.session_state.student_db.empty or "Student Name" not in st.session_state.student_db.columns:
            raise ValueError
    except Exception:
        if os.path.exists("student_database.csv"):
            st.session_state.student_db = pd.read_csv("student_database.csv")
        else:
            st.session_state.student_db = pd.DataFrame({
                "Student Name": ["Rudra", "Supratik", "Vivek", "Ananya", "Arup"],
                "Math Score": [85, 92, 78, 95, 88],
                "Monthly Fee (₹)": [1500, 1500, 1500, 1500, 1500],
                "Fee Status": ["Paid", "Pending", "Paid", "Paid", "Pending"]
            })
            st.session_state.student_db.to_csv("student_database.csv", index=False)

    # [DATAFRAME PIPELINE 2]: STABLE HISTORICAL ATTENDANCE TRACKING LAYER
    try:
        st.session_state.attendance_db = conn.read(spreadsheet=GSHEET_URL, worksheet="Attendance")
        if st.session_state.attendance_db.empty or "Student Name" not in st.session_state.attendance_db.columns:
            raise ValueError
    except Exception:
        if os.path.exists("attendance_log.csv"):
            st.session_state.attendance_db = pd.read_csv("attendance_log.csv")
        else:
            st.session_state.attendance_db = pd.DataFrame(columns=["Date", "Student Name", "Status"])
            st.session_state.attendance_db.to_csv("attendance_log.csv", index=False)

    # [DATAFRAME PIPELINE 3]: STABLE BULLETIN BOARD ANNOUNCEMENTS LAYER
    try:
        st.session_state.announcements = conn.read(spreadsheet=GSHEET_URL, worksheet="Announcements")
        if st.session_state.announcements.empty or "Notice" not in st.session_state.announcements.columns:
            raise ValueError
    except Exception:
        if os.path.exists("announcements.csv"):
            st.session_state.announcements = pd.read_csv("announcements.csv")
        else:
            st.session_state.announcements = pd.DataFrame([
                {"Date": datetime.now().strftime("%Y-%m-%d"), "Notice": "Welcome to the new MathScience Academy digital Tuition Portal! 🎉"}
            ])
            st.session_state.announcements.to_csv("announcements.csv", index=False)

except Exception as e:
    st.error("Cloud Database Connection Pending. Verify your active internet link and configuration settings.")
    st.stop()


# ==============================================================================
# 3. VERIFICATION REGISTRIES & CORE HELPER INTERFACE ROUTINES
# ==============================================================================
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
# 4. SIDEBAR NAVIGATION CONSOLE & SECURE LOGIN GATEWAY
# ==============================================================================
with st.sidebar:
    st.markdown("## 🧭 Navigation Control")
    portal_mode = st.radio(
        "🔄 Select Portal Mode:", 
        ["Teacher Dashboard", "Student View", "Parent Portal"]
    )
    
    st.markdown("---")
    
    # MOVED HERE: Verification inputs are now locked tightly inside the sidebar
    st.markdown("### 🔒 Multi-User Verification")
    teacher_list = ["-- Select Profile --"] + list(TEACHER_REGISTRY.keys())
    selected_teacher = st.selectbox("Identify Your Teacher Profile:", teacher_list)
    entered_pin = st.text_input("Enter Unique Secret PIN:", type="password", placeholder="****")

st.markdown("---")


# ==============================================================================
# 5. DYNAMIC PORTAL DESK MODULAR LAYOUT ENGINES
# ==============================================================================

if portal_mode == "Teacher Dashboard":
    # Check authorization first inside the sidebar variable states
    if selected_teacher != "-- Select Profile --" and entered_pin == TEACHER_REGISTRY.get(selected_teacher):
        st.toast(f"Welcome back, {selected_teacher}! Identity Verified.", icon="🔑")
        
        # ROSTER MANAGEMENT CONTROLS (ADD, UPDATE FEE, DELETE)
        with st.container(border=True):
            st.markdown("### ⚙️ Teacher Operations & Student Management")
            tab1, tab2, tab3 = st.tabs(["➕ Add Student", "✏️ Change/Update Monthly Fee", "❌ Delete Student"])
            
            # TAB 1: ADD NEW STUDENT
            with tab1:
                with st.form("add_student_form", clear_on_submit=True):
                    new_name = st.text_input("Enter Student Full Name:")
                    new_score = st.number_input("Initial Math Score:", min_value=0, max_value=100, value=80)
                    new_fee = st.number_input("Monthly Tuition Fee (₹):", min_value=0, value=1500, step=100)
                    new_status = st.selectbox("Fee Status:", ["Paid", "Pending"])
                    submit_add = st.form_submit_button("Add Student to Database", use_container_width=True)
                    
                    if submit_add and new_name:
                        new_row = pd.DataFrame([{
                            "Student Name": new_name.strip(),
                            "Math Score": int(new_score),
                            "Monthly Fee (₹)": int(new_fee),
                            "Fee Status": new_status
                        }])
                        st.session_state.student_db = pd.concat([st.session_state.student_db, new_row], ignore_index=True)
                        st.session_state.student_db.to_csv("student_database.csv", index=False)
                        st.success(f"Successfully added student: {new_name}")
                        st.rerun()

            # TAB 2: UPDATE MONTHLY FEE
            with tab2:
                with st.form("update_fee_form"):
                    select_student_fee = st.selectbox("Select Student to Update:", df["Student Name"].unique())
                    updated_fee = st.number_input("Modify Monthly Fee (₹):", min_value=0, value=1500, step=100)
                    updated_status = st.selectbox("Update Fee Ledger Status:", ["Paid", "Pending"])
                    submit_update = st.form_submit_button("Update Fee Record Details", use_container_width=True)
                    
                    if submit_update:
                        st.session_state.student_db.loc[st.session_state.student_db["Student Name"] == select_student_fee, "Monthly Fee (₹)"] = int(updated_fee)
                        st.session_state.student_db.loc[st.session_state.student_db["Student Name"] == select_student_fee, "Fee Status"] = updated_status
                        st.session_state.student_db.to_csv("student_database.csv", index=False)
                        st.success(f"Updated registration records for {select_student_fee} successfully!")
                        st.rerun()

            # TAB 3: DELETE STUDENT PROFILE
            with tab3:
                select_student_del = st.selectbox("Choose Student Profile to Delete:", ["-- Select Student --"] + list(df["Student Name"].unique()))
                confirm_check = st.checkbox("⚠️ Check this box to confirm total profile deletion")
                submit_delete = st.button("Permanently Remove Student From System", use_container_width=True, type="primary")
                
                if submit_delete:
                    if select_student_del != "-- Select Student --" and confirm_check:
                        st.session_state.student_db = st.session_state.student_db[st.session_state.student_db["Student Name"] != select_student_del]
                        st.session_state.student_db.to_csv("student_database.csv", index=False)
                        st.success(f"Profile records for {select_student_del} completely erased.")
                        st.rerun()
                    else:
                        st.warning("Please select a student and click the checkbox to confirm deletion.")

        # BULLETIN BROADCAST DESK
        with st.container(border=True):
            st.markdown(f"### 📢 Broadcast Desk (Publisher: {selected_teacher})")
            with st.form("notice_form", clear_on_submit=True):
                notice_text = st.text_area("Type Announcement text here:", placeholder="Enter updates...")
                publish_btn = st.form_submit_button("Publish Announcement to All Portals", use_container_width=True)
                
                if publish_btn and notice_text:
                    signed_notice = f"{notice_text} (Posted by: {selected_teacher})"
                    new_notice_row = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "Notice": signed_notice}])
                    st.session_state.announcements = pd.concat([st.session_state.announcements, new_notice_row], ignore_index=True)
                    st.session_state.announcements.to_csv("announcements.csv", index=False)
                    st.success("Announcement published live successfully!")
                    st.rerun()

        # MOBILE IMAGE PROFILE UPLOADER
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

        # REVENUE LEDGER METRICS CARDS
        with st.container(border=True):
            st.markdown("### 📊 Business & Revenue Analytics")
            total_collected = df[df["Fee Status"] == "Paid"]["Monthly Fee (₹)"].sum()
            total_pending = df[df["Fee Status"] == "Pending"]["Monthly Fee (₹)"].sum()
            
            card1, card2 = st.columns(2)
            card1.metric(label="🟢 Total Revenue Collected", value=f"₹{total_collected:,}")
            card2.metric(label="🔴 Total Revenue Pending", value=f"₹{total_pending:,}")

        # OPERATIONS ATTENDANCE LOGGER MATRIX
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
                st.session_state.attendance_db.to_csv("attendance_log.csv", index=False)
                st.success(f"Attendance log updated for {date_str} successfully!")

        # ACTIVE ADMINISTRATIVE ROSTER DATA GRID
        with st.container(border=True):
            st.markdown("### 📋 Active Student Roster & Fee Desk")
            st.dataframe(df, use_container_width=True, hide_index=True)

    else:
        if entered_pin != "":
            st.sidebar.error("❌ Incorrect PIN. Try again.")
        else:
            st.warning("🔒 Please complete your verification profile inside the sidebar menu to unlock administrative access.")
        render_notice_board()

# ------------------------------------------------------------------------------
# PORTAL MODULE DIRECTION: SECURE STUDENT & PARENT DISPLAY PLATFORMS
# ------------------------------------------------------------------------------
else:
    st.markdown(f"## 👤 {portal_mode}")
    render_notice_board()
    
    # SCORES REPORT DESK
    with st.container(border=True):
        st.markdown("### 📈 Your Academic Performance Profile")
        st.dataframe(df[["Student Name", "Math Score", "Fee Status"]], use_container_width=True, hide_index=True)

    # COMPREHENSIVE ATTENDANCE RECORDS LOG LEDGER
    with st.container(border=True):
        st.markdown("### 📅 Verified Historical Attendance Ledger")
        att_history = st.session_state.attendance_db
        if not att_history.empty:
            st.dataframe(att_history, use_container_width=True, hide_index=True)
        else:
            st.info("No historical attendance marks logged in database yet.")

    # COMMUNICATIONS HUB ENGINE (WHATSAPP SMART LINKS)
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