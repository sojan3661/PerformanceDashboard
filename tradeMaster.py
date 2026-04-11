import pandas as pd
import numpy as np

def process_fyers_data(xls):
    sheet_names = xls.sheet_names
    df_eq = pd.DataFrame()
    df_eq1 = pd.DataFrame()
    df_fo = pd.DataFrame()
    
    if "Fyers - EQ " in sheet_names:
        df_eq = pd.read_excel(xls, sheet_name="Fyers - EQ ")
        if 'Symbol' in df_eq.columns:
            df_eq = df_eq.dropna(subset=['Symbol'])
            
    if "Fyers - EQ ShortTerm Trading" in sheet_names:
        df_eq1 = pd.read_excel(xls, sheet_name="Fyers - EQ ShortTerm Trading")
        if 'Symbol' in df_eq1.columns:
            df_eq1 = df_eq1.dropna(subset=['Symbol'])

    df_combined = pd.concat([df_eq, df_eq1], ignore_index=True)
    if not df_combined.empty:
        if 'Txn Type' in df_combined.columns:
            df_combined = df_combined.drop(columns=['Txn Type'])
        if 'Segment' in df_combined.columns:
            df_combined = df_combined.drop(columns=['Segment'])
        df_combined['Segment'] = 'Equity & Mutual Fund'
        df_combined['StrikePrice'] = None
        
    if "Fyers - Options" in sheet_names:
        df_fo = pd.read_excel(xls, sheet_name="Fyers - Options")
        if not df_fo.empty and 'Symbol' in df_fo.columns:
            df_fo = df_fo.dropna(subset=['Symbol'])
            
            split_df = df_fo['Symbol'].astype(str).str.split(' ', n=3, expand=True)
            for col in range(4):
                if col not in split_df.columns:
                    split_df[col] = ''
            df_fo['Symbol'] = split_df[0]
            df_fo['StrikePrice'] = split_df[2].fillna('').astype(str) + " " + split_df[3].fillna('').astype(str)
            df_fo['StrikePrice'] = df_fo['StrikePrice'].str.strip()
                
            if 'Segment' in df_fo.columns:
                df_fo = df_fo.drop(columns=['Segment'])
            if 'Txn Type' in df_fo.columns:
                df_fo = df_fo.rename(columns={'Txn Type': 'Segment'})
                
    final_df = pd.concat([df_combined, df_fo], ignore_index=True)
    if final_df.empty:
        return pd.DataFrame()
        
    if 'Buy Date' in final_df.columns and 'Sell Date' in final_df.columns:
        final_df['Buy Date'] = pd.to_datetime(final_df['Buy Date'], errors='coerce')
        final_df['Sell Date'] = pd.to_datetime(final_df['Sell Date'], errors='coerce')
        final_df['EnteredDate'] = final_df[['Buy Date', 'Sell Date']].min(axis=1)
        final_df['ExitedDate'] = final_df[['Buy Date', 'Sell Date']].max(axis=1)
    else:
        final_df['EnteredDate'] = None
        final_df['ExitedDate'] = None
        
    rename_dict = {'Sell Qty': 'Qty', 'Buy Rate (₹)': 'BuyRate', 'Sell Rate (₹)': 'SellRate'}
    final_df = final_df.rename(columns=rename_dict)
    
    cols_to_remove = ['Buy Date', 'Sell Date', 'Buy Qty', 'Buy Value (₹)', 'Sell Value (₹)', 'P&L Amt (₹)', 'Total days', 'ISIN', 'Turnover (₹)', 'Txn Type']
    final_df = final_df.drop(columns=[c for c in cols_to_remove if c in final_df.columns])
    return final_df

