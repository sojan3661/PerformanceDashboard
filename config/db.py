from supabase import create_client, Client
import streamlit as st
import pandas as pd
import numpy as np
import re


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

def save_to_fyers_trade_data(df: pd.DataFrame):
    """
    Saves or upserts Fyers tradebook DataFrame into Supabase 'FyersTradeData' table.
    Primary Key: 'orderID' (mapped from OMS order ID).
    """
    if df.empty:
        return 0, 0
        
    client = init_connection()
    records_map = {}

    for idx, row in df.iterrows():
        # Parse orderID
        raw_order_id = row.get('orderID')
        order_id = None
        if pd.notna(raw_order_id) and str(raw_order_id).strip() not in ['None', 'nan', 'NaN', '']:
            try:
                order_id = int(float(str(raw_order_id).strip()))
            except Exception:
                order_id = None

        if order_id is None:
            continue
            
        raw_dt = row.get('DateTime')
        dt_str = None
        if pd.notna(raw_dt) and str(raw_dt).strip() not in ['None', 'nan', 'NaN', 'NaT', '']:
            try:
                dt_str = pd.to_datetime(raw_dt).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                dt_str = str(raw_dt).strip()

        qty = float(row.get('Qty', 0) or 0) if (pd.notna(row.get('Qty')) and str(row.get('Qty')).strip() not in ['None', 'nan', 'NaN', '']) else None
        traded_price = float(row.get('Traded price', 0) or 0) if (pd.notna(row.get('Traded price')) and str(row.get('Traded price')).strip() not in ['None', 'nan', 'NaN', '']) else None

        name = str(row.get('Name')).strip() if pd.notna(row.get('Name')) and str(row.get('Name')).strip() not in ['None', 'nan', 'NaN', ''] else None
        side = str(row.get('Side')).strip() if pd.notna(row.get('Side')) and str(row.get('Side')).strip() not in ['None', 'nan', 'NaN', ''] else None
        prod_type = str(row.get('Product type')).strip() if pd.notna(row.get('Product type')) and str(row.get('Product type')).strip() not in ['None', 'nan', 'NaN', ''] else None
        segment = str(row.get('Segment')).strip() if pd.notna(row.get('Segment')) and str(row.get('Segment')).strip() not in ['None', 'nan', 'NaN', ''] else None

        rec_dict = {
            'orderID': order_id,
            'DateTime': dt_str,
            'Name': name,
            'Side': side,
            'Product type': prod_type,
            'Qty': qty,
            'Traded price': traded_price,
            'Segment': segment
        }
        rec_dict = _clean_record_dict(rec_dict)
        # Deduplicate within batch by setting key
        records_map[order_id] = rec_dict

    records_to_upsert = list(records_map.values())

    if not records_to_upsert:
        return 0, 0

    chunk_size = 500
    upserted = 0
    for i in range(0, len(records_to_upsert), chunk_size):
        chunk = records_to_upsert[i:i+chunk_size]
        client.table("FyersTradeData").upsert(chunk, on_conflict="orderID").execute()
        upserted += len(chunk)

    return upserted, 0

def fetch_fyers_trade_data() -> pd.DataFrame:
    """
    Fetches all records from 'FyersTradeData' table in Supabase.
    """
    client = init_connection()
    all_data = []
    limit = 1000
    offset = 0
    while True:
        try:
            response = client.table("FyersTradeData").select("*").range(offset, offset + limit - 1).execute()
            data = response.data
            if data:
                all_data.extend(data)
                offset += limit
                if len(data) < limit:
                    break
            else:
                break
        except Exception as e:
            st.error(f"Error fetching from FyersTradeData: {e}")
            break
            
    if all_data:
        df = pd.DataFrame(all_data)
        if 'DateTime' in df.columns:
            df['DateTime'] = pd.to_datetime(df['DateTime'], errors='coerce')
        return df
    else:
        return pd.DataFrame()

