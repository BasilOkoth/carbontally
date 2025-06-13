import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, firestore
from firebase_admin.exceptions import FirebaseError
from firebase_admin import exceptions
import uuid
import datetime
import re
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# This file provides Firebase authentication and user management for CarbonTally app
# It includes email notifications for account approval, rejection, and password reset

# Configuration
BASE_DIR = Path(__file__).parent if "__file__" in locals() else Path.cwd()

# Email Templates
EMAIL_TEMPLATES = {
    "approval": {
        "subject": "CarbonTally - Your Account Has Been Approved",
        "body": """
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">
                <div style="text-align: center; margin-bottom: 20px;">
                    <h2 style="color: #2e8b57;">🌱 CarbonTally</h2>
                </div>
                <p>Dear {fullName},</p>
                <p>Congratulations! Your CarbonTally account has been approved.</p>
                <p>You can now log in using your email and password at <a href="{app_url}" style="color: #2e8b57;">CarbonTally</a>.</p>
                <p><strong>Your Tree Tracking Number:</strong> {treeTrackingNumber}</p>
                <p>This unique tracking number will help you monitor and track all trees you plant through our platform.</p>
                <p>Thank you for joining our mission to combat climate change through tree planting initiatives!</p>
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; font-size: 0.8em; color: #666;">
                    <p>CarbonTally - Empowering Tree Monitoring and Climate Action</p>
                    <p>If you have any questions, please contact us at <a href="mailto:okothbasil45@gmail.com" style="color: #2e8b57;">okothbasil45@gmail.com</a></p>
                </div>
            </div>
        </body>
        </html>
        """
    },
    "rejection": {
        "subject": "CarbonTally - Account Application Status",
        "body": """
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">
                <div style="text-align: center; margin-bottom: 20px;">
                    <h2 style="color: #2e8b57;">🌱 CarbonTally</h2>
                </div>
                <p>Dear {fullName},</p>
                <p>Thank you for your interest in CarbonTally.</p>
                <p>We regret to inform you that your account application has not been approved at this time.</p>
                <p>This could be due to various reasons, such as incomplete information or not meeting our current criteria.</p>
                <p>You are welcome to submit a new application with complete information or contact us for more details.</p>
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; font-size: 0.8em; color: #666;">
                    <p>CarbonTally - Empowering Tree Monitoring and Climate Action</p>
                    <p>If you have any questions, please contact us at <a href="mailto:okothbasil45@gmail.com" style="color: #2e8b57;">okothbasil45@gmail.com</a></p>
                </div>
            </div>
        </body>
        </html>
        """
    },
    "password_reset": {
        "subject": "CarbonTally - Password Reset Link",
        "body": """
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">
                <div style="text-align: center; margin-bottom: 20px;">
                    <h2 style="color: #2e8b57;">🌱 CarbonTally</h2>
                </div>
                <p>Dear User,</p>
                <p>We received a request to reset your password for your CarbonTally account.</p>
                <p>To reset your password, please click on the link below:</p>
                <p style="text-align: center;">
                    <a href="{reset_link}" style="display: inline-block; padding: 10px 20px; background-color: #2e8b57; color: white; text-decoration: none; border-radius: 5px;">Reset Password</a>
                </p>
                <p>This link will expire in 24 hours.</p>
                <p>If you did not request a password reset, please ignore this email or contact us if you have concerns.</p>
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; font-size: 0.8em; color: #666;">
                    <p>CarbonTally - Empowering Tree Monitoring and Climate Action</p>
                    <p>If you have any questions, please contact us at <a href="mailto:okothbasil45@gmail.com" style="color: #2e8b57;">okothbasil45@gmail.com</a></p>
                </div>
            </div>
        </body>
        </html>
        """
    }
}