def process_angelone_data(xls):
    sheet_names = xls.sheet_names
    df_eq = pd.DataFrame()
    df_fo = pd.DataFrame()
    
    if "AngelOne - EQ" in sheet_names:
        df_eq = pd.read_excel(xls, sheet_name="AngelOne - EQ")
        if not df_eq.empty:
            if 'Scrip Name' in df_eq.columns:
                df_eq = df_eq.rename(columns={'Scrip Name': 'Symbol'})
            
            df_eq['Segment'] = 'Equity & Mutual Fund'
            
            rename_eq = {'Avg Buy Price': 'BuyRate', 'Avg Sell Price': 'SellRate', 'Buy Date': 'EnteredDate', 'Sell Date': 'ExitedDate'}
            df_eq = df_eq.rename(columns=rename_eq)
            
            cols_to_drop_eq = ["ISIN", "Type of instrument", "Purchase Type", "Short term taxable income", "Long term taxable income", "Net Profit/Loss", "STT", "Charges and Statutory Levies", "Cost Of Acquisition", "Sell Value", "Buy Value"]
            df_eq = df_eq.drop(columns=[c for c in cols_to_drop_eq if c in df_eq.columns])
            df_eq['StrikePrice'] = None

    if "AngelOne - FO" in sheet_names:
        df_fo = pd.read_excel(xls, sheet_name="AngelOne - FO")
        if not df_fo.empty:
            if 'Symbol Name' in df_fo.columns:
                df_fo = df_fo.rename(columns={'Symbol Name': 'Symbol'})
                
            if 'Segment' in df_fo.columns:
                df_fo = df_fo.drop(columns=['Segment'])
                
            if 'Option Type' in df_fo.columns:
                df_fo['Segment'] = df_fo['Option Type'].apply(lambda x: "Options" if pd.notna(x) and str(x).strip() != "" else "Equity & Mutual Fund")
            else:
                df_fo['Segment'] = "Equity & Mutual Fund"
                
            if 'Strike Price' in df_fo.columns and 'Option Type' in df_fo.columns:
                strike_str = df_fo['Strike Price'].astype(str).str.replace(r'\.0$', '', regex=True)
                # replace 'nan' literal with empty string just in case
                strike_str = strike_str.replace('nan', '')
                opt_type = df_fo['Option Type'].fillna('').astype(str)
                df_fo['StrikePrice'] = strike_str + " " + opt_type
                df_fo['StrikePrice'] = df_fo['StrikePrice'].str.strip()
            else:
                df_fo['StrikePrice'] = None
                
            if 'Buy Date' in df_fo.columns and 'Sell date' in df_fo.columns:
                df_fo['Buy Date'] = pd.to_datetime(df_fo['Buy Date'], errors='coerce')
                df_fo['Sell date'] = pd.to_datetime(df_fo['Sell date'], errors='coerce')
                df_fo['EnteredDate'] = df_fo[['Buy Date', 'Sell date']].min(axis=1)
                df_fo['ExitedDate'] = df_fo[['Buy Date', 'Sell date']].max(axis=1)
            else:
                df_fo['EnteredDate'] = None
                df_fo['ExitedDate'] = None
                
            rename_fo = {'Avg Buy Price': 'BuyRate', 'Avg Sell Price': 'SellRate'}
            df_fo = df_fo.rename(columns=rename_fo)
            
            cols_to_drop_fo = ["Turnover", "Taxable P&L", "STT", "Total Charges and Statutory Levies", "Sell Value", "Buy Value", "Expiry date", "Strike Price", "Option Type", "Buy Date", "Sell date"]
            df_fo = df_fo.drop(columns=[c for c in cols_to_drop_fo if c in df_fo.columns])

    final_df = pd.concat([df_eq, df_fo], ignore_index=True)
    return final_df

