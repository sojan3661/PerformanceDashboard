import pandas as pd

def process_charges_data(xls):
    sheet_names = xls.sheet_names
    df_charges = pd.DataFrame()
    
    if "Charges" in sheet_names:
        df_charges = pd.read_excel(xls, sheet_name="Charges")
        if not df_charges.empty:
            # Keep only expected columns if they exist
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
    
    if "Fyers - Charges" in sheet_names:
        df_fyers_charges = pd.read_excel(xls, sheet_name="Fyers - Charges")
        if not df_fyers_charges.empty:
            # Remove specific columns according to PowerQuery logic
            cols_to_remove = ["Turnover (₹)", "Brokerage (₹)", "STT/CTT", "IPFT (₹)", 
                              "Stamp Duty (₹)", "GST (₹)", "Exchange Transaction (₹)", 
                              "SEBI Turnover (₹)", "CM Charges (₹)"]
            
            # Since pandas might read differently because of encoding (e.g. â‚¹ vs ₹)
            # We can also drop by checking substrings or just exact match
            actual_cols_to_drop = [c for c in df_fyers_charges.columns if any(rem.split(' ')[0] in c for rem in cols_to_remove)]
            df_fyers_charges = df_fyers_charges.drop(columns=actual_cols_to_drop, errors='ignore')
            
            if 'Date' in df_fyers_charges.columns:
                df_fyers_charges['Date'] = pd.to_datetime(df_fyers_charges['Date'], errors='coerce')
            if 'Charge' in df_fyers_charges.columns:
                df_fyers_charges['Charge'] = pd.to_numeric(df_fyers_charges['Charge'], errors='coerce').fillna(0)
            
            # Fyers charges processing stripped to Date and Charge
    return df_fyers_charges

def build_charges_dataframe(xls):
    charges_df = process_charges_data(xls)
    fyers_charges_df = process_fyers_charges_data(xls)
    
    final_df = pd.concat([charges_df, fyers_charges_df], ignore_index=True)
    
    if not final_df.empty:
        if 'Date' in final_df.columns:
            final_df = final_df.dropna(subset=['Date'])
        
        # Ensure we just have the 2 columns expected
        expected_cols = ['Date', 'Charge']
        for col in expected_cols:
            if col not in final_df.columns:
                final_df[col] = None
                
        final_df = final_df[expected_cols]
        
    return final_df