def fetch_fyers_segments() -> list:
    """
    Fetches distinct non-null segments existing in 'FyersTradeData' table in Supabase.
    """
    client = init_connection()
    try:
        response = client.table("FyersTradeData").select("Segment").execute()
        data = response.data
        if data:
            segments = sorted(list(set(
                str(row['Segment']).strip() 
                for row in data 
                if row.get('Segment') and str(row.get('Segment')).strip() not in ['None', 'nan', 'NaN', '']
            )))
            return segments
    except Exception as e:
        print(f"Error fetching segments from FyersTradeData: {e}")
    return []

def extract_expiry_date_from_symbol(symbol: str, date_format='%d/%m/%y'):
    """
    Extracts expiry date from Fyers symbol string.
    Rule:
    - Finds first sequence of digits right after symbol string prefix.
    - First 2 characters = Year (e.g. '26' -> 2026)
    - Next 1 or 2 characters = Month (1..9 for Jan-Sept, 10..12 for Oct-Dec)
    - Next 2 characters = Day (01..31)
    """
    if not symbol or pd.isna(symbol):
        return None
        
    symbol_str = str(symbol).strip().upper()
    match = re.search(r'[A-Z]+(\d+)', symbol_str)
    if not match:
        return None
        
    digits_str = match.group(1)
    if len(digits_str) < 4:
        return None
        
    yy_str = digits_str[0:2]
    try:
        year = 2000 + int(yy_str)
    except ValueError:
        return None
        
    rem = digits_str[2:]
    month = None
    day = None
    
    # Try 2-digit month (10, 11, 12) first if applicable
    if len(rem) >= 4 and rem[0:2] in ['10', '11', '12']:
        possible_day = int(rem[2:4])
        if 1 <= possible_day <= 31:
            month = int(rem[0:2])
            day = possible_day
            
    # Fallback to 1-digit month (1..9)
    if month is None and len(rem) >= 3:
        possible_month = int(rem[0:1])
        possible_day = int(rem[1:3])
        if 1 <= possible_month <= 9 and 1 <= possible_day <= 31:
            month = possible_month
            day = possible_day

    if month and day:
        try:
            exp_ts = pd.Timestamp(year=year, month=month, day=day)
            if date_format:
                return exp_ts.strftime(date_format)
            return exp_ts.strftime('%Y-%m-%d')
        except Exception:
            return None
            
    return None