def process_upstox_data(xls):
    sheet_names = xls.sheet_names
    df_eq = pd.DataFrame()
    df_fo = pd.DataFrame()

    if "Upstox - EQ" in sheet_names:
        df_eq = pd.read_excel(xls, sheet_name="Upstox - EQ")

    if "Upstox - Options" in sheet_names:
        df_fo = pd.read_excel(xls, sheet_name="Upstox - Options")

    final_df = pd.concat([df_eq, df_fo], ignore_index=True)

    if final_df.empty:
        return pd.DataFrame()

    cols_to_drop = ["Scrip Name ", "Scrip Code", "ISIN", "Buy Amt", "Sell Amt", "Days", "Total PL", "Short Term", "Long Term", "Speculation", "Turn Over"]
    final_df = final_df.drop(columns=[c for c in cols_to_drop if c in final_df.columns])

    if 'Strike Price' in final_df.columns:
        final_df['Strike Price'] = final_df['Strike Price'].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
    else:
        final_df['Strike Price'] = ''

    if 'Scrip Opt' in final_df.columns:
        scrip_opt = final_df['Scrip Opt'].fillna('').astype(str).str.strip()
    else:
        scrip_opt = pd.Series('', index=final_df.index)

    def get_segment(row):
        sp = str(row.get('Strike Price', '')).strip()
        so = str(row.get('Scrip Opt', '')).strip().upper()
        if not sp:
            return "Equity & Mutual Fund"
        elif so in ["CE", "PE"]:
            return "Options"
        else:
            return "Equity & Mutual Fund"
    
    final_df['Segment'] = final_df.apply(get_segment, axis=1)
    
    final_df['StrikePrice'] = final_df['Strike Price'].astype(str) + " " + scrip_opt
    final_df['StrikePrice'] = final_df['StrikePrice'].str.strip()

    if 'Scrip Opt' in final_df.columns:
        final_df = final_df.drop(columns=['Scrip Opt'])
    if 'Strike Price' in final_df.columns:
        final_df = final_df.drop(columns=['Strike Price'])

    if 'Buy Date' in final_df.columns and 'Sell Date' in final_df.columns:
        final_df['Buy Date'] = pd.to_datetime(final_df['Buy Date'], errors='coerce')
        final_df['Sell Date'] = pd.to_datetime(final_df['Sell Date'], errors='coerce')
        final_df['EnteredDate'] = final_df[['Buy Date', 'Sell Date']].min(axis=1)
        final_df['ExitedDate'] = final_df[['Buy Date', 'Sell Date']].max(axis=1)
    else:
        final_df['EnteredDate'] = None
        final_df['ExitedDate'] = None

    rename_upstox = {'Buy Rate': 'BuyRate', 'Sell Rate': 'SellRate'}
    final_df = final_df.rename(columns=rename_upstox)
    
    if 'Buy Date' in final_df.columns:
        final_df = final_df.drop(columns=['Buy Date'])
    if 'Sell Date' in final_df.columns:
        final_df = final_df.drop(columns=['Sell Date'])
        
    return final_df

def process_zerodha_data(xls):
    sheet_names = xls.sheet_names
    df_eq = pd.DataFrame()
    df_mf = pd.DataFrame()

    if "Zerodha" in sheet_names:
        df_eq = pd.read_excel(xls, sheet_name="Zerodha")
        if not df_eq.empty:
            df_eq['Segment'] = 'Equity & Mutual Fund'
            
            if 'Quantity' in df_eq.columns and 'Buy Value' in df_eq.columns:
                df_eq['Buy Rate'] = df_eq['Buy Value'] / df_eq['Quantity']
            if 'Quantity' in df_eq.columns and 'Sell Value' in df_eq.columns:
                df_eq['Sell Rate'] = df_eq['Sell Value'] / df_eq['Quantity']
                
            rename_dict = {'Quantity': 'Qty', 'Entry Date': 'EnteredDate', 'Exit Date': 'ExitedDate', 'Buy Rate': 'BuyRate', 'Sell Rate': 'SellRate'}
            df_eq = df_eq.rename(columns=rename_dict)
            
            cols_to_drop = ["ISIN", "STT", "Stamp Duty", "IGST", "SGST", "CGST", "SEBI Charges", "IPFT", "Exchange Transaction Charges", "Brokerage", "Turnover", "Taxable Profit", "Fair Market Value", "Period of Holding", "Profit", "Buy Value", "Sell Value"]
            df_eq = df_eq.drop(columns=[c for c in cols_to_drop if c in df_eq.columns])
            df_eq['StrikePrice'] = None

    if "Zerodha - MF" in sheet_names:
        df_mf = pd.read_excel(xls, sheet_name="Zerodha - MF")
        if not df_mf.empty:
            df_mf['Segment'] = 'Equity & Mutual Fund'
            
            if 'Quantity' in df_mf.columns and 'Buy Value' in df_mf.columns:
                df_mf['Buy Rate'] = df_mf['Buy Value'] / df_mf['Quantity']
            if 'Quantity' in df_mf.columns and 'Sell Value' in df_mf.columns:
                df_mf['Sell Rate'] = df_mf['Sell Value'] / df_mf['Quantity']
                
            rename_dict = {'Quantity': 'Qty', 'Entry Date': 'EnteredDate', 'Exit Date': 'ExitedDate', 'Buy Rate': 'BuyRate', 'Sell Rate': 'SellRate'}
            df_mf = df_mf.rename(columns=rename_dict)
            
            cols_to_drop = ["ISIN", "Turnover", "Taxable Profit", "Fair Market Value", "Period of Holding", "Profit", "Buy Value", "Sell Value"]
            df_mf = df_mf.drop(columns=[c for c in cols_to_drop if c in df_mf.columns])
            df_mf['StrikePrice'] = None

    final_df = pd.concat([df_eq, df_mf], ignore_index=True)
    return final_df