def initialize_firebase():
    """Initialize Firebase Admin SDK if not already initialized"""
    try:
        if not firebase_admin._apps:
            try:
                # Try to load Firebase config from Streamlit secrets
                firebase_config = {
                    "type": st.secrets["FIREBASE"]["TYPE"],
                    "project_id": st.secrets["FIREBASE"]["PROJECT_ID"],
                    "private_key_id": st.secrets["FIREBASE"]["PRIVATE_KEY_ID"],
                    "private_key": st.secrets["FIREBASE"]["PRIVATE_KEY"].replace('\\n', '\n'),
                    "client_email": st.secrets["FIREBASE"]["CLIENT_EMAIL"],
                    "client_id": st.secrets["FIREBASE"]["CLIENT_ID"],
                    "auth_uri": st.secrets["FIREBASE"]["AUTH_URI"],
                    "token_uri": st.secrets["FIREBASE"]["TOKEN_URI"],
                    "auth_provider_x509_cert_url": st.secrets["FIREBASE"]["AUTH_PROVIDER_X509_CERT_URL"],
                    "client_x509_cert_url": st.secrets["FIREBASE"]["CLIENT_X509_CERT_URL"],
                    "universe_domain": st.secrets["FIREBASE"]["UNIVERSE_DOMAIN"]
                }
            except KeyError:
                # Fallback to local file if Streamlit secrets are not available
                st.warning("Firebase secrets not found. Attempting to load credentials from firebase_credentials.json.")
                cred_path = BASE_DIR / "firebase_credentials.json"
                with open(cred_path, 'r') as f:
                    firebase_config = json.load(f)

            # Initialize Firebase app
            cred = credentials.Certificate(firebase_config)
            firebase_admin.initialize_app(cred)

        # Initialize Firestore
        db = firestore.client()

        # Cache in session state
        if 'firebase_db' not in st.session_state:
            st.session_state.firebase_db = db

        return db

    except Exception as e:
        st.error(f"Firebase initialization failed: {str(e)}")
        st.info("Please ensure your `.streamlit/secrets.toml` is correctly configured or `firebase_credentials.json` is present.")
        return None

# Email Utility Functions
def send_email(recipient_email, subject, html_content):
    """
    Send an email using SMTP settings from secrets.toml
    
    Args:
        recipient_email (str): Email address of the recipient
        subject (str): Email subject
        html_content (str): HTML content of the email
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        # Get SMTP settings from secrets.toml
        smtp_server = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(st.secrets.get("SMTP_PORT", 587))
        smtp_username = st.secrets.get("SMTP_USERNAME", "")
        smtp_password = st.secrets.get("SMTP_PASSWORD", "")
        sender_email = st.secrets.get("SMTP_SENDER", smtp_username)
        
        if not smtp_username or not smtp_password:
            logger.warning("SMTP credentials not found in secrets.toml. Email not sent.")
            return False
            
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = sender_email
        message["To"] = recipient_email
        
        # Attach HTML content
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, recipient_email, message.as_string())
            
        logger.info(f"Email sent successfully to {recipient_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

def send_approval_email(user_data):
    """
    Send approval email to user
    
    Args:
        user_data (dict): User data including email, fullName, and treeTrackingNumber
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        recipient_email = user_data.get("email")
        full_name = user_data.get("fullName", "User")
        tracking_number = user_data.get("treeTrackingNumber", "")
        
        # Get app URL from secrets or use default
        app_url = st.secrets.get("APP_URL", "https://carbontally.app")
        
        # Format email template
        template = EMAIL_TEMPLATES["approval"]
        subject = template["subject"]
        body = template["body"].format(
            fullName=full_name,
            treeTrackingNumber=tracking_number,
            app_url=app_url
        )
        
        # Send email
        return send_email(recipient_email, subject, body)
        
    except Exception as e:
        logger.error(f"Failed to send approval email: {str(e)}")
        return False

def send_rejection_email(user_data):
    """
    Send rejection email to user
    
    Args:
        user_data (dict): User data including email and fullName
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        recipient_email = user_data.get("email")
        full_name = user_data.get("fullName", "User")
        
        # Format email template
        template = EMAIL_TEMPLATES["rejection"]
        subject = template["subject"]
        body = template["body"].format(fullName=full_name)
        
        # Send email
        return send_email(recipient_email, subject, body)
        
    except Exception as e:
        logger.error(f"Failed to send rejection email: {str(e)}")
        return False

def send_password_reset_email(email):
    """
    Send password reset email to user
    
    Args:
        email (str): User's email address
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        # Generate password reset link using Firebase Auth
        reset_link = generate_password_reset_link(email)
        
        if not reset_link:
            logger.error(f"Failed to generate password reset link for {email}")
            return False
            
        # Format email template
        template = EMAIL_TEMPLATES["password_reset"]
        subject = template["subject"]
        body = template["body"].format(reset_link=reset_link)
        
        # Send email
        return send_email(email, subject, body)
        
    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}")
        return False

