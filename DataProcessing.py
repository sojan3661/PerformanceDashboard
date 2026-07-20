import pandas as pd
import streamlit as st
from config.db import init_connection

def _fetch_all_from_table(table_name: str) -> pd.DataFrame:
    client = init_connection()
    all_data = []
    limit = 1000
    offset = 0
    while True:
        try:
            response = client.table(table_name).select("*").range(offset, offset + limit - 1).execute()
            data = response.data
            if data:
                all_data.extend(data)
                offset += limit
                if len(data) < limit:
                    break
            else:
                break
        except Exception as e:
            st.error(f"Error fetching from {table_name}: {e}")
            break
            
    if all_data:
        return pd.DataFrame(all_data)
    else:
        return pd.DataFrame()

@st.cache_data
def get_processed_data():
    """
    Fetches all data from database, enriches it, and caches the result for the session.
    """
    def get_fy(date):
        if pd.isna(date): return None
        # April 1 to March 31
        y = date.year
        return f"{y}-{y+1}" if date.month >= 4 else f"{y-1}-{y}"
        
    def get_quarter(date):
        if pd.isna(date): return None
        m = date.month
        if m in [4, 5, 6]: return "Q1"
        elif m in [7, 8, 9]: return "Q2"
        elif m in [10, 11, 12]: return "Q3"
        elif m in [1, 2, 3]: return "Q4"
        return None
        
    def get_month(date):
        if pd.isna(date): return None
        return date.strftime('%B')

    trade_df = _fetch_all_from_table("TradeMaster")
    charges_df = _fetch_all_from_table("Charges")
    
    # Process TradeMaster
    if not trade_df.empty:
        # Pre-process dates explicitly
        if 'EnteredDate' in trade_df.columns:
            trade_df['EnteredDate'] = pd.to_datetime(trade_df['EnteredDate']).dt.date
        if 'ExitedDate' in trade_df.columns:
            trade_df['ExitedDate'] = pd.to_datetime(trade_df['ExitedDate']).dt.date
            
        trade_df['Qty'] = pd.to_numeric(trade_df.get('Qty', 0), errors='coerce').fillna(0)
        trade_df['BuyRate'] = pd.to_numeric(trade_df.get('BuyRate', 0), errors='coerce').fillna(0)
        trade_df['SellRate'] = pd.to_numeric(trade_df.get('SellRate', 0), errors='coerce').fillna(0)
        
        trade_df['Buy Value'] = trade_df['Qty'] * trade_df['BuyRate']
        trade_df['Sell Value'] = trade_df['Qty'] * trade_df['SellRate']
    else:
        # Create empty with expected columns
        trade_df = pd.DataFrame(columns=['EnteredDate', 'ExitedDate', 'Qty', 'BuyRate', 'SellRate', 'Buy Value', 'Sell Value'])
    
    # Process Charges
    if not charges_df.empty:
        if 'Date' in charges_df.columns:
            charges_df['Date'] = pd.to_datetime(charges_df['Date']).dt.date
            
        charges_df['Charge'] = pd.to_numeric(charges_df.get('Charge', 0), errors='coerce').fillna(0)
        
        charges_df['FY'] = charges_df['Date'].apply(get_fy)
        charges_df['Quarter'] = charges_df['Date'].apply(get_quarter)
        charges_df['Month'] = charges_df['Date'].apply(get_month)
        
        charges_df['EnteredTradeCount'] = 0
        charges_df['ExitedTradeCount'] = 0
        charges_df['TotalTradeCount'] = 0
        charges_df['PerTradeCharge'] = 0.0
        
        if not trade_df.empty:
            for idx, charge_row in charges_df.iterrows():
                charge_date = charge_row['Date']
                if pd.notna(charge_date):
                    # Count matches separately for EnteredDate and ExitedDate
                    entered_count = (trade_df['EnteredDate'] == charge_date).sum()
                    exited_count = (trade_df['ExitedDate'] == charge_date).sum()
                    total_count = entered_count + exited_count
                    
                    charges_df.at[idx, 'EnteredTradeCount'] = entered_count
                    charges_df.at[idx, 'ExitedTradeCount'] = exited_count
                    charges_df.at[idx, 'TotalTradeCount'] = total_count
                    
                    if total_count > 0:
                        charges_df.at[idx, 'PerTradeCharge'] = charge_row['Charge'] / total_count
                    else:
                        charges_df.at[idx, 'PerTradeCharge'] = 0.0
    else:
        charges_df = pd.DataFrame(columns=['Date', 'Charge', 'EnteredTradeCount', 'ExitedTradeCount', 'TotalTradeCount', 'PerTradeCharge', 'FY', 'Quarter', 'Month'])

    # Map PerTradeCharge back to TradeMaster
    if not trade_df.empty and not charges_df.empty:
        # If there are multiple charges on the same date, we sum their per-trade costs
        cost_per_date = charges_df.groupby('Date')['PerTradeCharge'].sum().to_dict()
        
        trade_df['EnteredTradeCharges'] = trade_df['EnteredDate'].map(cost_per_date).fillna(0.0)
        trade_df['ExitedTradeCharges'] = trade_df['ExitedDate'].map(cost_per_date).fillna(0.0)
    else:
        if not trade_df.empty:
            trade_df['EnteredTradeCharges'] = 0.0
            trade_df['ExitedTradeCharges'] = 0.0
        else:
            trade_df['EnteredTradeCharges'] = pd.Series(dtype='float64')
            trade_df['ExitedTradeCharges'] = pd.Series(dtype='float64')

    if not trade_df.empty:
        trade_df['P&L'] = trade_df['Sell Value'] - trade_df['Buy Value'] - trade_df['EnteredTradeCharges'] - trade_df['ExitedTradeCharges']
        trade_df['P&L Without Charge'] = trade_df['Sell Value'] - trade_df['Buy Value']
        
        trade_df['FY'] = trade_df['ExitedDate'].apply(get_fy)
        trade_df['Quarter'] = trade_df['ExitedDate'].apply(get_quarter)
        trade_df['Month'] = trade_df['ExitedDate'].apply(get_month)
        trade_df['Day'] = pd.to_datetime(trade_df['ExitedDate']).dt.day
    else:
        trade_df['P&L'] = pd.Series(dtype='float64')
        trade_df['P&L Without Charge'] = pd.Series(dtype='float64')
        trade_df['FY'] = pd.Series(dtype='object')
        trade_df['Quarter'] = pd.Series(dtype='object')
        trade_df['Month'] = pd.Series(dtype='object')
        trade_df['Day'] = pd.Series(dtype='object')
    trade_df['Instrument'] = (
        trade_df['Symbol'] + " " + trade_df['StrikePrice'].fillna('').astype(str)
    ).str.strip()

    return trade_df, charges_df
