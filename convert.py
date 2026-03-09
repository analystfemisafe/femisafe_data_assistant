import pandas as pd

# 1. Load your wide-format framework file
df = pd.read_csv("framework.csv")

bom_data = []

# 2. Loop through the rows (stepping by 2 because row 1 is SKU, row 2 is Cost)
for i in range(0, len(df), 2):
    # Get the Finished Good SKU from the first column
    fg_sku = df.iloc[i, 0]
    
    # Skip if it's empty
    if pd.isna(fg_sku) or str(fg_sku).strip() == "":
        continue
        
    # 3. Loop through ITEM 1 to ITEM 10 (Columns 1 through 10)
    for col_idx in range(1, 11):
        rm_sku = df.iloc[i, col_idx]
        
        # If an RM exists in this slot
        if pd.notna(rm_sku) and str(rm_sku).strip() != "":
            # Grab the cost from the row directly below it
            try:
                rm_cost = df.iloc[i+1, col_idx]
                if pd.isna(rm_cost):
                    rm_cost = 0
            except IndexError:
                rm_cost = 0
                
            # Add it to our clean list
            bom_data.append({
                "fg_sku": str(fg_sku).strip(),
                "rm_sku": str(rm_sku).strip(),
                "qty_required": 1,  # Defaulting to 1 unit required
                "rm_cost": rm_cost
            })

# 4. Create the final clean DataFrame and export it!
bom_df = pd.DataFrame(bom_data)
bom_df.to_csv("inv_bom_ready.csv", index=False)

print(f"✅ Success! Flattened {len(df)} rows into {len(bom_df)} Recipe mappings.")
print("File saved as 'inv_bom_ready.csv'")