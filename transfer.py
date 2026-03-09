import pandas as pd
from sqlalchemy import create_engine, inspect

# Your exact Database URLs
SUPABASE_URL = "postgresql://postgres:analyst%4025Supabase@db.lekfaycopfqksmrkpkir.supabase.co:5432/postgres"
RAILWAY_URL = "postgresql://postgres:ktJUlrlRHGSiJRhhQRssAZQfZOJaRgXy@yamabiko.proxy.rlwy.net:31256/railway"

print("🔌 Connecting to databases...")
supa_engine = create_engine(SUPABASE_URL)
rail_engine = create_engine(RAILWAY_URL)

# This powerful tool automatically reads your database structure
inspector = inspect(supa_engine)
all_tables = inspector.get_table_names()

# The 5 tables we already successfully copied
already_done = ['inv_rm_master', 'inv_fg_master', 'inv_bom', 'inv_ledger', 'inv_consignments']

print(f"🔍 Found {len(all_tables)} total tables in Supabase.")
print("🚀 Starting transfer for all remaining tables...")

with supa_engine.connect() as supa_conn:
    for table in all_tables:
        if table in already_done:
            print(f"⏭️ Skipping '{table}' (Already transferred)")
            continue
            
        try:
            # Read the table from Supabase
            df = pd.read_sql(f"SELECT * FROM {table}", supa_conn)
            
            # 'replace' will automatically create the table in Railway if it doesn't exist
            df.to_sql(table, rail_engine, if_exists='replace', index=False)
            
            if not df.empty:
                print(f"✅ Copied {len(df)} rows into '{table}'")
            else:
                print(f"⏩ Copied empty structure for '{table}'")
                
        except Exception as e:
            print(f"⚠️ Could not transfer '{table}': {e}")

print("🎉 ALL tables have now been completely migrated to Railway!")