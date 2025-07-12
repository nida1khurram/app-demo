# type:ignore   #https://knai-school.streamlit.app/
import streamlit as st
from datetime import datetime, timedelta
import os
import pandas as pd
import numpy as np
from hashlib import md5, sha256
import json
from PIL import Image
import base64
import re

# Hide GitHub icon and other Streamlit elements
def hide_streamlit_elements():
    """Hide only the GitHub icon while keeping deploy button"""
    st.markdown("""
    <style>
    /* Hide only the GitHub icon specifically */
    div[data-testid="stToolbar"] > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) {
        display: none !important;
    }
    
    /* Alternative selector for GitHub icon */
    button[title="View app source on GitHub"] {
        display: none !important;
    }
    
    /* Hide GitHub fork button */
    .stActionButton:has([title*="GitHub"]) {
        display: none !important;
    }
    
    /* More specific GitHub icon hiding */
    div[data-testid="stToolbar"] button[kind="header"]:first-child {
        display: none !important;
    }
    
    /* Hide the GitHub icon in the toolbar */
    .stApp > header button:first-child {
        display: none !important;
    }
    
    /* Keep deploy button visible but hide GitHub */
    div[data-testid="stToolbar"] > div > div > div:first-child {
        display: none !important;
    }
    
    /* Alternative approach - hide by icon content */
    button[aria-label*="GitHub"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize or load files
CSV_FILE = "fees_data.csv"
USER_DB_FILE = "users.json"
STUDENT_FEES_FILE = "student_fees.json"

# Initialize session state for authentication and app state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'form_key' not in st.session_state:
    st.session_state.form_key = 0
if 'available_months' not in st.session_state:
    st.session_state.available_months = []
if 'current_student_id' not in st.session_state:
    st.session_state.current_student_id = None
if 'last_saved_records' not in st.session_state:
    st.session_state.last_saved_records = None
if 'last_student_name' not in st.session_state:
    st.session_state.last_student_name = ""
if 'last_class_category' not in st.session_state:
    st.session_state.last_class_category = None
if 'last_class_section' not in st.session_state:
    st.session_state.last_class_section = ""
if 'trial_remaining' not in st.session_state:
    st.session_state.trial_remaining = None

def initialize_files():
    """Initialize all required files"""
    initialize_csv()
    initialize_user_db()
    initialize_student_fees()

def initialize_user_db():
    """Initialize the user database if it doesn't exist"""
    if not os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, 'w') as f:
            json.dump({}, f)

def initialize_student_fees():
    """Initialize the student fees JSON file if it doesn't exist"""
    if not os.path.exists(STUDENT_FEES_FILE):
        with open(STUDENT_FEES_FILE, 'w') as f:
            json.dump({}, f)

def hash_password(password):
    """Hash a password for storing"""
    return sha256(password.encode('utf-8')).hexdigest()

def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    return stored_password == sha256(provided_password.encode('utf-8')).hexdigest()

