import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import xml.etree.ElementTree as ET
import google.generativeai as genai
import datetime 


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

# NEW: Global Syllabus Sequence
# Moving this here ensures every column in your cockpit knows the lesson order
module_sequence = [
    "SOP-GEAR-01", # Canopy Systems & Ripcords
    "SOP-GEAR-02", # Altimeter Mastery & Decision Windows
    "SOP-ENV-01"   # Weather & Atmospheric Limits
]

# Tier 1 AI Engine
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# --- 2. DATA HANDLERS ---

def log_interaction(user_msg, ai_msg):
    email = st.session_state.get("student_email")
    if not email:
        return

    is_grad = st.session_state.get("graduated", False)
    sop_ref = "POST_GRAD_ASSISTANT" if is_grad else st.session_state.get("current_node", "GENERAL")
    
    log_ref = db.collection("students").document(email).collection("module_logs").document(sop_ref)
    
    # Use Python's datetime for the nested array element
    # Use firestore.SERVER_TIMESTAMP only for the top-level field
    log_ref.set({
        "sop_ref": str(sop_ref),
        "last_updated": firestore.SERVER_TIMESTAMP, 
        "history": firestore.ArrayUnion([
            {
                "timestamp": datetime.datetime.now(datetime.timezone.utc), # FIX HERE
                "user": str(user_msg),
                "ai": str(ai_msg)
            }
        ])
    }, merge=True)

def get_lesson_content(node_id):
    try:
        # 1. Standardize the incoming ID to prevent mismatches
        target_id = str(node_id).strip() 
        
        tree = ET.parse("master_syllabus.xml")
        root = tree.getroot()
        
        for element in root.findall(".//element"):
            # 2. Compare standardized IDs
            if element.get("id").strip() == target_id:
                return {
                    "title": element.find("title").text,
                    "video_url": element.find("video_url").text,
                    "technical_details": element.find("technical_details").text.strip()
                }
    except Exception as e:
        st.error(f"XML Error: {e}") # Debugging tool for your demo
        
    # FALLBACK: If this appears, the ID match failed
    return {
        "title": "SOP DATA NOT FOUND", 
        "video_url": "https://www.youtube.com/watch?v=oX3PB6_zrCU",
        "technical_details": "Error: Check XML IDs."
    }

def update_student_node(email, next_node):
    db.collection("students").document(email).update({"current_node": next_node,"updated_at": firestore.SERVER_TIMESTAMP})
    st.session_state.current_node = next_node
    if "chat_session" in st.session_state: del st.session_state.chat_session
    if "messages" in st.session_state: del st.session_state.messages
    st.rerun()


def reset_student_progress(email):
    # 1. Update the 'Cloud Truth'
    db.collection("students").document(email).update({
        "current_node": "SOP-GEAR-01",
        "updated_at": firestore.SERVER_TIMESTAMP
    })
    # 2. Reset the 'Local Truth'
    st.session_state.current_node = "SOP-GEAR-01"
    st.session_state.graduated = False
    st.session_state.quiz_passed = False
    
    # 3. Clean up chat history for a fresh start
    if "messages" in st.session_state: del st.session_state.messages
    if "chat_session" in st.session_state: del st.session_state.chat_session
    if "asst_messages" in st.session_state: del st.session_state.asst_messages
    if "asst_chat_session" in st.session_state: del st.session_state.asst_chat_session
    
    st.rerun()

def generate_mastery_report(email):
    # 1. Gather all logs vertically
    logs_ref = db.collection("students").document(email).collection("module_logs").stream()
    full_transcript = ""
    for doc in logs_ref:
        data = doc.to_dict()
        full_transcript += f"\n--- SOP: {data.get('sop_ref')} ---\n"
        for entry in data.get("history", []):
            full_transcript += f"User: {entry['user']}\nAI: {entry['ai']}\n"

    # 2. One-shot Analysis (TPM efficient)
    analysis_prompt = f"""
    Analyze this student's training transcript:
    {full_transcript}
    
    Provide a high-level 'Mastery Report':
    1. Comment on areas they mastered exceptionally well.
    2. Note any outstanding details they asked about or struggled with that they should keep in mind moving forward .
    3. A final 'Instructor's Note' on their readiness, congratulating them on passing the course.
    """
    
    # Use the model to generate a single summary response
    report = model.generate_content(analysis_prompt)
    return report.text    

