import pandas as pd
import re

def _find_sheet(sheet_names, patterns):
    for pattern in patterns:
        compiled = re.compile(pattern, re.IGNORECASE)
        for s in sheet_names:
            if compiled.search(s.strip()):
                return s
    return None

def process_charges_data(xls):
    sheet_names = xls.sheet_names
    df_charges = pd.DataFrame()
    
    charges_sheet = _find_sheet(sheet_names, [r'^charges$', r'^\s*charges\s*$'])
    if charges_sheet:
        df_charges = pd.read_excel(xls, sheet_name=charges_sheet)
        if not df_charges.empty:
            cols_to_keep = ['Date', 'Charge']
            existing_cols = [c for c in cols_to_keep if c in df_charges.columns]
            df_charges = df_charges[existing_cols]
            
            if 'Date' in df_charges.columns:
                df_charges['Date'] = pd.to_datetime(df_charges['Date'], errors='coerce')
            if 'Charge' in df_charges.columns:
                df_charges['Charge'] = pd.to_numeric(df_charges['Charge'], errors='coerce').fillna(0)
                
    return df_charges

def process_fyers_charges_data(xls):
    sheet_names = xls.sheet_names
    df_fyers_charges = pd.DataFrame()
    
    fyers_charges_sheet = _find_sheet(sheet_names, [r'fyers.*charge'])
    if fyers_charges_sheet:
        df_fyers_charges = pd.read_excel(xls, sheet_name=fyers_charges_sheet)
        if not df_fyers_charges.empty:
            cols_to_remove = ["Turnover (₹)", "Brokerage (₹)", "STT/CTT", "IPFT (₹)", 
                              "Stamp Duty (₹)", "GST (₹)", "Exchange Transaction (₹)", 
                              "SEBI Turnover (₹)", "CM Charges (₹)"]
            
            actual_cols_to_drop = [c for c in df_fyers_charges.columns if any(rem.split(' ')[0] in c for rem in cols_to_remove)]
            df_fyers_charges = df_fyers_charges.drop(columns=actual_cols_to_drop, errors='ignore')
            
            if 'Date' in df_fyers_charges.columns:
                df_fyers_charges['Date'] = pd.to_datetime(df_fyers_charges['Date'], errors='coerce')
            if 'Charge' in df_fyers_charges.columns:
                df_fyers_charges['Charge'] = pd.to_numeric(df_fyers_charges['Charge'], errors='coerce').fillna(0)
            
    return df_fyers_charges

def build_charges_dataframe(xls):
    charges_df = process_charges_data(xls)
    fyers_charges_df = process_fyers_charges_data(xls)
    
    final_df = pd.concat([charges_df, fyers_charges_df], ignore_index=True)
    
    if not final_df.empty:
        if 'Date' in final_df.columns:
            final_df = final_df.dropna(subset=['Date'])
        
        expected_cols = ['Date', 'Charge']
        for col in expected_cols:
            if col not in final_df.columns:
                final_df[col] = None
                
        final_df = final_df[expected_cols]
        
    return final_df