def build_trademaster(xls):
    fyers_df = process_fyers_data(xls)
    angel_df = process_angelone_data(xls)
    upstox_df = process_upstox_data(xls)
    zerodha_df = process_zerodha_data(xls)
    
    # Merge all pipelines
    trademaster_df = pd.concat([fyers_df, angel_df, upstox_df, zerodha_df], ignore_index=True)
    
    if not trademaster_df.empty:
        expected_cols = ['Segment', 'Symbol', 'StrikePrice', 'Qty', 'BuyRate', 'EnteredDate', 'SellRate', 'ExitedDate']
        for col in expected_cols:
            if col not in trademaster_df.columns:
                trademaster_df[col] = None
                
        trademaster_df = trademaster_df[expected_cols]
        
        # Convert to numeric for grouping calculations
        trademaster_df['Qty'] = pd.to_numeric(trademaster_df['Qty'], errors='coerce').fillna(0)
        trademaster_df['BuyRate'] = pd.to_numeric(trademaster_df['BuyRate'], errors='coerce').fillna(0)
        trademaster_df['SellRate'] = pd.to_numeric(trademaster_df['SellRate'], errors='coerce').fillna(0)
    
        # Calculate intermediate Total values
        trademaster_df['TotalBuy'] = trademaster_df['Qty'] * trademaster_df['BuyRate']
        trademaster_df['TotalSell'] = trademaster_df['Qty'] * trademaster_df['SellRate']
        
        # Group by composite keys
        groupby_cols = ['Segment', 'Symbol', 'StrikePrice', 'EnteredDate', 'ExitedDate']
        
        # Handle NA values in groupby_cols by temporarily filling them
        trademaster_df[groupby_cols] = trademaster_df[groupby_cols].fillna('__MISSING__')
        
        trademaster_df = trademaster_df.groupby(groupby_cols, as_index=False).agg({
            'Qty': 'sum',
            'TotalBuy': 'sum',
            'TotalSell': 'sum'
        })
        
        # Re-calculate weighted averages
        trademaster_df['BuyRate'] = np.where(trademaster_df['Qty'] > 0, trademaster_df['TotalBuy'] / trademaster_df['Qty'], 0)
        trademaster_df['SellRate'] = np.where(trademaster_df['Qty'] > 0, trademaster_df['TotalSell'] / trademaster_df['Qty'], 0)
        
        # Restore NA values
        trademaster_df[groupby_cols] = trademaster_df[groupby_cols].replace('__MISSING__', None)
        
        # Ensure correct column order again
        trademaster_df = trademaster_df[expected_cols]
    return trademaster_df