def generate_password_reset_link(email):
    """
    Generate a password reset link using Firebase Auth
    
    Args:
        email (str): User's email address
        
    Returns:
        str: Password reset link or None if failed
    """
    try:
        # Get app URL from secrets or use default
        app_url = st.secrets.get("APP_URL", "https://carbontally.app")
        
        # Generate action code settings
        action_code_settings = auth.ActionCodeSettings(
            url=f"{app_url}/reset-password",
            handle_code_in_app=True
        )
        
        # Generate password reset link
        reset_link = auth.generate_password_reset_link(
            email, 
            action_code_settings
        )
        
        return reset_link
        
    except Exception as e:
        logger.error(f"Failed to generate password reset link: {str(e)}")
        return None

# User Authentication Functions
def firebase_login_ui():
    """Display Firebase login UI and handle authentication"""
    st.markdown("<h3 style='text-align: center; color: #1D7749;'>Login to Your Account</h3>", unsafe_allow_html=True)
    
    with st.form("firebase_login_form"):
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Login", use_container_width=True)
        
        if submitted:
            if not email or not password:
                st.warning("Please enter both email and password")
            else:
                try:
                    user_record = auth.get_user_by_email(email)
                    
                    db = st.session_state.firebase_db
                    user_doc = db.collection('users').document(user_record.uid).get()
                    
                    if user_doc.exists:
                        user_data = user_doc.to_dict()
                        
                        # Check if user is approved
                        if user_data.get('status') != 'approved':
                            st.error("Your account is pending approval. Please wait for admin approval.")
                            return
                        
                        # Store ALL required user data in session state
                        st.session_state.user = {
                            'uid': user_record.uid,
                            'email': user_record.email,
                            'username': user_data.get('username', user_record.email.split('@')[0]),  # Fallback to email prefix if no username
                            'displayName': user_data.get('fullName', 'User'),
                            'role': user_data.get('role', 'individual'),  # Required: user_type
                            'user_type': user_data.get('role', 'individual'),  # Alias for compatibility
                            'institution': user_data.get('institution', ''),
                            'treeTrackingNumber': user_data.get('treeTrackingNumber', '')
                        }
                        
                        st.session_state.authenticated = True
                        
                        # Set appropriate page based on role
                        if user_data.get('role') == 'admin':
                            st.session_state.page = "Admin Dashboard"
                        else:
                            st.session_state.page = "User Dashboard"
                        
                        st.success(f"Welcome {user_data.get('fullName', 'User')}!")
                        st.rerun()
                    else:
                        st.error("User profile not found in Firestore. Please contact support.")
                except exceptions.FirebaseError as e:
                    st.error(f"Firebase error: {e}")
                except Exception as e:
                    st.error(f"An unexpected error occurred during login: {str(e)}")

