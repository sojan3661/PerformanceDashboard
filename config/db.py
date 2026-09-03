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

def make_full_trade_key(symbol, segment, strike_price, qty, buy_rate, sell_rate, entered_date, exited_date):
    sym_str = str(symbol).strip().upper() if pd.notna(symbol) and str(symbol).strip().upper() not in ['NONE', 'NAN', ''] else ''
    seg_str = str(segment).strip() if pd.notna(segment) and str(segment).strip() not in ['NONE', 'NAN', ''] else ''
    strk_str = str(strike_price).strip().upper() if pd.notna(strike_price) and str(strike_price).strip().upper() not in ['NONE', 'NAN', ''] else ''
    
    qty_val = round(float(qty), 4) if (pd.notna(qty) and str(qty).strip() not in ['None', 'nan', 'NaN', '']) else 0.0
    buy_val = round(float(buy_rate), 4) if (pd.notna(buy_rate) and str(buy_rate).strip() not in ['None', 'nan', 'NaN', '']) else 0.0
    sell_val = round(float(sell_rate), 4) if (pd.notna(sell_rate) and str(sell_rate).strip() not in ['None', 'nan', 'NaN', '']) else 0.0
    
    qty_str = f"{qty_val:.4f}"
    buy_str = f"{buy_val:.4f}"
    sell_str = f"{sell_val:.4f}"
    
    ent_str = ''
    if pd.notna(entered_date) and str(entered_date).strip() not in ['None', 'nan', 'NaN', 'NaT', '<NA>', '']:
        try:
            ent_str = pd.to_datetime(entered_date).strftime('%Y-%m-%d')
        except Exception:
            ent_str = str(entered_date).strip()
            
    ext_str = ''
    if pd.notna(exited_date) and str(exited_date).strip() not in ['None', 'nan', 'NaN', 'NaT', '<NA>', '']:
        try:
            ext_str = pd.to_datetime(exited_date).strftime('%Y-%m-%d')
        except Exception:
            ext_str = str(exited_date).strip()
            
    return f"{sym_str}-{seg_str}-{strk_str}-{qty_str}-{buy_str}-{sell_str}-{ent_str}-{ext_str}"

def save_to_trademaster(df: pd.DataFrame):
    if df.empty:
        return 0, 0
        
    client = init_connection()
    select_cols = ['id', 'Symbol', 'Segment', 'StrikePrice', 'Qty', 'BuyRate', 'SellRate', 'EnteredDate', 'ExitedDate']
    
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

    # Build composite key set for all existing records fetched from TradeMaster database table
    existing_db_keys = set()
    if all_existing_data:
        for row in all_existing_data:
            k = make_full_trade_key(
                row.get('Symbol'),
                row.get('Segment'),
                row.get('StrikePrice'),
                row.get('Qty'),
                row.get('BuyRate'),
                row.get('SellRate'),
                row.get('EnteredDate'),
                row.get('ExitedDate')
            )
            existing_db_keys.add(k)

    records_to_insert = []
    seen_in_batch = set()

    for idx, row in df.iterrows():
        k = make_full_trade_key(
            row.get('Symbol'),
            row.get('Segment'),
            row.get('StrikePrice'),
            row.get('Qty'),
            row.get('BuyRate'),
            row.get('SellRate'),
            row.get('EnteredDate'),
            row.get('ExitedDate')
        )
        
        # Insert only keys which are not matching database keys (and not duplicate within current upload batch)
        if k not in existing_db_keys and k not in seen_in_batch:
            seen_in_batch.add(k)
            
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
                'Symbol': symbol,
                'Segment': segment,
                'StrikePrice': strike,
                'Qty': qty,
                'BuyRate': buy_rate,
                'SellRate': sell_rate,
                'EnteredDate': entered_date,
                'ExitedDate': exited_date
            }
            rec_dict = _clean_record_dict(rec_dict)
            records_to_insert.append(rec_dict)

    inserted = 0

    # Bulk insert chunks of 500
    if records_to_insert:
        chunk_size = 500
        for i in range(0, len(records_to_insert), chunk_size):
            chunk = records_to_insert[i:i+chunk_size]
            client.table("TradeMaster").insert(chunk).execute()
            inserted += len(chunk)

    return inserted, 0

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
