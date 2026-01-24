import smtplib
import pandas as pd
from sqlalchemy import create_engine, text
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =========================================================
# ⚙️ CONFIGURATION (Fill these in!)
# =========================================================
# 1. Your Neon Database URL (Copy from .streamlit/secrets.toml)
DB_URL = "postgresql://neondb_owner:YOUR_PASSWORD@ep-shiny-...aws.neon.tech/neondb?sslmode=require"

# 2. Your Email Details (Use an App Password if using Gmail)
SENDER_EMAIL = "your_email@gmail.com"
SENDER_PASSWORD = "your_app_password"  # NOT your normal login password!
RECEIVER_EMAIL = "your_email@gmail.com"

# =========================================================
# 📊 DATA FETCHING
# =========================================================
def get_data():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            # Optimize: Select only required columns and alias them for consistency.
            # This is faster and more robust than fetching all columns with SELECT *.
            # NOTE: Column names with spaces/mixed-case must be double-quoted.
            shopify_query = text("""
                SELECT "total sales" AS total_sales, "quantity ordered" AS quantity_ordered
                FROM femisafe_shopify_salesdata
            """)
            amazon_query = text("""
                SELECT "ordered product sales" AS ordered_product_sales, "units ordered" AS units_ordered
                FROM femisafe_amazon_salesdata
            """)
            # The column names in the dataframe will now be 'total_sales', 'quantity_ordered', etc.
            df_s = pd.read_sql(shopify_query, conn)
            df_a = pd.read_sql(amazon_query, conn)
        return df_s, df_a
    except Exception as e:
        print(f"❌ Database Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

# =========================================================
# 🧮 CALCULATIONS
# =========================================================
print("🔄 Connecting to Neon Database...")
df_shopify, df_amazon = get_data()

if df_shopify.empty or df_amazon.empty:
    print("⚠️ Data missing. Aborting email.")
    exit()

# Calculations
# The column names are now clean because of the SQL aliases.
# Add pd.to_numeric to handle any non-numeric data gracefully.
shop_rev = pd.to_numeric(df_shopify['total_sales'], errors='coerce').fillna(0).sum()
shop_units = pd.to_numeric(df_shopify['quantity_ordered'], errors='coerce').fillna(0).sum()
amz_rev = pd.to_numeric(df_amazon['ordered_product_sales'], errors='coerce').fillna(0).sum()
amz_units = pd.to_numeric(df_amazon['units_ordered'], errors='coerce').fillna(0).sum()

total_rev = shop_rev + amz_rev

# =========================================================
# 📨 SEND EMAIL
# =========================================================
subject = f"📊 Daily Sales Snapshot: ₹{total_rev:,.0f}"

body = f"""
<html>
  <body>
    <h2>🚀 FemiSafe Daily Performance</h2>
    <p>Here is your latest status from the cloud database:</p>
    
    <table style="border-collapse: collapse; width: 100%; border: 1px solid #ddd;">
      <tr style="background-color: #f2f2f2;">
        <th style="padding: 8px; border: 1px solid #ddd;">Channel</th>
        <th style="padding: 8px; border: 1px solid #ddd;">Revenue</th>
        <th style="padding: 8px; border: 1px solid #ddd;">Units</th>
      </tr>
      <tr>
        <td style="padding: 8px; border: 1px solid #ddd;">🛍️ Shopify</td>
        <td style="padding: 8px; border: 1px solid #ddd;">₹{shop_rev:,.2f}</td>
        <td style="padding: 8px; border: 1px solid #ddd;">{int(shop_units)}</td>
      </tr>
      <tr>
        <td style="padding: 8px; border: 1px solid #ddd;">📦 Amazon</td>
        <td style="padding: 8px; border: 1px solid #ddd;">₹{amz_rev:,.2f}</td>
        <td style="padding: 8px; border: 1px solid #ddd;">{int(amz_units)}</td>
      </tr>
      <tr style="font-weight: bold; background-color: #e6f7ff;">
        <td style="padding: 8px; border: 1px solid #ddd;">TOTAL</td>
        <td style="padding: 8px; border: 1px solid #ddd;">₹{total_rev:,.2f}</td>
        <td style="padding: 8px; border: 1px solid #ddd;">{int(shop_units + amz_units)}</td>
      </tr>
    </table>
    
    <p><i>This email was sent automatically by your Python Bot. 🤖</i></p>
  </body>
</html>
"""

msg = MIMEMultipart()
msg['From'] = SENDER_EMAIL
msg['To'] = RECEIVER_EMAIL
msg['Subject'] = subject
msg.attach(MIMEText(body, 'html'))

try:
    print("📨 Sending email...")
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    server.send_message(msg)
    server.quit()
    print("✅ Email sent successfully!")
except Exception as e:
    print(f"❌ Email Failed: {e}")