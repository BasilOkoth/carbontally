import streamlit as st
import requests
import json
import time
import pandas as pd
import sqlite3
import qrcode
from io import BytesIO
import base64
import os
from pathlib import Path
import re
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns

# KoBo Toolbox configuration
KOBO_API_URL = "https://kf.kobotoolbox.org/api/v2"
KOBO_API_TOKEN = st.secrets["KOBO_API_TOKEN"]
KOBO_ASSET_ID = st.secrets["KOBO_ASSET_ID"]
KOBO_MONITORING_ASSET_ID = st.secrets.get("KOBO_MONITORING_ASSET_ID", "aDSNfsXbXygrn8rwKog5Yd")

# Database configuration
BASE_DIR = Path(__file__).parent if "__file__" in locals() else Path.cwd()
DATA_DIR = BASE_DIR / "data"
SQLITE_DB = DATA_DIR / "trees.db"
QR_CODE_DIR = DATA_DIR / "qr_codes"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True, parents=True)
QR_CODE_DIR.mkdir(exist_ok=True, parents=True)

def initialize_database():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(SQLITE_DB)
    try:
        c = conn.cursor()
        
        # Create trees table if not exists
        c.execute('''
            CREATE TABLE IF NOT EXISTS trees (
                tree_id TEXT PRIMARY KEY,
                local_name TEXT,
                scientific_name TEXT,
                date_planted TEXT,
                student_name TEXT,
                institution TEXT,
                status TEXT,
                tree_stage TEXT,
                rcd_cm REAL,
                dbh_cm REAL,
                height_m REAL,
                co2_kg REAL,
                qr_code TEXT,
                last_monitored TEXT,
                latitude REAL,
                longitude REAL
            )
        ''')
        
        # Create monitoring_history table if not exists
        c.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_history (
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
                kobo_submission_id TEXT,
                FOREIGN KEY (tree_id) REFERENCES trees (tree_id)
            )
        ''')
        
        # Create processed_monitoring_submissions table
        c.execute('''
            CREATE TABLE IF NOT EXISTS processed_monitoring_submissions (
                submission_id TEXT PRIMARY KEY,
                tree_id TEXT,
                processed_date TEXT,
                FOREIGN KEY (tree_id) REFERENCES trees (tree_id)
            )
        ''')
        
        conn.commit()
    except Exception as e:
        st.error(f"Database initialization error: {e}")
    finally:
        conn.close()
def validate_user_session():
    """
    Validate that the user session has all required fields
    Returns True if valid, False otherwise
    """
    if "user" not in st.session_state:
        st.error("User session not found. Please log in again.")
        return False
        
    required_fields = ["username", "user_type"]
    missing_fields = [field for field in required_fields if field not in st.session_state.user]
    
    if missing_fields:
        st.error(f"User session missing required fields: {', '.join(missing_fields)}")
        return False
        
    # Institution is handled separately with a fallback option
    return True
def ensure_institution_assigned():
    """
    Ensure that an institution is assigned to the current user
    Returns the institution name if available or selected, None otherwise
    """
    if "user" not in st.session_state:
        return None
        
    user_institution = st.session_state.user.get("institution")
    
    if user_institution:
        return user_institution
        
    # If no institution is assigned, provide a selection interface
    st.warning("No institution assigned to your account. Please select your institution:")
    
    # Get available institutions from database or use a default list
    conn = sqlite3.connect(SQLITE_DB)
    try:
        institutions_df = pd.read_sql(
            "SELECT DISTINCT institution FROM trees WHERE institution IS NOT NULL AND institution != ''",
            conn
        )
        available_institutions = institutions_df["institution"].tolist()
    except Exception as e:
        st.error(f"Error fetching institutions: {e}")
        available_institutions = []
    finally:
        conn.close()
    
    # Add some default options if none found in database
    if not available_institutions:
        available_institutions = ["School A", "School B", "NGO Partner", "Government Agency"]
    
    # Sort alphabetically for better UX
    available_institutions.sort()
    
    # Add custom option
    available_institutions = ["-- Select an institution --"] + available_institutions + ["Other (specify)"]
    
    selected_institution = st.selectbox(
        "Select your institution",
        available_institutions,
        index=0
    )
    
    # Handle custom institution entry
    if selected_institution == "Other (specify)":
        custom_institution = st.text_input("Enter your institution name")
        if custom_institution and custom_institution.strip():
            selected_institution = custom_institution.strip()
        else:
            selected_institution = None
    elif selected_institution == "-- Select an institution --":
        selected_institution = None
    
    # Save the selected institution to session state if valid
    if selected_institution:
        st.session_state.user["institution"] = selected_institution
        st.success(f"Institution set to: {selected_institution}")
        return selected_institution
    else:
        st.error("Please select or enter a valid institution to continue.")
        return None
def generate_tree_qr_code(tree_id, tree_data=None):
    """
    Generate and save a single QR code for tree monitoring
    Returns: (base64_image, file_path)
    """
    try:
        if tree_data is None:
            tree_data = get_tree_details(tree_id)
            if tree_data is None:
                st.error(f"Tree with ID {tree_id} not found.")
                return None, None
        
        # Create URL with parameters for monitoring form
        base_url = f"https://ee.kobotoolbox.org/x/{KOBO_MONITORING_ASSET_ID}"
        params = {
            "tree_id": tree_id,
            "local_name": tree_data.get("local_name", ""),
            "scientific_name": tree_data.get("scientific_name", ""),
            "date_planted": tree_data.get("date_planted", ""),
            "planter": tree_data.get("student_name", ""),
            "institution": tree_data.get("institution", "")
        }
        
        url_params = "&".join([f"{k}={v}" for k, v in params.items() if v])
        monitoring_url = f"{base_url}?{url_params}"
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(monitoring_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#2e8b57", back_color="white")

        # Save QR code
        QR_CODE_DIR.mkdir(exist_ok=True, parents=True)
        file_path = QR_CODE_DIR / f"{tree_id}.png"
        img.save(file_path)

        # Create base64 encoded version for display
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return img_str, str(file_path)
    except Exception as e:
        st.error(f"Error generating QR code: {str(e)}")
        return None, None

def get_tree_details(tree_id):
    """Get complete details for a specific tree"""
    if not tree_id:
        return None
        
    conn = sqlite3.connect(SQLITE_DB)
    try:
        tree_data = pd.read_sql(
            "SELECT * FROM trees WHERE tree_id = ?",
            conn,
            params=(tree_id,)
        )
        
        if tree_data.empty:
            return None
            
        monitoring_history = pd.read_sql(
            """
            SELECT * FROM monitoring_history 
            WHERE tree_id = ? 
            ORDER BY monitor_date DESC
            """,
            conn,
            params=(tree_data.iloc[0]["tree_id"],)
        )
        
        result = tree_data.iloc[0].to_dict()
        result["monitoring_history"] = monitoring_history.to_dict('records')
        return result
    except Exception as e:
        st.error(f"Error getting tree details: {str(e)}")
        return None
    finally:
        conn.close()

def admin_tree_lookup():
    """Admin interface for looking up tree details and managing QR codes"""
    st.title("🔍 Admin Tree Lookup")
    
    # Validate admin access
    if "user" not in st.session_state or st.session_state.user.get("user_type") != "admin":
        st.error("Administrator access required")
        return
    
    # Tree ID input
    tree_id = st.text_input("Enter Tree ID")
    
    if tree_id:
        tree_data = get_tree_details(tree_id)
        if not tree_data:
            st.error("Tree not found")
            return
            
        # Display tree information
        st.subheader(f"Tree {tree_data['tree_id']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Basic Information")
            st.write(f"**Local Name:** {tree_data.get('local_name', 'N/A')}")
            st.write(f"**Scientific Name:** {tree_data.get('scientific_name', 'N/A')}")
            st.write(f"**Institution:** {tree_data.get('institution', 'N/A')}")
            st.write(f"**Planted By:** {tree_data.get('student_name', 'N/A')}")
            st.write(f"**Date Planted:** {tree_data.get('date_planted', 'N/A')}")
            
        with col2:
            st.markdown("### Status & Measurements")
            st.write(f"**Status:** {tree_data.get('status', 'N/A')}")
            st.write(f"**Growth Stage:** {tree_data.get('tree_stage', 'N/A')}")
            st.write(f"**RCD:** {tree_data.get('rcd_cm', 'N/A')} cm")
            st.write(f"**DBH:** {tree_data.get('dbh_cm', 'N/A')} cm")
            st.write(f"**Height:** {tree_data.get('height_m', 'N/A')} m")
            st.write(f"**CO₂ Sequestered:** {tree_data.get('co2_kg', 'N/A')} kg")
        
        # QR Code Management
        st.subheader("QR Code Management")
        
        if tree_data.get('qr_code'):
            st.image(f"data:image/png;base64,{tree_data['qr_code']}", 
                    caption=f"Monitoring QR for Tree {tree_data['tree_id']}")
            
            qr_path = QR_CODE_DIR / f"{tree_data['tree_id']}.png"
            if os.path.exists(qr_path):
                with open(qr_path, "rb") as f:
                    st.download_button(
                        "Download QR Code",
                        f.read(),
                        file_name=f"tree_{tree_data['tree_id']}_qr.png",
                        mime="image/png",
                        key=f"download_{tree_data['tree_id']}"
                    )
        else:
            st.warning("No QR code exists for this tree")
        
        if st.button("Generate/Regenerate QR Code"):
            with st.spinner("Generating QR code..."):
                qr_img, qr_path = generate_tree_qr_code(tree_data['tree_id'], tree_data)
                if qr_img:
                    # Update database
                    conn = sqlite3.connect(SQLITE_DB)
                    try:
                        conn.execute(
                            "UPDATE trees SET qr_code = ? WHERE tree_id = ?",
                            (qr_img, tree_data['tree_id'])
                        )
                        conn.commit()
                        st.success("QR code updated successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error updating QR code: {str(e)}")
                    finally:
                        conn.close()
        
        # Monitoring History
        st.subheader("Monitoring History")
        if tree_data.get('monitoring_history'):
            df = pd.DataFrame(tree_data['monitoring_history'])
            st.dataframe(df[['monitor_date', 'monitor_status', 'monitor_stage', 
                            'rcd_cm', 'dbh_cm', 'height_m', 'co2_kg', 'monitor_by']])
        else:
            st.info("No monitoring history available")

def monitoring_section():
    """Main monitoring interface"""
    st.title("🌳 Tree Monitoring System")
    initialize_database()
    
    # Tab interface
    tab1, tab2 = st.tabs(["Tree Lookup", "Monitoring Dashboard"])
    
    with tab1:
        st.header("Tree Lookup")
        tree_id = st.text_input("Enter Tree ID", key="monitoring_lookup")
        
        if tree_id:
            tree_data = get_tree_details(tree_id)
            if tree_data:
                display_tree_details(tree_data)
            else:
                st.error("Tree not found")
    
    with tab2:
        st.header("Monitoring Dashboard")
        # Add dashboard visualization code here
def get_kobo_monitoring_submissions(time_filter_hours=24, submission_id=None):
    """
    Retrieve monitoring submissions from KoBo Toolbox API with optional filters
    """
    if not KOBO_API_TOKEN or not KOBO_MONITORING_ASSET_ID:
        st.error("KoBo API credentials (token or monitoring asset ID) not configured.")
        return None

    headers = {
        "Authorization": f"Token {KOBO_API_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    params = {}
    if time_filter_hours and not submission_id:
        time_filter = datetime.now() - timedelta(hours=time_filter_hours)
        params["query"] = json.dumps({"_submission_time": {"$gte": time_filter.isoformat()}})

    if submission_id:
        params["query"] = json.dumps({"_id": submission_id})

    url = f"{KOBO_API_URL}/assets/{KOBO_MONITORING_ASSET_ID}/data/"

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '').lower()
        if 'application/json' not in content_type:
            st.error("Received non-JSON response from KoBo API. Expected 'application/json'.")
            st.error(f"Actual Content-Type: {content_type}")
            st.error(f"Response preview: {response.text[:500]}...")
            return None

        return response.json().get("results", [])

    except json.JSONDecodeError as e:
        st.error(f"JSON decoding error from KoBo API response: {e}")
        st.error(f"Problematic response text (first 500 chars): {response.text[:500]}...")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP error from KoBo API: {e.response.status_code} - {e.response.reason}")
        st.error(f"Response body: {e.response.text[:500]}...")
        return None
    except requests.exceptions.ConnectionError as e:
        st.error(f"Network connection error to KoBo API: {e}")
        return None
    except requests.exceptions.Timeout as e:
        st.error(f"Request to KoBo API timed out: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred while fetching KoBo monitoring submissions: {str(e)}")
        return None

def is_monitoring_submission_processed(submission_id):
    """Check if a KoBo monitoring submission has already been processed"""
    if not submission_id:
        return False

    conn = sqlite3.connect(SQLITE_DB)
    try:
        c = conn.cursor()
        c.execute("SELECT 1 FROM processed_monitoring_submissions WHERE submission_id = ?", (submission_id,))
        return c.fetchone() is not None
    except Exception as e:
        st.error(f"Database error in is_monitoring_submission_processed: {e}")
        return False
    finally:
        conn.close()

def map_monitoring_submission_to_database(kobo_data):
    """
    Map KoBo monitoring form fields to database columns
    """
    try:
        # Extract tree_id from submission
        tree_id = kobo_data.get("tree_id", "").strip()
        if not tree_id:
            st.warning(f"Monitoring submission {kobo_data.get('_id', 'N/A')} missing tree_id.")
            return None
            
        # Get current tree data to ensure it exists
        tree_data = get_tree_details(tree_id)
        if not tree_data:
            st.error(f"Tree with ID {tree_id} not found in database")
            return None
            
        # Map monitoring data
        mapped = {
            "tree_id": tree_id,
            "monitor_date": kobo_data.get("monitor_date", datetime.now().date().isoformat()),
            "monitor_status": kobo_data.get("tree_status", "Alive"),
            "monitor_stage": kobo_data.get("growth_stage", tree_data.get("tree_stage", "Seedling")),
            "rcd_cm": float(kobo_data.get("rcd_cm", 0)) if kobo_data.get("rcd_cm") is not None else tree_data.get("rcd_cm", 0.0),
            "dbh_cm": float(kobo_data.get("dbh_cm", 0)) if kobo_data.get("dbh_cm") is not None else tree_data.get("dbh_cm", 0.0),
            "height_m": float(kobo_data.get("height_m", 0)) if kobo_data.get("height_m") is not None else tree_data.get("height_m", 0.0),
            "notes": kobo_data.get("monitor_notes", ""),
            "monitor_by": kobo_data.get("monitor_name", "Unknown"),
            "kobo_submission_id": kobo_data.get("_id", "")
        }
        
        # Calculate CO2 sequestration
        mapped["co2_kg"] = calculate_co2_sequestration(
            tree_data.get("scientific_name", "Unknown"),
            mapped["rcd_cm"],
            mapped["dbh_cm"]
        )
        
        return mapped
    except Exception as e:
        st.error(f"Error mapping monitoring data: {str(e)}")
        return None

def calculate_co2_sequestration(species, rcd=None, dbh=None):
    """
    Calculate estimated CO2 sequestration based on tree measurements.
    """
    conn = sqlite3.connect(SQLITE_DB)
    try:
        species_data = pd.read_sql(
            "SELECT wood_density FROM species WHERE scientific_name = ?",
            conn,
            params=(species,)
        )

        density = species_data["wood_density"].iloc[0] if not species_data.empty and species_data["wood_density"].iloc[0] is not None else 0.6

        agb = 0.0
        if dbh is not None and dbh > 0:
            agb = 0.0509 * density * (dbh ** 2.5)
        elif rcd is not None and rcd > 0:
            agb = 0.042 * (rcd ** 2.5)
        else:
            return 0.0

        bgb = 0.2 * agb

        co2_sequestration = 0.47 * (agb + bgb) * 3.67
        return round(co2_sequestration, 2)
    except Exception as e:
        st.error(f"CO2 calculation error for species '{species}': {str(e)}")
        return 0.0
    finally:
        conn.close()

def save_monitoring_submission(monitoring_data):
    """
    Save a processed KoBo monitoring submission to the database
    """
    if not monitoring_data:
        st.warning("No valid monitoring data provided to save.")
        return False
        
    conn = sqlite3.connect(SQLITE_DB)
    try:
        c = conn.cursor()
        
        # Insert into monitoring_history
        c.execute('''
            INSERT INTO monitoring_history (
                tree_id, monitor_date, monitor_status, monitor_stage,
                rcd_cm, dbh_cm, height_m, co2_kg, notes, monitor_by, kobo_submission_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            monitoring_data["tree_id"],
            monitoring_data["monitor_date"],
            monitoring_data["monitor_status"],
            monitoring_data["monitor_stage"],
            monitoring_data["rcd_cm"],
            monitoring_data["dbh_cm"],
            monitoring_data["height_m"],
            monitoring_data["co2_kg"],
            monitoring_data["notes"],
            monitoring_data["monitor_by"],
            monitoring_data["kobo_submission_id"]
        ))
        
        # Update the tree record with latest monitoring data
        c.execute('''
            UPDATE trees SET
                status = ?,
                tree_stage = ?,
                rcd_cm = ?,
                dbh_cm = ?,
                height_m = ?,
                co2_kg = ?,
                last_monitored = ?
            WHERE tree_id = ?
        ''', (
            monitoring_data["monitor_status"],
            monitoring_data["monitor_stage"],
            monitoring_data["rcd_cm"],
            monitoring_data["dbh_cm"],
            monitoring_data["height_m"],
            monitoring_data["co2_kg"],
            monitoring_data["monitor_date"],
            monitoring_data["tree_id"]
        ))
        
        # Mark submission as processed
        c.execute('''
            INSERT INTO processed_monitoring_submissions (
                submission_id, tree_id, processed_date
            ) VALUES (?, ?, ?)
        ''', (
            monitoring_data["kobo_submission_id"],
            monitoring_data["tree_id"],
            datetime.now().isoformat()
        ))
        
        conn.commit()
        st.success(f"Successfully saved monitoring data for tree {monitoring_data['tree_id']}.")
        return True
    except sqlite3.IntegrityError as e:
        st.error(f"Duplicate submission detected or integrity error: {str(e)}")
        conn.rollback()
        return False
    except Exception as e:
        st.error(f"Unexpected database error while saving monitoring data: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def check_for_new_monitoring_submissions(hours=24):
    """
    Check for new monitoring submissions and process them
    """
    st.info(f"Fetching KoBo monitoring submissions from the last {hours} hours...")
    
    # Get monitoring submissions
    submissions = get_kobo_monitoring_submissions(hours)
    if not submissions:
        st.info("No new monitoring submissions found from KoBo Toolbox.")
        return []
        
    results = []
    st.info(f"Found {len(submissions)} monitoring submissions. Processing...")
    
    # Get institution from session with fallback option
    user_institution = ensure_institution_assigned()
    if not user_institution:
        st.error("Institution selection required to check submissions.")
        return []
        
    for sub in submissions:
        submission_kobo_id = sub.get("_id")
        if not submission_kobo_id:
            st.warning(f"Skipping submission with no ID: {sub}")
            continue
            
        if is_monitoring_submission_processed(submission_kobo_id):
            if st.session_state.get('debug_mode', False):
                st.text(f"[DEBUG] Monitoring submission {submission_kobo_id} already processed")
            continue
            
        # Extract tree_id from submission
        tree_id = sub.get("tree_id", "").strip()
        if not tree_id:
            st.warning(f"Monitoring submission {submission_kobo_id} missing tree_id - skipping")
            continue
            
        # Get tree details to check institution
        tree_data = get_tree_details(tree_id)
        if not tree_data:
            st.error(f"Tree with ID {tree_id} not found in database")
            continue
            
        # Check if tree belongs to user's institution
        tree_institution = tree_data.get("institution", "").strip()
        is_institution_match = (tree_institution.lower() == user_institution.lower())
        
        if is_institution_match:
            st.success(f"Processing monitoring submission for tree {tree_id} (matches your institution)")
            mapped_data = map_monitoring_submission_to_database(sub)
            
            if mapped_data:
                success = save_monitoring_submission(mapped_data)
                
                if success:
                    results.append({
                        "tree_id": tree_id,
                        "status": mapped_data["monitor_status"],
                        "stage": mapped_data["monitor_stage"],
                        "date": mapped_data["monitor_date"],
                        "co2": mapped_data["co2_kg"]
                    })
            else:
                st.warning(f"Failed to map monitoring submission {submission_kobo_id}")
                
    return results

def display_monitoring_results(results):
    """Display processed monitoring results in Streamlit"""
    if results:
        st.success(f"🎉 Successfully processed {len(results)} new monitoring submission(s)! 🎉")

        for result in results:
            with st.expander(f"🌳 Tree {result.get('tree_id', 'N/A')} - {result.get('status', 'Unknown Status')}"):
                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Status", result.get("status", "N/A"))
                    st.metric("Growth Stage", result.get("stage", "N/A"))
                    st.metric("Monitoring Date", result.get("date", "N/A"))

                with col2:
                    st.metric("CO₂ Sequestered", f"{result.get('co2', 0.0)} kg")
                    
                    # Get tree details for QR code
                    tree_data = get_tree_details(result.get("tree_id"))
                    if tree_data:
                        # Generate monitoring QR code
                        _, qr_path = generate_monitoring_qr_code(result.get("tree_id"), tree_data)
                        
                        if qr_path and os.path.isfile(qr_path):
                            st.image(qr_path, caption=f"Monitoring QR for Tree {result['tree_id']}")
                            with open(qr_path, "rb") as f:
                                st.download_button(
                                    "Download QR Code",
                                    f.read(),
                                    file_name=f"tree_{result['tree_id']}_monitoring_qr.png",
                                    mime="image/png"
                                )
    else:
        st.info("No monitoring results to display at this time.")

def get_monitoring_stats():
    """Get monitoring statistics for dashboard"""
    conn = sqlite3.connect(SQLITE_DB)
    try:
        # Get overall stats
        stats = pd.read_sql(
            """
            SELECT 
                COUNT(DISTINCT tree_id) as monitored_trees,
                COUNT(*) as monitoring_events,
                AVG(co2_kg) as avg_co2,
                SUM(CASE WHEN monitor_status = 'Alive' THEN 1 ELSE 0 END) as alive_count,
                COUNT(DISTINCT monitor_by) as monitors_count
            FROM monitoring_history
            """,
            conn
        )
        
        # Get monitoring by date
        monitoring_by_date = pd.read_sql(
            """
            SELECT 
                monitor_date,
                COUNT(*) as count
            FROM monitoring_history
            GROUP BY monitor_date
            ORDER BY monitor_date
            """,
            conn
        )
        
        # Get monitoring by institution
        monitoring_by_institution = pd.read_sql(
            """
            SELECT 
                t.institution,
                COUNT(DISTINCT m.tree_id) as monitored_trees,
                COUNT(*) as monitoring_events
            FROM monitoring_history m
            JOIN trees t ON m.tree_id = t.tree_id
            GROUP BY t.institution
            ORDER BY monitored_trees DESC
            """,
            conn
        )
        
        # Get growth stages
        growth_stages = pd.read_sql(
            """
            SELECT 
                monitor_stage,
                COUNT(*) as count
            FROM monitoring_history
            GROUP BY monitor_stage
            ORDER BY count DESC
            """,
            conn
        )
        
        return {
            "stats": stats.iloc[0].to_dict() if not stats.empty else {},
            "monitoring_by_date": monitoring_by_date.to_dict('records') if not monitoring_by_date.empty else [],
            "monitoring_by_institution": monitoring_by_institution.to_dict('records') if not monitoring_by_institution.empty else [],
            "growth_stages": growth_stages.to_dict('records') if not growth_stages.empty else []
        }
    except Exception as e:
        st.error(f"Error getting monitoring stats: {str(e)}")
        return {
            "stats": {},
            "monitoring_by_date": [],
            "monitoring_by_institution": [],
            "growth_stages": []
        }
    finally:
        conn.close()

def display_monitoring_dashboard():
    """Display monitoring dashboard with statistics and charts"""
    st.title("🌳 Tree Monitoring Dashboard")
    
    # Get monitoring stats
    stats = get_monitoring_stats()
    
    # Display overall metrics
    st.subheader("Overall Monitoring Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Trees Monitored", stats["stats"].get("monitored_trees", 0))
    with col2:
        st.metric("Monitoring Events", stats["stats"].get("monitoring_events", 0))
    with col3:
        survival_rate = (stats["stats"].get("alive_count", 0) / stats["stats"].get("monitoring_events", 1)) * 100 if stats["stats"].get("monitoring_events", 0) > 0 else 0
        st.metric("Survival Rate", f"{survival_rate:.1f}%")
    with col4:
        st.metric("Avg. CO₂ per Tree", f"{stats['stats'].get('avg_co2', 0):.2f} kg")
    
    # Display monitoring by institution
    st.subheader("Monitoring by Institution")
    
    if stats["monitoring_by_institution"]:
        # Create DataFrame for chart
        df = pd.DataFrame(stats["monitoring_by_institution"])
        
        # Display bar chart
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.barplot(x="institution", y="monitored_trees", data=df, ax=ax)
        ax.set_xlabel("Institution")
        ax.set_ylabel("Trees Monitored")
        ax.set_title("Trees Monitored by Institution")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig)
        
        # Display table
        st.dataframe(df)
    else:
        st.info("No monitoring data by institution available yet.")
    
    # Display growth stages
    st.subheader("Tree Growth Stages")
    
    if stats["growth_stages"]:
        # Create DataFrame for chart
        df = pd.DataFrame(stats["growth_stages"])
        
        # Display pie chart
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.pie(df["count"], labels=df["monitor_stage"], autopct="%1.1f%%", startangle=90)
        ax.axis("equal")
        st.pyplot(fig)
    else:
        st.info("No growth stage data available yet.")
    
    # Display monitoring by date
    st.subheader("Monitoring Activity Over Time")
    
    if stats["monitoring_by_date"]:
        # Create DataFrame for chart
        df = pd.DataFrame(stats["monitoring_by_date"])
        df["monitor_date"] = pd.to_datetime(df["monitor_date"])
        
        # Display line chart
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.lineplot(x="monitor_date", y="count", data=df, ax=ax)
        ax.set_xlabel("Date")
        ax.set_ylabel("Monitoring Events")
        ax.set_title("Monitoring Events Over Time")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig)
    else:
        st.info("No monitoring date data available yet.")
