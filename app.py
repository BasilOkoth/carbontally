import streamlit as st
# Set page config - MUST BE THE FIRST STREAMLIT COMMAND
st.set_page_config(
    page_title="CarbonTally - Tree Monitoring",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)
from branding_footer import add_branding_footer

import pandas as pd
import datetime
from geopy.distance import geodesic
from pathlib import Path
import re
import random
import os
import time
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import hashlib
from typing import Optional, Tuple, Dict, Any
from geopy.geocoders import Nominatim
import qrcode
from io import BytesIO
import base64
import requests
from PIL import Image
import paypalrestsdk
from paypalrestsdk import Payment
import json
# Import the KoBo integration module
from kobo_integration import plant_a_tree_section, check_for_new_submissions
from donor_dashboard import donor_dashboard
# Import the NEW monitoring module
from kobo_monitoring import monitoring_section, admin_tree_lookup

# define location
from geopy.geocoders import Nominatim

def get_location():
    try:
        # Optional: Try browser geolocation via streamlit_javascript if installed
        from streamlit_javascript import st_javascript
        result = st_javascript(
            "navigator.geolocation.getCurrentPosition(pos => ({latitude: pos.coords.latitude, longitude: pos.coords.longitude}))"
        )
        if result and "latitude" in result and "longitude" in result:
            return {
                "latitude": result["latitude"],
                "longitude": result["longitude"]
            }
    except:
        pass

    # Fallback: Use static/default location via geopy
    try:
        geolocator = Nominatim(user_agent="tree_monitoring_app")
        location = geolocator.geocode("Kenya")
        if location:
            return {"latitude": location.latitude, "longitude": location.longitude}
    except:
        pass

    raise Exception("Could not detect location")

# --- Custom CSS for Styling ---
def load_css():
    st.markdown("""
    <style>
        /* Main styling */
        body {
            font-family: 'Arial', sans-serif;
            background-color: #f5f5f5;
        }
        
        /* Header styling */
        .header-text {
            color: #2e8b57;
            font-weight: 700;
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }
        
        /* Sidebar styling */
        .sidebar .sidebar-content {
            background-color: #e8f5e9;
        }
        
        /* Button styling */
        .stButton>button {
            background-color: #4CAF50;
            color: white;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            border: none;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .stButton>button:hover {
            background-color: #388E3C;
            transform: scale(1.02);
        }
        
        /* Card styling */
        .card {
            background-color: white;
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            margin-bottom: 1.5rem;
        }
        
        /* Tree visualization */
        .tree-visualization {
            text-align: center;
            margin: 2rem 0;
        }
        
        /* Progress bars */
        .progress-container {
            background-color: #e0e0e0;
            border-radius: 10px;
            height: 20px;
            margin: 1rem 0;
        }
        
        .progress-bar {
            background-color: #4CAF50;
            height: 100%;
            border-radius: 10px;
            transition: width 0.5s;
        }
        
        /* Custom tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background-color: #e8f5e9;
            border-radius: 8px 8px 0 0 !important;
            padding: 10px 20px;
            transition: all 0.3s;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #4CAF50 !important;
            color: white !important;
        }
        
        /* Tree growth animation */
        @keyframes grow {
            0% { transform: scaleY(0.1); }
            100% { transform: scaleY(1); }
        }
        
        .tree-icon {
            font-size: 2rem;
            display: inline-block;
            animation: grow 1.5s ease-in-out;
        }
        
        /* Footer styling */
        .footer {
            margin-top: 3rem;
            padding-top: 1rem;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            color: #666;
        }
        
        /* QR code styling */
        .qr-container {
            display: flex;
            justify-content: center;
            margin: 2rem 0;
        }
        
        /* Landing page metrics */
        .metric-card {
            background-color: white;
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            margin-bottom: 1.5rem;
            text-align: center;
        }
        
        .metric-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: #2e8b57;
            margin: 0.5rem 0;
        }
        
        .metric-label {
            font-size: 1rem;
            color: #666;
        }
        
        /* Payment styling */
        .payment-amount {
            font-size: 1.5rem;
            font-weight: bold;
            color: #2e8b57;
            text-align: center;
            margin: 1rem 0;
        }
    </style>
    """, unsafe_allow_html=True)

# --- Configuration ---
DEFAULT_SPECIES = ["Acacia", "Eucalyptus", "Mango", "Neem", "Oak", "Pine"]
BASE_DIR = Path(__file__).parent if "__file__" in locals() else Path.cwd()
DATA_DIR = BASE_DIR / "data"
SQLITE_DB = DATA_DIR / "trees.db"
QR_CODE_DIR = DATA_DIR / "qr_codes"
STORAGE_METHOD = "sqlite"

# Ensure QR code directory exists
QR_CODE_DIR.mkdir(exist_ok=True, parents=True)

# PayPal Configuration
PAYPAL_MODE = "sandbox"  # or "live" for production
PAYPAL_CLIENT_ID = st.secrets.get("PAYPAL_CLIENT_ID", "your_client_id")
PAYPAL_CLIENT_SECRET = st.secrets.get("PAYPAL_CLIENT_SECRET", "your_client_secret")
PAYPAL_WEBHOOK_ID = st.secrets.get("PAYPAL_WEBHOOK_ID", "your_webhook_id")  # For production