def transform_fyers_data_by_segment(segment: str, start_date=None, end_date=None):
    """
    Transforms raw FyersTradeData execution records for a selected segment into
    matched trade records using FIFO matching algorithm, with optional date filtering
    on Buy Date or Sell Date.
    
    Target DataFrame Columns:
    - Symbol
    - P&L Amt (₹)
    - Txn Type
    - Segment
    - Qty
    - Buy Date
    - Buy Rate (₹)
    - Buy Value (₹)
    - Sell Date
    - Sell Rate (₹)
    - Sell Value (₹)
    """
    client = init_connection()
    try:
        all_data = []
        limit = 1000
        offset = 0
        while True:
            response = client.table("FyersTradeData").select("*").eq("Segment", segment).range(offset, offset + limit - 1).execute()
            data = response.data
            if data:
                all_data.extend(data)
                offset += limit
                if len(data) < limit:
                    break
            else:
                break
                
        if not all_data:
            return False, f"No trade records found in database for segment '{segment}'.", pd.DataFrame()

        df = pd.DataFrame(all_data)
        
        # Ensure DateTime sorting
        if 'DateTime' in df.columns:
            df['DateTime_dt'] = pd.to_datetime(df['DateTime'], errors='coerce')
            df = df.sort_values(by=['DateTime_dt', 'orderID'], ascending=True)

        matched_trades = []

        # Group executions by Symbol / Name
        for symbol, group in df.groupby('Name', sort=False):
            buy_queue = []
            sell_queue = []

            sym_upper = str(symbol).strip().upper() if pd.notna(symbol) else ''
            txn_type = 'Option' if ('CE' in sym_upper or 'PE' in sym_upper) else 'Future'

            for _, row in group.iterrows():
                side = str(row.get('Side', '')).strip().upper()
                qty = float(row.get('Qty', 0) or 0)
                price = float(row.get('Traded price', 0) or 0)
                dt = row.get('DateTime_dt')
                dt_str = dt.strftime('%Y-%m-%d') if pd.notna(dt) else None

                if qty <= 0:
                    continue

                if side == 'BUY':
                    while qty > 0 and sell_queue:
                        sell_item = sell_queue[0]
                        match_qty = min(qty, sell_item['qty'])
                        
                        b_date = dt_str
                        s_date = sell_item['date']
                        b_rate = price
                        s_rate = sell_item['price']
                        b_val = round(match_qty * b_rate, 2)
                        s_val = round(match_qty * s_rate, 2)
                        pnl = round(s_val - b_val, 2)

                        matched_trades.append({
                            'Symbol': symbol,
                            'P&L Amt (₹)': pnl,
                            'Txn Type': txn_type,
                            'Segment': segment,
                            'Qty': match_qty,
                            'Buy Date': b_date,
                            'Buy Rate (₹)': b_rate,
                            'Buy Value (₹)': b_val,
                            'Sell Date': s_date,
                            'Sell Rate (₹)': s_rate,
                            'Sell Value (₹)': s_val
                        })

                        qty -= match_qty
                        sell_item['qty'] -= match_qty
                        if sell_item['qty'] <= 1e-6:
                            sell_queue.pop(0)

                    if qty > 1e-6:
                        buy_queue.append({'date': dt_str, 'qty': qty, 'price': price})

                elif side == 'SELL':
                    while qty > 0 and buy_queue:
                        buy_item = buy_queue[0]
                        match_qty = min(qty, buy_item['qty'])

                        b_date = buy_item['date']
                        s_date = dt_str
                        b_rate = buy_item['price']
                        s_rate = price
                        b_val = round(match_qty * b_rate, 2)
                        s_val = round(match_qty * s_rate, 2)
                        pnl = round(s_val - b_val, 2)

                        matched_trades.append({
                            'Symbol': symbol,
                            'P&L Amt (₹)': pnl,
                            'Txn Type': txn_type,
                            'Segment': segment,
                            'Qty': match_qty,
                            'Buy Date': b_date,
                            'Buy Rate (₹)': b_rate,
                            'Buy Value (₹)': b_val,
                            'Sell Date': s_date,
                            'Sell Rate (₹)': s_rate,
                            'Sell Value (₹)': s_val
                        })

                        qty -= match_qty
                        buy_item['qty'] -= match_qty
                        if buy_item['qty'] <= 1e-6:
                            buy_queue.pop(0)

                    if qty > 1e-6:
                        sell_queue.append({'date': dt_str, 'qty': qty, 'price': price})

            # Unmatched Buy positions
            for b in buy_queue:
                b_val = round(b['qty'] * b['price'], 2)
                matched_trades.append({
                    'Symbol': symbol,
                    'P&L Amt (₹)': 0.0,
                    'Txn Type': txn_type,
                    'Segment': segment,
                    'Qty': b['qty'],
                    'Buy Date': b['date'],
                    'Buy Rate (₹)': b['price'],
                    'Buy Value (₹)': b_val,
                    'Sell Date': None,
                    'Sell Rate (₹)': 0.0,
                    'Sell Value (₹)': 0.0
                })

            # Unmatched Sell positions
            for s in sell_queue:
                s_val = round(s['qty'] * s['price'], 2)
                matched_trades.append({
                    'Symbol': symbol,
                    'P&L Amt (₹)': 0.0,
                    'Txn Type': txn_type,
                    'Segment': segment,
                    'Qty': s['qty'],
                    'Buy Date': None,
                    'Buy Rate (₹)': 0.0,
                    'Buy Value (₹)': 0.0,
                    'Sell Date': s['date'],
                    'Sell Rate (₹)': s['price'],
                    'Sell Value (₹)': s_val
                })


        res_df = pd.DataFrame(matched_trades)
        expected_cols = [
            'Symbol', 'P&L Amt (₹)', 'Txn Type', 'Segment', 'Qty',
            'Buy Date', 'Buy Rate (₹)', 'Buy Value (₹)',
            'Sell Date', 'Sell Rate (₹)', 'Sell Value (₹)'
        ]
        if res_df.empty:
            res_df = pd.DataFrame(columns=expected_cols)
        else:
            res_df = res_df[expected_cols]

        # Format dates nicely to DD/MM/YY format
        for col in ['Buy Date', 'Sell Date']:
            if col in res_df.columns:
                res_df[col] = res_df[col].apply(
                    lambda x: pd.to_datetime(x, errors='coerce').strftime('%d/%m/%y')
                    if pd.notna(x) and str(x).strip() not in ['None', 'nan', 'NaN', 'NaT', '']
                    else x
                )

        # Collect all valid trade dates in the dataset to check for future dates
        all_dates = []
        for idx, row in res_df.iterrows():
            b_dt = pd.to_datetime(row['Buy Date'], format='%d/%m/%y', errors='coerce') if pd.notna(row['Buy Date']) else None
            s_dt = pd.to_datetime(row['Sell Date'], format='%d/%m/%y', errors='coerce') if pd.notna(row['Sell Date']) else None
            if pd.notna(b_dt):
                all_dates.append(b_dt.date())
            if pd.notna(s_dt):
                all_dates.append(s_dt.date())

        # Fill missing Sell Date or Buy Date with Expiry Date if future dates exist in dataset
        for idx, row in res_df.iterrows():
            b_val = row['Buy Date']
            s_val = row['Sell Date']
            
            b_dt = pd.to_datetime(b_val, format='%d/%m/%y', errors='coerce').date() if pd.notna(b_val) and str(b_val).strip() not in ['None', 'nan', 'NaN', ''] else None
            s_dt = pd.to_datetime(s_val, format='%d/%m/%y', errors='coerce').date() if pd.notna(s_val) and str(s_val).strip() not in ['None', 'nan', 'NaN', ''] else None

            # If Sell Date is missing
            if s_dt is None and b_dt is not None:
                has_future = any(d > b_dt for d in all_dates)
                if has_future:
                    exp_date_str = extract_expiry_date_from_symbol(row['Symbol'], date_format='%d/%m/%y')
                    if exp_date_str:
                        res_df.at[idx, 'Sell Date'] = exp_date_str
                        res_df.at[idx, 'Sell Rate (₹)'] = 0.0
                        res_df.at[idx, 'Sell Value (₹)'] = 0.0
                        b_val = float(row.get('Buy Value (₹)', 0) or 0)
                        res_df.at[idx, 'P&L Amt (₹)'] = round(0.0 - b_val, 2)

            # If Buy Date is missing
            elif b_dt is None and s_dt is not None:
                has_future = any(d > s_dt for d in all_dates)
                if has_future:
                    exp_date_str = extract_expiry_date_from_symbol(row['Symbol'], date_format='%d/%m/%y')
                    if exp_date_str:
                        res_df.at[idx, 'Buy Date'] = exp_date_str
                        res_df.at[idx, 'Buy Rate (₹)'] = 0.0
                        res_df.at[idx, 'Buy Value (₹)'] = 0.0
                        s_val = float(row.get('Sell Value (₹)', 0) or 0)
                        res_df.at[idx, 'P&L Amt (₹)'] = round(s_val - 0.0, 2)

        # Exclude records where either Buy Date or Sell Date is empty
        if not res_df.empty:
            def is_complete(row):
                b_valid = pd.notna(row.get('Buy Date')) and str(row.get('Buy Date')).strip() not in ['None', 'nan', 'NaN', 'NaT', '']
                s_valid = pd.notna(row.get('Sell Date')) and str(row.get('Sell Date')).strip() not in ['None', 'nan', 'NaN', 'NaT', '']
                return b_valid and s_valid

            res_df = res_df[res_df.apply(is_complete, axis=1)].reset_index(drop=True)



        # Apply date filter on Buy Date OR Sell Date
        if not res_df.empty and (start_date is not None or end_date is not None):
            s_dt = pd.to_datetime(start_date).date() if pd.notna(start_date) else None
            e_dt = pd.to_datetime(end_date).date() if pd.notna(end_date) else None

            def is_in_range(row):
                b_dt = pd.to_datetime(row['Buy Date'], format='%d/%m/%y', errors='coerce').date() if pd.notna(row.get('Buy Date')) else None
                s_dt_val = pd.to_datetime(row['Sell Date'], format='%d/%m/%y', errors='coerce').date() if pd.notna(row.get('Sell Date')) else None

                b_match = (b_dt is not None) and ((s_dt is None or b_dt >= s_dt) and (e_dt is None or b_dt <= e_dt))
                s_match = (s_dt_val is not None) and ((s_dt is None or s_dt_val >= s_dt) and (e_dt is None or s_dt_val <= e_dt))

                return b_match or s_match

            res_df = res_df[res_df.apply(is_in_range, axis=1)].reset_index(drop=True)

        return True, f"Successfully transformed {len(res_df):,} record(s) for segment '{segment}'.", res_df

    except Exception as e:
        return False, f"Transformation error: {e}", pd.DataFrame()


