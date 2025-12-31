import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json

# --- INITIAL SETUP ---
st.set_page_config(page_title="ULE | Skyhigh Coach", layout="wide")

# Load CSS
with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize Firestore (Make sure your GOOGLE_APPLICATION_CREDENTIALS env var is set)
creds_info = st.secrets["gcp_service_account"]
credentials = service_account.Credentials.from_service_account_info(creds_info)
db = firestore.Client(database="ule-store1", credentials=credentials)

#The Driver Function
def get_current_lesson(student_email):
    # Find the student by email field
    users_ref = db.collection("students")
    query = users_ref.where("email", "==", student_email).limit(1).stream()
    
    student_data = None
    for doc in query:
        student_data = doc.to_dict()
        student_data['id'] = doc.id # Keep the unique Doc ID for updates
    
    if student_data:
        # For now, we'll return the 'current_node' value
        # Later, this will trigger the XML lookup!
        return student_data
    else:
        return None

# --- STATE MANAGEMENT ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_node" not in st.session_state:
    st.session_state.current_node = "EL-01.1.A" # Start at first element

# --- UI COMPONENTS ---

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
            # Simple email-based resume
            login_email = st.text_input("Enter your Email to Resume", placeholder="name@company.com")
            if st.button("Resume Progress", use_container_width=True):
                if login_email:
                    # LOGIC: Check Firestore for document ID == login_email
                    st.session_state.student_email = login_email.lower().strip()
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.warning("Please enter your email address.")

        with tab_reg:
            reg_name = st.text_input("Full Name")
            reg_email = st.text_input("Email Address (This will be your Login ID)")
            
            # THE CONTEXT FIELD
            user_context = st.text_area(
                "Your Profile & Goals", 
                placeholder="e.g. I am a safety officer looking to understand drone risk protocols..."
            )
            
            if st.button("Start New Training", use_container_width=True):
                if reg_name and reg_email:
                    # LOGIC: Save to Firestore using reg_email as the Document ID
                    st.session_state.student_email = reg_email.lower().strip()
                    st.session_state.user_context = user_context
                    st.session_state.authenticated = True
                    st.success(f"Profile Created for {reg_email}!")
                    st.rerun()
                else:
                    st.error("Name and Email are required.")

# App Entry Point
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    welcome_screen()
else:
    # This is where the Instructor-Led Engine takes over
    st.write(f"### Welcome back, {st.session_state.get('student_email')}!")
    st.write("Loading your personalized Skyhigh syllabus...")




def coach_interface():
    # SIDEBAR: The Live Syllabus
    with st.sidebar:
        st.image("https://your-logo-url.com/skyhigh-logo.png", width=100)
        st.header("Syllabus Progress")
        st.progress(15) # Example progress %
        st.write(f"**Current Element:** {st.session_state.current_node}")
        st.divider()
        st.info("Instructor-Led Mode: Active")

    # MAIN CHAT (Jump Assistant Style)
    st.header("Guided Training")
    
    # Placeholder for the "Resource Slot" (Videos/Images for current node)
    with st.container(border=True):
        st.write("📺 **Resource for this Lesson:** Propeller Inspection Guide")
        # st.video(...) would go here based on XML
    
    # Chat History Container
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Morning! I'm your Skyhigh Coach. Are you ready to begin Step 1: Physical Integrity?"}
        ]

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    # User Input (Limited by state - e.g., can't skip ahead)
    if prompt := st.chat_input("Respond to the coach..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        # Here we will add the Gemini 2.0 call later!

# --- RENDER LOGIC ---
if not st.session_state.authenticated:
    welcome_screen()
else:
    # IMPORTANT: Sync the local state with Firestore once at the start of the session
    if "user_data" not in st.session_state:
        # For the shakedown, we use the email you created manually
        data = get_current_lesson("petercameronburnett@gmail.com") 
        if data:
            st.session_state.user_data = data
            # Sync the XML node from Firestore to your UI state
            st.session_state.current_node = data.get("current_node", "EL-GEAR-01-A")
    
    coach_interface()