# KoBo Toolbox configuration
KOBO_API_URL = "https://kf.kobotoolbox.org/api/v2"
KOBO_API_TOKEN = st.secrets.get("KOBO_API_TOKEN", "your_kobo_api_token")  # Replace with your actual token
KOBO_ASSET_ID = st.secrets.get("KOBO_ASSET_ID", "your_asset_id")  # Replace with your actual asset ID

# --- Password Hashing ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# --- User Types ---
USER_TYPES = {
    "admin": "Administrator",
    "school": "Institution User",
    "public": "Public Viewer",
    "field": "Field Agent",
    "donor": "Guest Donor"
}

# --- Database Initialization with Migration ---
def initialize_data_files():
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    if STORAGE_METHOD == "sqlite":
        init_db()


def init_db():
    conn = sqlite3.connect(SQLITE_DB)
    c = conn.cursor()
    
    # Create tables with new schema if they don't exist
    c.execute("""CREATE TABLE IF NOT EXISTS trees (
        tree_id TEXT PRIMARY KEY,
        institution TEXT,
        local_name TEXT,
        scientific_name TEXT,
        student_name TEXT,
        date_planted TEXT,
        tree_stage TEXT,
        rcd_cm REAL,
        dbh_cm REAL,
        height_m REAL,
        latitude REAL,
        longitude REAL,
        co2_kg REAL,
        status TEXT,
        country TEXT,
        county TEXT,
        sub_county TEXT,
        ward TEXT,
        adopter_name TEXT,
        last_monitored TEXT,
        monitor_notes TEXT,
        qr_code TEXT,
        kobo_submission_id TEXT UNIQUE
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS species (
        scientific_name TEXT PRIMARY KEY,
        local_name TEXT,
        wood_density REAL,
        benefits TEXT
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        user_type TEXT,
        institution TEXT,
        is_test_user INTEGER DEFAULT 0
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS monitoring_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tree_id TEXT,
        monitor_date TEXT,
        monitor_status TEXT,
        monitor_stage TEXT,
        rcd_cm REAL,
        dbh_cm REAL,
        height_m REAL,
        co2_kg REAL,
        notes TEXT,
        monitor_by TEXT,
        kobo_submission_id TEXT UNIQUE,
        FOREIGN KEY (tree_id) REFERENCES trees (tree_id)
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS payments (
        payment_id TEXT PRIMARY KEY,
        tree_id TEXT,
        institution TEXT,
        donor_name TEXT,
        donor_email TEXT,
        amount REAL,
        currency TEXT,
        payment_date TEXT,
        payment_status TEXT,
        message TEXT,
        FOREIGN KEY (tree_id) REFERENCES trees (tree_id)
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS processed_monitoring_submissions (
        submission_id TEXT PRIMARY KEY,
        tree_id TEXT,
        processed_date TEXT,
        FOREIGN KEY (tree_id) REFERENCES trees (tree_id)
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS donations (
        donation_id TEXT PRIMARY KEY,
        donor_email TEXT,
        donor_name TEXT,
        institution TEXT,
        num_trees INTEGER,
        amount REAL,
        currency TEXT,
        donation_date TEXT,
        payment_id TEXT,
        payment_status TEXT,
        message TEXT
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS donated_trees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donation_id TEXT,
        tree_id TEXT,
        FOREIGN KEY (donation_id) REFERENCES donations (donation_id),
        FOREIGN KEY (tree_id) REFERENCES trees (tree_id)
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS institution_qualification (
        institution TEXT PRIMARY KEY,
        is_qualified INTEGER DEFAULT 0,
        last_checked TEXT
    )""")
    
    # Initialize default data
    if c.execute("SELECT COUNT(*) FROM species").fetchone()[0] == 0:
        default_species = [
            ("Acacia spp.", "Acacia", 0.65, "Drought-resistant, nitrogen-fixing, provides shade"),
            ("Eucalyptus spp.", "Eucalyptus", 0.55, "Fast-growing, timber production, medicinal uses"),
            ("Mangifera indica", "Mango", 0.50, "Fruit production, shade tree, ornamental"),
            ("Azadirachta indica", "Neem", 0.60, "Medicinal properties, insect repellent, drought-resistant"),
            ("Quercus spp.", "Oak", 0.75, "Long-term carbon storage, wildlife habitat, durable wood"),
            ("Pinus spp.", "Pine", 0.45, "Reforestation, timber production, resin production")
        ]
        c.executemany("INSERT INTO species VALUES (?, ?, ?, ?)", default_species)
    
    # Update admin user with new schema
    c.execute("""INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?)""", 
             ("admin", hash_password("admin123"), "admin", "All Institutions", 1))
    
    # Add field agent user
    c.execute("""INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?)""", 
             ("field", hash_password("field123"), "field", "Field Team", 1))
    
    # Add test donor user
    c.execute("""INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?)""", 
             ("donor_test", hash_password("donor123"), "public", "", 1))
    
    conn.commit()
    conn.close()
    
    # Initialize PayPal
    init_paypal()