def monitoring_section():
    """Main Streamlit UI workflow for tree monitoring via KoBo Toolbox"""
    st.title("🌳 Tree Monitoring")
    
    # Initialize database
    initialize_database()
    
    # Validate user session before proceeding
    if not validate_user_session():
        st.warning("Please log in to access tree monitoring.")
        return
    
    # Create tabs for different sections
    tab1, tab2, tab3 = st.tabs(["Check for Updates", "Monitoring Dashboard", "Generate QR Codes"])
    
    with tab1:
        st.header("Check for New Monitoring Submissions")
        
        st.markdown("""
        Check for new tree monitoring submissions from KoBo Toolbox.
        """)
        
        # Time filter selection
        hours = st.slider("Hours to look back", min_value=1, max_value=168, value=24)
        
        if st.button("Check for New Monitoring Submissions"):
            with st.spinner("Checking for new monitoring submissions..."):
                results = check_for_new_monitoring_submissions(hours)
                display_monitoring_results(results)
    
    with tab2:
        display_monitoring_dashboard()
    
    with tab3:
        st.header("Generate Monitoring QR Codes")
        
        st.markdown("""
        Generate QR codes for tree monitoring. Users can scan these QR codes to fill out monitoring forms.
        """)
        
        # Tree ID input
        tree_id = st.text_input("Tree ID", key="qr_tree_id")
        
        if st.button("Generate QR Code"):
            if not tree_id:
                st.error("Please enter a tree ID.")
                return
                
            # Get tree details
            tree_data = get_tree_details(tree_id)
            
            if not tree_data:
                st.error(f"Tree with ID {tree_id} not found.")
                return
                
            # Generate and display QR code
            qr_img, qr_path = generate_monitoring_qr_code(tree_id, tree_data)
            
            if qr_img:
                st.success(f"QR code generated for tree {tree_id}")
                st.image(f"data:image/png;base64,{qr_img}", caption=f"Monitoring QR for Tree {tree_id}")
                
                # Download button
                if qr_path and os.path.isfile(qr_path):
                    with open(qr_path, "rb") as f:
                        st.download_button(
                            "Download QR Code",
                            f.read(),
                            file_name=f"tree_{tree_id}_monitoring_qr.png",
                            mime="image/png"
                        )
            else:
                st.error(f"Failed to generate QR code for tree {tree_id}")        
