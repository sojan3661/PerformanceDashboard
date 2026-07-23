from supabase import create_client, Client
import streamlit as st
import pandas as pd
import numpy as np

@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

from supabase import create_client, Client
import streamlit as st
import pandas as pd
import numpy as np

@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def _clean_record_dict(rec_dict):
    """Clean dictionary for JSON serialization so no NaN or nan strings exist."""
    cleaned = {}
    for k, v in rec_dict.items():
        if pd.isna(v) or str(v).strip() in ['nan', 'NaN', 'None', '<NA>']:
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned

def save_to_trademaster(df: pd.DataFrame):
    if df.empty:
        return 0, 0
        
    client = init_connection()
    keys = ['Segment', 'Symbol', 'StrikePrice', 'EnteredDate', 'ExitedDate']
    select_cols = ['id'] + keys + ['Qty', 'BuyRate', 'SellRate']
    
    all_existing_data = []
    limit = 1000
    offset = 0
    while True:
        response = client.table("TradeMaster").select(",".join(select_cols)).range(offset, offset + limit - 1).execute()
        data = response.data
        if data:
            all_existing_data.extend(data)
            offset += limit
            if len(data) < limit:
                break
        else:
            break
            
    def make_key(segment, symbol, strike, entered, exited):
        seg_str = str(segment).strip() if pd.notna(segment) else ''
        sym_str = str(symbol).strip().upper() if pd.notna(symbol) else ''
        strk_str = str(strike).strip().upper() if pd.notna(strike) and str(strike).strip().upper() not in ['NONE', 'NAN', ''] else ''
        
        ent_str = ''
        if pd.notna(entered):
            try:
                ent_str = pd.to_datetime(entered).strftime('%Y-%m-%d')
            except Exception:
                ent_str = str(entered).strip()
                
        ext_str = ''
        if pd.notna(exited):
            try:
                ext_str = pd.to_datetime(exited).strftime('%Y-%m-%d')
            except Exception:
                ext_str = str(exited).strip()
                
        return f"{seg_str}|{sym_str}|{strk_str}|{ent_str}|{ext_str}"

    existing_map = {}
    if all_existing_data:
        for row in all_existing_data:
            k = make_key(row.get('Segment'), row.get('Symbol'), row.get('StrikePrice'), row.get('EnteredDate'), row.get('ExitedDate'))
            existing_map[k] = row

    records_to_insert = []
    records_to_update = []

    for idx, row in df.iterrows():
        k = make_key(row.get('Segment'), row.get('Symbol'), row.get('StrikePrice'), row.get('EnteredDate'), row.get('ExitedDate'))
        
        qty = float(row.get('Qty', 0) or 0)
        buy_rate = float(row.get('BuyRate', 0) or 0)
        sell_rate = float(row.get('SellRate', 0) or 0)
        
        entered_date = pd.to_datetime(row.get('EnteredDate')).strftime('%Y-%m-%d') if pd.notna(row.get('EnteredDate')) else None
        exited_date = pd.to_datetime(row.get('ExitedDate')).strftime('%Y-%m-%d') if pd.notna(row.get('ExitedDate')) else None
        
        symbol = str(row.get('Symbol')).strip().upper() if pd.notna(row.get('Symbol')) else None
        strike = str(row.get('StrikePrice')).strip().upper() if pd.notna(row.get('StrikePrice')) and str(row.get('StrikePrice')).strip().upper() not in ['NONE', 'NAN', ''] else None
        segment = str(row.get('Segment')).strip() if pd.notna(row.get('Segment')) else None

        rec_dict = {
            'Segment': segment,
            'Symbol': symbol,
            'StrikePrice': strike,
            'Qty': qty,
            'BuyRate': buy_rate,
            'EnteredDate': entered_date,
            'SellRate': sell_rate,
            'ExitedDate': exited_date
        }
        rec_dict = _clean_record_dict(rec_dict)

        if k not in existing_map:
            records_to_insert.append(rec_dict)
        else:
            existing_row = existing_map[k]
            ex_qty = float(existing_row.get('Qty', 0) or 0)
            ex_buy = float(existing_row.get('BuyRate', 0) or 0)
            ex_sell = float(existing_row.get('SellRate', 0) or 0)
            
            if abs(qty - ex_qty) > 1e-4 or abs(buy_rate - ex_buy) > 1e-4 or abs(sell_rate - ex_sell) > 1e-4:
                record_id = existing_row['id']
                records_to_update.append((record_id, rec_dict))

    inserted = 0
    updated = 0

    if records_to_insert:
        chunk_size = 500
        for i in range(0, len(records_to_insert), chunk_size):
            chunk = records_to_insert[i:i+chunk_size]
            client.table("TradeMaster").insert(chunk).execute()
            inserted += len(chunk)

    if records_to_update:
        for rec_id, update_dict in records_to_update:
            client.table("TradeMaster").update(update_dict).eq('id', rec_id).execute()
            updated += 1

    return inserted, updated

def save_to_charges(df: pd.DataFrame):
    if df.empty:
        return 0, 0
        
    client = init_connection()
    select_cols = ['id', 'Date', 'Charge']
    
    all_existing_data = []
    limit = 1000
    offset = 0
    while True:
        response = client.table("Charges").select(",".join(select_cols)).range(offset, offset + limit - 1).execute()
        data = response.data
        if data:
            all_existing_data.extend(data)
            offset += limit
            if len(data) < limit:
                break
        else:
            break

    existing_map = {}
    if all_existing_data:
        for row in all_existing_data:
            dt_str = ''
            if pd.notna(row.get('Date')):
                dt_str = pd.to_datetime(row.get('Date')).strftime('%Y-%m-%d')
            existing_map[dt_str] = row

    records_to_insert = []
    records_to_update = []

    for idx, row in df.iterrows():
        if pd.isna(row.get('Date')): continue
        dt_str = pd.to_datetime(row.get('Date')).strftime('%Y-%m-%d')
        chg = round(float(row.get('Charge', 0) or 0), 4)

        rec_dict = {
            'Date': dt_str,
            'Charge': chg
        }
        rec_dict = _clean_record_dict(rec_dict)

        if dt_str not in existing_map:
            records_to_insert.append(rec_dict)
        else:
            ex_row = existing_map[dt_str]
            ex_chg = round(float(ex_row.get('Charge', 0) or 0), 4)
            if abs(chg - ex_chg) > 1e-4:
                record_id = ex_row['id']
                records_to_update.append((record_id, rec_dict))

    inserted = 0
    updated = 0

    if records_to_insert:
        chunk_size = 500
        for i in range(0, len(records_to_insert), chunk_size):
            chunk = records_to_insert[i:i+chunk_size]
            client.table("Charges").insert(chunk).execute()
            inserted += len(chunk)

    if records_to_update:
        for rec_id, update_dict in records_to_update:
            client.table("Charges").update(update_dict).eq('id', rec_id).execute()
            updated += 1

    return inserted, updated