def parse_fyers_symbol_for_trademaster(symbol_str: str):
    """
    Parses a raw Fyers symbol string into (base_symbol, strike_price).
    Examples:
    - 'NIFTY2690124150CE' -> ('NIFTY', '24150 CE')
    - 'NIFTY 22600 CE' -> ('NIFTY', '22600 CE')
    - 'NIFTY 29MAY25 22600 CE' -> ('NIFTY', '22600 CE')
    - 'RELIANCE' -> ('RELIANCE', None)
    """
    if not symbol_str or pd.isna(symbol_str):
        return None, None
        
    raw = str(symbol_str).strip().upper()
    
    # 1. Space-separated format
    parts = raw.split()
    if len(parts) >= 4:
        return parts[0], " ".join(parts[2:])
    elif len(parts) == 3:
        return parts[0], " ".join(parts[1:])
    elif len(parts) == 2:
        return parts[0], parts[1]
        
    # 2. Compressed format e.g. NIFTY2690124150CE or SENSEX2690377700CE
    m = re.match(r'^([A-Z]+)(\d+)(CE|PE)$', raw)
    if m:
        base_sym = m.group(1)
        digits_part = m.group(2)
        opt_type = m.group(3)
        
        rem = digits_part[2:]
        strike_digits = ""
        
        if len(rem) >= 4 and rem[0:2] in ['10', '11', '12']:
            possible_day = int(rem[2:4])
            if 1 <= possible_day <= 31:
                strike_digits = rem[4:]
                
        if not strike_digits and len(rem) >= 3:
            possible_month = int(rem[0:1])
            possible_day = int(rem[1:3])
            if 1 <= possible_month <= 9 and 1 <= possible_day <= 31:
                strike_digits = rem[3:]
                
        if strike_digits:
            return base_sym, f"{strike_digits} {opt_type}"
        return base_sym, f"{rem} {opt_type}"

    # Plain symbol e.g. RELIANCE
    return raw, None


