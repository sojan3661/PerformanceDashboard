import pandas as pd
import numpy as np
import re

def _find_sheet(sheet_names, patterns):
    """
    Finds a sheet name in sheet_names matching any pattern in patterns.
    Matches case-insensitively and ignores leading/trailing whitespace.
    """
    for pattern in patterns:
        compiled = re.compile(pattern, re.IGNORECASE)
        for s in sheet_names:
            if compiled.search(s.strip()):
                return s
    return None

def _clean_symbol(val):
    if pd.isna(val): return None
    s = str(val).strip().upper()
    return s if s not in ['', 'NAN', 'NONE', '<NA>'] else None

def _clean_strikeprice(val):
    if pd.isna(val): return None
    s = str(val).strip().upper()
    return s if s not in ['', 'NAN', 'NONE', '<NA>'] else None

def process_fyers_data(xls):
    sheet_names = xls.sheet_names
    df_eq = pd.DataFrame()
    df_eq1 = pd.DataFrame()
    df_fo = pd.DataFrame()
    df_comm = pd.DataFrame()

    eq_sheet = _find_sheet(sheet_names, [r'^fyers\s*-\s*eq\b(?!.*short)'])
    if eq_sheet:
        df_eq = pd.read_excel(xls, sheet_name=eq_sheet)
        if 'Symbol' in df_eq.columns:
            df_eq = df_eq.dropna(subset=['Symbol'])

    short_sheet = _find_sheet(sheet_names, [r'fyers.*short.*term', r'fyers.*eq.*short'])
    if short_sheet:
        df_eq1 = pd.read_excel(xls, sheet_name=short_sheet)
        if 'Symbol' in df_eq1.columns:
            df_eq1 = df_eq1.dropna(subset=['Symbol'])

    df_combined = pd.concat([df_eq, df_eq1], ignore_index=True)
    if not df_combined.empty:
        df_combined['StrikePrice'] = None

    options_sheet = _find_sheet(sheet_names, [r'fyers.*option', r'fyers.*fo'])
    if options_sheet:
        df_fo = pd.read_excel(xls, sheet_name=options_sheet)

    comm_sheet = _find_sheet(sheet_names, [r'fyers.*commodi'])
    if comm_sheet:
        df_comm = pd.read_excel(xls, sheet_name=comm_sheet)
        if not df_comm.empty:
            rename_comm = {
                'Name': 'Symbol',
                'Txn type': 'Txn Type',
                'Buy date': 'Buy Date',
                'Sell date': 'Sell Date',
                'Buy price': 'Buy Rate (₹)',
                'Sell price': 'Sell Rate (₹)',
                'Buy value': 'Buy Value (₹)',
                'Sell value': 'Sell Value (₹)',
                'P&L': 'P&L Amt (₹)',
                'Turnover': 'Turnover (₹)',
            }
            df_comm = df_comm.rename(columns=rename_comm)

    df_fo = pd.concat([df_fo, df_comm], ignore_index=True)

    if not df_fo.empty and 'Symbol' in df_fo.columns:
        df_fo = df_fo.dropna(subset=['Symbol'])

        split_df = df_fo['Symbol'].astype(str).str.split(' ', n=3, expand=True)
        for col in range(4):
            if col not in split_df.columns:
                split_df[col] = ''
        df_fo['Symbol'] = split_df[0]
        df_fo['StrikePrice'] = split_df[2].fillna('').astype(str) + " " + split_df[3].fillna('').astype(str)
        df_fo['StrikePrice'] = df_fo['StrikePrice'].str.strip()

    final_df = pd.concat([df_combined, df_fo], ignore_index=True)
    if final_df.empty:
        return pd.DataFrame()

    if 'Segment' not in final_df.columns:
        final_df['Segment'] = ''

    segment_mapping = {
        'NSE-FNO': 'Options',
        'NSE-Cash': 'Equity',
        'BSE-Cash': 'Equity',
        'BSE-MF': 'Mutual Fund'
    }
    final_df['Segment'] = final_df['Segment'].replace(segment_mapping)

    def apply_segment_rule(row):
        seg = str(row.get('Segment', '')).strip()
        txn = str(row.get('Txn Type', '')).strip()

        if seg.lower() in ['equity', 'mutual fund']:
            return 'Equity & Mutual Fund'
        elif seg.lower() == 'commodity':
            return f"Commodity-{txn}" if txn else "Commodity"
        else:
            return txn if txn else seg

    final_df['Segment'] = final_df.apply(apply_segment_rule, axis=1)
    if 'Buy Date' in final_df.columns and 'Sell Date' in final_df.columns:
        final_df['Buy Date'] = pd.to_datetime(final_df['Buy Date'], errors='coerce')
        final_df['Sell Date'] = pd.to_datetime(final_df['Sell Date'], errors='coerce')
        final_df['EnteredDate'] = final_df[['Buy Date', 'Sell Date']].min(axis=1)
        final_df['ExitedDate'] = final_df[['Buy Date', 'Sell Date']].max(axis=1)
    else:
        final_df['EnteredDate'] = None
        final_df['ExitedDate'] = None

    rename_dict = {'Buy Rate (₹)': 'BuyRate', 'Sell Rate (₹)': 'SellRate'}
    if 'Qty' not in final_df.columns:
        if 'Sell Qty' in final_df.columns:
            rename_dict['Sell Qty'] = 'Qty'
        elif 'Buy Qty' in final_df.columns:
            rename_dict['Buy Qty'] = 'Qty'

    final_df = final_df.rename(columns=rename_dict)

    cols_to_remove = ['Buy Date', 'Sell Date', 'Buy Qty', 'Sell Qty', 'Buy Value (₹)', 'Sell Value (₹)', 'P&L Amt (₹)', 'Total days', 'ISIN', 'Turnover (₹)', 'Txn Type']
    final_df = final_df.drop(columns=[c for c in cols_to_remove if c in final_df.columns])
    return final_df

