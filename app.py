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
        /* Global Resets & Base Styles */
        html, body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
            background-color: #f0f2f5; /* Lighter, cleaner background */
            color: #333;
            line-height: 1.6;
        }

        /* Main App Container - More Compact */
        .main .block-container {
            padding-top: 1.5rem; /* Reduced top padding */
            padding-bottom: 1.5rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 1200px; /* Constrain width for better readability on large screens */
            margin: 0 auto;
        }

        /* Header Styling - Modern & Clean */
        .header-text {
            color: #1D7749; /* Deeper, more sophisticated green */
            font-weight: 700;
            font-size: 2.2rem; /* Slightly reduced for compactness */
            margin-bottom: 1rem; /* Consistent spacing */
            text-align: left;
        }

        /* Sidebar Styling - Clean & Functional */
        .sidebar .sidebar-content {
            background-color: #ffffff; /* White sidebar for cleaner look */
            border-right: 1px solid #e0e0e0;
            padding: 1rem;
        }
        .sidebar .sidebar-content h3 {
            color: #1D7749;
            font-size: 1.1rem;
            margin-top: 0;
        }
        .sidebar .sidebar-content p {
            font-size: 0.9rem;
            color: #555;
        }
        .sidebar .stRadio > label {
            font-weight: 600;
            font-size: 1rem;
            color: #333;
        }
        .sidebar .stRadio div[role="radiogroup"] > div {
            margin-bottom: 0.5rem;
        }

        /* Button Styling - Modern & Action-Oriented */
        .stButton>button {
            background-color: #28a745; /* Vibrant green */
            color: white;
            border-radius: 6px; /* Slightly less rounded */
            padding: 0.6rem 1.2rem; /* Adjusted padding */
            border: none;
            font-weight: 600;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stButton>button:hover {
            background-color: #218838; /* Darker on hover */
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .stButton>button:active {
            transform: translateY(0px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        /* Card Styling - Elevated & Informative */
        .card {
            background-color: white;
            border-radius: 8px; /* Consistent rounding */
            padding: 1.2rem; /* Adjusted padding */
            box-shadow: 0 3px 6px rgba(0,0,0,0.08); /* Softer shadow */
            margin-bottom: 1.2rem;
            border: 1px solid #e0e0e0;
        }
        .card h3 {
            color: #1D7749;
            margin-top: 0;
            margin-bottom: 0.5rem;
            font-size: 1.3rem;
        }
        .card p {
            font-size: 0.95rem;
            color: #444;
            margin-bottom: 0.8rem;
        }

        /* Metric Card Styling - Impactful & Clear */
        .metric-card {
            background-color: #ffffff;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 3px 6px rgba(0,0,0,0.07);
            margin-bottom: 1rem;
            text-align: center;
            border: 1px solid #e8e8e8;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .metric-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 5px 10px rgba(0,0,0,0.1);
        }
        .metric-value {
            font-size: 2rem; /* Slightly reduced for compactness */
            font-weight: 700;
            color: #1D7749;
            margin: 0.3rem 0;
        }
        .metric-label {
            font-size: 0.85rem; /* Slightly reduced */
            color: #555;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* Form Elements - Clean & User-Friendly */
        .stTextInput input, .stDateInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div {
            border-radius: 6px !important;
            border: 1px solid #ccc !important;
                    }
        .stTextArea textarea {
            border-radius: 6px !important;
            border: 1px solid #ccc !important;
            padding: 0.75rem !important;
        }
        .stForm {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 1.5rem;
            background-color: #f9f9f9;
        }

        /* Tabs Styling - Modern & Integrated */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px; /* Reduced gap */
            border-bottom: 2px solid #e0e0e0;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: transparent; /* Cleaner look */
            border-radius: 6px 6px 0 0 !important;
            padding: 0.7rem 1.2rem; /* Adjusted padding */
            color: #555;
            font-weight: 600;
            border: none !important; /* Remove default borders */
            border-bottom: 2px solid transparent !important;
            transition: all 0.2s ease-in-out;
        }
        .stTabs [aria-selected="true"] {
            background-color: transparent !important;
            color: #1D7749 !important;
            border-bottom: 2px solid #1D7749 !important;
        }

        /* Tree Visualization - More Compact */
        .tree-visualization {
            text-align: center;
            margin: 1rem 0; /* Reduced margin */
        }
        .tree-visualization .progress-container {
            margin: 0.5rem auto; /* Center and reduce margin */
            max-width: 300px;
        }

        /* Footer Styling - Unobtrusive */
        .footer {
            margin-top: 2rem; /* Reduced margin */
            padding: 1rem 0;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            font-size: 0.85rem;
            color: #777;
        }

        /* Responsive Adjustments */
        @media (max-width: 768px) {
            .main .block-container {
                padding-top: 1rem;
                padding-left: 0.5rem;
                padding-right: 0.5rem;
            }
            .header-text {
                font-size: 1.8rem;
            }
            .metric-card {
                padding: 0.8rem;
                margin-bottom: 0.8rem;
            }
            .metric-value {
                font-size: 1.6rem;
            }
            .metric-label {
                font-size: 0.75rem;
            }
            .stButton>button {
                padding: 0.5rem 1rem;
                width: 100%; /* Full width buttons on mobile */
            }
            .stTabs [data-baseweb="tab"] {
                padding: 0.6rem 1rem;
            }
            .card {
                padding: 1rem;
            }
            .stForm {
                padding: 1rem;
            }
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
    
    # Fixed regex pattern with proper escaping
    max_num = max([int(re.search(r'\d+$', str(id)).group()) for id in existing_ids if re.search(r'\d+$', str(id))])
    return f"{prefix}{max_num + 1:03d}"

def calculate_co2(scientific_name: str, rcd: Optional[float] = None, dbh: Optional[float] = None) -> float:
    species_data = load_species_data()
    try:
        density = species_data[species_data["scientific_name"] == scientific_name]["wood_density"].values[0]
    except:
        density = 0.6 # Default wood density if species not found
    
    if dbh is not None and dbh > 0:
        agb = 0.0509 * density * (dbh ** 2.5)
    elif rcd is not None and rcd > 0:
        agb = 0.042 * (rcd ** 2.5)
    else:
        return 0.0
        
    bgb = 0.2 * agb
    carbon = 0.47 * (agb + bgb)
    return round(carbon * 3.67, 2)

def generate_qr_code(tree_id):
    """
    Generate and save QR code for a tree linking to Kobo form with tree_id pre-filled
    """
    try:
        KOBO_FORM_BASE_URL = "https://ee.kobotoolbox.org/single/dXdb36aV?tree_id=" + tree_id

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=8,  # Slightly smaller for compactness
            border=3,
        )
        qr.add_data(KOBO_FORM_BASE_URL)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#1D7749", back_color="white")

        # Save as file
        file_path = QR_CODE_DIR / f"{tree_id}_qr.png"
        img.save(file_path)

        # Also create base64 encoded version for display
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return img_str

    except Exception as e:
        print(f"QR code generation failed for tree {tree_id}: {e}")
        return None

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
    growth_percentage = min((height_m / max_height) * 100, 100) if height_m is not None else 0
    current_height = height_m if height_m is not None else 0
    
    st.markdown(f"""
    <div class="tree-visualization">
        <div style="font-size: 2.5rem; color: #2e8b57;">{'🌱' if current_height < 1 else '🌳' if current_height < 5 else '🌲'}</div>
        <div style="font-weight: bold; margin: 0.3rem 0; font-size: 0.9rem;">Height: {current_height:.2f} meters</div>
        <div class="progress-container">
            <div class="progress-bar" style="width: {growth_percentage}%"></div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 0.3rem; font-size: 0.8rem;">
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
    
    # Main header card - More concise
    st.markdown("""
    <div class="card" style="margin-bottom: 1.5rem;">
        <h3>Track, Monitor, & Celebrate Your Trees</h3>
        <p>Join our community in growing a greener future, one tree at a time.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Load data for metrics
    trees = load_tree_data()
    total_trees = len(trees)
    alive_trees = len(trees[trees["status"] == "Alive"])
    total_co2 = round(trees["co2_kg"].sum(), 2)
    institutions_count = trees["institution"].nunique()
    survival_rate = round((alive_trees / total_trees) * 100, 1) if total_trees > 0 else 0
    
    # Metrics section - Using st.columns for better responsiveness
    cols = st.columns(4)
    metrics_data = [
        (f"{total_trees:,}", "Trees Planted"),
        (f"{survival_rate}%", "Survival Rate"),
        (f"{total_co2:,} kg", "CO₂ Sequestered"),
        (f"{institutions_count}", "Institutions")
    ]
    
    for i, (value, label) in enumerate(metrics_data):
        with cols[i]:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{value}</div>
                <div class="metric-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Call to Action Section - More compact
    st.markdown("""
    <div class="card" style="margin-top: 1rem;">
        <h4>Ready to Make a Difference?</h4>
        <p style="margin-bottom: 1rem;">Choose how you'd like to contribute:</p>
    </div>
    """, unsafe_allow_html=True)
    
    action_cols = st.columns(2)
    with action_cols[0]:
        if st.button("🌱 Plant Trees With Us", key="plant_cta",
                    use_container_width=True,
                    help="Join as an institution or field agent to plant and monitor trees"):
            st.session_state.landing_action = "plant"
            st.rerun()
    with action_cols[1]:
        if st.button("🤝 Donate Trees", key="donate_cta",
                   use_container_width=True,
                   help="Support existing trees and track their growth"):
            st.session_state.landing_action = "donate"
            st.rerun()
    
    # Direct login option - More subtle
    st.markdown("""
    <div style="text-align: center; margin-top: 1.5rem; font-size: 0.9rem;">
        Already have an account? <a href="#" onclick="window.location.href='?show_login=true'" style="color: #1D7749; font-weight: 600;">Login here</a>
    </div>
    """, unsafe_allow_html=True)
    
    # Handle the selected action
    if hasattr(st.session_state, 'landing_action'):
        if st.session_state.landing_action == "plant":
            show_plant_trees_options()
        elif st.session_state.landing_action == "donate":
            st.session_state.user = {
                "username": "guest_donor", "user_type": "donor", "email": "", "institution": ""
            }
            st.session_state.authenticated = True
            st.session_state.page = "Donor Dashboard"
            del st.session_state.landing_action
            st.rerun()
    
    # Recent trees map - More compact presentation
    if not hasattr(st.session_state, 'landing_action'):
        st.markdown("<h4 style='color: #1D7749; margin-top: 2rem; margin-bottom: 0.5rem;'>Recently Planted Trees</h4>", unsafe_allow_html=True)
        if not trees.empty:
            recent_trees = trees.sort_values("date_planted", ascending=False).head(50)
            fig = px.scatter_mapbox(
                recent_trees,
                lat="latitude", lon="longitude",
                hover_name="tree_id",
                hover_data={"local_name": True, "institution": True, "date_planted": True, "latitude": False, "longitude": False},
                color="status",
                color_discrete_map={"Alive": "#28a745", "Dead": "#dc3545", "Adopted": "#007bff"},
                zoom=4, height=400 # Reduced height
            )
            fig.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":0,"l":0,"b":0})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trees planted yet. Be the first to plant one!")

def show_plant_trees_options():
    st.markdown("<h4 style='color: #1D7749; margin-bottom: 0.5rem;'>Get Involved in Tree Planting</h4>", unsafe_allow_html=True)
    
    option = st.radio("Select an option:", 
                     ["I'm an existing user - Take me to login", 
                      "I'm new here - Show me how to register"], label_visibility="collapsed")
    
    if option == "I'm an existing user - Take me to login":
        if st.button("Proceed to Login", key="proceed_login_plant"):
            st.session_state.show_login = True
            if 'landing_action' in st.session_state: del st.session_state.landing_action
            st.rerun()
    else:
        st.markdown("""
        <div class="card" style="font-size: 0.9rem;">
            <h5 style="color: #1D7749; margin-top:0;">How to Register:</h5>
            <ul style="padding-left: 20px; margin-bottom: 0;">
                <li><strong>Institutions:</strong> Contact us at <a href="mailto:okothbasil45@gmail.com" style="color: #1D7749;">okothbasil45@gmail.com</a> to create an administrator account.</li>
                <li><strong>Field Agents:</strong> Request credentials from your institution administrator.</li>
                <li><strong>Individuals:</strong> Download our mobile app (coming soon!).</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
    if st.button("Back to Main Page", key="back_plant_options"):
        if 'landing_action' in st.session_state: del st.session_state.landing_action
        st.rerun()

def show_adoptable_institutions():
    # This function is now primarily handled by the donor_dashboard module
    # but can be a simple info display if needed on landing page flow
    st.markdown("<h4 style='color: #1D7749; margin-bottom: 0.5rem;'>Adopt a Tree</h4>", unsafe_allow_html=True)
    st.info("You can choose an institution to support and adopt trees through our Donor Dashboard.")
    if st.button("Go to Donor Dashboard", key="go_to_donor_adopt"):
        st.session_state.user = {
            "username": "guest_donor", "user_type": "donor", "email": "", "institution": ""
        }
        st.session_state.authenticated = True
        st.session_state.page = "Donor Dashboard"
        if 'landing_action' in st.session_state: del st.session_state.landing_action
        st.rerun()
    if st.button("Back to Main Page", key="back_adopt_options"):
        if 'landing_action' in st.session_state: del st.session_state.landing_action
        st.rerun()

# --- Login Page ---
def login():
    st.markdown("<h1 class='header-text' style='text-align: center; margin-bottom: 1.5rem;'>🌳 CarbonTally Login</h1>", unsafe_allow_html=True)
    
    cols = st.columns([1,2,1]) # Centering the form
    with cols[1]:
        with st.form("login_form"):
            st.markdown("<h4 style='color: #1D7749; text-align:center; margin-bottom:1rem;'>Welcome Back!</h4>", unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            login_button_cols = st.columns([1,2,1])
            with login_button_cols[1]:
                 submitted = st.form_submit_button("Login", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.warning("Please enter both username and password")
                else:
                    user = authenticate(username, password)
                    if user:
                        st.session_state.user = {
                            "username": user[0], "user_type": user[2],
                            "institution": user[3] if len(user) > 3 else "",
                            "is_test_user": user[4] if len(user) > 4 else 0
                        }
                        st.success(f"Welcome {user[0]}!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                        if username == "admin": st.info("Default admin: admin/admin123")
        
        st.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; font-size:0.9rem;'>Or donate as a guest:</p>", unsafe_allow_html=True)
        guest_button_cols = st.columns([1,2,1])
        with guest_button_cols[1]:
            if st.button("Continue as Guest Donor", key="guest_donor_login", use_container_width=True):
                st.session_state.user = {
                    "username": "guest_donor", "user_type": "donor", "email": "", "institution": ""
                }
                st.session_state.authenticated = True
                st.session_state.page = "Donor Dashboard"
                st.rerun()

        st.markdown("<p style='text-align:center; margin-top:1.5rem;'><a href='#' onclick=\"window.location.href='?'\" style='color: #1D7749; font-weight: 600;'>← Back to Home</a></p>", unsafe_allow_html=True)

    # --- Show Troubleshooting Tools ONLY IF logged in as admin ---
    if st.session_state.get("user", {}).get("user_type") == "admin":
        st.markdown("### 🔧 Troubleshooting Tools")
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


# --- Main App ---
def main():
    initialize_data_files()
    load_css()

    if "user" not in st.session_state:
        if st.query_params.get("show_login") == "true" or (hasattr(st.session_state, 'show_login') and st.session_state.show_login):
            login()
        else:
            landing_page()
        return

    user_type = st.session_state.user.get("user_type", "")
    
    with st.sidebar:
        st.markdown(f"<h3 style='margin-bottom:0.2rem;'>🌳 CarbonTally</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:0.9rem; margin-top:0; margin-bottom:1rem;'>Welcome, <strong>{st.session_state.user.get('username', 'User')}</strong> ({USER_TYPES.get(user_type, 'User')})</p>", unsafe_allow_html=True)
        
        nav_options = []
        if user_type == "admin":
            nav_options = ["Dashboard", "Plant a Tree", "Monitoring", "Tree Lookup", "Reports", "Donor Dashboard"]
        elif user_type == "school":
            nav_options = ["Dashboard", "Plant a Tree", "Monitoring", "Reports"]
        elif user_type == "field":
            nav_options = ["Plant a Tree", "Monitoring"]
        elif user_type == "donor":
            nav_options = ["Donor Dashboard"]
        else: # public (logged in, but not donor type - e.g. adopted tree user)
            nav_options = ["My Trees", "Adopt a Tree"]
            
        if 'page' not in st.session_state or st.session_state.page not in nav_options:
            st.session_state.page = nav_options[0]
            
        page = st.radio("Navigation", nav_options, key="navigation_radio", index=nav_options.index(st.session_state.page), label_visibility="collapsed")
        if page != st.session_state.page:
             st.session_state.page = page
             st.rerun() # Rerun to reflect page change immediately

        st.markdown("<hr style='margin: 1rem 0;'>", unsafe_allow_html=True)
        if st.button("Logout", use_container_width=True, key="logout_button"):
            keys_to_clear = ["user", "authenticated", "page", "landing_action", "show_login", "adopt_institution"]
            for key in keys_to_clear:
                if key in st.session_state: del st.session_state[key]
            st.success("Logged out successfully!")
            time.sleep(0.8)
            st.rerun()

    current_page = st.session_state.page
    
    if current_page == "Dashboard":
        if user_type == "admin": admin_dashboard()
        elif user_type == "school": institution_dashboard()
        else: st.error("Access denied.")
    elif current_page == "Plant a Tree": plant_a_tree_section()
    elif current_page == "Monitoring": monitoring_section()
    elif current_page == "Tree Lookup":
        if user_type == "admin": admin_tree_lookup()
        else: st.error("Access denied.")
    elif current_page == "Reports":
        if user_type in ["admin", "school"]: reports_page()
        else: st.error("Access denied.")
    elif current_page == "Donor Dashboard": donor_dashboard()
    elif current_page == "Adopt a Tree": donor_dashboard() # Public users can adopt/donate
    elif current_page == "My Trees": my_trees_page()
    else: st.error("Page not found.")

# --- Institution Dashboard ---
def institution_dashboard():
    institution = st.session_state.user.get("institution", "")
    header_text = f"🏫 {institution} Dashboard" if institution else "🏫 Institution Dashboard"
    st.markdown(f"<h1 class='header-text'>{header_text}</h1>", unsafe_allow_html=True)
    
    trees = load_tree_data()
    institution_trees = trees[trees["institution"] == institution]
    
    cols = st.columns(4)
    metrics_data = [
        (len(institution_trees), "Total Trees"),
        (f"{round((len(institution_trees[institution_trees['status'] == 'Alive']) / len(institution_trees)) * 100, 1) if len(institution_trees) > 0 else 0}%", "Survival Rate"),
        (f"{round(institution_trees['co2_kg'].sum(), 2)} kg", "CO₂ Sequestered"),
        (len(institution_trees[institution_trees["adopter_name"].notna()]), "Adopted Trees")
    ]
    for i, (value, label) in enumerate(metrics_data):
        with cols[i]:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{value}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📊 Recent Plantings & Map", "📈 Growth Charts"])
    with tab1:
        st.markdown("<h4 style='color: #1D7749; margin-top:1rem; margin-bottom: 0.5rem;'>Recent Tree Plantings</h4>", unsafe_allow_html=True)
        if not institution_trees.empty:
            recent_trees_display = institution_trees.sort_values("date_planted", ascending=False).head(10)
            st.dataframe(recent_trees_display[["tree_id", "local_name", "scientific_name", "student_name", "date_planted", "status"]], use_container_width=True)
            
            st.markdown("<h4 style='color: #1D7749; margin-top:1rem; margin-bottom: 0.5rem;'>Tree Map</h4>", unsafe_allow_html=True)
            fig_map = px.scatter_mapbox(
                institution_trees, lat="latitude", lon="longitude", hover_name="tree_id",
                hover_data={"local_name": True, "student_name": True, "date_planted": True, "latitude":False, "longitude":False},
                color="status", color_discrete_map={"Alive": "#28a745", "Dead": "#dc3545", "Adopted": "#007bff"},
                zoom=10, height=400
            )
            fig_map.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":0,"l":0,"b":0})
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.info("No trees planted yet. Click on 'Plant a Tree' to get started!")
    with tab2:
        st.markdown("<h4 style='color: #1D7749; margin-top:1rem; margin-bottom: 0.5rem;'>Overall Growth Trends</h4>", unsafe_allow_html=True)
        # Placeholder for aggregated growth charts - requires more data processing
        st.info("Aggregated growth charts for the institution will be available here soon.")

# --- Reports Page ---
def reports_page():
    st.markdown("<h1 class='header-text'>📊 Reports</h1>", unsafe_allow_html=True)
    user_type = st.session_state.user.get("user_type", "")
    institution = st.session_state.user.get("institution", "")
    
    trees = load_tree_data()
    if user_type == "admin":
        filtered_trees = trees
        st.markdown("<h4 style='color: #1D7749; margin-bottom: 0.5rem;'>System-wide Reports</h4>", unsafe_allow_html=True)
    elif user_type == "school":
        filtered_trees = trees[trees["institution"] == institution]
        st.markdown(f"<h4 style='color: #1D7749; margin-bottom: 0.5rem;'>Reports for {institution}</h4>", unsafe_allow_html=True)
    else:
        st.error("You don't have permission to view reports.")
        return
    
    date_cols = st.columns(2)
    with date_cols[0]:
        start_date = st.date_input("Start Date", datetime.datetime.now() - datetime.timedelta(days=365))
    with date_cols[1]:
        end_date = st.date_input("End Date", datetime.datetime.now())
    
    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()
    date_filtered_trees = filtered_trees[
        (filtered_trees["date_planted"] >= start_date_str) & 
        (filtered_trees["date_planted"] <= end_date_str)
    ]
    
    st.markdown("<h5 style='color: #333; margin-top:1rem; margin-bottom: 0.5rem;'>Summary Statistics</h5>", unsafe_allow_html=True)
    metric_cols = st.columns(3)
    report_metrics = [
        (len(date_filtered_trees), "Trees in Period"),
        (f"{round((len(date_filtered_trees[date_filtered_trees['status'] == 'Alive']) / len(date_filtered_trees)) * 100, 1) if len(date_filtered_trees) > 0 else 0}%", "Survival Rate"),
        (f"{round(date_filtered_trees['co2_kg'].sum(), 2)} kg", "CO₂ Sequestered")
    ]
    for i, (value, label) in enumerate(report_metrics):
        with metric_cols[i]:
            st.markdown(f'<div class="metric-card" style="padding:0.8rem;"><div class="metric-value" style="font-size:1.6rem;">{value}</div><div class="metric-label" style="font-size:0.8rem;">{label}</div></div>', unsafe_allow_html=True)
    
    st.markdown("<h5 style='color: #333; margin-top:1rem; margin-bottom: 0.5rem;'>Tree Data Table</h5>", unsafe_allow_html=True)
    st.dataframe(date_filtered_trees, use_container_width=True)
    
    csv = date_filtered_trees.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Report as CSV",
        data=csv,
        file_name=f"tree_report_{start_date_str}_to_{end_date_str}.csv",
        mime="text/csv",
        use_container_width=True
    )

# --- Admin Dashboard ---
# --- Admin Dashboard ---
def admin_dashboard():
    st.markdown("<h1 class='header-text'>👑 Admin Dashboard</h1>", unsafe_allow_html=True)
    trees = load_tree_data()

    # Load users
    conn_users = sqlite3.connect(SQLITE_DB)
    users_df = pd.read_sql("SELECT * FROM users", conn_users)
    conn_users.close()

    st.markdown("<h4 style='color: #1D7749; margin-bottom: 0.5rem;'>System Overview</h4>", unsafe_allow_html=True)
    admin_metric_cols = st.columns(4)
    admin_metrics = [
        (len(trees), "Total Trees"),
        (f"{round((len(trees[trees['status'] == 'Alive']) / len(trees)) * 100, 1) if len(trees) > 0 else 0}%", "Overall Survival"),
        (f"{round(trees['co2_kg'].sum(), 2)} kg", "Total CO₂"),
        (len(users_df), "Registered Users")
    ]
    for i, (value, label) in enumerate(admin_metrics):
        with admin_metric_cols[i]:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{value}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

    tab_inst, tab_users = st.tabs(["🏢 Institution Performance", "👥 User Management"])

    with tab_inst:
        st.markdown("<h5 style='color: #333; margin-top:1rem; margin-bottom: 0.5rem;'>Institution Performance</h5>", unsafe_allow_html=True)
        institution_stats = trees.groupby("institution").agg(
            total_trees=pd.NamedAgg(column="tree_id", aggfunc="count"),
            alive_trees=pd.NamedAgg(column="status", aggfunc=lambda x: (x == "Alive").sum()),
            total_co2=pd.NamedAgg(column="co2_kg", aggfunc="sum")
        ).reset_index()
        institution_stats["survival_rate"] = round((institution_stats["alive_trees"] / institution_stats["total_trees"]) * 100, 1).fillna(0)

        fig_inst = px.bar(
            institution_stats.sort_values("total_trees", ascending=False),
            x="institution", y="total_trees", title="Trees Planted by Institution",
            color="survival_rate", color_continuous_scale=px.colors.sequential.Greens
        )
        fig_inst.update_layout(title_x=0.5)
        st.plotly_chart(fig_inst, use_container_width=True)
        st.dataframe(institution_stats, use_container_width=True)

    with tab_users:
        st.markdown("<h5 style='color: #333; margin-top:1rem; margin-bottom: 0.5rem;'>User Management</h5>", unsafe_allow_html=True)
        st.dataframe(users_df[["username", "user_type", "institution"]], use_container_width=True)

        with st.expander("Add New User"):
            with st.form("add_user_form"):
                new_username = st.text_input("Username")
                new_password = st.text_input("Password", type="password")
                new_user_type = st.selectbox("User Type", list(USER_TYPES.keys()))
                new_institution = st.text_input("Institution (if applicable)")

                if st.form_submit_button("Add User", use_container_width=True):
                    if not new_username or not new_password:
                        st.error("Username and password are required")
                    else:
                        try:
                            conn = sqlite3.connect(SQLITE_DB)
                            c = conn.cursor()
                            c.execute(
                                "INSERT INTO users (username, password, user_type, institution) VALUES (?, ?, ?, ?)",
                                (new_username, hash_password(new_password), new_user_type, new_institution)
                            )
                            conn.commit()
                            st.success(f"User {new_username} added!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error(f"User {new_username} already exists.")
                        except Exception as e:
                            st.error(f"Error: {e}")
                        finally:
                            conn.close()

        st.subheader("Remove User")
        username_to_remove = st.selectbox("Select a user to remove", users_df["username"].values)

        if st.button("Remove Selected User"):
            try:
                conn = sqlite3.connect(SQLITE_DB)
                conn.execute("DELETE FROM users WHERE username = ?", (username_to_remove,))
                conn.commit()
                st.success(f"User {username_to_remove} removed successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error removing user: {e}")
            finally:
                conn.close()

# --- My Trees Page (for public users who adopted) ---
def my_trees_page():
    st.markdown("<h1 class='header-text'>💚 My Adopted Trees</h1>", unsafe_allow_html=True)
    donor_email = st.session_state.user.get("email", "")
    
    if not donor_email:
        donor_email = st.text_input("Enter your email to view your adopted trees:", key="donor_email_my_trees")
        if not donor_email:
            st.info("Please enter the email address you used for adoption.")
            return
            
    conn = sqlite3.connect(SQLITE_DB)
    try:
        adopted_trees_df = pd.read_sql("""
            SELECT t.* FROM trees t 
            JOIN payments p ON t.tree_id = p.tree_id 
            WHERE p.donor_email = ? AND p.payment_status = 'approved'
        """, conn, params=(donor_email,))
    except Exception as e:
        st.error(f"Error loading your trees: {e}")
        adopted_trees_df = pd.DataFrame()
    finally:
        conn.close()
        
    if adopted_trees_df.empty:
        st.warning("No adopted trees found for this email address.")
        return
        
    st.success(f"Found {len(adopted_trees_df)} adopted tree(s) for {donor_email}")
    
    for _, tree_row in adopted_trees_df.iterrows():
        with st.expander(f"🌳 Tree {tree_row['tree_id']} - {tree_row['local_name']} ({tree_row['institution']})"):
            tree_cols = st.columns([2,1]) # Details on left, growth viz on right
            with tree_cols[0]:
                st.markdown(f"""**Species:** {tree_row['local_name']} ({tree_row['scientific_name']})<br>
                               **Planted on:** {tree_row['date_planted']}<br>
                               **Status:** {tree_row['status']}<br>
                               **CO₂ Sequestered:** {tree_row['co2_kg']:.2f} kg""", unsafe_allow_html=True)
            with tree_cols[1]:
                display_tree_growth(tree_row["height_m"])
            
            monitoring_hist_df = load_monitoring_history(tree_row['tree_id'])
            if not monitoring_hist_df.empty:
                st.markdown("<h6 style='margin-top:0.5rem; margin-bottom:0.3rem;'>Recent Monitoring</h6>", unsafe_allow_html=True)
                st.dataframe(monitoring_hist_df.head(3)[["monitor_date", "monitor_status", "height_m", "co2_kg"]], use_container_width=True, hide_index=True)

# --- Main Execution ---
if __name__ == "__main__":
    main()
    add_branding_footer() # Add the footer at the end
