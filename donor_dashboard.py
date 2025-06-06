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
BASE_DIR = Path(__file__).parent if "__file__ in locals()" else Path.cwd()
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
    """Interface for viewing overall impact (without graphs/charts)"""
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
    
    # Institution comparison - now as a table instead of charts
    st.subheader("Institution Performance")
    
    # Prepare data for display
    display_df = stats_df[['institution', 'total_trees', 'alive_trees', 'co2_kg', 
                          'donation_count', 'total_donations', 'donated_trees']]
    display_df = display_df.rename(columns={
        'institution': 'Institution',
        'total_trees': 'Total Trees',
        'alive_trees': 'Alive Trees',
        'co2_kg': 'CO₂ (kg)',
        'donation_count': 'Donations',
        'total_donations': 'Total Donated ($)',
        'donated_trees': 'Trees Donated'
    })
    
    # Format columns
    display_df['Total Donated ($)'] = display_df['Total Donated ($)'].apply(lambda x: f"${x:,.2f}")
    display_df['CO₂ (kg)'] = display_df['CO₂ (kg)'].apply(lambda x: f"{x:,.2f}")
    
    # Display the table
    st.dataframe(display_df)

def admin_dashboard():
    """Admin interface for tracking donations"""
    st.title("🔒 Admin Dashboard")
    
    # Password protection (in a real app, use proper authentication)
    admin_password = st.text_input("Enter Admin Password", type="password")
    
    # For demo purposes, use a simple password. In production, use secure authentication.
    if admin_password != "admin123":
        st.warning("Please enter the correct password to access the admin dashboard.")
        return
    
    st.success("Welcome, Admin!")
    
    # Create tabs for different admin sections
    tab1, tab2, tab3 = st.tabs(["Donation Records", "Institution Management", "System Reports"])
    
    with tab1:
        # Donation Records
        st.header("Donation Records")
        
        # Get all donations from the database
        conn = sqlite3.connect(SQLITE_DB)
        donations_df = pd.read_sql("SELECT * FROM donations ORDER BY donation_date DESC", conn)
        conn.close()
        
        if donations_df.empty:
            st.info("No donations found in the database.")
        else:
            # Convert donation_date to datetime for filtering
            donations_df['donation_date'] = pd.to_datetime(donations_df['donation_date'])
            
            # Filters
            col1, col2, col3 = st.columns(3)
            with col1:
                status_filter = st.selectbox(
                    "Filter by Status",
                    ["All"] + donations_df['payment_status'].unique().tolist()
                )
            with col2:
                institution_filter = st.selectbox(
                    "Filter by Institution",
                    ["All"] + donations_df['institution'].unique().tolist()
                )
            with col3:
                date_range = st.date_input(
                    "Filter by Date Range",
                    value=[donations_df['donation_date'].min(), donations_df['donation_date'].max()],
                    min_value=donations_df['donation_date'].min(),
                    max_value=donations_df['donation_date'].max()
                )
            
            # Apply filters
            filtered_df = donations_df.copy()
            if status_filter != "All":
                filtered_df = filtered_df[filtered_df['payment_status'] == status_filter]
            if institution_filter != "All":
                filtered_df = filtered_df[filtered_df['institution'] == institution_filter]
            if len(date_range) == 2:
                filtered_df = filtered_df[
                    (filtered_df['donation_date'].dt.date >= date_range[0]) & 
                    (filtered_df['donation_date'].dt.date <= date_range[1])
                ]
            
            # Display metrics
            st.subheader("Summary Metrics")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Donations", f"${filtered_df['amount'].sum():,.2f}")
            with col2:
                st.metric("Number of Donations", len(filtered_df))
            with col3:
                st.metric("Total Trees Donated", filtered_df['tree_count'].sum())
            with col4:
                completed = len(filtered_df[filtered_df['payment_status'] == 'completed'])
                st.metric("Completed Donations", f"{completed} ({completed/len(filtered_df)*100:.1f}%)")
            
            # Display detailed table
            st.subheader("Donation Details")
            
            # Select columns to display
            display_cols = [
                'donation_id', 'donor_name', 'donor_email', 'institution', 
                'amount', 'tree_count', 'donation_date', 'payment_status'
            ]
            display_df = filtered_df[display_cols].rename(columns={
                'donation_id': 'ID',
                'donor_name': 'Donor Name',
                'donor_email': 'Email',
                'institution': 'Institution',
                'amount': 'Amount',
                'tree_count': 'Trees',
                'donation_date': 'Date',
                'payment_status': 'Status'
            })
            
            # Format columns
            display_df['Amount'] = display_df['Amount'].apply(lambda x: f"${x:,.2f}")
            display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d %H:%M')
            
            # Show the dataframe with expandable details
            st.dataframe(display_df)
            
            # Allow admin to view details of each donation
            selected_donation_id = st.selectbox(
                "View details for a specific donation",
                ["-- Select a donation --"] + filtered_df['donation_id'].tolist()
            )
            
            if selected_donation_id != "-- Select a donation --":
                donation_details = get_donation_by_id(selected_donation_id)
                if donation_details:
                    st.subheader("Donation Details")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Donation ID:** {donation_details['donation_id']}")
                        st.write(f"**Donor Name:** {donation_details['donor_name']}")
                        st.write(f"**Donor Email:** {donation_details['donor_email']}")
                        st.write(f"**Institution:** {donation_details['institution']}")
                    
                    with col2:
                        st.write(f"**Amount:** ${donation_details['amount']:.2f}")
                        st.write(f"**Trees Donated:** {donation_details['tree_count']}")
                        st.write(f"**Date:** {donation_details['donation_date']}")
                        st.write(f"**Status:** {donation_details['payment_status'].title()}")
                    
                    # Show assigned trees if payment is completed
                    if donation_details['payment_status'] == 'completed' and donation_details.get('trees'):
                        st.subheader("Assigned Trees")
                        trees_df = pd.DataFrame(donation_details['trees'])
                        
                        # Select columns to display
                        tree_display_cols = ['tree_id', 'local_name', 'scientific_name', 'date_planted', 'status', 'co2_kg']
                        tree_display_df = trees_df[tree_display_cols].rename(columns={
                            'tree_id': 'Tree ID',
                            'local_name': 'Local Name',
                            'scientific_name': 'Scientific Name',
                            'date_planted': 'Date Planted',
                            'status': 'Status',
                            'co2_kg': 'CO₂ (kg)'
                        })
                        
                        st.dataframe(tree_display_df)
                    
                    # Admin actions
                    st.subheader("Admin Actions")
                    if donation_details['payment_status'] != 'completed':
                        if st.button("Mark as Completed", key=f"complete_{selected_donation_id}"):
                            if update_payment_status(selected_donation_id, "completed"):
                                st.success("Donation marked as completed!")
                                st.rerun()
                            else:
                                st.error("Failed to update donation status")
                    
                    # Download certificate if available
                    if donation_details.get('certificate_path'):
                        with open(donation_details['certificate_path'], "rb") as file:
                            st.download_button(
                                label="Download Certificate",
                                data=file,
                                file_name=f"Certificate_{selected_donation_id}.png",
                                mime="image/png"
                            )
    
    with tab2:
        # Institution Management
        st.header("Institution Management")
        
        # Get all institutions
        conn = sqlite3.connect(SQLITE_DB)
        institutions_df = pd.read_sql("""
            SELECT 
                i.institution,
                i.qualified,
                i.qualification_reason,
                i.qualification_date,
                COUNT(d.donation_id) as donation_count,
                SUM(d.amount) as total_donations,
                SUM(d.tree_count) as total_trees_donated
            FROM institution_qualification i
            LEFT JOIN donations d ON i.institution = d.institution
            GROUP BY i.institution
            ORDER BY i.institution
        """, conn)
        conn.close()
        
        # Display current institutions
        st.subheader("Current Institutions")
        if institutions_df.empty:
            st.info("No institutions found in the database.")
        else:
            # Display metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Institutions", len(institutions_df))
            with col2:
                qualified = institutions_df['qualified'].sum()
                st.metric("Qualified Institutions", f"{qualified} ({qualified/len(institutions_df)*100:.1f}%)")
            with col3:
                st.metric("Total Donations Received", f"${institutions_df['total_donations'].sum():,.2f}")
            
            # Display institution table
            st.dataframe(institutions_df)
            
            # Institution management
            st.subheader("Manage Institutions")
            selected_institution = st.selectbox(
                "Select an institution to manage",
                ["-- Select an institution --"] + institutions_df['institution'].tolist()
            )
            
            if selected_institution != "-- Select an institution --":
                institution_data = institutions_df[institutions_df['institution'] == selected_institution].iloc[0]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Institution:** {institution_data['institution']}")
                    st.write(f"**Currently Qualified:** {'Yes' if institution_data['qualified'] else 'No'}")
                    st.write(f"**Qualification Reason:** {institution_data['qualification_reason']}")
                    st.write(f"**Qualification Date:** {institution_data['qualification_date']}")
                
                with col2:
                    st.write(f"**Donation Count:** {institution_data['donation_count']}")
                    st.write(f"**Total Donations:** ${institution_data['total_donations']:,.2f}")
                    st.write(f"**Trees Donated:** {institution_data['total_trees_donated']}")
                
                # Update qualification status
                new_status = st.checkbox("Qualified for Donations", value=bool(institution_data['qualified']))
                new_reason = st.text_area("Qualification Reason", value=institution_data['qualification_reason'])
                
                if st.button("Update Institution Status"):
                    conn = sqlite3.connect(SQLITE_DB)
                    try:
                        c = conn.cursor()
                        c.execute(
                            "UPDATE institution_qualification SET qualified = ?, qualification_reason = ?, qualification_date = ? WHERE institution = ?",
                            (int(new_status), new_reason, datetime.now().isoformat(), selected_institution)
                        )
                        conn.commit()
                        st.success("Institution status updated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error updating institution: {str(e)}")
                    finally:
                        conn.close()
    
    with tab3:
        # System Reports
        st.header("System Reports")
        
        # Get all data for reports
        conn = sqlite3.connect(SQLITE_DB)
        
        # Donation trends over time
        st.subheader("Donation Trends")
        donation_trends = pd.read_sql("""
            SELECT 
                date(donation_date) as day,
                COUNT(*) as donation_count,
                SUM(amount) as total_amount,
                SUM(tree_count) as total_trees
            FROM donations
            WHERE payment_status = 'completed'
            GROUP BY date(donation_date)
            ORDER BY day
        """, conn)
        
        if not donation_trends.empty:
            # Display as tables instead of charts
            st.write("Daily Donation Counts:")
            st.dataframe(donation_trends[['day', 'donation_count']].rename(columns={
                'day': 'Date',
                'donation_count': 'Donations'
            }))
            
            st.write("Daily Donation Amounts:")
            st.dataframe(donation_trends[['day', 'total_amount']].rename(columns={
                'day': 'Date',
                'total_amount': 'Amount ($)'
            }))
            
            st.write("Daily Trees Donated:")
            st.dataframe(donation_trends[['day', 'total_trees']].rename(columns={
                'day': 'Date',
                'total_trees': 'Trees'
            }))
        
        # Institution performance
        st.subheader("Institution Performance")
        institution_performance = pd.read_sql("""
            SELECT 
                institution,
                COUNT(*) as donation_count,
                SUM(amount) as total_amount,
                SUM(tree_count) as total_trees,
                AVG(amount) as avg_donation
            FROM donations
            WHERE payment_status = 'completed'
            GROUP BY institution
            ORDER BY total_amount DESC
        """, conn)
        
        if not institution_performance.empty:
            st.dataframe(institution_performance.rename(columns={
                'institution': 'Institution',
                'donation_count': 'Donations',
                'total_amount': 'Total Amount ($)',
                'total_trees': 'Total Trees',
                'avg_donation': 'Average Donation ($)'
            }))
        
        conn.close()

def main():
    """Main application function with navigation"""
    st.sidebar.title("Navigation")
    app_mode = st.sidebar.selectbox("Choose the dashboard", ["Donor Dashboard", "Admin Dashboard"])
    
    if app_mode == "Donor Dashboard":
        donor_dashboard()
    elif app_mode == "Admin Dashboard":
        admin_dashboard()

# Initialize session state variables
if 'show_payment' not in st.session_state:
    st.session_state.show_payment = False
if 'current_donation_id' not in st.session_state:
    st.session_state.current_donation_id = None
if 'current_donation_amount' not in st.session_state:
    st.session_state.current_donation_amount = 0

if __name__ == "__main__":
    main()