def init_paypal():
    try:
        paypalrestsdk.configure({
            "mode": PAYPAL_MODE,
            "client_id": PAYPAL_CLIENT_ID,
            "client_secret": PAYPAL_CLIENT_SECRET
        })
    except Exception as e:
        st.warning(f"PayPal SDK configuration failed: {e}. PayPal features may not work.")

# --- Tree Management Functions ---
def load_tree_data() -> pd.DataFrame:
    conn = sqlite3.connect(SQLITE_DB)
    try:
        df = pd.read_sql("SELECT * FROM trees", conn)
    except Exception as e:
        st.error(f"Error loading tree data: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def load_species_data() -> pd.DataFrame:
    conn = sqlite3.connect(SQLITE_DB)
    try:
        df = pd.read_sql("SELECT * FROM species", conn)
    except Exception as e:
        st.error(f"Error loading species data: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def load_monitoring_history(tree_id: str) -> pd.DataFrame:
    conn = sqlite3.connect(SQLITE_DB)
    try:
        df = pd.read_sql("SELECT * FROM monitoring_history WHERE tree_id = ? ORDER BY monitor_date DESC", conn, params=(tree_id,))
    except Exception as e:
        st.error(f"Error loading monitoring history: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def save_tree_data(df: pd.DataFrame) -> bool:
    try:
        conn = sqlite3.connect(SQLITE_DB)
        df.to_sql("trees", conn, if_exists="replace", index=False)
        conn.close()
        return True
    except Exception as e:
        st.error(f"Database error saving tree data: {e}")
        return False

def save_species_data(df: pd.DataFrame) -> bool:
    try:
        conn = sqlite3.connect(SQLITE_DB)
        df.to_sql("species", conn, if_exists="replace", index=False)
        conn.close()
        return True
    except Exception as e:
        st.error(f"Database error saving species data: {e}")
        return False

def add_monitoring_record(tree_id: str, data: dict) -> bool:
    try:
        conn = sqlite3.connect(SQLITE_DB)
        c = conn.cursor()
        
        c.execute("""INSERT INTO monitoring_history (
            tree_id, monitor_date, monitor_status, monitor_stage, 
            rcd_cm, dbh_cm, height_m, co2_kg, notes, monitor_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
        (
            tree_id,
            data["monitor_date"],
            data["monitor_status"],
            data["monitor_stage"],
            data["rcd_cm"],
            data["dbh_cm"],
            data["height_m"],
            data["co2_kg"],
            data["notes"],
            data["monitor_by"]
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Database error adding monitoring record: {e}")
        return False

def generate_tree_id(institution_name: str) -> str:
    prefix = institution_name[:3].upper()
    trees = load_tree_data()
    
    if trees.empty:
        return f"{prefix}001"
    
    institution_trees = trees[trees["institution"].str.lower() == institution_name.lower()]
    existing_ids = [id for id in institution_trees["tree_id"] if str(id).startswith(prefix)]
    
    if not existing_ids:
        return f"{prefix}001"
    
    max_num = max([int(re.search(r'\d+$', str(id)).group()) for id in existing_ids if re.search(r'\d+$', str(id))])
    return f"{prefix}{max_num + 1:03d}"

def calculate_co2(scientific_name: str, rcd: Optional[float] = None, dbh: Optional[float] = None) -> float:
    species_data = load_species_data()
    try:
        density = species_data[species_data["scientific_name"] == scientific_name]["wood_density"].values[0]
    except:
        density = 0.6
    
    if dbh is not None and dbh > 0:
        agb = 0.0509 * density * (dbh ** 2.5)
    elif rcd is not None and rcd > 0:
        agb = 0.042 * (rcd ** 2.5)
    else:
        return 0.0
        
    bgb = 0.2 * agb
    carbon = 0.47 * (agb + bgb)
    return round(carbon * 3.67, 2)

def generate_qr_code(tree_id: str) -> str:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(tree_id)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save as file
    file_path = QR_CODE_DIR / f"{tree_id}_qr.png"
    img.save(file_path)
    
    # Also create base64 encoded version for display
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return img_str

# --- Payment Functions ---
def save_payment_record(adoption_data: dict, payment: Payment):
    conn = sqlite3.connect(SQLITE_DB)
    c = conn.cursor()
    
    try:
        c.execute("""INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                 (
                     payment.id,
                     adoption_data["tree_id"],
                     adoption_data["institution"],
                     adoption_data["donor_name"],
                     adoption_data["donor_email"],
                     adoption_data["amount"],
                     "USD",
                     datetime.datetime.now().isoformat(),
                     payment.state,
                     adoption_data.get("message", "")
                 ))
        conn.commit()
    except Exception as e:
        st.error(f"Error saving payment record: {e}")
    finally:
        conn.close()

# --- Authentication Function ---
def authenticate(username: str, password: str) -> Optional[Tuple]:
    try:
        conn = sqlite3.connect(SQLITE_DB)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        
        if not user:
            return None
            
        if hash_password(password) == user[1]:
            return user
        else:
            return None
            
    except Exception as e:
        print(f"Authentication error: {e}")
        return None
    finally:
        conn.close()

# --- Visual Tree Growth Display ---
def display_tree_growth(height_m, max_height=30):
    growth_percentage = min((height_m / max_height) * 100, 100)
    
    st.markdown(f"""
    <div class="tree-visualization">
        <div style="font-size: 3rem; color: #2e8b57;">{'🌱' if height_m < 1 else '🌳' if height_m < 5 else '🌲'}</div>
        <div style="font-weight: bold; margin: 0.5rem 0;">Height: {height_m} meters</div>
        <div class="progress-container">
            <div class="progress-bar" style="width: {growth_percentage}%"></div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 0.5rem;">
            <span>0m</span>
            <span>{max_height}m</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- Test User Creation ---
def create_test_users():
    """Create default test users for demonstration purposes"""
    test_users = [
        ("admin", hash_password("admin123"), "admin", "All Institutions", 1),
        ("institution1", hash_password("inst123"), "school", "Greenwood High", 1),
        ("public1", hash_password("public123"), "public", "", 1),
        ("field1", hash_password("field123"), "field", "Field Team", 1),
        ("donor_test", hash_password("donor123"), "public", "", 1)
    ]
    
    conn = sqlite3.connect(SQLITE_DB)
    try:
        c = conn.cursor()
        
        for user in test_users:
            try:
                c.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?)", user)
            except sqlite3.IntegrityError:
                pass  # User already exists
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# --- Landing Page ---
def landing_page():
    st.markdown("<h1 class='header-text'>🌳 CarbonTally</h1>", unsafe_allow_html=True)
    
    # Main header card
    st.markdown("""
    <div class="card">
        <h3>Track, Monitor, and Celebrate Your Trees</h3>
        <p>Join our community in growing a greener future, one tree at a time.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Load data for metrics
    trees = load_tree_data()
    total_trees = len(trees)
    alive_trees = len(trees[trees["status"] == "Alive"])
    adopted_trees = len(trees[trees["adopter_name"].notna()])
    total_co2 = round(trees["co2_kg"].sum(), 2)
    institutions = trees["institution"].nunique()
    survival_rate = round((alive_trees / total_trees) * 100, 1) if total_trees > 0 else 0
    
    # Metrics section with 4 cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total_trees:,}</div>
            <div class="metric-label">Trees Planted</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{survival_rate}%</div>
            <div class="metric-label">Survival Rate</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total_co2:,} kg</div>
            <div class="metric-label">CO₂ Sequestered</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{institutions}</div>
            <div class="metric-label">Institutions</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Call to Action Section
    st.markdown("""
    <div class="card">
        <h3>Ready to Make a Difference?</h3>
        <p>Choose how you'd like to contribute to our green initiative:</p>
    </div>
    """, unsafe_allow_html=True)
    
    action_col1, action_col2 = st.columns(2)
    
    with action_col1:
        if st.button("🌱 Plant Trees With Us", 
                    use_container_width=True,
                    help="Join as an institution or field agent to plant and monitor trees"):
            st.session_state.landing_action = "plant"
            st.rerun()
    
    with action_col2:
        if st.button("🤝 Donate Trees", 
                   use_container_width=True,
                   help="Support existing trees and track their growth"):
            st.session_state.landing_action = "donate"
            st.rerun()
    
    # Direct login option
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem;">
        <p>Already have an account? <a href="#" onclick="window.location.href='?show_login=true'">Login here</a></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Handle the selected action
    if hasattr(st.session_state, 'landing_action'):
        if st.session_state.landing_action == "plant":
            show_plant_trees_options()
        elif st.session_state.landing_action == "donate":
            # Directly show donor dashboard as guest
            st.session_state.user = {
                "username": "guest_donor",
                "user_type": "donor",
                "email": "",
                "institution": ""
            }
            st.session_state.authenticated = True
            st.session_state.page = "Donor Dashboard" # Set page to donor dashboard
            del st.session_state.landing_action
            st.rerun()
    
    # Recent trees map (only show if no action selected)
    if not hasattr(st.session_state, 'landing_action'):
        st.subheader("Recently Planted Trees")
        if not trees.empty:
            recent_trees = trees.sort_values("date_planted", ascending=False).head(50)
            fig = px.scatter_mapbox(
                recent_trees,
                lat="latitude",
                lon="longitude",
                hover_name="tree_id",
                hover_data=["local_name", "institution", "date_planted"],
                color="status",
                color_discrete_map={"Alive": "#2e8b57", "Dead": "#d62728", "Adopted": "#1f77b4"},
                zoom=5,
                height=500
            )
            fig.update_layout(mapbox_style="open-street-map")
            fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
            st.plotly_chart(fig)
        else:
            st.info("No trees planted yet. Be the first to plant one!")

def show_plant_trees_options():
    st.subheader("Get Involved in Tree Planting")
    
    option = st.radio("Select an option:", 
                     ["I'm an existing user - Take me to login", 
                      "I'm new here - Show me how to register"])
    
    if option == "I'm an existing user - Take me to login":
        if st.button("Proceed to Login"):
            st.session_state.show_login = True
            del st.session_state.landing_action
            st.rerun()
    else:
        st.markdown("""
        <div class="card">
            <h4>How to Register:</h4>
            <ol>
                <li><strong>Institutions:</strong> Contact us at okothbasil45@gmail.com to create an administrator account</li>
                <li><strong>Field Agents:</strong> Request credentials from your institution administrator</li>
                <li><strong>Individuals:</strong> Download our mobile app from your app store</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Back to Main Page"):
            del st.session_state.landing_action
            st.rerun()

def show_adoptable_institutions():
    # This function is now handled by the donor dashboard
    pass

# --- Login Page ---
def login():
    st.markdown("<h1 class='header-text'>🌳 CarbonTally</h1>", unsafe_allow_html=True)
    
    # Add back button to return to landing page
    if st.button("← Back to Home"):
        if hasattr(st.session_state, 'show_login'):
            del st.session_state.show_login
        st.rerun()
    
    st.markdown("""
    <div class="card">
        <h3>Track, Monitor, and Celebrate Your Trees</h3>
        <p>Join our community in growing a greener future, one tree at a time.</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("🔧 Troubleshooting Tools", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Reset Database"):
                try:
                    if SQLITE_DB.exists():
                        SQLITE_DB.unlink()
                    initialize_data_files()
                    st.success("Database completely reset! Default admin: admin/admin123")
                except Exception as e:
                    st.error(f"Error resetting database: {e}")
        
        with col2:
            if st.button("Create Test Users"):
                create_test_users()
                st.success("Created test users: admin/admin123, institution1/inst123, public1/public123, field/field123")
        
        if st.button("Show All Users"):
            try:
                conn = sqlite3.connect(SQLITE_DB)
                users = pd.read_sql("SELECT username, user_type, institution FROM users", conn)
                conn.close()
                st.dataframe(users)
            except Exception as e:
                st.error(f"Error showing users: {e}")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            if not username or not password:
                st.warning("Please enter both username and password")
                return
                
            user = authenticate(username, password)
            
            if user:
                user_data = {
                    "username": user[0],
                    "user_type": user[2],
                    "institution": user[3] if len(user) > 3 else "",
                    "is_test_user": user[4] if len(user) > 4 else 0
                }
                
                st.session_state.user = user_data
                st.success(f"Welcome {user[0]}!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Invalid username or password")
                if username == "admin":
                    st.info("Default admin password is 'admin123'")
    # Guest donor option
    st.markdown("---")
    st.markdown("### Donate as Guest")
    st.markdown("Support tree planting initiatives without creating an account.")
    
    if st.button("Continue as Guest Donor"):
        # Set up guest donor session
        st.session_state.user = {
            "username": "guest_donor",
            "user_type": "donor",
            "email": "",
            "institution": ""
        }
        st.session_state.authenticated = True
        st.session_state.page = "Donor Dashboard" # Set page to donor dashboard
        st.rerun()

# --- Main App ---
def main():
    # Initialize data files if they don't exist
    initialize_data_files()
    
    # Load CSS
    load_css()
    
    # Page config is already set at the top of the file
    # Do not call st.set_page_config() here
    
    # Check if user is logged in
    if "user" not in st.session_state:
        # Show login page if requested
        if hasattr(st.session_state, 'show_login') and st.session_state.show_login:
            login()
        else:
            landing_page()
        return
    
    # User is logged in, show appropriate dashboard
    user_type = st.session_state.user.get("user_type", "")
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown(f"<h3>Welcome, {st.session_state.user.get('username', 'User')}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p>Role: {USER_TYPES.get(user_type, 'User')}</p>", unsafe_allow_html=True)
        
        # Define navigation options based on user type
        nav_options = []
        if user_type == "admin":
            nav_options = ["Dashboard", "Plant a Tree", "Monitoring", "Tree Lookup", "Reports", "Donor Dashboard"]
        elif user_type == "school":
            nav_options = ["Dashboard", "Plant a Tree", "Monitoring", "Reports"]
        elif user_type == "field":
            nav_options = ["Plant a Tree", "Monitoring"]
        elif user_type == "donor": # Guest Donor
            nav_options = ["Donor Dashboard"]
        else: # public (logged in)
            nav_options = ["Adopt a Tree", "My Trees"]
            
        # Use session state to manage the current page
        if 'page' not in st.session_state:
            st.session_state.page = nav_options[0] # Default to first option
            
        page = st.radio("Go to:", nav_options, key="navigation", index=nav_options.index(st.session_state.page))
        st.session_state.page = page # Update session state when radio changes
        
        if st.button("Logout"):
            # Clear relevant session state keys on logout
            keys_to_clear = ["user", "authenticated", "page", "landing_action", "show_login", "adopt_institution"]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.success("Logged out successfully!")
            time.sleep(1)
            st.rerun()

    # Display selected page based on session state
    current_page = st.session_state.page
    
    if current_page == "Dashboard":
        if user_type == "admin":
            admin_dashboard()
        elif user_type == "school":
            institution_dashboard()
        else:
            st.error("Access denied.")
    elif current_page == "Plant a Tree":
        plant_a_tree_section()
    elif current_page == "Monitoring":
        monitoring_section() # Use the new monitoring section
    elif current_page == "Tree Lookup":
        if user_type == "admin":
            admin_tree_lookup() # Use the new admin lookup
        else:
            st.error("Access denied.")
    elif current_page == "Reports":
        if user_type in ["admin", "school"]:
            reports_page()
        else:
            st.error("Access denied.")
    elif current_page == "Donor Dashboard":
        donor_dashboard()
    elif current_page == "Adopt a Tree":
        donor_dashboard() # Public users can adopt/donate
    elif current_page == "My Trees":
        my_trees_page() # For public users who adopted
    else:
        st.error("Page not found.")

# --- Institution Dashboard ---
def institution_dashboard():
    institution = st.session_state.user.get("institution", "")
    header_text = f"🏫 {institution} Dashboard" if institution else "🏫 Institution Dashboard"
    st.markdown(f"<h1 class='header-text'>{header_text}</h1>", unsafe_allow_html=True)
    
    # Load data
    trees = load_tree_data()
    institution_trees = trees[trees["institution"] == institution]
    
    # Institution metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Trees", len(institution_trees))
    
    with col2:
        alive_trees = len(institution_trees[institution_trees["status"] == "Alive"])
        survival_rate = round((alive_trees / len(institution_trees)) * 100, 1) if len(institution_trees) > 0 else 0
        st.metric("Survival Rate", f"{survival_rate}%")
    
    with col3:
        total_co2 = round(institution_trees["co2_kg"].sum(), 2)
        st.metric("CO₂ Sequestered", f"{total_co2} kg")
    
    with col4:
        adopted_trees = len(institution_trees[institution_trees["adopter_name"].notna()])
        st.metric("Adopted Trees", adopted_trees)
    
    # Recent plantings
    st.subheader("Recent Tree Plantings")
    if not institution_trees.empty:
        recent_trees = institution_trees.sort_values("date_planted", ascending=False).head(10)
        st.dataframe(recent_trees[["tree_id", "local_name", "scientific_name", "student_name", "date_planted", "status"]])
    else:
        st.info("No trees planted yet. Click on 'Plant a Tree' to get started!")
    
    # Tree map
    st.subheader("Tree Map")
    if not institution_trees.empty:
        fig = px.scatter_mapbox(
            institution_trees,
            lat="latitude",
            lon="longitude",
            hover_name="tree_id",
            hover_data=["local_name", "student_name", "date_planted"],
            color="status",
            color_discrete_map={"Alive": "#2e8b57", "Dead": "#d62728", "Adopted": "#1f77b4"},
            zoom=10,
            height=400
        )
        fig.update_layout(mapbox_style="open-street-map")
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig)
    else:
        st.info("No trees to display on the map.")

# --- REMOVED OLD monitor_trees() FUNCTION ---
# The functionality is now handled by kobo_monitoring.py

# --- Reports Page ---
def reports_page():
    st.markdown("<h1 class='header-text'>📊 Reports</h1>", unsafe_allow_html=True)
    
    user_type = st.session_state.user.get("user_type", "")
    institution = st.session_state.user.get("institution", "")
    
    # Load data
    trees = load_tree_data()
    
    # Filter trees based on user type
    if user_type == "admin":
        filtered_trees = trees
        st.subheader("System-wide Reports")
    elif user_type == "school":
        filtered_trees = trees[trees["institution"] == institution]
        st.subheader(f"Reports for {institution}")
    else:
        st.error("You don't have permission to view reports.")
        return
    
    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.datetime.now() - datetime.timedelta(days=365))
    with col2:
        end_date = st.date_input("End Date", datetime.datetime.now())
    
    # Convert to string format for comparison
    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()
    
    # Filter by date range
    date_filtered_trees = filtered_trees[
        (filtered_trees["date_planted"] >= start_date_str) & 
        (filtered_trees["date_planted"] <= end_date_str)
    ]
    
    st.subheader("Summary Statistics")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Trees Planted in Period", len(date_filtered_trees))
    with col2:
        alive_trees = len(date_filtered_trees[date_filtered_trees["status"] == "Alive"])
        survival_rate = round((alive_trees / len(date_filtered_trees)) * 100, 1) if len(date_filtered_trees) > 0 else 0
        st.metric("Survival Rate", f"{survival_rate}%")
    with col3:
        total_co2 = round(date_filtered_trees["co2_kg"].sum(), 2)
        st.metric("CO₂ Sequestered", f"{total_co2} kg")
    
    st.subheader("Tree Data Table")
    st.dataframe(date_filtered_trees)
    
    # Download button
    csv = date_filtered_trees.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Report as CSV",
        data=csv,
        file_name=f"tree_report_{start_date_str}_to_{end_date_str}.csv",
        mime="text/csv",
    )

def admin_dashboard():
    st.markdown("<h1 class='header-text'>🌳 Administrator Dashboard</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🌿 Manage Trees", "🌳 Manage Species", "👥 Manage Users", "💰 Payments", "📊 Analytics"])
    
    # --- Manage Trees ---
    with tab1:
        st.subheader("All Trees")
        trees = load_tree_data()
        st.dataframe(trees)
        
        st.subheader("Add/Edit Tree")
        with st.form("admin_tree_form"):
            col1, col2 = st.columns(2)
            with col1:
                tree_id = st.text_input("Tree ID*").strip()
            
            if tree_id:
                tree_data = trees[trees['tree_id'] == tree_id]
                
                if not tree_data.empty:
                    tree = tree_data.iloc[0]
                    institution = tree['institution']
                    student = tree['student_name']
                    local_name = tree['local_name']
                    scientific_name = tree['scientific_name']
                    
                    st.text_input("Institution Name", value=institution, disabled=True)
                    st.text_input("Student Name", value=student, disabled=True)
                    st.text_input("Local Name", value=local_name, disabled=True)
                    
                    # Editable by Admin
                    scientific_name = st.text_input("Scientific Name", value=scientific_name)  
                    
                    county = tree.get('county', '')
                    sub_county = tree.get('sub_county', '')
                    ward = tree.get('ward', '')
                    
                    st.text_input("County", value=county, disabled=True)
                    st.text_input("Sub-County", value=sub_county, disabled=True)
                    st.text_input("Ward", value=ward, disabled=True)
                    
                    status = st.selectbox("Status", ["Alive", "Dead", "Adopted"], index=["Alive", "Dead", "Adopted"].index(tree['status']) if tree['status'] in ["Alive", "Dead", "Adopted"] else 0)
                else:
                    st.error(f"Tree ID {tree_id} not found")
            else:
                st.info("Enter a Tree ID to edit an existing tree")
            
            # Add a single submit button at the end of the form
            submit_button = st.form_submit_button("Update Tree" if tree_id else "Search Tree")
            
            # Process form submission after the button
            if submit_button and tree_id:
                tree_data = trees[trees['tree_id'] == tree_id]
                if not tree_data.empty:
                    trees.loc[trees['tree_id'] == tree_id, 'scientific_name'] = scientific_name
                    trees.loc[trees['tree_id'] == tree_id, 'status'] = status
                    
                    if save_tree_data(trees):
                        st.success(f"Tree {tree_id} updated successfully!")
                        st.rerun()

    # --- Manage Species ---
    with tab2:
        st.subheader("All Species")
        species_data = load_species_data()
        st.dataframe(species_data)
        
        st.subheader("Add New Species")
        with st.form("add_species_form"):
            new_scientific_name = st.text_input(
                "Scientific Name*",
                help="Latin name, e.g., Acacia spp."
            )
            
            new_local_name = st.text_input(
                "Local Name*",
                help="Common name, e.g., Acacia"
            )
            
            new_wood_density = st.number_input(
                "Wood Density",
                min_value=0.1,
                max_value=1.5,
                value=0.6,
                step=0.05,
                help="Wood density in g/cm³, used for CO₂ calculations"
            )
            
            new_benefits = st.text_area(
                "Benefits/Ecological Importance*",
                help="Describe the benefits of this species"
            )
            
            if st.form_submit_button("Add Species"):
                if new_local_name and new_scientific_name and new_benefits:
                    # Check if species already exists
                    existing_species = species_data[
                        (species_data["scientific_name"].str.lower() == new_scientific_name.lower()) | 
                        (species_data["local_name"].str.lower() == new_local_name.lower())
                    ]
                    
                    if not existing_species.empty:
                        st.error("Species with this scientific or local name already exists")
                    else:
                        new_species = pd.DataFrame([{
                            "scientific_name": new_scientific_name,
                            "local_name": new_local_name,
                            "wood_density": new_wood_density,
                            "benefits": new_benefits
                        }])
                        
                        updated_species = pd.concat([species_data, new_species], ignore_index=True)
                        if save_species_data(updated_species):
                            st.success(f"New species {new_scientific_name} added successfully!")
                            st.rerun()
                else:
                    st.error("Please fill all required fields (marked with *)")
        
        st.subheader("Bulk Import Species")
        uploaded_file = st.file_uploader(
            "Upload CSV file with species data",
            type=["csv"],
            help="CSV should have columns: scientific_name, local_name, wood_density, benefits"
        )
        
        if uploaded_file is not None:
            try:
                new_species = pd.read_csv(uploaded_file)
                required_columns = ["scientific_name", "local_name", "wood_density", "benefits"]
                
                if all(col in new_species.columns for col in required_columns):
                    st.success("CSV file parsed successfully!")
                    st.dataframe(new_species.head())
                    
                    if st.button("Import Species"):
                        # Merge with existing data
                        updated_species = pd.concat([species_data, new_species], ignore_index=True)
                        # Remove duplicates
                        updated_species = updated_species.drop_duplicates(
                            subset=["scientific_name"],
                            keep="last"
                        )
                        
                        if save_species_data(updated_species):
                            st.success(f"Imported {len(new_species)} species successfully!")
                            st.rerun()
                else:
                    st.error("CSV file is missing required columns")
            except Exception as e:
                st.error(f"Error reading CSV file: {str(e)}")

    # --- Manage Users ---
    with tab3:
        st.subheader("User Management")
        
        conn = sqlite3.connect(SQLITE_DB)
        try:
            users = pd.read_sql("SELECT username, user_type, institution, is_test_user FROM users", conn)
            st.dataframe(users)
            
            st.subheader("Add New User")
            with st.form("add_user_form"):
                username = st.text_input("Username*").strip()
                password = st.text_input("Password*", type="password").strip()
                user_type = st.selectbox("User Type", list(USER_TYPES.keys()))
                institution = st.text_input("Institution (for institution users)").strip()
                is_test_user = st.checkbox("Is this a test user?")
                
                if st.form_submit_button("Add User"):
                    if username and password:
                        try:
                            conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", 
                                        (username, hash_password(password), user_type, institution, 1 if is_test_user else 0))
                            conn.commit()
                            st.success("User added successfully!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Username already exists")
            
            st.subheader("Remove User")
            username_to_remove = st.selectbox("Select a user to remove", users["username"].values)
            
            if st.button("Remove Selected User"):
                try:
                    conn.execute("DELETE FROM users WHERE username = ?", (username_to_remove,))
                    conn.commit()
                    st.success(f"User {username_to_remove} removed successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error removing user: {e}")
                    
        except Exception as e:
            st.error(f"Database error: {str(e)}")
        finally:
            conn.close()

    # --- Payment Management ---
    with tab4:
        st.subheader("Payment Records")
        
        conn = sqlite3.connect(SQLITE_DB)
        try:
            payments = pd.read_sql("SELECT * FROM payments", conn)
            
            if not payments.empty:
                st.dataframe(payments)
                
                # Payment statistics
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Payments", f"${payments['amount'].sum():.2f}")
                with col2:
                    st.metric("Successful Transactions", len(payments[payments['payment_status'] == 'approved']))
                
                # Export option
                if st.button("Export Payment Records"):
                    csv = payments.to_csv(index=False)
                    st.download_button(
                        "Download CSV",
                        data=csv,
                        file_name="tree_payments.csv",
                        mime="text/csv"
                    )
            else:
                st.info("No payment records found")
        except Exception as e:
            st.error(f"Error loading payments: {str(e)}")
        finally:
            conn.close()

    # --- Analytics Dashboard ---
    with tab5:
        st.subheader("Analytics Dashboard")
        trees = load_tree_data()
        
        # Get unique institutions and adopted trees
        unique_institutions = trees["institution"].nunique()
        adopted_trees = len(trees[trees["adopter_name"].notna()])
        
        # Metrics in cards
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="card">
                <h3>🏫 Institutions Supported</h3>
                <h2>{unique_institutions}</h2>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="card">
                <h3>🌳 Total Trees</h3>
                <h2>{len(trees)}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="card">
                <h3>🤝 Adopted Trees</h3>
                <h2>{adopted_trees}</h2>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="card">
                <h3>🌍 CO₂ Sequestered</h3>
                <h2>{round(trees["co2_kg"].sum(), 2)} kg</h2>
            </div>
            """, unsafe_allow_html=True)
        
        st.subheader("CO₂ Sequestration by Institution")
        co2_by_institution = trees.groupby("institution")["co2_kg"].sum().reset_index()
        fig = px.bar(co2_by_institution, x="institution", y="co2_kg", 
                     title="CO₂ Sequestration by Institution",
                     color="co2_kg",
                     color_continuous_scale="Greens")
        st.plotly_chart(fig)
        
        st.subheader("Tree Status Distribution")
        status_counts = trees["status"].value_counts().reset_index()
        fig = px.pie(status_counts, values="count", names="status", 
                     title="Tree Status Distribution",
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig)
        
        st.subheader("Top Tree Species")
        species_counts = trees["scientific_name"].value_counts().reset_index().head(10)
        fig = px.bar(species_counts, x="scientific_name", y="count",
                    title="Top 10 Tree Species",
                    labels={"scientific_name": "Scientific Name", "count": "Number of Trees"})
        st.plotly_chart(fig)
add_branding_footer()


# --- My Trees Page (for public users who adopted) ---
def my_trees_page():
    st.markdown("<h1 class='header-text'>💚 My Adopted Trees</h1>", unsafe_allow_html=True)
    
    donor_email = st.session_state.user.get("email", "")
    
    if not donor_email:
        donor_email = st.text_input("Enter your email to view your adopted trees:")
        if not donor_email:
            st.info("Please enter the email address you used for adoption.")
            return
            
    # Load adopted trees for this donor
    conn = sqlite3.connect(SQLITE_DB)
    try:
        adopted_trees = pd.read_sql("""
            SELECT t.* FROM trees t 
            JOIN payments p ON t.tree_id = p.tree_id 
            WHERE p.donor_email = ? AND p.payment_status = 'approved'
        """, conn, params=(donor_email,))
    except Exception as e:
        st.error(f"Error loading your trees: {e}")
        adopted_trees = pd.DataFrame()
    finally:
        conn.close()
        
    if adopted_trees.empty:
        st.warning("No adopted trees found for this email address.")
        return
        
    st.success(f"Found {len(adopted_trees)} adopted tree(s) for {donor_email}")
    
    for _, tree in adopted_trees.iterrows():
        with st.expander(f"🌳 Tree {tree['tree_id']} - {tree['local_name']} ({tree['institution']})"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Species:** {tree['local_name']} ({tree['scientific_name']})")
                st.write(f"**Planted on:** {tree['date_planted']}")
                st.write(f"**Status:** {tree['status']}")
                st.write(f"**CO₂ Sequestered:** {tree['co2_kg']} kg")
            
            with col2:
                # Display tree growth visualization
                display_tree_growth(tree["height_m"])
            
            # Monitoring history
            monitoring_history = load_monitoring_history(tree['tree_id'])
            if not monitoring_history.empty:
                st.subheader("Recent Monitoring")
                st.dataframe(monitoring_history.head(5)[["monitor_date", "monitor_status", "height_m", "co2_kg"]])

# --- Main Execution ---
if __name__ == "__main__":
    main()
    add_branding_footer() # Add the footer at the end
