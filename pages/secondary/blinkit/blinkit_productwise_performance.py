import streamlit as st
import pandas as pd
import psycopg2
from datetime import timedelta

# ==========================================================
# PAGE: BLINKIT → SKU SALES REPORT (LAST 7 DAYS COMPARISON)
# ==========================================================

def page():

    st.markdown("### 📦 SKU-wise Sales Report (Last 7 Days Comparison)")

    # ===================== Get Blinkit Data =====================
    @st.cache_data(ttl=600)
    def get_blinkit_data():
        conn = psycopg2.connect(
            dbname="femisafe_test_db",
            user="ayish",
            password="ajtp@511Db",
            host="localhost",
            port="5432"
        )
        query = """
            SELECT 
                order_date,
                sku,
                feeder_wh,
                net_revenue,
                quantity
            FROM femisafe_blinkit_salesdata;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df

    df = get_blinkit_data()
    df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
    df['date'] = df['order_date'].dt.date

    # ===================== Key Dates =====================
    latest_date = df['date'].max()
    d1_date = latest_date - timedelta(days=1)
    d7_date = latest_date - timedelta(days=7)

    df_filtered = df[df['date'].isin([d7_date, d1_date, latest_date])]

    # ===================== Grouping =====================
    grouped = df_filtered.groupby(
        ['sku', 'feeder_wh', 'date']
    ).agg({
        'net_revenue': 'sum',
        'quantity': 'sum'
    }).reset_index()

    pivot = grouped.pivot_table(
        index=['sku', 'feeder_wh'],
        columns='date',
        values=['net_revenue', 'quantity'],
        fill_value=0
    ).reset_index()

    # Flatten columns
    pivot.columns = [
        f"{i}_{j.strftime('%b%d')}" if j != '' else i
        for i, j in pivot.columns
    ]

    # ===================== ENSURE ALL REQUIRED COLUMNS EXIST =====================
    required_cols = [
        f'quantity_{d7_date.strftime("%b%d")}',
        f'net_revenue_{d7_date.strftime("%b%d")}',
        f'quantity_{d1_date.strftime("%b%d")}',
        f'net_revenue_{d1_date.strftime("%b%d")}',
        f'quantity_{latest_date.strftime("%b%d")}',
        f'net_revenue_{latest_date.strftime("%b%d")}',
    ]

    for col in required_cols:
        if col not in pivot.columns:
            pivot[col] = 0

    # Filter only needed columns
    pivot = pivot[[
        'sku', 'feeder_wh',
        *required_cols
    ]]

    # ===================== Delta calculations =====================
    pivot['Units Delta'] = (
        pivot[f'quantity_{latest_date.strftime("%b%d")}'] -
        pivot[f'quantity_{d7_date.strftime("%b%d")}']
    )
    pivot['Revenue Delta'] = (
        pivot[f'net_revenue_{latest_date.strftime("%b%d")}'] -
        pivot[f'net_revenue_{d7_date.strftime("%b%d")}']
    )

    # ===================== Subtotals per SKU =====================
    subtotal_rows = []

    for sku_name, group in pivot.groupby('sku', group_keys=False):

        subtotal = pd.DataFrame({
            'sku': [sku_name],
            'feeder_wh': [f"{sku_name} Total"],
            **{col: [group[col].sum()] for col in required_cols},
        })

        subtotal['Units Delta'] = (
            subtotal[f'quantity_{latest_date.strftime("%b%d")}'] -
            subtotal[f'quantity_{d7_date.strftime("%b%d")}']
        )
        subtotal['Revenue Delta'] = (
            subtotal[f'net_revenue_{latest_date.strftime("%b%d")}'] -
            subtotal[f'net_revenue_{d7_date.strftime("%b%d")}']
        )

        prev = subtotal[f'net_revenue_{d7_date.strftime("%b%d")}'].iloc[0] or 0
        curr = subtotal[f'net_revenue_{latest_date.strftime("%b%d")}'].iloc[0]
        subtotal['Growth %'] = 0 if prev == 0 else round(((curr - prev) / prev) * 100, 2)

        group['Growth %'] = ""

        subtotal_rows.append(pd.concat([group, subtotal], ignore_index=True))

    final_df = pd.concat(subtotal_rows, ignore_index=True)

    # Convert quantity to int
    for c in final_df.columns:
        if "quantity" in c:
            final_df[c] = final_df[c].astype(int)

    # ===================== Sorting =====================
    is_subtotal = final_df['feeder_wh'].astype(str).str.contains('Total')

    latest_q_col = f'quantity_{latest_date.strftime("%b%d")}'
    source_rows = final_df[~is_subtotal].copy()

    sku_totals = source_rows.groupby('sku')[latest_q_col].sum().reset_index()
    sku_totals = sku_totals.sort_values(by=latest_q_col, ascending=False)

    feeder_totals = source_rows.groupby(['sku', 'feeder_wh'])[latest_q_col].sum().reset_index()

    ordered_parts = []

    for sku_name in sku_totals['sku']:
        sku_rows = source_rows[source_rows['sku'] == sku_name].copy()

        # SAFE MERGE — prevents KeyError
        merged = sku_rows.merge(
            feeder_totals[feeder_totals['sku'] == sku_name][['feeder_wh', latest_q_col]],
            on='feeder_wh',
            how='left'
        )

        if latest_q_col in merged.columns:
            merged = merged.rename(columns={latest_q_col: 'feed_total'})
        else:
            merged['feed_total'] = 0

        sku_rows = merged.sort_values(by='feed_total', ascending=False).drop(columns=['feed_total'])

        ordered_parts.append(sku_rows)

        subtotal_row = final_df[
            (final_df['sku'] == sku_name) &
            (final_df['feeder_wh'].str.contains('Total'))
        ]

        ordered_parts.append(subtotal_row)

    ordered_df = pd.concat(ordered_parts, ignore_index=True)

    # ===================== Grand Total =====================
    g = source_rows
    grand_total = pd.DataFrame({
        'sku': ['Grand Total'],
        'feeder_wh': [''],
        **{col: [g[col].sum()] for col in required_cols},
        'Units Delta': [g['Units Delta'].sum()],
        'Revenue Delta': [g['Revenue Delta'].sum()],
        'Growth %': [
            round(
                (
                    (
                        g[f'net_revenue_{latest_date.strftime("%b%d")}'].sum() -
                        g[f'net_revenue_{d7_date.strftime("%b%d")}'].sum()
                    ) /
                    (g[f'net_revenue_{d7_date.strftime("%b%d")}'].sum() or 1)
                ) * 100, 2
            )
        ]
    })

    final_df = pd.concat([ordered_df, grand_total], ignore_index=True)

    # ===================== Formatting =====================
    for c in final_df.columns:
        if 'net_revenue' in c:
            final_df[c] = final_df[c].apply(lambda x: f"₹{int(x):,}")
        if c == 'Growth %':
            final_df[c] = final_df[c].apply(lambda x: f"{x:+.2f}%" if x != "" else "")
        if c in ['Units Delta', 'Revenue Delta']:
            final_df[c] = final_df[c].apply(lambda x: f"{int(x):,}")

    # ===================== MultiIndex Headers =====================
    date_labels = {
        d7_date.strftime("%b%d"): d7_date.strftime("%B %d"),
        d1_date.strftime("%b%d"): d1_date.strftime("%B %d"),
        latest_date.strftime("%b%d"): latest_date.strftime("%B %d"),
    }

    columns = pd.MultiIndex.from_tuples([
        ('SKU', ''),
        ('Feeder WH', ''),
        (date_labels[d7_date.strftime("%b%d")], 'Units'),
        (date_labels[d7_date.strftime("%b%d")], 'Net Rev'),
        (date_labels[d1_date.strftime("%b%d")], 'Units'),
        (date_labels[d1_date.strftime("%b%d")], 'Net Rev'),
        (date_labels[latest_date.strftime("%b%d")], 'Units'),
        (date_labels[latest_date.strftime("%b%d")], 'Net Rev'),
        ('Delta', 'Units Delta'),
        ('Delta', 'Revenue Delta'),
        ('Delta', 'Growth %')
    ])

    final_df = final_df.iloc[:, :len(columns)]
    final_df.columns = columns

    # ===================== Styling =====================
    def highlight_rows(row):
        if "Total" in str(row[('Feeder WH', '')]):
            return ['background-color:#2e2e2e;color:white;font-weight:bold'] * len(row)
        if "Grand Total" in str(row[('SKU', '')]):
            return ['background-color:#444;color:white;font-weight:bold'] * len(row)
        return [''] * len(row)

    def highlight_growth(val):
        try:
            v = float(str(val).replace('%', '').replace('+', ''))
            if v < 0:
                return 'background-color:#ffcccc;color:black;font-weight:bold'
            return 'background-color:#ccffcc;color:black;font-weight:bold'
        except:
            return ''

    # ===================== Display =====================
    st.dataframe(
        final_df.style
        .apply(highlight_rows, axis=1)
        .applymap(highlight_growth, subset=[('Delta', 'Growth %')]),
        use_container_width=True
    )