# --- 3. UI SCREENS ---

def welcome_screen():
    st.title("Universal Learning Engine")
    st.subheader("Skyhigh Demo Edition")
    col_v, col_a = st.columns([0.6, 0.4], gap="large")
    with col_v: st.video("https://www.youtube.com/watch?v=ryXNsPSF2T0") 
    with col_a:
        tab_login, tab_reg = st.tabs(["🔄 Resume", "🚀 New Training"])
        with tab_login:
            login_email = st.text_input("Email to Resume")
            if st.button("Resume Mission", use_container_width=True):
                email_to_check = login_email.lower().strip()
                
                # 1. Peek into the DB to see if they exist
                query = db.collection("students").document(email_to_check).get()
                
                if query.exists:
                    # 2. They exist! Proceed to mission
                    st.session_state.student_email = email_to_check
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    # 3. Handling code for missing user
                    st.error(f"User '{email_to_check}' not found. Please check your spelling or register a 'New Training' profile.")

        with tab_reg:
                    reg_name = st.text_input("Full Name")
                    reg_email = st.text_input("Email Address (This will be your Login ID)")
                    
                    # THE CONTEXT FIELD
                    user_context = st.text_area(
                        "Your Profile & Goals", 
                        placeholder="This field helps the system tailor its training even further to the user's specific goals and/or experience levels."
                    )
                    
                    if st.button("Start New Training", use_container_width=True):
                        if reg_name and reg_email:
                            email_clean = reg_email.lower().strip()
                            
                            # LOGIC: Initialize the student document in Firestore
                            db.collection("students").document(email_clean).set({
                                "name": reg_name,
                                "email": email_clean,
                                "context": user_context,
                                "current_node": "SOP-GEAR-01", # THE CRITICAL STARTING POINT
                                "created_at": firestore.SERVER_TIMESTAMP,
                                "updated_at": firestore.SERVER_TIMESTAMP
                            })
                            
                            # Set local session state
                            st.session_state.student_email = email_clean
                            st.session_state.full_name = reg_name
                            st.session_state.user_context = user_context
                            st.session_state.current_node = "SOP-GEAR-01"
                            st.session_state.authenticated = True
                            
                            st.success(f"Profile Created for {email_clean}!")
                            st.rerun()               

