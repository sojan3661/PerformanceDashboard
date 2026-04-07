from supabase import create_client, Client
import streamlit as st
import pandas as pd
import numpy as np

@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def save_to_trademaster(df: pd.DataFrame):
    if df.empty:
        return 0
        
    client = init_connection()
    
    # Composite keys to check uniqueness
    keys = ['Segment', 'Symbol', 'StrikePrice', 'EnteredDate', 'ExitedDate']
    
    # Fetch all existing records to check for duplicates (handling pagination)
    all_existing_data = []
    limit = 1000
    offset = 0
    while True:
        response = client.table("TradeMaster").select(",".join(keys)).range(offset, offset + limit - 1).execute()
        data = response.data
        if data:
            all_existing_data.extend(data)
            offset += limit
            if len(data) < limit:
                break
        else:
            break
            
    if all_existing_data and len(all_existing_data) > 0:
        existing_df = pd.DataFrame(all_existing_data)
        
        df_keys = df[keys].copy()
        ext_keys = existing_df[keys].copy()
        
        # Format dates for string comparison
        for date_col in ['EnteredDate', 'ExitedDate']:
            if date_col in df_keys.columns:
                df_keys[date_col] = pd.to_datetime(df_keys[date_col]).dt.strftime('%Y-%m-%d').replace('NaT', np.nan)
            if date_col in ext_keys.columns:
                ext_keys[date_col] = pd.to_datetime(ext_keys[date_col]).dt.strftime('%Y-%m-%d').replace('NaT', np.nan)
                
        df_keys = df_keys.fillna('')
        ext_keys = ext_keys.fillna('')
        
        def make_key(row):
            return "|".join([str(row[c]) for c in keys])
            
        df['__key__'] = df_keys.apply(make_key, axis=1)
        existing_keys = set(ext_keys.apply(make_key, axis=1).tolist())
        
        new_df = df[~df['__key__'].isin(existing_keys)].copy()
        new_df.drop(columns=['__key__'], inplace=True, errors='ignore')
        df.drop(columns=['__key__'], inplace=True, errors='ignore') # cleanup original
    else:
        new_df = df.copy()
        
    if new_df.empty:
        return 0

    # Ensure clean data for Supabase insertions
    records = new_df.copy()
    
    # Convert dates to ISO format strings
    for date_col in ['EnteredDate', 'ExitedDate']:
        if date_col in records.columns:
            records[date_col] = pd.to_datetime(records[date_col]).dt.strftime('%Y-%m-%d')
            records[date_col] = records[date_col].replace({'NaT': None, 'nan': None})
            
    # Replace any pandas NaNs with None for JSON serialization
    records = records.replace({np.nan: None})
    records_dict = records.to_dict(orient="records")
    
    # Insert in chunks to avoid payload limits
    chunk_size = 500
    inserted = 0
    for i in range(0, len(records_dict), chunk_size):
        chunk = records_dict[i:i+chunk_size]
        client.table("TradeMaster").insert(chunk).execute()
        inserted += len(chunk)
        
    return inserted

def save_to_charges(df: pd.DataFrame):
    if df.empty:
        return 0
        
    client = init_connection()
    keys = ['Date', 'Charge']
    
    # Fetch all existing records to check for duplicates
    all_existing_data = []
    limit = 1000
    offset = 0
    while True:
        response = client.table("Charges").select(",".join(keys)).range(offset, offset + limit - 1).execute()
        data = response.data
        if data:
            all_existing_data.extend(data)
            offset += limit
            if len(data) < limit:
                break
        else:
            break
            
    if all_existing_data and len(all_existing_data) > 0:
        existing_df = pd.DataFrame(all_existing_data)
        
        df_keys = df[keys].copy()
        ext_keys = existing_df[keys].copy()
        
        for date_col in ['Date']:
            if date_col in df_keys.columns:
                df_keys[date_col] = pd.to_datetime(df_keys[date_col]).dt.strftime('%Y-%m-%d').replace('NaT', np.nan)
            if date_col in ext_keys.columns:
                ext_keys[date_col] = pd.to_datetime(ext_keys[date_col]).dt.strftime('%Y-%m-%d').replace('NaT', np.nan)
                
        # To avoid float format disparity, try rounding Charge
        if 'Charge' in df_keys.columns:
            df_keys['Charge'] = pd.to_numeric(df_keys['Charge'], errors='coerce').round(4)
        if 'Charge' in ext_keys.columns:
            ext_keys['Charge'] = pd.to_numeric(ext_keys['Charge'], errors='coerce').round(4)
            
        df_keys = df_keys.fillna('')
        ext_keys = ext_keys.fillna('')
        
        def make_key(row):
            return "|".join([str(row[c]) for c in keys])
            
        df['__key__'] = df_keys.apply(make_key, axis=1)
        existing_keys = set(ext_keys.apply(make_key, axis=1).tolist())
        
        new_df = df[~df['__key__'].isin(existing_keys)].copy()
        new_df.drop(columns=['__key__'], inplace=True, errors='ignore')
        df.drop(columns=['__key__'], inplace=True, errors='ignore')
    else:
        new_df = df.copy()
        
    if new_df.empty:
        return 0

    records = new_df.copy()
    
    # Ensure only Date and Charge are sent to Supabase to match schema
    ext_keys = [k for k in keys if k in records.columns]
    records = records[ext_keys]
    if 'Date' in records.columns:
        records['Date'] = pd.to_datetime(records['Date']).dt.strftime('%Y-%m-%d')
        records['Date'] = records['Date'].replace({'NaT': None, 'nan': None})
        
    records = records.replace({np.nan: None})
    records_dict = records.to_dict(orient="records")
    
    chunk_size = 500
    inserted = 0
    for i in range(0, len(records_dict), chunk_size):
        chunk = records_dict[i:i+chunk_size]
        client.table("Charges").insert(chunk).execute()
        inserted += len(chunk)
        
    return inserted

