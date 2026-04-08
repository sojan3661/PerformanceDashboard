import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="My Performance Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("File Upload Data")
st.markdown("Upload your Trade Details Excel file below. It extracts and merges data from Fyers, AngelOne, Upstox, and Zerodha sheets into the TradeMaster format.")

from tradeMaster import build_trademaster
from chargesMaster import build_charges_dataframe
from DataProcessing import get_processed_data
from assets.Chart import ChartDrillDown

uploaded_file = st.file_uploader(
    "Choose a Trade Details Excel file", 
    type=['xlsx', 'xls'], 
    help="Upload your Trade Details.xlsx file containing Fyers, AngelOne, Upstox, and/or Zerodha sheets"
)

if uploaded_file is not None:
    st.success(f"File '{uploaded_file.name}' has been uploaded successfully!")
    
    try:
        xls = pd.ExcelFile(uploaded_file)
        
        with st.spinner('Processing Trade data...'):
            trademaster_df = build_trademaster(xls)

        if trademaster_df.empty:
            st.warning("No relevant Fyers, AngelOne, Upstox, or Zerodha data found in the uploaded file.")
        else:
            st.write(f"### Processed TradeMaster Data ({len(trademaster_df)} records)")
            
            # Save to Database
            with st.spinner('Checking database for duplicates and saving new records...'):
                try:
                    from config.db import save_to_trademaster
                    inserted_count = save_to_trademaster(trademaster_df)
                    if inserted_count > 0:
                        st.success(f"Successfully added {inserted_count} new records to the TradeMaster database!")
                    else:
                        st.info("No new records to add. All trades in this document were already in the database.")
                except Exception as db_e:
                    st.error(f"Failed to connect and save to Supabase: {db_e}. Please make sure you have added your Supabase URL and Key in `.streamlit/secrets.toml`!")
            
            display_df = trademaster_df.copy()
            if 'EnteredDate' in display_df.columns:
                display_df['EnteredDate'] = pd.to_datetime(display_df['EnteredDate']).dt.date
            if 'ExitedDate' in display_df.columns:
                display_df['ExitedDate'] = pd.to_datetime(display_df['ExitedDate']).dt.date
                
            st.dataframe(display_df, use_container_width=True)
            
            csv_data = trademaster_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download TradeMaster as CSV",
                data=csv_data,
                file_name='TradeMaster.csv',
                mime='text/csv',
            )

        with st.spinner('Processing Charges data...'):
            charges_df = build_charges_dataframe(xls)

        if charges_df.empty:
            st.warning("No relevant Charges data found in the uploaded file.")
        else:
            st.write(f"### Processed Charges Data ({len(charges_df)} records)")
            
            # Save to Database for Charges
            with st.spinner('Checking database for duplicate charges and saving new records...'):
                try:
                    from config.db import save_to_charges
                    inserted_charges = save_to_charges(charges_df)
                    if inserted_charges > 0:
                        st.success(f"Successfully added {inserted_charges} new records to the Charges database!")
                    else:
                        st.info("No new charges to add. All charges were already in the database.")
                except Exception as db_e:
                    st.error(f"Failed to connect and save to Supabase: {db_e}. Please verify your database connection string!")
            
            display_charges_df = charges_df.copy()
            if 'Date' in display_charges_df.columns:
                display_charges_df['Date'] = pd.to_datetime(display_charges_df['Date']).dt.date
                
            st.dataframe(display_charges_df, use_container_width=True)
            
            csv_charges = charges_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Charges as CSV",
                data=csv_charges,
                file_name='Charges.csv',
                mime='text/csv',
            )
            
        # Clear the cache whenever a file is uploaded to ensure subsequent UI 
        # uses the freshest data from the database.
        get_processed_data.clear()
            
    except Exception as e:
        import traceback
        st.error(f"An error occurred while processing the file: {e}")
        with st.expander("Show stack trace"):
            st.code(traceback.format_exc())

# st.divider()
# st.header("📋 Database Overview (Cached)")
# st.markdown("This section fetches and computes the processed data directly from your database. It automatically updates when you upload new files.")

with st.spinner("Fetching and processing data from database..."):
    cached_trades, cached_charges = get_processed_data()

# col1, col2 = st.tabs(["TradeMaster View", "Charges View"])

# with col1:
#     if not cached_trades.empty:
#         st.write(f"**TradeMaster Data ({len(cached_trades)} records)**")
#         st.dataframe(cached_trades, use_container_width=True)
#     else:
#         st.info("No TradeMaster data found in database.")

# with col2:
#     if not cached_charges.empty:
#         st.write(f"**Charges Data ({len(cached_charges)} records)**")
#         st.dataframe(cached_charges, use_container_width=True)
#     else:
#         st.info("No Charges data found in database.")

st.divider()
FY_MONTH_ORDER = [
    "Apr", "May", "Jun",
    "Jul", "Aug", "Sep",
    "Oct", "Nov", "Dec",
    "Jan", "Feb", "Mar"
]
ChartDrillDown.drill_down_chart(
    df=cached_trades,
    level_config=[
        {"name": "FY", "group_col": "FY","tooltip": ["P&L"]},
        {"name": "Quarter", "group_col": "Quarter"},
        {"name": "Month", "group_col": "Month"},
        {"name": "Day", "group_col": "Day"},
        {"name": "Instrument", "group_col": "Instrument"},
        
    ],
    metric_col="P&L",
    sort_config={
        "FY": {"type": "label_asc"},
        "Quarter": {"type": "label_asc"},
        "Month": {"type": "custom", "order": FY_MONTH_ORDER},
        "Day": {"type": "asc"},
    }
)
    
