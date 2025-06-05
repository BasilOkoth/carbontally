import streamlit as st
import sqlite3
import pandas as pd
import qrcode
import base64
from io import BytesIO
from datetime import datetime
from pathlib import Path
import uuid
import json
import re

# Database configuration
BASE_DIR = Path(__file__).parent if "__file__" in locals() else Path.cwd()
DATA_DIR = BASE_DIR / "data"
SQLITE_DB = DATA_DIR / "trees.db"
CERT_DIR = DATA_DIR / "certificates"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True, parents=True)
CERT_DIR.mkdir(exist_ok=True, parents=True)

def initialize_donor_database():
    """Initialize the database tables needed for donor functionality"""
    conn = sqlite3.connect(SQLITE_DB)
    try:
        c = conn.cursor()
        
        # Create donations table if not exists
        c.execute('''
            CREATE TABLE IF NOT EXISTS donations (
                donation_id TEXT PRIMARY KEY,
                donor_name TEXT,
                donor_email TEXT,
                institution TEXT,
                amount REAL,
                tree_count INTEGER,
                donation_date TEXT,
                payment_status TEXT,
                payment_id TEXT,
                certificate_path TEXT
            )
        ''')
        conn.commit()
        
        # Create donated_trees table to track which trees were funded by donations
        c.execute('''
            CREATE TABLE IF NOT EXISTS donated_trees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donation_id TEXT,
                tree_id TEXT,
                FOREIGN KEY (donation_id) REFERENCES donations (donation_id),
                FOREIGN KEY (tree_id) REFERENCES trees (tree_id)
            )
        ''')
        conn.commit()
        
        # Create institution_qualification table to track which institutions qualify for donations
        c.execute('''
            CREATE TABLE IF NOT EXISTS institution_qualification (
                institution TEXT PRIMARY KEY,
                qualified BOOLEAN,
                qualification_reason TEXT,
                qualification_date TEXT
            )
        ''')
        conn.commit()
        
    except Exception as e:
        st.error(f"Error initializing donor database: {str(e)}")
    finally:
        conn.close()

def get_qualifying_institutions():
    """Get a list of institutions that qualify for donations"""
    conn = sqlite3.connect(SQLITE_DB)
    try:
        # First check the qualification table
        qualified_df = pd.read_sql(
            "SELECT institution FROM institution_qualification WHERE qualified = 1",
            conn
        )
        
        if not qualified_df.empty:
            return qualified_df["institution"].tolist()
        
        # If no explicit qualifications, get all institutions with trees
        institutions_df = pd.read_sql(
            "SELECT DISTINCT institution FROM trees WHERE institution IS NOT NULL AND institution != ''",
            conn
        )
        
        # Mark all as qualified by default
        for institution in institutions_df["institution"]:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO institution_qualification (institution, qualified, qualification_reason, qualification_date) VALUES (?, 1, ?, ?)",
                (institution, "Default qualification", datetime.now().isoformat())
            )
        conn.commit()
        
        return institutions_df["institution"].tolist()
    except Exception as e:
        st.error(f"Error getting qualifying institutions: {str(e)}")
        return []
    finally:
        conn.close()

def get_institution_stats(institution):
    """Get statistics for a specific institution"""
    conn = sqlite3.connect(SQLITE_DB)
    try:
        # Get tree counts
        stats = pd.read_sql(
            """
            SELECT 
                COUNT(*) as total_trees,
                SUM(CASE WHEN status = 'Alive' THEN 1 ELSE 0 END) as alive_trees,
                SUM(CASE WHEN status = 'Alive' THEN co2_kg ELSE 0 END) as co2_kg
            FROM trees
            WHERE institution = ?
            """,
            conn,
            params=(institution,)
        )
        
        # Get donation stats
        donation_stats = pd.read_sql(
            """
            SELECT 
                COUNT(*) as donation_count,
                SUM(amount) as total_donations,
                SUM(tree_count) as donated_trees
            FROM donations
            WHERE institution = ? AND payment_status = 'completed'
            """,
            conn,
            params=(institution,)
        )
        
        # Combine stats
        result = {
            "institution": institution,
            "total_trees": int(stats["total_trees"].iloc[0]) if not stats.empty else 0,
            "alive_trees": int(stats["alive_trees"].iloc[0]) if not stats.empty else 0,
            "co2_kg": float(stats["co2_kg"].iloc[0]) if not stats.empty and stats["co2_kg"].iloc[0] is not None else 0.0,
            "donation_count": int(donation_stats["donation_count"].iloc[0]) if not donation_stats.empty else 0,
            "total_donations": float(donation_stats["total_donations"].iloc[0]) if not donation_stats.empty and donation_stats["total_donations"].iloc[0] is not None else 0.0,
            "donated_trees": int(donation_stats["donated_trees"].iloc[0]) if not donation_stats.empty else 0
        }
        
        # Calculate survival rate
        if result["total_trees"] > 0:
            result["survival_rate"] = (result["alive_trees"] / result["total_trees"]) * 100
        else:
            result["survival_rate"] = 0
            
        return result
    except Exception as e:
        st.error(f"Error getting institution stats: {str(e)}")
        return {
            "institution": institution,
            "total_trees": 0,
            "alive_trees": 0,
            "co2_kg": 0.0,
            "survival_rate": 0,
            "donation_count": 0,
            "total_donations": 0.0,
            "donated_trees": 0
        }
    finally:
        conn.close()

