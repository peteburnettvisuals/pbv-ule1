import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json
import xml.etree.ElementTree as ET
import google.generativeai as genai

# --- 1. INITIAL SETUP ---
st.set_page_config(page_title="ULE | Skyhigh Coach", layout="wide")

# Style Injector
def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except:
        pass # Fallback if style.css is missing

local_css("style.css")

# Initialize Firestore
creds_info = st.secrets["gcp_service_account"]
credentials = service_account.Credentials.from_service_account_info(creds_info)
db = firestore.Client(database="ule-store1", credentials=credentials)

# Initialize Gemini (Tier 1 / Paid Tier)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# --- 2. DATA DRIVERS ---

def get_lesson_content(node_id):
    """Parses the XML syllabus to find lesson details."""
    try:
        tree = ET.parse("master_syllabus.xml")
        root = tree.getroot()
        for element in root.findall(".//element"):
            if element.get("id") == node_id:
                return {
                    "title": element.find("title").text,
                    "video": element.find("video_url").text
                }
    except Exception:
        return {"title": "Welcome to Skyhigh", "video": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    return {"title": "Lesson Not Found", "video": None}

def get_current_lesson(student_email):
    """Retrieves student profile from Firestore."""
    users_ref = db.collection("students")
    query = users_ref.where("email", "==", student_email).limit(1).stream()
    for doc in query:
        data = doc.to_dict()
        data['id'] = doc.id
        return data
    return None

# --- 3. UI SCREENS ---

def welcome_screen():
    st.title("Welcome to the Universal Learning Engine")
    st.subheader("Skyhigh Demo Edition")

    col_video, col_auth = st.columns([0.6, 0.4], gap="large")

    with col_video:
        st.video("https://www.youtube.com/watch?v=your_skyhigh_welcome")
        st.info("💡 **Tailored Learning:** Enter your email to resume your mission.")

    with col_auth:
        tab_login, tab_reg = st.tabs(["🔄 Resume", "🚀 New Training"])

        with tab_login:
            login_email = st.text_input("Enter your Email to Resume", placeholder="name@company.com")
            if st.button("Resume Progress", use_container_width=True):
                if login_email:
                    st.session_state.student_email = login_email.lower().strip()
                    st.session_state.authenticated = True
                    st.rerun()

        with tab_reg:
            reg_name = st.text_input("Full Name")
            reg_email = st.text_input("Email Address")
            user_context = st.text_area("Your Profile & Goals", placeholder="e.g. Returning to 1985...")
            
            if st.button("Start New Training", use_container_width=True):
                if reg_name and reg_email:
                    payload = {
                        "name": reg_name,
                        "email": reg_email.lower().strip(),
                        "context": user_context,
                        "current_node": "EL-01.1.A",
                        "created_at": firestore.SERVER_TIMESTAMP 
                    }
                    db.collection("students").document(reg_email.lower().strip()).set(payload)
                    st.session_state.student_email = reg_email.lower().strip()
                    st.session_state.authenticated = True
                    st.rerun()

def coach_interface():
    # Fetch Content
    lesson = get_lesson_content(st.session_state.get("current_node", "EL-01.1.A"))

    # Sidebar
    with st.sidebar:
        st.image("ule-skyhigh-logo1.jpg", use_container_width=True)
        st.header("Syllabus Progress")
        st.write(f"Learner: {st.session_state.get('full_name', 'Explorer')}")
        st.progress(15)
        st.write(f"**Current Element:** {st.session_state.get('current_node', 'EL-01.1.A')}")
        st.divider()
        if st.button("🔄 Reset Coach Session", use_container_width=True):
            if "chat_session" in st.session_state: del st.session_state.chat_session
            if "messages" in st.session_state: del st.session_state.messages
            st.rerun()

    # Main UI
    st.header("Guided Training")
    with st.container(border=True):
        st.write(f"📺 **Current Lesson:** {lesson['title']}")
        if lesson['video']:
            st.video(lesson['video'])
    
    # AI Chat Logic
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if not st.session_state.messages:
        try:
            st.session_state.chat_session = model.start_chat(history=[])
            sys_prompt = f"You are the Skyhigh Coach. Student: {st.session_state.full_name}. Goal: {st.session_state.user_context}. Lesson: {lesson['title']}. Introduce the lesson."
            response = st.session_state.chat_session.send_message(sys_prompt)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception:
            st.info("Coach is recalibrating temporal sensors. Please wait 60 seconds.")
            return

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Respond to the coach..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        try:
            response = st.session_state.chat_session.send_message(prompt)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.rerun()
        except Exception:
            st.error("Engine overheating! Please wait a moment.")

# --- 4. RENDER SWITCHBOARD ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    welcome_screen()
else:
    if "user_data" not in st.session_state:
        data = get_current_lesson(st.session_state.student_email)
        if data:
            st.session_state.user_data = data
            st.session_state.current_node = data.get("current_node", "EL-01.1.A")
            st.session_state.user_context = data.get("context", "your goals")
            st.session_state.full_name = data.get("name", "User Name")
    
    coach_interface()