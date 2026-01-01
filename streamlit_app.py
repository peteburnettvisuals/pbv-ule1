import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json
import xml.etree.ElementTree as ET
import google.generativeai as genai

# Use the API key from your secrets
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Specify the model at the point of interaction
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# --- 1. INITIAL SETUP ---
st.set_page_config(page_title="ULE | Skyhigh Coach", layout="wide")

# Style Injector
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css("style.css")

# Initialize Firestore
creds_info = st.secrets["gcp_service_account"]
credentials = service_account.Credentials.from_service_account_info(creds_info)
db = firestore.Client(database="ule-store1", credentials=credentials)

# Configure Gemini
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# --- 2. DATA HELPER FUNCTIONS ---

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

# --- 3. STATE MANAGEMENT ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_node" not in st.session_state:
    st.session_state.current_node = "EL-01.1.A"
if "full_name" not in st.session_state:
    st.session_state.full_name = "User Name"

# --- 4. UI SCREENS ---

def welcome_screen():
    st.title("Welcome to the Universal Learning Engine")
    st.subheader("Skyhigh Demo Edition")

    col_video, col_auth = st.columns([0.6, 0.4], gap="large")

    with col_video:
        st.video("https://www.youtube.com/watch?v=your_skyhigh_welcome")
        st.info("💡 **Tailored Learning:** Your email allows us to save your progress exactly where you left off.")

    with col_auth:
        tab_login, tab_reg = st.tabs(["🔄 Resume", "🚀 New Training"])

        with tab_login:
            login_email = st.text_input("Enter your Email to Resume", placeholder="name@company.com")
            if st.button("Resume Progress", use_container_width=True):
                if login_email:
                    st.session_state.student_email = login_email.lower().strip()
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.warning("Please enter your email address.")

        with tab_reg:
            reg_name = st.text_input("Full Name")
            reg_email = st.text_input("Email Address")
            user_context = st.text_area("Your Profile & Goals", placeholder="Tell us what you want to achieve...")
            
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
                    st.session_state.user_context = user_context
                    st.session_state.authenticated = True
                    st.rerun()

def coach_interface():
    # 1. Sidebar & XML Lookup (Keep your existing code here)
    with st.sidebar:
        st.image("ule-skyhigh-logo1.jpg", use_container_width=True)
        st.header("Syllabus Progress")
        st.write(f"Learner: {st.session_state.full_name}")
        st.progress(15)
        st.write(f"**Current Element:** {st.session_state.current_node}")
        st.divider()
        st.info("Instructor-Led Mode: Active")

    lesson = get_lesson_content(st.session_state.current_node)
    st.header("Guided Training")
    
    with st.container(border=True):
        st.write(f"📺 **Current Lesson:** {lesson['title']}")
        if lesson['video']:
            st.video(lesson['video'])
    
    # 2. INITIALIZE AI SESSION
    if "chat_session" not in st.session_state:
        # We prime the AI with Marty's specific goal (e.g., getting back to 1985)
        system_instruction = f"""
        You are the Skyhigh AI Flight Instructor. 
        Student Name: {st.session_state.full_name}
        Student Goal: {st.session_state.user_context}
        Current Lesson: {lesson['title']}
        
        Introduce yourself and this lesson. Specifically explain how mastering 
        '{lesson['title']}' will help them achieve their goal: '{st.session_state.user_context}'.
        Keep it professional, encouraging, and brief.
        """
        
        # Start the chat session
        st.session_state.chat_session = model.start_chat(history=[])
        
        # Get the very first personalized message from the AI
        response = st.session_state.chat_session.send_message(system_instruction)
        st.session_state.messages = [{"role": "assistant", "content": response.text}]

    # 3. DISPLAY CHAT HISTORY
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    # 4. HANDLE USER INPUT & AI RESPONSE
    if prompt := st.chat_input("Respond to the coach...", key="main_chat_input"):
        # Add user message to UI
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        
        # Send message to Gemini and get real-time response
        response = st.session_state.chat_session.send_message(prompt)
        
        # Add AI message to UI
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        st.chat_message("assistant").write(response.text)

# --- 5. RENDER LOGIC (The Switchboard) ---
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