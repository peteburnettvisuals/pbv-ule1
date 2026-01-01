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
    """Parses the XML for title, video, and technical source of truth."""
    try:
        tree = ET.parse("master_syllabus.xml")
        root = tree.getroot()
        for element in root.findall(".//element"):
            if element.get("id") == node_id:
                return {
                    "title": element.find("title").text,
                    "video": element.find("video_url").text,
                    "technical_details": element.find("technical_details").text.strip()
                }
    except Exception:
        pass
    return {
        "title": "Welcome to Skyhigh", 
        "video": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "technical_details": "Follow standard safety protocols."
    }

def update_student_node(email, next_node):
    db.collection("students").document(email).update({"current_node": next_node})
    st.session_state.current_node = next_node
    if "chat_session" in st.session_state: del st.session_state.chat_session
    if "messages" in st.session_state: del st.session_state.messages
    st.rerun()

# --- 3. UI SCREENS ---

def welcome_screen():
    st.title("Universal Learning Engine")
    st.subheader("Skyhigh Demo Edition")
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
        
        # 1. Define the module sequence
        module_sequence = [
            "SOP-GEAR-01", "SOP-GEAR-02", "SOP-ENV-01", 
            "SOP-BODY-01", "SOP-NAV-01", "SOP-CRIS-01", 
            "SOP-CRIS-02", "SOP-CRIS-03"
        ]
        
        # 2. Calculate Progress Metrics
        try:
            current_idx = module_sequence.index(st.session_state.current_node)
        except ValueError:
            current_idx = 0 
            
        # Math: (Completed Modules / Total Modules) * 100
        # We use current_idx because it represents how many stages are fully behind the student
        progress_percentage = int((current_idx / len(module_sequence)) * 100)

        # 3. Render Progress UI
        st.write(f"**Learner:** {st.session_state.full_name}")
        st.progress(progress_percentage)
        st.write(f"**Syllabus Progress:** {progress_percentage}%")
        st.write(f"**Current Element:** {st.session_state.current_node}")
        
        st.divider()

        # 4. Dynamic Action Buttons
        if not st.session_state.quiz_passed:
            # Quiz Mode: Unlock the 'Complete' button
            if st.button("📝 Start Module Quiz", type="primary", use_container_width=True):
                st.session_state.quiz_active = True
                quiz_prompt = f"The student is ready for the quiz on {lesson['title']}. Please ask 3 multiple-choice questions one at a time."
                response = st.session_state.chat_session.send_message(quiz_prompt)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()
        else:
            # Completion Mode: Move to next stage
            if current_idx < len(module_sequence) - 1:
                next_node = module_sequence[current_idx + 1]
                btn_label = "🚀 Complete & Next Module"
            else:
                next_node = "COMPLETED"
                btn_label = "🏁 Graduate Training"

            if st.button(btn_label, type="primary", use_container_width=True):
                if next_node == "COMPLETED":
                    st.balloons()
                    st.success("Training Complete!")
                else:
                    # IMPORTANT: Reset quiz state so the next module is locked
                    st.session_state.quiz_passed = False
                    update_student_node(st.session_state.student_email, next_node)
        
        st.divider()
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
        
        # 1. Create the scrolling container
        chat_history = st.container(height=500, border=True)
        
        # 2. State Initialization (Moved inside the column for clarity)
        if "messages" not in st.session_state:
            st.session_state.messages = []

        if not st.session_state.messages:
            try:
                st.session_state.chat_session = model.start_chat(history=[])
                sys_prompt = f"""
                You are the Skyhigh Flight Instructor. 
                Syllabus Source of Truth: {lesson['technical_details']}
                Goal: {st.session_state.user_context}.

                PEDAGOGICAL RULES:
                1. Progressively teach: Deliver only ONE line item from the technical details at a time.
                2. Contextualize: Explain how that specific detail relates to the student's goal.
                3. Interactive Loop: After each detail, ask if it makes sense or if they have a specific question. 
                4. Do NOT move to the next detail until the student acknowledges or asks a follow-up.
                5. Quiz: Only start the quiz after all technical details for this lesson have been discussed.
                """
                response = st.session_state.chat_session.send_message(sys_prompt)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception:
                st.info("The Coach is recalibrating sensors. Please wait 60 seconds.")

        # 3. THE DISPLAY LOOP: Draws the messages inside the scroll box
        with chat_history:
            for msg in st.session_state.messages: 
                st.chat_message(msg["role"]).write(msg["content"])

        # 4. CHAT INPUT & LISTENER: Outside the loop but inside the column
        if p := st.chat_input("Ask your coach a question..."):
            st.session_state.messages.append({"role": "user", "content": p})
            
            # Send message to Gemini
            resp = st.session_state.chat_session.send_message(p)
            ai_text = resp.text
            
            # The 'Listener' for the secret keyword
            if "QUIZ_PASSED" in ai_text:
                st.session_state.quiz_passed = True
                ai_text = ai_text.replace("QUIZ_PASSED", "").strip()
                ai_text += "\n\n✨ **Assessment Complete! Check the sidebar to proceed.**"

            st.session_state.messages.append({"role": "assistant", "content": ai_text})
            st.rerun()
            

# --- 4. RENDER SWITCHBOARD ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "quiz_active" not in st.session_state: st.session_state.quiz_active = False
if "quiz_passed" not in st.session_state: st.session_state.quiz_passed = False
if not st.session_state.authenticated:
    welcome_screen()
else:
    if "user_data" not in st.session_state:
        query = db.collection("students").where("email", "==", st.session_state.student_email).limit(1).stream()
        for doc in query:
            d = doc.to_dict()
            st.session_state.user_data, st.session_state.full_name = d, d.get("name", "Explorer")
            st.session_state.current_node = d.get("current_node", "SOP-GEAR-01")
            st.session_state.user_context = d.get("context", "your goals")
    coach_interface()