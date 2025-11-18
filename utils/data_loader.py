import pandas as pd
import psycopg2

def get_data():
    """
    Fetches month, revenue, and unit data from Postgres.
    Returns a cleaned pandas DataFrame.
    """

    conn = psycopg2.connect(
        dbname="femisafe_test_db",
        user="ayish",
        password="ajtp@511Db",
        host="localhost",
        port="5432"
    )

    query = """
        SELECT month, revenue, sku_units AS units
        FROM femisafe_sales
    """

    df = pd.read_sql(query, conn)
    conn.close()

    # clean
    df.columns = df.columns.str.strip().str.lower()
    df['month'] = df['month'].astype(str)

    return df