def firebase_signup_ui():
    """Display Firebase signup UI and handle user registration"""
    st.markdown("<h3 style='text-align: center; color: #1D7749;'>Create New Account</h3>", unsafe_allow_html=True)
    
    with st.form("firebase_signup_form"):
        fullname = st.text_input("Full Name", key="signup_fullname")
        email = st.text_input("Email", key="signup_email")
        
        # User role selection (simplified to individual/institution)
        role = st.selectbox("Account Type", ["individual", "institution"], key="signup_role")
        
        # Institution name field (shown only for institution role)
        institution = ""
        if role == "institution":
            institution = st.text_input("Institution Name", key="signup_institution")
        
        # Additional fields as per requirements
        country = st.text_input("Country", key="signup_country")
        county = st.text_input("County", key="signup_county")
        location = st.text_input("Location", key="signup_location")
        reason = st.text_area("Reason for Joining", key="signup_reason")
        
        # How did you hear about us
        heard_about = st.selectbox("How did you hear about us?", 
                                  ["Social Media", "Friend/Colleague", "Search Engine", "Event", "Other"], 
                                  key="signup_heard_about")
        
        # Terms and conditions
        terms_agreed = st.checkbox("I agree to the Terms and Conditions", key="signup_terms")
        
        # Password fields
        password = st.text_input("Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm_password")
        
        submitted = st.form_submit_button("Sign Up", use_container_width=True)
        
        if submitted:
            # Validate inputs
            if not fullname or not email or not password or not confirm_password:
                st.error("Please fill in all required fields")
                return
                
            if role == "institution" and not institution:
                st.error("Institution name is required for institution accounts")
                return
                
            if not terms_agreed:
                st.error("You must agree to the Terms and Conditions")
                return
                
            if password != confirm_password:
                st.error("Passwords do not match")
                return
                
            if len(password) < 6:
                st.error("Password must be at least 6 characters")
                return
            
            # Create user in Firebase Auth
            try:
                # Check if user already exists
                try:
                    existing_user = auth.get_user_by_email(email)
                    st.error("An account with this email already exists")
                    return
                except firebase_admin.auth.UserNotFoundError: # Correct exception for user not found
                    pass # User doesn't exist, proceed with creation
                
                # Create user in Firebase Auth
                user = auth.create_user(
                    email=email,
                    password=password,
                    display_name=fullname,
                    disabled=False  # Account is enabled but will need approval
                )
                
                # Store additional user data in Firestore
                db = st.session_state.firebase_db
                user_data = {
                    'fullName': fullname,
                    'email': email,
                    'role': role,
                    'institution': institution if role == "institution" else "",
                    'country': country,
                    'county': county,
                    'location': location,
                    'reason': reason,
                    'heardAbout': heard_about,
                    'termsAgreed': terms_agreed,
                    'createdAt': firestore.SERVER_TIMESTAMP,
                    'status': 'pending',  # Pending admin approval
                    'treeTrackingNumber': ""  # Will be assigned upon approval
                }
                
                db.collection('users').document(user.uid).set(user_data)
                
                st.success("Account created successfully! Your account is pending approval by an administrator.")
                
            except Exception as e:
                st.error(f"An unexpected error occurred during account creation: {str(e)}")

def firebase_password_recovery_ui():
    """Display password recovery UI and send reset email"""
    st.markdown("<h3 style='text-align: center; color: #1D7749;'>Reset Your Password</h3>", unsafe_allow_html=True)
    
    with st.form("password_recovery_form"):
        email = st.text_input("Email Address", key="recovery_email")
        submitted = st.form_submit_button("Send Reset Link", use_container_width=True)
        
        if submitted:
            if not email:
                st.warning("Please enter your email address")
                return
                
            try:
                # Check if user exists
                try:
                    user = auth.get_user_by_email(email)
                    
                    # Send password reset email
                    if send_password_reset_email(email):
                        st.success(f"Password reset link sent to {email}. Please check your inbox.")
                    else:
                        st.warning(f"Password reset link could not be sent. Please try again later or contact support.")
                        
                except firebase_admin.auth.UserNotFoundError:
                    # For security reasons, don't reveal if email exists or not
                    st.success(f"If an account with {email} exists, a password reset link has been sent to it. Please check your inbox.")
                    
            except Exception as e:
                logger.error(f"Password reset error: {str(e)}")
                st.error("An error occurred while processing your request. Please try again later.")

def generate_tree_tracking_number(role, institution=None):
    """
    Generate a unique tree tracking number for approved users
    
    Format: [I/N][Institution prefix if applicable][Random 6 digits]
    I = Institution, N = Individual
    
    Examples:
    - Individual: N123456
    - Institution (Acme School): IACM123456
    """
    # Role prefix: I for institution, N for individual
    prefix = "I" if role == "institution" else "N"
    
    # Add institution prefix if applicable (first 3 letters, uppercase)
    inst_prefix = ""
    if role == "institution" and institution:
        # Remove spaces, special chars, take first 3 letters
        inst_prefix = re.sub(r'[^a-zA-Z]', '', institution)[:3].upper()
    
    # Generate random 6-digit number
    random_digits = str(uuid.uuid4().int)[:6]
    
    # Combine to form tracking number
    tracking_number = f"{prefix}{inst_prefix}{random_digits}"
    
    return tracking_number