def create_donation(donor_name, donor_email, institution, amount, tree_count):
    """Create a new donation record"""
    donation_id = f"DON{uuid.uuid4().hex[:8].upper()}"
    donation_date = datetime.now().isoformat()
    
    conn = sqlite3.connect(SQLITE_DB)
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO donations 
            (donation_id, donor_name, donor_email, institution, amount, tree_count, donation_date, payment_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (donation_id, donor_name, donor_email, institution, amount, tree_count, donation_date, "pending")
        )
        conn.commit()
        return donation_id
    except Exception as e:
        st.error(f"Error creating donation: {str(e)}")
        return None
    finally:
        conn.close()

def update_payment_status(donation_id, payment_status, payment_id=None):
    """Update the payment status for a donation"""
    conn = sqlite3.connect(SQLITE_DB)
    try:
        c = conn.cursor()
        if payment_id:
            c.execute(
                "UPDATE donations SET payment_status = ?, payment_id = ? WHERE donation_id = ?",
                (payment_status, payment_id, donation_id)
            )
        else:
            c.execute(
                "UPDATE donations SET payment_status = ? WHERE donation_id = ?",
                (payment_status, donation_id)
            )
        conn.commit()
        
        # If payment is completed, generate certificate and assign trees
        if payment_status == "completed":
            donation_data = pd.read_sql(
                "SELECT * FROM donations WHERE donation_id = ?",
                conn,
                params=(donation_id,)
            )
            
            if not donation_data.empty:
                # Generate certificate
                cert_path = generate_donation_certificate(donation_data.iloc[0])
                
                # Update certificate path
                c.execute(
                    "UPDATE donations SET certificate_path = ? WHERE donation_id = ?",
                    (cert_path, donation_id)
                )
                conn.commit()
                
                # Assign trees to donation
                assign_trees_to_donation(donation_id, donation_data.iloc[0]["institution"], donation_data.iloc[0]["tree_count"])
        
        return True
    except Exception as e:
        st.error(f"Error updating payment status: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def assign_trees_to_donation(donation_id, institution, tree_count):
    """Assign trees to a donation"""
    conn = sqlite3.connect(SQLITE_DB)
    try:
        # Get unassigned trees for this institution
        trees_df = pd.read_sql(
            """
            SELECT t.tree_id 
            FROM trees t
            LEFT JOIN donated_trees dt ON t.tree_id = dt.tree_id
            WHERE t.institution = ? AND dt.tree_id IS NULL
            LIMIT ?
            """,
            conn,
            params=(institution, tree_count)
        )
        
        if trees_df.empty:
            st.warning(f"No available trees to assign for donation {donation_id}")
            return False
            
        # Assign trees to donation
        c = conn.cursor()
        for tree_id in trees_df["tree_id"]:
            c.execute(
                "INSERT INTO donated_trees (donation_id, tree_id) VALUES (?, ?)",
                (donation_id, tree_id)
            )
        conn.commit()
        
        # If not enough trees available, log a warning
        if len(trees_df) < tree_count:
            st.warning(f"Only {len(trees_df)} trees available for donation {donation_id}, which requested {tree_count} trees")
            
        return True
    except Exception as e:
        st.error(f"Error assigning trees to donation: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def generate_donation_certificate(donation_data):
    """Generate a certificate for a donation"""
    try:
        # Create a unique filename
        filename = f"certificate_{donation_data['donation_id']}.png"
        file_path = CERT_DIR / filename
        
        # Get institution stats
        institution_stats = get_institution_stats(donation_data["institution"])
        
        # Create certificate image (simple version)
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        
        # Create a white certificate background
        width, height = 1200, 900
        certificate = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(certificate)
        
        # Try to load fonts, fall back to default if not available
        try:
            title_font = ImageFont.truetype("arial.ttf", 60)
            header_font = ImageFont.truetype("arial.ttf", 40)
            body_font = ImageFont.truetype("arial.ttf", 30)
        except IOError:
            # Use default font if arial is not available
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            body_font = ImageFont.load_default()
        
        # Add border
        draw.rectangle([(20, 20), (width-20, height-20)], outline=(46, 139, 87), width=10)
        
        # Add title
        draw.text((width//2, 100), "Certificate of Donation", fill=(46, 139, 87), font=title_font, anchor="mm")
        
        # Add donor name
        draw.text((width//2, 200), f"This certifies that", fill=(0, 0, 0), font=body_font, anchor="mm")
        draw.text((width//2, 250), f"{donation_data['donor_name']}", fill=(0, 0, 0), font=header_font, anchor="mm")
        
        # Add donation details
        draw.text((width//2, 350), f"has generously donated", fill=(0, 0, 0), font=body_font, anchor="mm")
        draw.text((width//2, 400), f"${donation_data['amount']:.2f}", fill=(46, 139, 87), font=header_font, anchor="mm")
        draw.text((width//2, 450), f"to support {donation_data['tree_count']} trees at", fill=(0, 0, 0), font=body_font, anchor="mm")
        draw.text((width//2, 500), f"{donation_data['institution']}", fill=(0, 0, 0), font=header_font, anchor="mm")
        
        # Add impact
        co2_impact = institution_stats["co2_kg"] / institution_stats["alive_trees"] * donation_data["tree_count"] if institution_stats["alive_trees"] > 0 else 0
        draw.text((width//2, 600), f"Estimated CO₂ Impact: {co2_impact:.2f} kg", fill=(0, 0, 0), font=body_font, anchor="mm")
        
        # Add date and signature
        donation_date = datetime.fromisoformat(donation_data["donation_date"]).strftime("%B %d, %Y")
        draw.text((width//2, 700), f"Donation Date: {donation_date}", fill=(0, 0, 0), font=body_font, anchor="mm")
        
        # Add CarbonTally logo text
        draw.text((width//2, 800), "🌱 CarbonTally", fill=(46, 139, 87), font=header_font, anchor="mm")
        
        # Save the certificate
        certificate.save(file_path)
        
        return str(file_path)
    except Exception as e:
        st.error(f"Error generating certificate: {str(e)}")
        return None

def get_donation_by_id(donation_id):
    """Get donation details by ID"""
    conn = sqlite3.connect(SQLITE_DB)
    try:
        donation_data = pd.read_sql(
            "SELECT * FROM donations WHERE donation_id = ?",
            conn,
            params=(donation_id,)
        )
        
        if donation_data.empty:
            return None
            
        # Get assigned trees
        trees_df = pd.read_sql(
            """
            SELECT t.* 
            FROM trees t
            JOIN donated_trees dt ON t.tree_id = dt.tree_id
            WHERE dt.donation_id = ?
            """,
            conn,
            params=(donation_id,)
        )
        
        result = donation_data.iloc[0].to_dict()
        result["trees"] = trees_df.to_dict('records') if not trees_df.empty else []
        
        return result
    except Exception as e:
        st.error(f"Error getting donation: {str(e)}")
        return None
    finally:
        conn.close()

def get_donations_by_email(email):
    """Get all donations for a specific email address"""
    conn = sqlite3.connect(SQLITE_DB)
    try:
        donations_df = pd.read_sql(
            "SELECT * FROM donations WHERE donor_email = ? ORDER BY donation_date DESC",
            conn,
            params=(email,)
        )
        
        return donations_df.to_dict('records') if not donations_df.empty else []
    except Exception as e:
        st.error(f"Error getting donations by email: {str(e)}")
        return []
    finally:
        conn.close()

def display_paypal_button(donation_id, amount):
    """Display a PayPal donation button"""
    # In a production environment, you would use the PayPal SDK
    # This is a simplified version for demonstration purposes
    
    paypal_html = f"""
    <div id="paypal-button-container-{donation_id}"></div>
    <script src="https://www.paypal.com/sdk/js?client-id=test&currency=USD"></script>
    <script>
      paypal.Buttons({{
        createOrder: function(data, actions) {{
          return actions.order.create({{
            purchase_units: [{{
              amount: {{
                value: '{amount:.2f}'
              }}
            }}]
          }});
        }},
        onApprove: function(data, actions) {{
          return actions.order.capture().then(function(details) {{
            // Call your server to update the payment status
            window.parent.postMessage({{
              type: 'payment_completed',
              donation_id: '{donation_id}',
              payment_id: details.id
            }}, '*');
            
            // Show a success message
            alert('Payment completed! Thank you for your donation.');
            
            // Reload the page to show updated status
            window.parent.location.reload();
          }});
        }}
      }}).render('#paypal-button-container-{donation_id}');
    </script>
    """
    
    st.components.v1.html(paypal_html, height=100)
    
    # For testing purposes, add a button to simulate payment completion
    if st.button(f"Simulate Payment Completion for {donation_id}"):
        update_payment_status(donation_id, "completed", f"SIMULATED-{uuid.uuid4().hex[:8].upper()}")
        st.success("Payment simulation completed! Refreshing page...")
        st.rerun()

def donor_dashboard():
    """Main donor dashboard interface"""
    st.title("🌳 Tree Donation Dashboard")
    
    # Initialize database tables if needed
    initialize_donor_database()
    
    # Create tabs for different sections
    tab1, tab2, tab3 = st.tabs(["Donate Trees", "Track Your Donations", "Impact Dashboard"])
    
    with tab1:
        donate_trees_section()
        
    with tab2:
        track_donations_section()
        
    with tab3:
        impact_dashboard_section()

def donate_trees_section():
    """Interface for donating trees"""
    st.header("Donate Trees")
    
    st.markdown("""
    Support tree planting initiatives by donating trees to qualifying institutions. 
    Your donation helps combat climate change and supports local communities.
    """)
    
    # Get qualifying institutions
    qualifying_institutions = get_qualifying_institutions()
    
    if not qualifying_institutions:
        st.warning("No qualifying institutions found. Please check back later.")
        return
    
    # Institution selection
    selected_institution = st.selectbox(
        "Select an institution to support",
        ["-- Select an institution --"] + qualifying_institutions
    )
    
    if selected_institution == "-- Select an institution --":
        st.info("Please select an institution to continue.")
        return
    
    # Display institution stats
    institution_stats = get_institution_stats(selected_institution)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Trees Planted", f"{institution_stats['total_trees']:,}")
    with col2:
        st.metric("Survival Rate", f"{institution_stats['survival_rate']:.1f}%")
    with col3:
        st.metric("CO₂ Sequestered", f"{institution_stats['co2_kg']:.2f} kg")
    
    # Donation form
    st.subheader("Your Donation")
    
    # Calculate tree cost (in a real app, this might vary by species or region)
    tree_cost = 5.00  # $5 per tree
    
    # Tree count selection
    tree_count = st.number_input("Number of trees to donate", min_value=1, value=5)
    donation_amount = tree_count * tree_cost
    
    st.info(f"Donation amount: ${donation_amount:.2f} (${tree_cost:.2f} per tree)")
    
    # Donor information
    st.subheader("Your Information")
    donor_name = st.text_input("Your Name")
    donor_email = st.text_input("Your Email")
    
    # Validate inputs
    if not donor_name or not donor_email or not re.match(r"[^@]+@[^@]+\.[^@]+", donor_email):
        st.warning("Please provide your name and a valid email address.")
        proceed_button_disabled = True
    else:
        proceed_button_disabled = False
    
    # Proceed to payment
    if st.button("Proceed to Payment", disabled=proceed_button_disabled):
        # Create donation record
        donation_id = create_donation(donor_name, donor_email, selected_institution, donation_amount, tree_count)
        
        if donation_id:
            st.session_state.current_donation_id = donation_id
            st.session_state.current_donation_amount = donation_amount
            st.success(f"Donation created! Please complete the payment below.")
            st.session_state.show_payment = True
            st.rerun()
    
    # Show payment options if donation was created
    if st.session_state.get("show_payment", False) and st.session_state.get("current_donation_id"):
        st.subheader("Complete Your Payment")
        st.write("Please complete your payment using PayPal:")
        
        display_paypal_button(
            st.session_state.current_donation_id,
            st.session_state.current_donation_amount
        )

def track_donations_section():
    """Interface for tracking donations"""
    st.header("Track Your Donations")
    
    st.markdown("""
    Enter your email address to view your donation history and track the impact of your contributions.
    """)
    
    # Email input
    tracking_email = st.text_input("Your Email Address")
    
    if st.button("Find My Donations", disabled=not tracking_email):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", tracking_email):
            st.error("Please enter a valid email address.")
            return
            
        # Get donations for this email
        donations = get_donations_by_email(tracking_email)
        
        if not donations:
            st.info("No donations found for this email address.")
            return
            
        st.success(f"Found {len(donations)} donation(s) for {tracking_email}")
        
        # Display donations
        for donation in donations:
            with st.expander(f"Donation {donation['donation_id']} - {donation['donation_date'][:10]}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Institution:** {donation['institution']}")
                    st.write(f"**Amount:** ${donation['amount']:.2f}")
                    st.write(f"**Trees:** {donation['tree_count']}")
                    st.write(f"**Status:** {donation['payment_status'].title()}")
                
                with col2:
                    # If payment is completed and certificate exists
                    if donation['payment_status'] == 'completed' and donation['certificate_path']:
                        try:
                            # Display certificate
                            from PIL import Image
                            cert_image = Image.open(donation['certificate_path'])
                            st.image(cert_image, caption="Donation Certificate", width=300)
                            
                            # Download button
                            with open(donation['certificate_path'], "rb") as file:
                                st.download_button(
                                    label="Download Certificate",
                                    data=file,
                                    file_name=f"CarbonTally_Certificate_{donation['donation_id']}.png",
                                    mime="image/png"
                                )
                        except Exception as e:
                            st.error(f"Error displaying certificate: {str(e)}")
                    elif donation['payment_status'] == 'pending':
                        st.warning("Payment pending. Please complete your payment to receive your certificate.")
                        display_paypal_button(donation['donation_id'], donation['amount'])
                
                # If payment is completed, show the trees
                if donation['payment_status'] == 'completed':
                    # Get full donation details including trees
                    full_donation = get_donation_by_id(donation['donation_id'])
                    
                    if full_donation and full_donation['trees']:
                        st.subheader("Your Trees")
                        
                        # Create a dataframe for display
                        trees_df = pd.DataFrame(full_donation['trees'])
                        
                        # Select columns to display
                        display_cols = ['tree_id', 'local_name', 'scientific_name', 'date_planted', 'status', 'co2_kg']
                        display_df = trees_df[display_cols].rename(columns={
                            'tree_id': 'Tree ID',
                            'local_name': 'Local Name',
                            'scientific_name': 'Scientific Name',
                            'date_planted': 'Date Planted',
                            'status': 'Status',
                            'co2_kg': 'CO₂ (kg)'
                        })
                        
                        st.dataframe(display_df)
                    else:
                        st.info("Trees are being assigned to your donation.")

def impact_dashboard_section():
    """Interface for viewing overall impact"""
    st.header("Donation Impact Dashboard")
    
    # Get qualifying institutions
    qualifying_institutions = get_qualifying_institutions()
    
    if not qualifying_institutions:
        st.warning("No qualifying institutions found.")
        return
    
    # Get stats for all institutions
    all_stats = []
    for institution in qualifying_institutions:
        stats = get_institution_stats(institution)
        all_stats.append(stats)
    
    # Create a dataframe for display
    stats_df = pd.DataFrame(all_stats)
    
    # Calculate totals
    total_trees = stats_df['total_trees'].sum()
    total_alive = stats_df['alive_trees'].sum()
    total_co2 = stats_df['co2_kg'].sum()
    total_donations = stats_df['total_donations'].sum()
    total_donated_trees = stats_df['donated_trees'].sum()
    
    # Overall metrics
    st.subheader("Overall Impact")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Trees", f"{total_trees:,}")
        st.metric("Total Donations", f"${total_donations:,.2f}")
    
    with col2:
        survival_rate = (total_alive / total_trees * 100) if total_trees > 0 else 0
        st.metric("Overall Survival Rate", f"{survival_rate:.1f}%")
        st.metric("Donated Trees", f"{total_donated_trees:,}")
    
    with col3:
        st.metric("CO₂ Sequestered", f"{total_co2:,.2f} kg")
        trees_needed = total_donated_trees - total_trees
        if trees_needed > 0:
            st.metric("Trees Needed", f"{trees_needed:,}")
        else:
            st.metric("Extra Trees", f"{abs(trees_needed):,}")
    
    # Institution comparison
    st.subheader("Institution Comparison")
    
    # Prepare data for charts
    chart_df = stats_df[['institution', 'total_trees', 'alive_trees', 'co2_kg', 'total_donations']]
    chart_df = chart_df.sort_values('total_trees', ascending=False)
    
    # Trees by institution
    st.bar_chart(chart_df.set_index('institution')['total_trees'])
    
    # CO2 by institution
    st.subheader("CO₂ Sequestration by Institution")
    st.bar_chart(chart_df.set_index('institution')['co2_kg'])
    
    # Donations by institution
    st.subheader("Donations by Institution")
    st.bar_chart(chart_df.set_index('institution')['total_donations'])

# Initialize session state variables
if 'show_payment' not in st.session_state:
    st.session_state.show_payment = False
if 'current_donation_id' not in st.session_state:
    st.session_state.current_donation_id = None
if 'current_donation_amount' not in st.session_state:
    st.session_state.current_donation_amount = 0
