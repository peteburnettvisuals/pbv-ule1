import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json
import xml.etree.ElementTree as ET

# --- INITIAL SETUP ---
st.set_page_config(page_title="ULE | Skyhigh Coach", layout="wide")

# --- 1. THE STYLE INJECTOR ---
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Call it immediately
local_css("style.css")

# Initialize Firestore (Make sure your GOOGLE_APPLICATION_CREDENTIALS env var is set)
creds_info = st.secrets["gcp_service_account"]
credentials = service_account.Credentials.from_service_account_info(creds_info)
db = firestore.Client(database="ule-store1", credentials=credentials)

#Current Lession XML Lookup
def get_lesson_content(node_id):
    try:
        # This reads the physical file you just showed me
        tree = ET.parse("master_syllabus.xml")
        root = tree.getroot()
        
        # Search for the element by its ID (e.g., EL-01.1.A)
        for element in root.findall(".//element"):
            if element.get("id") == node_id:
                return {
                    "title": element.find("title").text,
                    "video": element.find("video_url").text
                }
    except Exception as e:
        return {"title": "Welcome to Skyhigh", "video": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    
    return {"title": "Lesson Not Found", "video": None}

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

        import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json

# --- INITIAL SETUP ---
st.set_page_config(page_title="ULE | Skyhigh Coach", layout="wide")

# --- 1. THE STYLE INJECTOR ---
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Call it immediately
local_css("style.css")

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
if "full_name" not in st.session_state:
    st.session_state.full_name = "User Name" # Start at first element

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
            user_context = st.text_area("Your Profile & Goals", placeholder="This information allows the system to firther talior and personalise its instruction to the learner's background and aims.")
            
            if st.button("Start New Training", use_container_width=True):
                if reg_name and reg_email:
                    # THE WIRING: This dictionary is what goes to Firestore
                    student_payload = {
                        "name": reg_name,
                        "email": reg_email.lower().strip(),
                        "context": user_context, # NoSQL handles this automatically
                        "current_node": "EL-01.1.A",
                        "created_at": firestore.SERVER_TIMESTAMP 
                    }
                    
                    # Write the document using email as the ID
                    db.collection("students").document(reg_email.lower().strip()).set(student_payload)

                    # Keep it in local state for the current session
                    st.session_state.student_email = reg_email.lower().strip()
                    st.session_state.user_context = user_context
                    st.session_state.authenticated = True
                    st.rerun()


def coach_interface():
    # SIDEBAR: The Live Syllabus
    with st.sidebar:
        st.image("ule-skyhigh-logo1.jpg", use_container_width=True)
        st.header("Syllabus Progress")
        st.write(f"Learner: {st.session_state.full_name}")
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
        # Pull the context from session state
        context = st.session_state.get('user_context', "your career goals")
        
        # The 'Flavor' injected into the first interaction
        greeting = f"Morning! I'm your Skyhigh Coach. I've tailored this session to help with: '{context}'. Ready to begin Step 1?"
        
        st.session_state.messages = [{"role": "assistant", "content": greeting}]

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    # Add a unique key to the chat input
    if prompt := st.chat_input("Respond to the coach...", key="main_chat_input"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)


# --- THE ONLY RENDER BLOCK (At the very bottom of the file) ---

if not st.session_state.authenticated:
    welcome_screen()
else:
    # 1. Fetch data if it's the first time entering the coach mode
    if "user_data" not in st.session_state:
        data = get_current_lesson(st.session_state.student_email)
        if data:
            st.session_state.user_data = data
            st.session_state.current_node = data.get("current_node", "EL-01.1.A")
            st.session_state.user_context = data.get("context", "your goals")
            st.session_state.full_name = data.get("name", "User Name")
    
    # 2. RENDER THE COACH (Just once!)
    coach_interface()