def coach_interface():
    lesson = get_lesson_content(st.session_state.current_node)
    sop_number = st.session_state.current_node
    
    # 3-COLUMN LAYOUT START
    with st.sidebar:
        st.image("ule-skyhigh-logo1.jpg", use_container_width=True)
        
               
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
                    # 1. Flip states
                    st.session_state.graduated = True
                    st.session_state.current_node = "GRADUATED"
                    
                    # 2. Generate the "Chef's Kiss" Report
                    with st.spinner("Finalizing your Mastery Report..."):
                        report_text = generate_mastery_report(st.session_state.student_email)
                        st.session_state.mastery_report = report_text

                    # 3. PERMANENT CLOUD WRITE: Save report to main document
                    db.collection("students").document(st.session_state.student_email).update({
                        "current_node": "GRADUATED",
                        "mastery_report": report_text, # Save the generated analysis
                        "updated_at": firestore.SERVER_TIMESTAMP
                    })    
                    
                    st.balloons()
                else:
                    st.session_state.quiz_passed = False
                    update_student_node(st.session_state.student_email, next_node)
        
        st.divider()
        if st.button("🔄 Reset Training & Chat", use_container_width=True):
            reset_student_progress(st.session_state.student_email)

    # Split Main Area into Resources and Coach
    col_res, col_coach = st.columns([0.5, 0.5], gap="medium")

    # COLUMN 1: Pinned Resources
    with col_res:
        st.subheader("📖 Lesson Resources")
        with st.container(border=True):
            # Pulling directly from the 'lesson' dict fetched at top of function
            st.write(f"📺 **Video:** {lesson['title']}")
            st.video(lesson['video_url']) 
            st.info("💡 Watch the video above, and then you can chat with your AI coach about the learning content for this module.")

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
                You are the Skyhigh Parachuting Instructor. 
                Syllabus Title: {lesson['title']}
                SOP Number: {sop_number}
                Syllabus Source of Truth: {lesson['technical_details']}
                Goal: {st.session_state.user_context}.

                PEDAGOGICAL RULES:
                1. Progressively teach: Deliver only ONE line item from the technical details at a time.
                2. Contextualize: Explain how that specific detail relates to the student's goal.
                3. Interactive Loop: After each detail, ask if it makes sense or if they have a specific question. Ecourage them to feedback what they have learned in the chat, as recapping it back to you will check understanding and also myleinate the learning by phyical action.
                4. Do NOT move to the next detail until the student acknowledges or asks a follow-up.
                5. Quiz: Only start the quiz after all technical details for this lesson have been discussed.
                6. MANDATORY: Begin your briefing by clearly stating: "In the section, we are covering SOP {sop_number}: {lesson['title']}."
                7. Be polite, and keep to the training. Steer the student back to the lesson if they go off-topic.

                NEW QUIZ RULES:
                - When the quiz starts, ask 3 multiple-choice questions one at a time.
                - If the student gets at least 2 out of 3 correct, they pass.
                - MANDATORY: When the student passes, you MUST end your final congratulatory message with the exact hidden token: QUIZ_PASSED.
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
            log_interaction(p, ai_text)
            
            # The 'Listener' for the secret keyword
            if "QUIZ_PASSED" in ai_text:
                st.session_state.quiz_passed = True
                ai_text = ai_text.replace("QUIZ_PASSED", "").strip()
                ai_text += "\n\n✨ **Assessment Complete! Check the sidebar to proceed.**"

            st.session_state.messages.append({"role": "assistant", "content": ai_text})
            st.rerun()