def prepare_and_insert_migrated_fyers_data(transformed_df: pd.DataFrame):
    """
    Treats transformed DataFrame as source input for Fyers sheet,
    prepares data in TradeMaster format, deduplicates/groups records,
    and inserts them into the TradeMaster database table.
    """
    if transformed_df is None or transformed_df.empty:
        return False, "No data available to migrate."
        
    records = []
    for idx, row in transformed_df.iterrows():
        raw_sym = row.get('Symbol')
        base_sym, strike_price = parse_fyers_symbol_for_trademaster(raw_sym)
        
        # Segment mapping
        raw_seg = str(row.get('Segment', '')).strip()
        seg_lower = raw_seg.lower()
        if seg_lower in ['equity', 'mutual fund', 'equity & mutual fund', 'nse-cash', 'bse-cash']:
            segment = 'Equity & Mutual Fund'
        elif 'commodi' in seg_lower:
            segment = 'Commodity'
        elif seg_lower in ['options', 'fno', 'nse-fno', 'bse-fno', 'derivatives']:
            segment = 'Options'
        elif raw_seg:
            segment = raw_seg
        else:
            segment = 'Equity & Mutual Fund'

        # Dates
        b_dt_str = row.get('Buy Date')
        s_dt_str = row.get('Sell Date')
        
        b_dt = pd.to_datetime(b_dt_str, format='%d/%m/%y', errors='coerce') if pd.notna(b_dt_str) else None
        s_dt = pd.to_datetime(s_dt_str, format='%d/%m/%y', errors='coerce') if pd.notna(s_dt_str) else None
        
        if pd.isna(b_dt) and pd.notna(b_dt_str):
            b_dt = pd.to_datetime(b_dt_str, errors='coerce')
        if pd.isna(s_dt) and pd.notna(s_dt_str):
            s_dt = pd.to_datetime(s_dt_str, errors='coerce')
            
        entered_date = None
        exited_date = None
        
        if pd.notna(b_dt) and pd.notna(s_dt):
            entered_date = min(b_dt, s_dt).strftime('%Y-%m-%d')
            exited_date = max(b_dt, s_dt).strftime('%Y-%m-%d')
        elif pd.notna(b_dt):
            entered_date = b_dt.strftime('%Y-%m-%d')
            exited_date = b_dt.strftime('%Y-%m-%d')
        elif pd.notna(s_dt):
            entered_date = s_dt.strftime('%Y-%m-%d')
            exited_date = s_dt.strftime('%Y-%m-%d')

        qty = float(row.get('Qty', 0) or 0)
        buy_rate = float(row.get('Buy Rate (₹)', 0) or 0)
        sell_rate = float(row.get('Sell Rate (₹)', 0) or 0)

        records.append({
            'Segment': segment,
            'Symbol': base_sym,
            'StrikePrice': strike_price,
            'Qty': qty,
            'BuyRate': buy_rate,
            'EnteredDate': entered_date,
            'SellRate': sell_rate,
            'ExitedDate': exited_date
        })

    tm_df = pd.DataFrame(records)
    if tm_df.empty:
        return False, "Failed to prepare TradeMaster records."

    # Grouping & weighted average aggregation (matching build_trademaster logic)
    expected_cols = ['Segment', 'Symbol', 'StrikePrice', 'Qty', 'BuyRate', 'EnteredDate', 'SellRate', 'ExitedDate']
    for col in expected_cols:
        if col not in tm_df.columns:
            tm_df[col] = None

    tm_df['Qty'] = pd.to_numeric(tm_df['Qty'], errors='coerce').fillna(0)
    tm_df['BuyRate'] = pd.to_numeric(tm_df['BuyRate'], errors='coerce').fillna(0)
    tm_df['SellRate'] = pd.to_numeric(tm_df['SellRate'], errors='coerce').fillna(0)

    tm_df['TotalBuy'] = tm_df['Qty'] * tm_df['BuyRate']
    tm_df['TotalSell'] = tm_df['Qty'] * tm_df['SellRate']

    groupby_cols = ['Segment', 'Symbol', 'StrikePrice', 'EnteredDate', 'ExitedDate']
    tm_df[groupby_cols] = tm_df[groupby_cols].fillna('__MISSING__')

    tm_df = tm_df.groupby(groupby_cols, as_index=False).agg({
        'Qty': 'sum',
        'TotalBuy': 'sum',
        'TotalSell': 'sum'
    })

    tm_df['BuyRate'] = np.where(tm_df['Qty'] > 0, tm_df['TotalBuy'] / tm_df['Qty'], 0)
    tm_df['SellRate'] = np.where(tm_df['Qty'] > 0, tm_df['TotalSell'] / tm_df['Qty'], 0)
    tm_df[groupby_cols] = tm_df[groupby_cols].replace('__MISSING__', None)

    tm_df = tm_df[expected_cols]

    # Save to TradeMaster
    inserted_count, updated_count = save_to_trademaster(tm_df)
    
    # Clear Performance dashboard cache
    try:
        from DataProcessing import get_processed_data
        get_processed_data.clear()
    except Exception as e:
        print(f"Error clearing get_processed_data cache: {e}")

    msg_parts = []
    if inserted_count > 0:
        msg_parts.append(f"inserted {inserted_count:,} new trade(s)")
    if updated_count > 0:
        msg_parts.append(f"updated {updated_count:,} existing trade(s)")
        
    if msg_parts:
        return True, f"Successfully {' and '.join(msg_parts)} into TradeMaster database!"
    else:
        return True, "All trades were already present in TradeMaster database (0 new records added)."