def display_tree_details(tree_data):
    """Display tree details for regular users"""
    st.subheader(f"Tree {tree_data['tree_id']}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Tree Information")
        st.write(f"**Local Name:** {tree_data.get('local_name', 'N/A')}")
        st.write(f"**Scientific Name:** {tree_data.get('scientific_name', 'N/A')}")
        st.write(f"**Institution:** {tree_data.get('institution', 'N/A')}")
    
    with col2:
        st.markdown("### Status")
        st.write(f"**Status:** {tree_data.get('status', 'N/A')}")
        st.write(f"**Growth Stage:** {tree_data.get('tree_stage', 'N/A')}")
        st.write(f"**Last Monitored:** {tree_data.get('last_monitored', 'N/A')}")
    
    # Display QR code if available
    if tree_data.get('qr_code'):
        st.markdown("### Monitoring QR Code")
        st.image(f"data:image/png;base64,{tree_data['qr_code']}", 
                width=200, caption=f"Scan to monitor Tree {tree_data['tree_id']}")
        
        qr_path = QR_CODE_DIR / f"{tree_data['tree_id']}.png"
        if os.path.exists(qr_path):
            with open(qr_path, "rb") as f:
                st.download_button(
                    "Download QR Code",
                    f.read(),
                    file_name=f"tree_{tree_data['tree_id']}_qr.png",
                    mime="image/png",
                    key=f"download_{tree_data['tree_id']}"
                )