def validate_email(email):
    """Validate email format and ensure it's a Gmail address"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'
    return re.match(email_pattern, email) is not None

def authenticate_user(username, password):
    """Authenticate a user and check trial status"""
    try:
        with open(USER_DB_FILE, 'r') as f:
            users = json.load(f)
            
        if username in users:
            if verify_password(users[username]['password'], password):
                st.session_state.authenticated = True
                st.session_state.current_user = username
                st.session_state.is_admin = users[username].get('is_admin', False)
                
                # Check trial status
                trial_end = users[username].get('trial_end')
                if trial_end:
                    trial_end_date = datetime.strptime(trial_end, "%Y-%m-%d %H:%M:%S")
                    if datetime.now() > trial_end_date:
                        st.session_state.authenticated = False
                        st.error("Your free trial has expired. Please contact support.")
                        return False
                    remaining = trial_end_date - datetime.now()
                    st.session_state.trial_remaining = remaining
                else:
                    st.session_state.trial_remaining = None
                
                return True
        return False
    except Exception as e:
        st.error(f"Authentication error: {str(e)}")
        return False

def create_user(username, password, email, is_admin=False):
    """Create a new user account with email and 1-month trial"""
    try:
        if os.path.exists(USER_DB_FILE):
            with open(USER_DB_FILE, 'r') as f:
                users = json.load(f)
        else:
            users = {}
            
        if not validate_email(email):
            return False, "Please use a valid Gmail address (e.g., username@gmail.com)"
            
        # Check for email uniqueness
        for user in users.values():
            if 'email' in user and user['email'] == email:
                return False, "This Gmail address is already registered. Please use a different Gmail address or log in."
            
        trial_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trial_end = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        
        users[username] = {
            "password": hash_password(password),
            "is_admin": is_admin,
            "email": email,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "trial_start": trial_start,
            "trial_end": trial_end
        }
        
        with open(USER_DB_FILE, 'w') as f:
            json.dump(users, f)
        
        return True, "User created successfully"
    except Exception as e:
        return False, f"Error creating user: {str(e)}"

def initialize_csv():
    """Initialize the CSV file with proper columns if it doesn't exist"""
    if not os.path.exists(CSV_FILE):
        columns = [
            "ID", "Student Name", "Class Category", "Class Section", "Month", 
            "Monthly Fee", "Annual Charges", "Admission Fee",
            "Received Amount", "Payment Method", "Date", "Signature",
            "Entry Timestamp", "Academic Year"
        ]
        pd.DataFrame(columns=columns).to_csv(CSV_FILE, index=False)
    else:
        try:
            df = pd.read_csv(CSV_FILE)
            expected_columns = [
                "ID", "Student Name", "Class Category", "Class Section", "Month", 
                "Monthly Fee", "Annual Charges", "Admission Fee",
                "Received Amount", "Payment Method", "Date", "Signature",
                "Entry Timestamp", "Academic Year"
            ]
            
            for col in expected_columns:
                if col not in df.columns:
                    df[col] = np.nan
            
            df.to_csv(CSV_FILE, index=False)
        except Exception as e:
            st.error(f"Error initializing CSV: {str(e)}")
            pd.DataFrame(columns=expected_columns).to_csv(CSV_FILE, index=False)

def generate_student_id(student_name, class_category):
    """Generate a unique 8-character ID based on student name and class"""
    unique_str = f"{student_name}_{class_category}".encode('utf-8')
    return md5(unique_str).hexdigest()[:8].upper()

