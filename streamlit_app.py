import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import xml.etree.ElementTree as ET
import google.generativeai as genai

# --- 1. INITIAL SETUP ---
st.set_page_config(page_title="ULE | Skyhigh Cockpit", layout="wide")

# Style Injector (Injects custom CSS if available)
def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except: pass

local_css("style.css")

# Initialize Cloud Clients
creds_info = st.secrets["gcp_service_account"]
credentials = service_account.Credentials.from_service_account_info(creds_info)
db = firestore.Client(database="ule-store1", credentials=credentials)

# Tier 1 AI Engine
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# --- 2. DATA HANDLERS ---

def get_lesson_content(node_id):
    try:
        tree = ET.parse("master_syllabus.xml")
        root = tree.getroot()
        for element in root.findall(".//element"):
            if element.get("id") == node_id:
                return {"title": element.find("title").text, "video": element.find("video_url").text}
    except: pass
    return {"title": "Welcome to Skyhigh", "video": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}

def update_student_node(email, next_node):
    db.collection("students").document(email).update({"current_node": next_node})
    st.session_state.current_node = next_node
    if "chat_session" in st.session_state: del st.session_state.chat_session
    if "messages" in st.session_state: del st.session_state.messages
    st.rerun()

# --- 3. UI SCREENS ---

def welcome_screen():
    st.title("Universal Learning Engine")
    st.subheader("Skyhigh Flight Cockpit")
    col_v, col_a = st.columns([0.6, 0.4], gap="large")
    with col_v: st.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ") # Rickroll Placeholder
    with col_a:
        tab_l, tab_r = st.tabs(["🔄 Resume", "🚀 New Training"])
        with tab_l:
            login_email = st.text_input("Email to Resume")
            if st.button("Resume Mission", use_container_width=True):
                st.session_state.student_email = login_email.lower().strip()
                st.session_state.authenticated = True
                st.rerun()

def coach_interface():
    lesson = get_lesson_content(st.session_state.current_node)
    
    # 3-COLUMN LAYOUT START
    with st.sidebar:
        st.image("ule-skyhigh-logo1.jpg", use_container_width=True)
        st.write(f"**Learner:** {st.session_state.full_name}")
        st.progress(15 if st.session_state.current_node == "EL-01.1.A" else 50)
        st.write(f"**Element:** {st.session_state.current_node}")
        st.divider()
        if st.session_state.current_node == "EL-01.1.A":
            if st.button("✅ Complete Lesson", type="primary", use_container_width=True):
                update_student_node(st.session_state.student_email, "EL-01.1.B")
        if st.button("🔄 Reset Chat Session", use_container_width=True):
            if "chat_session" in st.session_state: del st.session_state.chat_session
            if "messages" in st.session_state: del st.session_state.messages
            st.rerun()

    # Split Main Area into Resources and Coach
    col_res, col_coach = st.columns([0.5, 0.5], gap="medium")

    # COLUMN 1: Pinned Resources
    with col_res:
        st.subheader("📖 Lesson Resources")
        with st.container(border=True):
            st.write(f"📺 **Video:** {lesson['title']}")
            st.video(lesson['video'])
            st.info("💡 Watch the video above while chatting with your coach on the right.")

    # COLUMN 2: Independent Scrolling Coach
    with col_coach:
        st.subheader("🤖 AI Instructor")
        
        # This container holds the chat and scrolls independently
        chat_history = st.container(height=500, border=True)
        
        if "messages" not in st.session_state: st.session_state.messages = []

        if not st.session_state.messages:
            try:
                st.session_state.chat_session = model.start_chat(history=[])
                prompt = f"You are the Skyhigh Coach. Student: {st.session_state.full_name}. Goal: {st.session_state.user_context}. Lesson: {lesson['title']}. Introduce the lesson."
                response = st.session_state.chat_session.send_message(prompt)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except: st.info("Recalibrating sensors... one moment.")

        with chat_history:
            for msg in st.session_state.messages: 
                st.chat_message(msg["role"]).write(msg["content"])

        # Chat input is placed directly below the history container
        if p := st.chat_input("Ask your coach a question..."):
            st.session_state.messages.append({"role": "user", "content": p})
            resp = st.session_state.chat_session.send_message(p)
            st.session_state.messages.append({"role": "assistant", "content": resp.text})
            st.rerun()

# --- 4. RENDER SWITCHBOARD ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    welcome_screen()
else:
    if "user_data" not in st.session_state:
        query = db.collection("students").where("email", "==", st.session_state.student_email).limit(1).stream()
        for doc in query:
            d = doc.to_dict()
            st.session_state.user_data, st.session_state.full_name = d, d.get("name", "Explorer")
            st.session_state.current_node = d.get("current_node", "EL-01.1.A")
            st.session_state.user_context = d.get("context", "your goals")
    coach_interface()