def process_angelone_data(xls):
    sheet_names = xls.sheet_names
    df_eq = pd.DataFrame()
    df_fo = pd.DataFrame()

    eq_sheet = _find_sheet(sheet_names, [r'angel.*eq', r'angel.*equity'])
    if eq_sheet:
        df_eq = pd.read_excel(xls, sheet_name=eq_sheet)
        if not df_eq.empty:
            if 'Scrip Name' in df_eq.columns:
                df_eq = df_eq.rename(columns={'Scrip Name': 'Symbol'})

            df_eq['Segment'] = 'Equity & Mutual Fund'

            rename_eq = {'Avg Buy Price': 'BuyRate', 'Avg Sell Price': 'SellRate', 'Buy Date': 'EnteredDate', 'Sell Date': 'ExitedDate'}
            df_eq = df_eq.rename(columns=rename_eq)

            cols_to_drop_eq = ["ISIN", "Type of instrument", "Purchase Type", "Short term taxable income", "Long term taxable income", "Net Profit/Loss", "STT", "Charges and Statutory Levies", "Cost Of Acquisition", "Sell Value", "Buy Value"]
            df_eq = df_eq.drop(columns=[c for c in cols_to_drop_eq if c in df_eq.columns])
            df_eq['StrikePrice'] = None

    fo_sheet = _find_sheet(sheet_names, [r'angel.*fo', r'angel.*f&o', r'angel.*option'])
    if fo_sheet:
        df_fo = pd.read_excel(xls, sheet_name=fo_sheet)
        if not df_fo.empty:
            if 'Symbol Name' in df_fo.columns:
                df_fo = df_fo.rename(columns={'Symbol Name': 'Symbol'})
            elif 'Scrip Name' in df_fo.columns:
                df_fo = df_fo.rename(columns={'Scrip Name': 'Symbol'})

            if 'Segment' in df_fo.columns:
                df_fo = df_fo.drop(columns=['Segment'])

            if 'Option Type' in df_fo.columns:
                df_fo['Segment'] = df_fo['Option Type'].apply(lambda x: "Options" if pd.notna(x) and str(x).strip() != "" else "Equity & Mutual Fund")
            else:
                df_fo['Segment'] = "Equity & Mutual Fund"

            if 'Strike Price' in df_fo.columns and 'Option Type' in df_fo.columns:
                strike_str = df_fo['Strike Price'].astype(str).str.replace(r'\.0$', '', regex=True)
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

    eq_sheet = _find_sheet(sheet_names, [r'upstox.*eq', r'upstox.*equity'])
    if eq_sheet:
        df_eq = pd.read_excel(xls, sheet_name=eq_sheet)

    fo_sheet = _find_sheet(sheet_names, [r'upstox.*option', r'upstox.*fo', r'upstox.*f&o'])
    if fo_sheet:
        df_fo = pd.read_excel(xls, sheet_name=fo_sheet)

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

    eq_sheet = _find_sheet(sheet_names, [r'^zerodha\b(?!.*mf)', r'zerodha.*eq', r'zerodha.*equity'])
    if eq_sheet:
        df_eq = pd.read_excel(xls, sheet_name=eq_sheet)
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

    mf_sheet = _find_sheet(sheet_names, [r'zerodha.*mf', r'zerodha.*mutual'])
    if mf_sheet:
        df_mf = pd.read_excel(xls, sheet_name=mf_sheet)
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

        # Clean Symbol and StrikePrice
        trademaster_df['Symbol'] = trademaster_df['Symbol'].apply(_clean_symbol)
        trademaster_df['StrikePrice'] = trademaster_df['StrikePrice'].apply(_clean_strikeprice)

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

        # Re-clean Symbol and StrikePrice after grouping
        trademaster_df['Symbol'] = trademaster_df['Symbol'].apply(_clean_symbol)
        trademaster_df['StrikePrice'] = trademaster_df['StrikePrice'].apply(_clean_strikeprice)

        # Ensure correct column order again
        trademaster_df = trademaster_df[expected_cols]
    return trademaster_df