def save_to_csv(data):
    """Save data to CSV with proper validation"""
    try:
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
        else:
            df = pd.DataFrame(columns=data[0].keys())
        
        new_df = pd.DataFrame(data)
        df = pd.concat([df, new_df], ignore_index=True)
        
        df.to_csv(CSV_FILE, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return False

def load_data():
    """Load data from CSV with robust error handling"""
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame()
    
    try:
        try:
            df = pd.read_csv(CSV_FILE)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
        except pd.errors.ParserError:
            df = pd.read_csv(CSV_FILE, on_bad_lines='skip')
        
        expected_columns = [
            "ID", "Student Name", "Class Category", "Class Section", "Month", 
            "Monthly Fee", "Annual Charges", "Admission Fee",
            "Received Amount", "Payment Method", "Date", "Signature",
            "Entry Timestamp", "Academic Year"
        ]
        
        for col in expected_columns:
            if col not in df.columns:
                df[col] = np.nan
        
        try:
            df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%d-%m-%Y')
        except:
            pass
        
        try:
            df['Entry Timestamp'] = pd.to_datetime(df['Entry Timestamp']).dt.strftime('%d-%m-%Y %H:%M')
        except:
            pass
        
        return df.dropna(how='all')
    
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

def update_data(updated_df):
    """Update the CSV file with the modified DataFrame"""
    try:
        updated_df.to_csv(CSV_FILE, index=False)
        return True
    except Exception as e:
        st.error(f"Error updating data: {str(e)}")
        return False

def load_student_fees():
    """Load student-specific fees from JSON file"""
    try:
        if os.path.exists(STUDENT_FEES_FILE):
            with open(STUDENT_FEES_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        st.error(f"Error loading student fees: {str(e)}")
        return {}

def save_student_fees(fees_data):
    """Save student-specific fees to JSON file"""
    try:
        with open(STUDENT_FEES_FILE, 'w') as f:
            json.dump(fees_data, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Error saving student fees: {str(e)}")
        return False

def format_currency(val):
    """Format currency with Pakistani Rupees symbol and thousand separators"""
    try:
        return f"Rs. {int(val):,}" if not pd.isna(val) and val != 0 else "Rs. 0"
    except:
        return "Rs. 0"

def style_row(row):
    """Apply styling to DataFrame rows based on payment status"""
    today = datetime.now()
    is_between_1st_and_10th = 1 <= today.day <= 10
    styles = [''] * len(row)
    
    if is_between_1st_and_10th:
        if row['Monthly Fee'] == 0:
            styles[0] = 'color: red'
        else:
            styles[0] = 'color: green'
    return styles

def get_academic_year(date):
    """Determine academic year based on date"""
    year = date.year
    if date.month >= 4:  # Academic year starts in April
        return f"{year}-{year+1}"
    return f"{year-1}-{year}"

def check_annual_admission_paid(student_id, academic_year):
    """Check if annual charges or admission fee have been paid for the academic year"""
    df = load_data()
    if df.empty:
        return False, False
    
    student_records = df[(df['ID'] == student_id) & (df['Academic Year'] == academic_year)]
    annual_paid = student_records['Annual Charges'].sum() > 0
    admission_paid = student_records['Admission Fee'].sum() > 0
    
    return annual_paid, admission_paid

def get_unpaid_months(student_id):
    """Get list of unpaid months for a specific student"""
    df = load_data()
    all_months = [
        "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
        "OCTOBER", "NOVEMBER", "DECEMBER", "JANUARY", "FEBRUARY", "MARCH"
    ]
    
    if df.empty or student_id is None:
        return all_months
    
    paid_months = df[(df['ID'] == student_id) & (df['Monthly Fee'] > 0)]['Month'].unique().tolist()
    
    unpaid_months = [month for month in all_months if month not in paid_months]
    
    return unpaid_months

def update_student_data():
    """Update session state with student data when name or class changes"""
    student_name = st.session_state.get(f"student_name_{st.session_state.form_key}", "")
    class_category = st.session_state.get(f"class_category_{st.session_state.form_key}", None)
    
    if student_name and class_category:
        student_id = generate_student_id(student_name, class_category)
        st.session_state.current_student_id = student_id
        st.session_state.available_months = get_unpaid_months(student_id)
    else:
        st.session_state.current_student_id = None
        st.session_state.available_months = []

def format_trial_remaining(remaining):
    """Format remaining trial time"""
    if remaining is None:
        return "No trial period"
    days = remaining.days
    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60
    return f"{days} days, {hours} hours, {minutes} minutes"

def home_page():
    """Display beautiful home page with logo and school name at the very top and about section in a dropdown"""
    st.set_page_config(page_title="School Fees Management", layout="wide", page_icon="🏫")
    
    # Hide GitHub icon and other elements
    hide_streamlit_elements()
    
    st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    .title-text {
        font-size: 3.5rem !important;
        font-weight: 600 !important;
        color: #2c3e50 !important;
        text-align: center;
        margin-bottom: 0.5rem !important;
    }
    .subtitle-text {
        font-size: 1.5rem !important;
        font-weight: 400 !important;
        color: #7f8c8d !important;
        text-align: center;
        margin-bottom: 2rem !important;
    }
    .feature-card {
        background-color: white;
        border-radius: 10px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease;
        height: 100%;
    }
    .feature-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
    }
    .feature-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        color: #3498db;
    }
    .feature-title {
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        color: #2c3e50;
    }
    .feature-desc {
        color: #7f8c8d;
        font-size: 0.9rem;
    }
    .login-btn {
        background: linear-gradient(135deg, #3498db 0%, #2c3e50 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.5rem 1.5rem;
        border-radius: 8px !important;
        font-weight: 600 !important;
        margin-top: 2rem !important;
    }
    .circle-container {
        display: flex;
        justify-content: center;
        margin-bottom: 1rem;
    }
    .circle {
        width: 200px;
        height: 200px;
        border-radius: 50%;
        background-color: white;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        display: flex;
        justify-content: center;
        align-items: center;
        overflow: hidden;
    }
    .circle img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .expander-content {
        background-color: white;
        border-radius: 10px;
        padding: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .about-heading {
        font-size: 2rem;
        font-weight: 600;
        color: #2c3e50;
        margin-bottom: 1rem;
        text-align: center;
    }
    .about-subheading {
        font-size: 1.5rem;
        font-weight: 500;
        color: #3498db;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    .about-text {
        color: #7f8c8d;
        font-size: 1rem;
        line-height: 1.6;
    }
    .about-list {
        color: #7f8c8d;
        font-size: 1rem;
        line-height: 1.6;
        margin-left: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Logo at the very top
    st.markdown('<div class="circle-container">', unsafe_allow_html=True)
    
    try:
        with open("school-pic.jpeg", "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        img_html = f'<img src="data:image/jpeg;base64,{img_base64}" alt="School Logo">'
    except:
        img_html = '<div style="color: gray; text-align: center; padding: 20px;">School Logo</div>'
    
    st.markdown(
        f"""
        <div class="circle">
            {img_html}
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # School Name and Subtitle
    st.markdown('<h1 class="title-text">British School of Karachi </h1>', unsafe_allow_html=True)
    st.markdown('<h1 class="title-text">Fees Management System</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle-text">Streamline your school\'s fee collection and tracking process with a 1-month free trial!</p>', unsafe_allow_html=True)
    
    # Feature Cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">💰</div>
            <h3 class="feature-title">Fee Collection</h3>
            <p class="feature-desc">Easily record and track student fee payments with a simple, intuitive interface.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">📊</div>
            <h3 class="feature-title">Reports</h3>
            <p class="feature-desc">Generate detailed reports on fee collection, outstanding payments, and student records.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🔒</div>
            <h3 class="feature-title">Secure Access</h3>
            <p class="feature-desc">Role-based authentication ensures only authorized staff can access sensitive data.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Login Button
    st.markdown('<div style="text-align: center;">', unsafe_allow_html=True)
    if st.button("Sign Up for Free Trial / Login", key="home_login_btn", help="Click to sign up or login"):
        st.session_state.show_login = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # About Section in Dropdown
    with st.expander("📌 About This App"):
        st.markdown('<div class="expander-content">', unsafe_allow_html=True)
        st.markdown('<h2 class="about-heading">School Fees Management System - Information, Features & Benefits</h2>', unsafe_allow_html=True)
        
        st.markdown('<h3 class="about-subheading">📌 What is this App?</h3>', unsafe_allow_html=True)
        st.markdown(
            """
            <p class="about-text">
                This is a digital system for schools to easily manage student fee records. It helps track payments, 
                generate reports, and maintain records securely.
            </p>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown('<h3 class="about-subheading">✯ Key Features</h3>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                """
                <p class="about-list"><strong>Easy Fee Collection</strong></p>
                <ul class="about-list">
                    <li>Record monthly, annual, and admission fees in one place.</li>
                    <li>Track paid/unpaid students with color-coded status (✅ Paid / ❌ Unpaid).</li>
                </ul>
                <p class="about-list"><strong>Admin Controls</strong></p>
                <ul class="about-list">
                    <li>Set custom fees for each student/class.</li>
                    <li>Manage users (add/remove staff accounts).</li>
                </ul>
                """,
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                """
                <p class="about-list"><strong>Student Reports</strong></p>
                <ul class="about-list">
                    <li>View payment history for any student.</li>
                    <li>Check yearly/monthly summaries and download reports.</li>
                </ul>
                <p class="about-list"><strong>Secure & Reliable</strong></p>
                <ul class="about-list">
                    <li>Login with username/password.</li>
                    <li>Data saved securely in files (no risk of losing records).</li>
                </ul>
                <p class="about-list"><strong>Free 1-Month Trial</strong></p>
                <ul class="about-list">
                    <li>New users get 30 days free to test all features.</li>
                </ul>
                """,
                unsafe_allow_html=True
            )
        
        st.markdown('<h3 class="about-subheading">👍 Why Use This App?</h3>', unsafe_allow_html=True)
        st.markdown(
            """
            <ul class="about-list">
                <li><strong>Saves Time</strong> – No more paper registers or manual calculations.</li>
                <li><strong>Reduces Errors</strong> – Automatic totals and reminders for unpaid fees.</li>
                <li><strong>Always Accessible</strong> – View records anytime, anywhere.</li>
                <li><strong>Data Security</strong> – No more lost fee registers or tampered records.</li>
            </ul>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown('<h3 class="about-subheading">🎯 Perfect For</h3>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                """
                <p class="about-list"><strong>School Admins</strong></p>
                <ul class="about-list">
                    <li>Manage all fee records in one place.</li>
                </ul>
                """,
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                """
                <p class="about-list"><strong>Accountants</strong></p>
                <ul class="about-list">
                    <li>Generate reports with a single click.</li>
                </ul>
                """,
                unsafe_allow_html=True
            )
        with col3:
            st.markdown(
                """
                <p class="about-list"><strong>Teachers</strong></p>
                <ul class="about-list">
                    <li>Quickly check which students have paid.</li>
                </ul>
                """,
                unsafe_allow_html=True
            )
        
        st.markdown('<h3 class="about-subheading">🚀 Get Started Today!</h3>', unsafe_allow_html=True)
        st.markdown(
            """
            <p class="about-text">
                Try the 1-month free trial – no payment needed!
            </p>
            """,
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown("""
    <div style="text-align: center; margin-top: 3rem; color: #7f8c8d; font-size: 0.8rem;">
        <p>© 2025 School Fees Management System | Developed with ❤️ for educational institutions</p>
        <p>Start your 1-month free trial today!</p>
    </div>
    """, unsafe_allow_html=True)

def login_page():
    """Display login page with signup option and handle authentication"""
    # Hide GitHub icon and other elements
    hide_streamlit_elements()
    
    st.title("🔒 School Fees Management - Login / Sign Up")
    
    st.markdown("**New users, including admins, must sign up with their Gmail address to start a 1-month free trial.**")
    st.markdown("**⚠️ Please use the same Gmail address you used to access this app.**")
    
    tabs = st.tabs(["Sign Up", "Login"])
    
    with tabs[0]:
        with st.form("signup_form"):
            new_username = st.text_input("Username*")
            new_email = st.text_input("Gmail Address*", placeholder="yourname@gmail.com", help="Only the Gmail address used to access this app is allowed.")
            new_password = st.text_input("Password*", type="password", key="signup_pass")
            confirm_password = st.text_input("Confirm Password*", type="password", key="signup_confirm")
            is_admin = st.checkbox("Register as Admin User")
            show_password = st.checkbox("Show Password")
            
            if show_password:
                st.text(f"Password will be: {new_password if new_password else '[not set]'}")
            
            signup_submit = st.form_submit_button("Sign Up (Start 1-month Free Trial)")
            
            if signup_submit:
                if not new_username or not new_password or not new_email:
                    st.error("Username, password, and Gmail address are required!")
                elif new_password != confirm_password:
                    st.error("Passwords do not match!")
                else:
                    success, message = create_user(new_username, new_password, new_email, is_admin)
                    if success:
                        st.success(f"{message} Your 1-month free trial has started!")
                        st.info(f"User '{new_username}' created with email: {new_email}")
                        if authenticate_user(new_username, new_password):
                            st.rerun()
                    else:
                        st.error(message)

    with tabs[1]:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if authenticate_user(username, password):
                    st.success(f"Welcome {username}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")

def main_app():
    """Main application after login"""
    st.set_page_config(page_title="School Fees Management", layout="wide")
    
    # Hide GitHub icon and other elements
    hide_streamlit_elements()
    
    st.title("📚 School Fees Management System")
    
    # Display trial status in sidebar
    if st.session_state.trial_remaining:
        st.sidebar.markdown(
            f"⏰ Free Trial Remaining: {format_trial_remaining(st.session_state.trial_remaining)}",
            unsafe_allow_html=True
        )
    
    if 'menu' not in st.session_state:
        st.session_state.menu = "Enter Fees"
    
    if st.session_state.is_admin:
        st.sidebar.markdown(f"Logged in as Admin: {st.session_state.current_user}")
        menu_options = [
            "Enter Fees", "View All Records", "Paid & Unpaid Students Record", 
            "Student Yearly Report", "User Management", "Set Student Fees"
        ]
        menu = st.sidebar.selectbox("Menu", menu_options, key="menu_select")
        st.session_state.menu = menu
    else:
        st.sidebar.markdown(f"Logged in as: {st.session_state.current_user}")
        menu_options = ["Enter Fees"]
        st.session_state.menu = "Enter Fees"
        menu = "Enter Fees"
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.session_state.is_admin = False
        st.session_state.show_login = False
        st.session_state.menu = None
        st.session_state.form_key = 0
        st.session_state.available_months = []
        st.session_state.current_student_id = None
        st.session_state.last_saved_records = None
        st.session_state.last_student_name = ""
        st.session_state.last_class_category = None
        st.session_state.last_class_section = ""
        st.session_state.trial_remaining = None
        st.rerun()
    
    CLASS_CATEGORIES = [
        "Nursery", "KGI", "KGII", 
        "Class 1", "Class 2", "Class 3", "Class 4", "Class 5",
        "Class 6", "Class 7", "Class 8", "Class 9", "Class 10 (Matric)"
    ]
    
    PAYMENT_METHODS = ["Cash", "Bank Transfer", "Cheque", "Online Payment", "Other"]
    
    if menu == "Enter Fees":
        st.header("➕ Enter Fee Details")
        
        # Create the form
        with st.form(key=f"fee_form_{st.session_state.form_key}", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                student_name = st.text_input(
                    "Student Name*", 
                    placeholder="Full name", 
                    value=st.session_state.last_student_name,
                    key=f"student_name_{st.session_state.form_key}"
                )
            with col2:
                class_category = st.selectbox(
                    "Class Category*", 
                    CLASS_CATEGORIES, 
                    index=CLASS_CATEGORIES.index(st.session_state.last_class_category) if st.session_state.last_class_category in CLASS_CATEGORIES else 0,
                    key=f"class_category_{st.session_state.form_key}"
                )
            
            class_section = st.text_input(
                "Class Section", 
                placeholder="A, B, etc. (if applicable)", 
                value=st.session_state.last_class_section,
                key=f"class_section_{st.session_state.form_key}"
            )
            
            # Add a button to update student data
            update_btn = st.form_submit_button("🔍 Check Student Records")
            
            if update_btn:
                update_student_data()
                st.rerun()
            
            student_id = st.session_state.current_student_id
            
            # Show student records if student_id is available
            if student_id:
                st.subheader("📋 Student Payment History")
                df = load_data()
                student_records = df[df['ID'] == student_id]
                
                if not student_records.empty:
                    # Display all records for the student
                    display_df = student_records[[
                        "Student Name", "Month", "Monthly Fee", "Annual Charges", 
                        "Admission Fee", "Received Amount", "Payment Method", "Date", "Academic Year"
                    ]].sort_values("Date", ascending=False)
                    
                    st.dataframe(
                        display_df.style.format({
                            "Monthly Fee": format_currency,
                            "Annual Charges": format_currency,
                            "Admission Fee": format_currency,
                            "Received Amount": format_currency
                        }),
                        use_container_width=True
                    )
                    
                    # Calculate totals
                    total_monthly = student_records["Monthly Fee"].sum()
                    total_annual = student_records["Annual Charges"].sum()
                    total_admission = student_records["Admission Fee"].sum()
                    total_received = student_records["Received Amount"].sum()
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Monthly", format_currency(total_monthly))
                    col2.metric("Total Annual", format_currency(total_annual))
                    col3.metric("Total Admission", format_currency(total_admission))
                    col4.metric("Total Received", format_currency(total_received))
                    
                    # Show payment status
                    st.subheader("Payment Status")
                    payment_date = st.session_state.get(f"payment_date_{st.session_state.form_key}", datetime.now())
                    academic_year = get_academic_year(payment_date)
                    
                    annual_paid, admission_paid = check_annual_admission_paid(student_id, academic_year)
                    unpaid_months = st.session_state.available_months
                    
                    col_paid, col_unpaid = st.columns(2)
                    
                    with col_paid:
                        st.markdown("#### ✅ Paid Months")
                        paid_months = student_records[student_records['Monthly Fee'] > 0]['Month'].unique()
                        if len(paid_months) > 0:
                            for month in sorted(paid_months):
                                amount = student_records[student_records['Month'] == month]['Monthly Fee'].iloc[0]
                                st.markdown(f"- {month}: {format_currency(amount)}")
                        else:
                            st.markdown("No months paid yet")
                    
                    with col_unpaid:
                        st.markdown("#### ❌ Unpaid Months")
                        if len(unpaid_months) > 0:
                            for month in unpaid_months:
                                st.markdown(f"- {month}")
                        else:
                            st.markdown("All months paid")
                    
                    st.markdown("---")
                    st.markdown(f"**Annual Fees Paid**: {'✅ Yes' if annual_paid else '❌ No'}")
                    st.markdown(f"**Admission Fee Paid**: {'✅ Yes' if admission_paid else '❌ No'}")
                else:
                    st.info("No fee records found for this student.")
                    unpaid_months = st.session_state.available_months
                    
                    st.markdown("#### ❌ Unpaid Months")
                    if len(unpaid_months) > 0:
                        for month in unpaid_months:
                            st.markdown(f"- {month}")
                    else:
                        st.markdown("All months paid")
            
            payment_date = st.date_input("Payment Date", value=datetime.now(),
                                       key=f"payment_date_{st.session_state.form_key}")
            academic_year = get_academic_year(payment_date)
            
            fee_type = st.radio("Select Fee Type*",
                              ["Monthly Fee", "Annual Charges", "Admission Fee"],
                              horizontal=True,
                              key=f"fee_type_{st.session_state.form_key}")
            
            selected_months = []
            monthly_fee = 0
            annual_charges = 0
            admission_fee = 0
            
            fees_data = load_student_fees()
            predefined_fees = fees_data.get(student_id, {})
            default_monthly_fee = predefined_fees.get("monthly_fee", 2000)
            default_annual_charges = predefined_fees.get("annual_charges", 5000)
            default_admission_fee = predefined_fees.get("admission_fee", 1000)
            
            if fee_type == "Monthly Fee":
                if not student_id:
                    st.warning("Please enter Student Name and select Class Category.")
                elif not st.session_state.available_months:
                    st.error("All months have been paid for this student!")
                else:
                    monthly_fee = st.number_input(
                        "Monthly Fee Amount per Month*",
                        min_value=0,
                        value=default_monthly_fee,
                        disabled=bool(predefined_fees) and not st.session_state.is_admin,
                        key=f"monthly_fee_{st.session_state.form_key}"
                    )
                    # Month selection as dropdown
                    selected_month = st.selectbox(
                        "Select Month*",
                        ["Select a month"] + st.session_state.available_months,
                        key=f"month_select_{st.session_state.form_key}"
                    )
                    if selected_month != "Select a month":
                        selected_months = [selected_month]
                        st.markdown(f"**Selected Month**: {selected_month}")
                    else:
                        st.markdown("**Selected Month**: None")
            
            elif fee_type == "Annual Charges":
                if student_id:
                    annual_paid, _ = check_annual_admission_paid(student_id, academic_year)
                    if annual_paid:
                        st.error("Annual charges have already been paid for this academic year!")
                    else:
                        selected_months = ["ANNUAL"]
                        annual_charges = st.number_input(
                            "Annual Charges Amount*",
                            min_value=0,
                            value=default_annual_charges,
                            disabled=bool(predefined_fees) and not st.session_state.is_admin,
                            key=f"annual_charges_{st.session_state.form_key}"
                        )
                else:
                    st.warning("Please enter Student Name and select Class Category.")
            
            elif fee_type == "Admission Fee":
                if student_id:
                    _, admission_paid = check_annual_admission_paid(student_id, academic_year)
                    if admission_paid:
                        st.error("Admission fee has already been paid for this academic year!")
                    else:
                        selected_months = ["ADMISSION"]
                        admission_fee = st.number_input(
                            "Admission Fee Amount*",
                            min_value=0,
                            value=default_admission_fee,
                            disabled=bool(predefined_fees) and not st.session_state.is_admin,
                            key=f"admission_fee_{st.session_state.form_key}"
                        )
                else:
                    st.warning("Please enter Student Name and select Class Category.")
            
            col3, col4 = st.columns(2)
            with col3:
                total_amount = (monthly_fee * len(selected_months)) + annual_charges + admission_fee
                st.text_input(
                    "Total Amount",
                    value=format_currency(total_amount),
                    disabled=True,
                    key=f"total_amount_{st.session_state.form_key}"
                )
                
                payment_method = st.selectbox(
                    "Payment Method*",
                    PAYMENT_METHODS,
                    key=f"payment_method_{st.session_state.form_key}"
                )
            with col4:
                received_amount = st.number_input(
                    "Received Amount*",
                    min_value=0,
                    value=total_amount,
                    key=f"received_amount_{st.session_state.form_key}"
                )
                
                signature = st.text_input(
                    "Received By (Signature)*",
                    placeholder="Your name",
                    key=f"signature_{st.session_state.form_key}"
                )
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("💾 Save Fee Record")
            with col_btn2:
                refresh = st.form_submit_button("🔄 Refresh Form")
            
            if refresh:
                st.session_state.form_key += 1
                st.session_state.last_student_name = ""
                st.session_state.last_class_category = None
                st.session_state.last_class_section = ""
                st.session_state.current_student_id = None
                st.session_state.available_months = []
                st.rerun()
            
            if submitted:
                if not student_name or not class_category or not signature:
                    st.error("Please fill all required fields (*)")
                elif not student_id:
                    st.error("Please enter Student Name and select Class Category.")
                elif fee_type == "Monthly Fee" and not selected_months:
                    st.error("Please select a month for Monthly Fee payment.")
                elif fee_type == "Annual Charges" and annual_paid:
                    st.error("Annual charges have already been paid for this academic year!")
                elif fee_type == "Admission Fee" and admission_paid:
                    st.error("Admission fee has already been paid for this academic year!")
                else:
                    fee_records = []
                    
                    if fee_type in ["Annual Charges", "Admission Fee"]:
                        fee_data = {
                            "ID": student_id,
                            "Student Name": student_name,
                            "Class Category": class_category,
                            "Class Section": class_section,
                            "Month": selected_months[0],
                            "Monthly Fee": 0,
                            "Annual Charges": annual_charges,
                            "Admission Fee": admission_fee,
                            "Received Amount": received_amount,
                            "Payment Method": payment_method,
                            "Date": payment_date.strftime("%Y-%m-%d"),
                            "Signature": signature,
                            "Entry Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Academic Year": academic_year
                        }
                        fee_records.append(fee_data)
                    
                    elif fee_type == "Monthly Fee":
                        for month in selected_months:
                            fee_data = {
                                "ID": student_id,
                                "Student Name": student_name,
                                "Class Category": class_category,
                                "Class Section": class_section,
                                "Month": month,
                                "Monthly Fee": monthly_fee,
                                "Annual Charges": 0,
                                "Admission Fee": 0,
                                "Received Amount": monthly_fee,
                                "Payment Method": payment_method,
                                "Date": payment_date.strftime("%Y-%m-%d"),
                                "Signature": signature,
                                "Entry Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "Academic Year": academic_year
                            }
                            fee_records.append(fee_data)
                    
                    if save_to_csv(fee_records):
                        st.session_state.last_student_name = student_name
                        st.session_state.last_class_category = class_category
                        st.session_state.last_class_section = class_section or ""
                        
                        st.session_state.form_key += 1
                        st.session_state.available_months = get_unpaid_months(student_id)
                        st.session_state.last_saved_records = fee_records
                        st.success("✅ Fee record(s) saved successfully!")
                        st.balloons()
                        st.rerun()
        
        # Display last saved records if available
        if st.session_state.last_saved_records:
            st.subheader("📋 Last Saved Fee Record(s)")
            saved_df = pd.DataFrame(st.session_state.last_saved_records)
            display_df = saved_df[[
                "Student Name", "Class Category", "Month", "Monthly Fee", 
                "Annual Charges", "Admission Fee", "Received Amount",
                "Payment Method", "Date", "Signature"
            ]]
            st.dataframe(
                display_df.style.format({
                    "Monthly Fee": format_currency,
                    "Annual Charges": format_currency,
                    "Admission Fee": format_currency,
                    "Received Amount": format_currency
                }),
                use_container_width=True
            )

def main():
    initialize_files()
    
    if 'show_login' not in st.session_state:
        st.session_state.show_login = False
    
    if not st.session_state.authenticated:
        if st.session_state.show_login:
            login_page()
        else:
            home_page()
    else:
        main_app()

if __name__ == "__main__":
    main()