def display_graduation_deck():
    st.title("🎖️ SkyHigh Graduation Deck")

    # 1. INITIALIZE JUMP ASSISTANT (Fixes the AttributeError)
    if "asst_chat_session" not in st.session_state:
        with open("master_syllabus.xml", "r") as f:
            full_syllabus = f.read()
        
        st.session_state.asst_chat_session = model.start_chat(history=[])
        asst_init_prompt = f"You are the SkyHigh Jump Assistant. Marty has graduated. Use this syllabus as your source of truth: {full_syllabus}"
        st.session_state.asst_chat_session.send_message(asst_init_prompt)

    # 2. PREPARE CERTIFICATE DATA
    name = st.session_state.get("full_name", "Marty McFly")
    try:
        raw_date = st.session_state.user_data.get("updated_at")
        pass_date = raw_date.strftime("%B %d, %Y")
    except:
        pass_date = "January 02, 2026"

    # 3. RENDER TWO-COLUMN LAYOUT
    col_cert, col_asst = st.columns([0.5, 0.5], gap="large")

    with col_cert:
        # ALL code for the certificate must be indented under this 'with'
        st.markdown(f"""
            <div style="text-align: center; padding: 50px; border: 8px double #FF4B4B; border-radius: 15px; background-color: #111; box-shadow: 0 10px 30px rgba(0,0,0,0.5); position: relative;">
                <div style="position: absolute; top: 10px; right: 20px; font-size: 50px; opacity: 0.3;">🏆</div>
                <h3 style="color: #FF4B4B; letter-spacing: 5px; margin-bottom: 0;">OFFICIAL CERTIFICATION</h3>
                <h1 style="color: white; font-size: 42px; margin-top: 10px; font-family: 'serif';">Certificate of Mastery</h1>
                <p style="font-size: 20px; color: #aaa; margin: 20px 0;">This document serves to confirm that</p>
                <h2 style="color: #fff; font-size: 36px; border-bottom: 2px solid #FF4B4B; display: inline-block; padding-bottom: 5px;">{name}</h2>
                <p style="font-size: 20px; color: #aaa; margin-top: 20px;">has successfully completed all requirements to be recognized as a</p>
                <h3 style="color: #FF4B4B; font-size: 28px;">SKYHIGH QUALIFIED JUMPER</h3>
                <div style="margin-top: 40px; display: flex; justify-content: space-around; border-top: 1px solid #333; padding-top: 20px;">
                    <div style="text-align: left;">
                        <p style="font-size: 12px; color: #666; margin: 0;">COMPLETION DATE</p>
                        <p style="font-size: 16px; color: #fff;">{pass_date}</p>
                    </div>
                    <div style="text-align: right;">
                        <p style="font-size: 12px; color: #666; margin: 0;">ENGINE VERIFIED</p>
                        <p style="font-size: 16px; color: #FF4B4B;">ULE-SKYHIGH-2.0</p>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        st.success(f"Verified Jumper: {st.session_state.student_email}")

        if "mastery_report" in st.session_state:
            st.markdown("### 📝 Instructor's Mastery Report")
            st.info(st.session_state.mastery_report)

    with col_asst:
        st.subheader("🤖 Jump Assistant (Unlocked)")
        st.info("You are now in 'Direct Access' mode. I can answer any technical question from the full syllabus immediately.")
        
        # Assistant Chat Logic (Standard scrolling container)
        if "asst_messages" not in st.session_state:
            st.session_state.asst_messages = [{"role": "assistant", "content": f"Ready for your jump, {name}? Ask me any questions about jump procedure or conditions and I'll answer based on the FULL specifics from the SkyHigh Standard Operating Procedure manual."}]
        
        chat_box = st.container(height=400, border=True)
        for m in st.session_state.asst_messages:
            chat_box.chat_message(m["role"]).write(m["content"])

        if p := st.chat_input("Ask your jump assistant..."):
            st.session_state.asst_messages.append({"role": "user", "content": p})
    
            # Send to the UNLOCKED assistant session
            resp = st.session_state.asst_chat_session.send_message(p)
            ai_text = resp.text
            log_interaction(p, ai_text)
    
            st.session_state.asst_messages.append({"role": "assistant", "content": ai_text})
            st.rerun() # Forces the new message to appear instantly 

    st.divider()
    col_spacer, col_reset = st.columns([0.7, 0.3])
    with col_reset:
        if st.button("🔄 Reset & Recertify", use_container_width=True, help="This will wipe your progress and start training from SOP-GEAR-01"):
            reset_student_progress(st.session_state.student_email)         
            

# --- 4. RENDER SWITCHBOARD ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "quiz_active" not in st.session_state: st.session_state.quiz_active = False
if "quiz_passed" not in st.session_state: st.session_state.quiz_passed = False
# NEW: Flag to trigger the transition to the Assistant UI
if "graduated" not in st.session_state: st.session_state.graduated = False

if not st.session_state.authenticated:
    welcome_screen()
else:
    # Authenticated: Ensure data is loaded
    if "user_data" not in st.session_state:
        query = db.collection("students").where("email", "==", st.session_state.student_email).limit(1).stream()
        for doc in query:
            d = doc.to_dict()
            st.session_state.user_data, st.session_state.full_name = d, d.get("name", "Explorer")
            st.session_state.current_node = d.get("current_node", "SOP-GEAR-01")
            st.session_state.user_context = d.get("context", "your goals")

            # NEW: Restore the report from the Cloud Truth
            st.session_state.mastery_report = d.get("mastery_report", "No report on file.")

    # NEW: Check if the database says he is already a graduate
    if st.session_state.current_node == "GRADUATED":
        st.session_state.graduated = True
    
    # NEW: The Switch between Training and Graduation
    if st.session_state.graduated:
        display_graduation_deck()
    else:
        coach_interface()