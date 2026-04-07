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
            
    except Exception as e:
        import traceback
        st.error(f"An error occurred while processing the file: {e}")
        with st.expander("Show stack trace"):
            st.code(traceback.format_exc())