def firebase_admin_approval_ui():
    """Display admin UI for approving new users and assigning tree tracking numbers"""
    if not st.session_state.get('authenticated'):
        st.error("You must be logged in as an admin to access this page")
        return
        
    user_role = st.session_state.user.get('role')
    if user_role != 'admin':
        st.error("You don't have permission to access this page")
        return
    
    st.markdown("<h3 style='color: #1D7749;'>User Approval Dashboard</h3>", unsafe_allow_html=True)
    
    try:
        db = st.session_state.firebase_db
        
        # Get pending users
        # For simplicity and to avoid complex Firestore indexing, we'll fetch all and filter in Python.
        # In a very large scale app, you'd use Firestore queries with `where` clauses.
        all_users_ref = db.collection('users').stream()
        pending_users = []
        
        for user_doc in all_users_ref:
            user_data = user_doc.to_dict()
            user_data['uid'] = user_doc.id # Add UID to the dictionary
            if user_data.get('status') == 'pending':
                pending_users.append(user_data)
        
        if not pending_users:
            st.info("No pending user applications")
            return
            
        st.write(f"Found {len(pending_users)} pending applications")
        
        for i, user in enumerate(pending_users):
            with st.expander(f"{user.get('fullName', 'N/A')} - {user.get('email', 'N/A')} ({user.get('role', 'N/A')})"):
                st.write(f"**Full Name:** {user.get('fullName', 'N/A')}")
                st.write(f"**Email:** {user.get('email', 'N/A')}")
                st.write(f"**Role:** {user.get('role', 'N/A')}")
                
                if user.get('role') == 'institution':
                    st.write(f"**Institution:** {user.get('institution', 'N/A')}")
                    
                st.write(f"**Country:** {user.get('country', 'N/A')}")
                st.write(f"**County:** {user.get('county', 'N/A')}")
                st.write(f"**Location:** {user.get('location', 'N/A')}")
                st.write(f"**Reason for Joining:** {user.get('reason', 'N/A')}")
                st.write(f"**Heard About Us:** {user.get('heardAbout', 'N/A')}")
                created_at_dt = None
                if user.get('createdAt'):
                    # Firestore Timestamps need conversion
                    if isinstance(user.get('createdAt'), datetime.datetime):
                        created_at_dt = user.get('createdAt')
                    elif hasattr(user.get('createdAt'), 'nanoseconds'): # Firebase Timestamp object
                         created_at_dt = user.get('createdAt').comparable_datetime(tzinfo=datetime.timezone.utc)
                    else:
                        created_at_dt = datetime.datetime.fromtimestamp(user.get('createdAt'), tz=datetime.timezone.utc) # Assume epoch if not datetime object
                st.write(f"**Applied On:** {created_at_dt.strftime('%Y-%m-%d %H:%M:%S') if created_at_dt else 'Unknown'}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("Approve", key=f"approve_{user.get('uid')}", use_container_width=True):
                        # Generate tree tracking number
                        tracking_number = generate_tree_tracking_number(user.get('role'), user.get('institution'))
                        
                        # Update user status and add tracking number
                        db.collection('users').document(user.get('uid')).update({
                            'status': 'approved',
                            'treeTrackingNumber': tracking_number,
                            'approvedAt': firestore.SERVER_TIMESTAMP
                        })
                        
                        # Update user data for email
                        user['treeTrackingNumber'] = tracking_number
                        
                        # Send approval email
                        email_sent = send_approval_email(user)
                        
                        # Log the approval and email status
                        if email_sent:
                            st.success(f"User approved with tracking number: {tracking_number}. Approval email sent.")
                        else:
                            st.warning(f"User approved with tracking number: {tracking_number}, but approval email could not be sent.")
                        
                        st.rerun()
                
                with col2:
                    if st.button("Reject", key=f"reject_{user.get('uid')}", use_container_width=True):
                        # Update user status
                        db.collection('users').document(user.get('uid')).update({
                            'status': 'rejected',
                            'rejectedAt': firestore.SERVER_TIMESTAMP
                        })
                        
                        # Send rejection email
                        email_sent = send_rejection_email(user)
                        
                        # Log the rejection and email status
                        if email_sent:
                            st.error("User rejected. Rejection email sent.")
                        else:
                            st.error("User rejected, but rejection email could not be sent.")
                        
                        st.rerun()
    
    except Exception as e:
        st.error(f"Error loading pending users: {str(e)}")

def firebase_logout():
    """Handle user logout"""
    # Clear session state
    if 'user' in st.session_state:
        del st.session_state.user
    
    if 'authenticated' in st.session_state:
        del st.session_state.authenticated
    
    # Note: Firebase Admin SDK doesn't have a logout method
    # Client-side Firebase Auth would handle token invalidation

def get_current_firebase_user():
    """Get current Firebase user from session state"""
    if st.session_state.get('authenticated') and 'user' in st.session_state:
        return st.session_state.user
    return None

def check_firebase_user_role(user, role):
    """Check if user has specified role"""
    if not user:
        return False
    
    return user.get('role') == role

def show_firebase_setup_guide():
    """Displays a guide for setting up Firebase credentials for this application."""
    st.markdown("<h3 style='color: #1D7749;'>Firebase Setup Guide</h3>", unsafe_allow_html=True)
    
    st.markdown("""
    To enable Firebase authentication and user management in this application, you need to configure your Firebase project and provide the service account credentials.

    **Follow these steps carefully:**

    ---
    #### Step 1: Create a Firebase Project
    1.  Go to the [Firebase Console](https://console.firebase.google.com/)
    2.  Click "Add project" and follow the on-screen instructions.
    3.  Enable Google Analytics for your project if desired.
    4.  Click "Create project".

    ---
    #### Step 2: Set Up Authentication
    1.  In your Firebase project, navigate to "Build" > "Authentication" in the left sidebar.
    2.  Click "Get started".
    3.  Go to the "Sign-in method" tab.
    4.  Enable the **"Email/Password"** provider.
    5.  Ensure "Email/Password" is enabled. You can optionally enable other providers later.
    6.  Save your changes.

    ---
    #### Step 3: Create a Firestore Database
    1.  In your Firebase project, navigate to "Build" > "Firestore Database" in the left sidebar.
    2.  Click "Create database".
    3.  Choose to start in **"production mode"** (you can adjust security rules later).
    4.  Select a location closest to your users.
    5.  Click "Enable".

    ---
    #### Step 4: Generate Service Account Credentials
    1.  In your Firebase project, go to "Project settings" (the gear icon next to "Project overview").
    2.  Navigate to the **"Service accounts"** tab.
    3.  Click the **"Generate new private key"** button.
    4.  A JSON file will be downloaded. This file contains your service account credentials.
    5.  **Save this JSON file securely.** It grants administrative access to your Firebase project.

    ---
    #### Step 5: Configure Streamlit Secrets or Place JSON File
    You have two primary options to provide these credentials to your Streamlit app:

    **Option A (Recommended for Deployment): Using Streamlit Secrets**
    * Create a `.streamlit` folder in your project's root directory if it doesn't exist.
    * Inside `.streamlit`, create a file named `secrets.toml`.
    * Open the JSON file you downloaded in Step 4. Copy its contents.
    * Paste the contents into `secrets.toml` under a `[FIREBASE]` section, converting JSON keys to TOML format.
        * **Important:** The `private_key` value in the JSON file contains newline characters (`\n`). In `secrets.toml`, these need to be escaped as `\\n`.

        Example `secrets.toml` structure:
        ```toml
        [FIREBASE]
        TYPE = "service_account"
        PROJECT_ID = "your-project-id"
        PRIVATE_KEY_ID = "your-private-key-id"
        PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\\n...your_private_key_content...\\n-----END PRIVATE KEY-----\\n"
        CLIENT_EMAIL = "firebase-adminsdk-xxxxx@your-project-id.iam.gserviceaccount.com"
        CLIENT_ID = "your-client-id"
        AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
        TOKEN_URI = "https://oauth2.googleapis.com/token"
        AUTH_PROVIDER_X509_CERT_URL = "https://www.googleapis.com/oauth2/v1/certs"
        CLIENT_X509_CERT_URL = "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-xxxxx%40your-project-id.iam.gserviceaccount.com"
        UNIVERSE_DOMAIN = "googleapis.com"
        
        # Email configuration for notifications
        SMTP_SERVER = "smtp.gmail.com"
        SMTP_PORT = 587
        SMTP_USERNAME = "your-email@gmail.com"
        SMTP_PASSWORD = "your-app-password"
        SMTP_SENDER = "CarbonTally <your-email@gmail.com>"
        APP_URL = "https://your-app-url.com"
        ```
        * **Ensure `PRIVATE_KEY` has `\\n` for newlines.**
        * **Add the email configuration for notifications.**

    **Option B (For Local Development, less secure for deployment): Placing the JSON File Directly**
    * Rename the downloaded JSON file to `firebase_credentials.json`.
    * Place this `firebase_credentials.json` file in the **same directory** as your `app.py` and `firebase_auth_integration.py` files.
    * The `initialize_firebase()` function will attempt to load from `secrets.toml` first, then fall back to `firebase_credentials.json`.

    ---
    #### Step 6: Configure Email Settings for Notifications
    To enable email notifications for account approval, rejection, and password reset:

    1. If using Gmail:
       * Go to your Google Account settings
       * Enable 2-Step Verification
       * Generate an App Password (under Security > App passwords)
       * Use this App Password in your `secrets.toml` file

    2. Add these settings to your `secrets.toml` file:
       ```toml
       SMTP_SERVER = "smtp.gmail.com"
       SMTP_PORT = 587
       SMTP_USERNAME = "your-email@gmail.com"
       SMTP_PASSWORD = "your-app-password"
       SMTP_SENDER = "CarbonTally <your-email@gmail.com>"
       APP_URL = "https://your-app-url.com"
       ```

    ---
    #### Step 7: Restart Your Streamlit Application
    After placing the `secrets.toml` file or `firebase_credentials.json`, restart your Streamlit application completely.

    If you've followed these steps, the "Authentication services are currently unavailable" message should disappear, and Firebase features will become active.
    """)
    
    if st.button("I've configured Firebase credentials. Try re-initializing.", use_container_width=True):
        if initialize_firebase():
            st.success("Firebase re-initialized successfully! You can now proceed with login/signup and other features.")
            st.session_state.firebase_initialized = True # Update session state
            st.rerun()
        else:
            st.error("Firebase re-initialization failed. Please double-check your credentials and setup.")
            st.session_state.firebase_initialized = False # Update session state

# The __name__ == "__main__" block for testing the module directly
if __name__ == "__main__":
    st.set_page_config(
        page_title="CarbonTally - Firebase Auth Test Module",
        layout="wide"
    )
    st.title("Firebase Authentication Integration Test Module")
    
    # Initialize Firebase at startup for testing within this module
    if 'firebase_initialized' not in st.session_state:
        st.session_state.firebase_initialized = initialize_firebase()

    st.markdown("---")
    st.subheader("Test UI for Firebase Auth Integration")

    if st.session_state.get('firebase_initialized'):
        st.success("Firebase Admin SDK is initialized.")
        
        test_tab_login, test_tab_signup, test_tab_recovery, test_tab_admin, test_tab_setup, test_tab_email = st.tabs([
            "Login", "Sign Up", "Password Recovery", "Admin Approval", "Setup Guide", "Test Email"
        ])

        with test_tab_login:
            firebase_login_ui()
        with test_tab_signup:
            firebase_signup_ui()
        with test_tab_recovery:
            firebase_password_recovery_ui()
        with test_tab_admin:
            st.info("To test Admin Approval, you need to be logged in as an 'admin' user.")
            firebase_admin_approval_ui()
        with test_tab_setup:
            show_firebase_setup_guide()
        with test_tab_email:
            st.subheader("Test Email Sending")
            
            email_type = st.selectbox("Email Type", ["Approval", "Rejection", "Password Reset"])
            recipient = st.text_input("Recipient Email")
            
            if st.button("Send Test Email"):
                if not recipient:
                    st.error("Please enter a recipient email address")
                else:
                    if email_type == "Approval":
                        user_data = {
                            "email": recipient,
                            "fullName": "Test User",
                            "treeTrackingNumber": "NTEST123456"
                        }
                        if send_approval_email(user_data):
                            st.success(f"Approval email sent to {recipient}")
                        else:
                            st.error(f"Failed to send approval email to {recipient}")
                    elif email_type == "Rejection":
                        user_data = {
                            "email": recipient,
                            "fullName": "Test User"
                        }
                        if send_rejection_email(user_data):
                            st.success(f"Rejection email sent to {recipient}")
                        else:
                            st.error(f"Failed to send rejection email to {recipient}")
                    else:  # Password Reset
                        if send_password_reset_email(recipient):
                            st.success(f"Password reset email sent to {recipient}")
                        else:
                            st.error(f"Failed to send password reset email to {recipient}")
            
        st.markdown("---")
        st.subheader("Current User Info (if logged in)")
        current_user = get_current_firebase_user()
        if current_user:
            st.json(current_user)
            if st.button("Logout from Test UI"):
                firebase_logout()
                st.rerun()
        else:
            st.info("No user currently logged in.")
            
    else:
        st.error("Firebase Admin SDK is NOT initialized. Please follow the setup guide.")
        show_firebase_setup_guide()
