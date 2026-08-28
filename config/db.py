from supabase import create_client, Client
import streamlit as st
import pandas as pd
import numpy as np

@st.cache_resource
def _get_client(url: str, key: str) -> Client:
    return create_client(url, key)

def init_connection() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return _get_client(url, key)

def _clean_record_dict(rec_dict):
    """Clean dictionary for JSON serialization so no NaN or nan strings exist."""
    cleaned = {}
    for k, v in rec_dict.items():
        if pd.isna(v) or str(v).strip() in ['nan', 'NaN', 'None', '<NA>']:
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned

def make_key(segment, symbol, strike, entered, exited):
    seg_str = str(segment).strip() if pd.notna(segment) and str(segment).strip() not in ['None', 'nan', 'NaN', '<NA>', ''] else ''
    sym_str = str(symbol).strip().upper() if pd.notna(symbol) and str(symbol).strip().upper() not in ['NONE', 'NAN', ''] else ''
    strk_str = str(strike).strip().upper() if pd.notna(strike) and str(strike).strip().upper() not in ['NONE', 'NAN', ''] else ''
    
    ent_str = ''
    if pd.notna(entered) and str(entered).strip() not in ['None', 'nan', 'NaN', 'NaT', '<NA>', '']:
        try:
            ent_str = pd.to_datetime(entered).strftime('%Y-%m-%d')
        except Exception:
            ent_str = str(entered).strip()
            
    ext_str = ''
    if pd.notna(exited) and str(exited).strip() not in ['None', 'nan', 'NaN', 'NaT', '<NA>', '']:
        try:
            ext_str = pd.to_datetime(exited).strftime('%Y-%m-%d')
        except Exception:
            ext_str = str(exited).strip()
            
    return f"{seg_str}|{sym_str}|{strk_str}|{ent_str}|{ext_str}"

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

    # Group existing DB data by composite key to handle duplicates
    existing_key_map = {}
    duplicate_ids_to_delete = []

    if all_existing_data:
        for row in all_existing_data:
            k = make_key(row.get('Segment'), row.get('Symbol'), row.get('StrikePrice'), row.get('EnteredDate'), row.get('ExitedDate'))
            if k not in existing_key_map:
                existing_key_map[k] = row
            else:
                # Mark excess duplicate row for cleanup
                duplicate_ids_to_delete.append(row['id'])

    # Clean up duplicate rows in Supabase if any exist
    if duplicate_ids_to_delete:
        chunk_size = 500
        for i in range(0, len(duplicate_ids_to_delete), chunk_size):
            chunk = duplicate_ids_to_delete[i:i+chunk_size]
            client.table("TradeMaster").delete().in_('id', chunk).execute()

    records_to_insert = []
    records_to_update = []

    for idx, row in df.iterrows():
        k = make_key(row.get('Segment'), row.get('Symbol'), row.get('StrikePrice'), row.get('EnteredDate'), row.get('ExitedDate'))
        
        qty = round(float(row.get('Qty', 0) or 0), 4)
        buy_rate = round(float(row.get('BuyRate', 0) or 0), 4)
        sell_rate = round(float(row.get('SellRate', 0) or 0), 4)
        
        entered_raw = row.get('EnteredDate')
        exited_raw = row.get('ExitedDate')

        entered_date = None
        if pd.notna(entered_raw) and str(entered_raw).strip() not in ['None', 'nan', 'NaN', 'NaT', '']:
            try:
                entered_date = pd.to_datetime(entered_raw).strftime('%Y-%m-%d')
            except Exception:
                entered_date = str(entered_raw).strip()

        exited_date = None
        if pd.notna(exited_raw) and str(exited_raw).strip() not in ['None', 'nan', 'NaN', 'NaT', '']:
            try:
                exited_date = pd.to_datetime(exited_raw).strftime('%Y-%m-%d')
            except Exception:
                exited_date = str(exited_raw).strip()
        
        symbol = str(row.get('Symbol')).strip().upper() if pd.notna(row.get('Symbol')) and str(row.get('Symbol')).strip().upper() not in ['NONE', 'NAN', ''] else None
        strike = str(row.get('StrikePrice')).strip().upper() if pd.notna(row.get('StrikePrice')) and str(row.get('StrikePrice')).strip().upper() not in ['NONE', 'NAN', ''] else None
        segment = str(row.get('Segment')).strip() if pd.notna(row.get('Segment')) and str(row.get('Segment')).strip() not in ['NONE', 'NAN', ''] else None

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

        if k not in existing_key_map:
            records_to_insert.append(rec_dict)
            # Add to local map so subsequent identical rows in the same batch don't double insert
            existing_key_map[k] = rec_dict
        else:
            existing_row = existing_key_map[k]
            if 'id' in existing_row:
                ex_qty = round(float(existing_row.get('Qty', 0) or 0), 4)
                ex_buy = round(float(existing_row.get('BuyRate', 0) or 0), 4)
                ex_sell = round(float(existing_row.get('SellRate', 0) or 0), 4)
                
                if abs(qty - ex_qty) > 1e-4 or abs(buy_rate - ex_buy) > 1e-4 or abs(sell_rate - ex_sell) > 1e-4:
                    record_id = existing_row['id']
                    records_to_update.append((record_id, rec_dict))

    inserted = 0
    updated = 0

    # Bulk insert chunks of 500
    if records_to_insert:
        chunk_size = 500
        for i in range(0, len(records_to_insert), chunk_size):
            chunk = records_to_insert[i:i+chunk_size]
            client.table("TradeMaster").insert(chunk).execute()
            inserted += len(chunk)

    # Update modified records
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

    # Group existing DB data by date string to handle duplicate date rows
    existing_date_map = {}
    duplicate_ids_to_delete = []

    if all_existing_data:
        for row in all_existing_data:
            dt_str = ''
            raw_dt = row.get('Date')
            if pd.notna(raw_dt) and str(raw_dt).strip() not in ['None', 'nan', 'NaN', 'NaT', '']:
                try:
                    dt_str = pd.to_datetime(raw_dt).strftime('%Y-%m-%d')
                except Exception:
                    dt_str = str(raw_dt).strip()
            if dt_str:
                if dt_str not in existing_date_map:
                    existing_date_map[dt_str] = row
                else:
                    duplicate_ids_to_delete.append(row['id'])

    # Delete duplicate date rows in DB
    if duplicate_ids_to_delete:
        chunk_size = 500
        for i in range(0, len(duplicate_ids_to_delete), chunk_size):
            chunk = duplicate_ids_to_delete[i:i+chunk_size]
            client.table("Charges").delete().in_('id', chunk).execute()

    records_to_insert = []
    records_to_update = []

    for idx, row in df.iterrows():
        raw_dt = row.get('Date')
        if pd.isna(raw_dt) or str(raw_dt).strip() in ['None', 'nan', 'NaN', 'NaT', '']:
            continue
        try:
            dt_str = pd.to_datetime(raw_dt).strftime('%Y-%m-%d')
        except Exception:
            dt_str = str(raw_dt).strip()
            
        if not dt_str:
            continue

        chg = round(float(row.get('Charge', 0) or 0), 4)

        rec_dict = {
            'Date': dt_str,
            'Charge': chg
        }
        rec_dict = _clean_record_dict(rec_dict)

        if dt_str not in existing_date_map:
            records_to_insert.append(rec_dict)
            existing_date_map[dt_str] = rec_dict
        else:
            ex_row = existing_date_map[dt_str]
            if 'id' in ex_row:
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