def generate_monitoring_qr_code(tree_id, tree_data=None):
    """
    Generate and save QR code for tree monitoring with pre-filled data
    """
    try:
        # If tree_data is not provided, fetch it
        if tree_data is None:
            tree_data = get_tree_details(tree_id)
            if tree_data is None:
                st.error(f"Tree with ID {tree_id} not found.")
                return None, None
        
        # Create URL with parameters for pre-filling the form
        base_url = f"https://ee.kobotoolbox.org/x/{KOBO_MONITORING_ASSET_ID}"
        
        # Add parameters for pre-filling
        params = {
            "tree_id": tree_id,
            "local_name": tree_data.get("local_name", ""),
            "scientific_name": tree_data.get("scientific_name", ""),
            "date_planted": tree_data.get("date_planted", ""),
            "planter": tree_data.get("student_name", ""),
            "institution": tree_data.get("institution", "")
        }
        
        # Build URL with parameters
        url_params = "&".join([f"{k}={v}" for k, v in params.items() if v])
        monitoring_url = f"{base_url}?{url_params}"
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(monitoring_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#2e8b57", back_color="white")

        # Save QR code
        QR_CODE_DIR.mkdir(exist_ok=True, parents=True)
        file_path = QR_CODE_DIR / f"{tree_id}_monitoring.png"
        img.save(file_path)

        # Create base64 encoded version for display
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return img_str, str(file_path)
    except Exception as e:
        st.error(f"Error generating monitoring QR code for tree ID '{tree_id}': {str(e)}")
        return None, None
# Main app execution
if __name__ == "__main__":
    st.set_page_config(page_title="Tree Monitoring", layout="wide")
    monitoring_section()
