import pandas as pd
import re

def _find_sheet(sheet_names, patterns):
    for pattern in patterns:
        compiled = re.compile(pattern, re.IGNORECASE)
        for s in sheet_names:
            if compiled.search(s.strip()):
                return s
    return None

def _extract_charge_column(df):
    """Find and return the charge values series from a DataFrame with various column synonyms."""
    charge_synonyms = ['charge', 'charges', 'total charge', 'total charges', 'net charge', 'charge (₹)', 'total charges (₹)', 'amount']
    for col in df.columns:
        if str(col).strip().lower() in charge_synonyms:
            return pd.to_numeric(df[col], errors='coerce').fillna(0)
    return pd.Series(0.0, index=df.index)

def _extract_date_column(df):
    """Find and return the date values series from a DataFrame with various column synonyms."""
    date_synonyms = ['date', 'trade date', 'transaction date', 'buy date', 'entry date']
    for col in df.columns:
        if str(col).strip().lower() in date_synonyms:
            return pd.to_datetime(df[col], errors='coerce')
    return pd.Series(pd.NaT, index=df.index)

def process_charges_data(xls):
    sheet_names = xls.sheet_names
    df_charges = pd.DataFrame()
    
    charges_sheet = _find_sheet(sheet_names, [r'^charges$', r'charges.*detail', r'trade.*charges', r'charges.*master'])
    if charges_sheet:
        raw_df = pd.read_excel(xls, sheet_name=charges_sheet)
        if not raw_df.empty:
            dates = _extract_date_column(raw_df)
            charges = _extract_charge_column(raw_df)
            df_charges = pd.DataFrame({'Date': dates, 'Charge': charges})
            df_charges = df_charges.dropna(subset=['Date'])
                
    return df_charges

def process_fyers_charges_data(xls):
    sheet_names = xls.sheet_names
    df_fyers_charges = pd.DataFrame()
    
    fyers_charges_sheet = _find_sheet(sheet_names, [r'fyers.*charge'])
    if fyers_charges_sheet:
        raw_df = pd.read_excel(xls, sheet_name=fyers_charges_sheet)
        if not raw_df.empty:
            dates = _extract_date_column(raw_df)
            charges = _extract_charge_column(raw_df)
            df_fyers_charges = pd.DataFrame({'Date': dates, 'Charge': charges})
            df_fyers_charges = df_fyers_charges.dropna(subset=['Date'])
            
    return df_fyers_charges

def build_charges_dataframe(xls):
    charges_df = process_charges_data(xls)
    fyers_charges_df = process_fyers_charges_data(xls)
    
    final_df = pd.concat([charges_df, fyers_charges_df], ignore_index=True)
    
    if not final_df.empty:
        final_df['Date'] = pd.to_datetime(final_df['Date'], errors='coerce').dt.strftime('%Y-%m-%d')
        final_df['Charge'] = pd.to_numeric(final_df['Charge'], errors='coerce').fillna(0)
        final_df = final_df.dropna(subset=['Date'])
        
        # Group by Date to consolidate multiple charges for the same date
        final_df = final_df.groupby('Date', as_index=False)['Charge'].sum()
        
        expected_cols = ['Date', 'Charge']
        final_df = final_df[expected_cols]
    else:
        final_df = pd.DataFrame(columns=['Date', 'Charge'])
        
    return final_df
