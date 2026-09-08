import pandas as pd
import re

def parse_fyers_tradebook(uploaded_file):
    """
    Parses a Fyers tradebook file (.xlsx, .xls, .csv).
    
    Expected Excel/CSV headers:
    Name | Date & time | Side | Product type | Qty | Traded price | Total value | Segment | Exchange order ID | OMS order ID
    
    Target DB Schema:
    - orderID (bigint primary key, mapped from 'OMS order ID')
    - DateTime (timestamp)
    - Name (text)
    - Side (text)
    - Product type (text)
    - Qty (double precision)
    - Traded price (double precision)
    - Segment (text)
    """
    df = pd.DataFrame()
    filename = getattr(uploaded_file, 'name', '').lower()

    if filename.endswith('.csv'):
        try:
            df = pd.read_csv(uploaded_file)
        except Exception:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='utf-8', errors='ignore')
    else:
        # Excel file (.xlsx, .xls)
        try:
            xls = pd.ExcelFile(uploaded_file)
            sheets = xls.sheet_names
            
            # Find matching tradebook sheet if multiple exist, otherwise use first sheet
            target_sheet = sheets[0]
            for sheet in sheets:
                if re.search(r'trade|fyers|order|book', sheet, re.IGNORECASE):
                    target_sheet = sheet
                    break
            
            df = pd.read_excel(xls, sheet_name=target_sheet)
        except Exception as e:
            raise ValueError(f"Unable to read Excel file: {e}")

    if df.empty:
        return pd.DataFrame()

    # Clean whitespace in column names
    df.columns = [str(c).strip() for c in df.columns]

    # Map column names case-insensitively
    col_map = {}
    for col in df.columns:
        col_clean = col.lower().strip()
        if col_clean in ['oms order id', 'oms_order_id', 'orderid', 'order id']:
            col_map[col] = 'orderID'
        elif col_clean in ['date & time', 'date and time', 'datetime', 'date_time', 'time']:
            col_map[col] = 'DateTime'
        elif col_clean in ['name', 'symbol', 'scrip']:
            col_map[col] = 'Name'
        elif col_clean in ['side', 'txn type', 'type']:
            col_map[col] = 'Side'
        elif col_clean in ['product type', 'product_type', 'product']:
            col_map[col] = 'Product type'
        elif col_clean in ['qty', 'quantity']:
            col_map[col] = 'Qty'
        elif col_clean in ['traded price', 'traded_price', 'price', 'rate']:
            col_map[col] = 'Traded price'
        elif col_clean in ['segment']:
            col_map[col] = 'Segment'

    df = df.rename(columns=col_map)

    required_cols = ['orderID', 'DateTime', 'Name', 'Side', 'Product type', 'Qty', 'Traded price', 'Segment']
    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    # Filter down to expected schema columns
    df = df[required_cols]

    # Clean and filter rows with valid orderID
    df['orderID_clean'] = pd.to_numeric(df['orderID'], errors='coerce')
    df = df.dropna(subset=['orderID_clean'])
    df['orderID'] = df['orderID_clean'].astype(int)
    df = df.drop(columns=['orderID_clean'])

    # Format DateTime
    df['DateTime'] = pd.to_datetime(df['DateTime'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')

    # Convert numeric fields
    df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
    df['Traded price'] = pd.to_numeric(df['Traded price'], errors='coerce').fillna(0)

    # Clean strings
    for col in ['Name', 'Side', 'Product type', 'Segment']:
        df[col] = df[col].astype(str).str.strip().replace({'nan': None, 'None': None, '<NA>': None, '': None})

    # Drop duplicate orderIDs if any exist in input file (keeping last occurrence)
    df = df.drop_duplicates(subset=['orderID'], keep='last')

    return df

