import hashlib
import streamlit as st
import pandas as pd
from patch_fyers import parse_fyers_tradebook
from config.db import (
    save_to_fyers_trade_data,
    fetch_fyers_trade_data,
    fetch_fyers_segments,
    transform_fyers_data_by_segment,
    prepare_and_insert_migrated_fyers_data
)

st.set_page_config(
    page_title="Fyers Tradebook Upload",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Fyers Tradebook Data Ingestion")
st.markdown("Upload your Fyers Tradebook file (`.xlsx`, `.xls`, `.csv`) to sync trade records directly to the `FyersTradeData` database table.")
st.divider()

@st.dialog("Migrate Fyers Data", width="large")
def show_migrate_dialog(db_df=None):
    st.write("Select segment and optional date filter (trades where **Buy Date** OR **Sell Date** falls within range will be included):")
    
    # Fetch segments from database or fallback to db_df
    segments = fetch_fyers_segments()
    if not segments and db_df is not None and not db_df.empty and 'Segment' in db_df.columns:
        segments = sorted(list(set(str(x).strip() for x in db_df['Segment'].dropna().unique() if str(x).strip())))
    
    if segments:
        col_seg, col_dates, col_btn = st.columns([2, 3, 1])
        with col_seg:
            selected_segment = st.selectbox("Database Segment", options=segments, key="dialog_selected_segment")
        with col_dates:
            date_range = st.date_input(
                "Filter Date Range (Buy / Sell Date)",
                value=(),
                help="Select start and end dates. Trades with Buy Date OR Sell Date in range will be displayed.",
                key="dialog_date_range"
            )
        with col_btn:
            st.write(" ")
            st.write(" ")
            apply_clicked = st.button("Apply", type="primary", use_container_width=True)

        start_date, end_date = None, None
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range[0], date_range[1]
        elif isinstance(date_range, (list, tuple)) and len(date_range) == 1:
            start_date, end_date = date_range[0], date_range[0]

        cache_key = f"{selected_segment}_{start_date}_{end_date}"

        # Trigger on button click or if viewing previously computed result
        if apply_clicked or (st.session_state.get('migrated_cache_key') == cache_key and 'migrated_df' in st.session_state):
            if apply_clicked:
                with st.spinner(f"Migrating segment '{selected_segment}'..."):
                    success, msg, transformed_df = transform_fyers_data_by_segment(
                        selected_segment, start_date=start_date, end_date=end_date
                    )
                    if success:
                        st.session_state['migrated_cache_key'] = cache_key
                        st.session_state['migrated_df'] = transformed_df
                        st.session_state['migrated_msg'] = msg
                    else:
                        st.session_state.pop('migrated_df', None)
                        st.error(f"❌ Migration failed: {msg}")

            if st.session_state.get('migrated_cache_key') == cache_key and 'migrated_df' in st.session_state:
                transformed_df = st.session_state['migrated_df']
                msg = st.session_state.get('migrated_msg', '')
                st.success(f"✅ {msg}")

                if not transformed_df.empty:
                    st.markdown("### 📊 Transformed Trade Data")
                    m1, m2, m3 = st.columns(3)
                    total_pnl = transformed_df['P&L Amt (₹)'].sum() if 'P&L Amt (₹)' in transformed_df.columns else 0.0
                    option_count = (transformed_df['Txn Type'] == 'Option').sum() if 'Txn Type' in transformed_df.columns else 0
                    future_count = (transformed_df['Txn Type'] == 'Future').sum() if 'Txn Type' in transformed_df.columns else 0

                    m1.metric("Total P&L", f"₹{total_pnl:,.2f}")
                    m2.metric("Option Trades", f"{option_count:,}")
                    m3.metric("Future Trades", f"{future_count:,}")

                    st.dataframe(
                        transformed_df,
                        use_container_width=True,
                        column_config={
                            "P&L Amt (₹)": st.column_config.NumberColumn("P&L Amt (₹)", format="₹%.2f"),
                            "Buy Rate (₹)": st.column_config.NumberColumn("Buy Rate (₹)", format="₹%.2f"),
                            "Buy Value (₹)": st.column_config.NumberColumn("Buy Value (₹)", format="₹%.2f"),
                            "Sell Rate (₹)": st.column_config.NumberColumn("Sell Rate (₹)", format="₹%.2f"),
                            "Sell Value (₹)": st.column_config.NumberColumn("Sell Value (₹)", format="₹%.2f"),
                            "Qty": st.column_config.NumberColumn("Qty", format="%.2f"),
                        }
                    )

                    col_dl, col_mig_db = st.columns([1, 1])
                    with col_dl:
                        csv_bytes = transformed_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download Transformed CSV",
                            data=csv_bytes,
                            file_name=f"fyers_migrated_{selected_segment.lower().replace(' ', '_')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    with col_mig_db:
                        if st.button("🚀 Migrate to TradeMaster Database", type="primary", use_container_width=True):
                            with st.spinner("Preparing & inserting records into TradeMaster database..."):
                                db_success, db_msg = prepare_and_insert_migrated_fyers_data(transformed_df)
                                st.session_state['db_migration_result'] = {'success': db_success, 'msg': db_msg}
                                if db_success:
                                    st.toast(f"🎉 {db_msg}", icon="✅")
                                else:
                                    st.toast(f"❌ Migration Failed: {db_msg}", icon="⚠️")
                                st.rerun()

                    if st.session_state.get('db_migration_result'):
                        res = st.session_state.get('db_migration_result')
                        if res.get('success'):
                            st.success(f"🎉 **TradeMaster Migration Complete:** {res.get('msg')}")
                        else:
                            st.error(f"❌ **Database Migration Failed:** {res.get('msg')}")
                else:
                    st.info("No transformed trade records fall within the selected date range.")
    else:
        st.info("No segments found in database to migrate.")


# Tab 1: Upload & Sync, Tab 2: Database Overview
tab_upload, tab_explorer = st.tabs(["📤 Upload & Sync", "📊 Stored Fyers Trade Data"])

with tab_upload:
    st.subheader("Upload Tradebook File")
    col_up1, col_up2 = st.columns([3, 1])
    
    with col_up1:
        uploaded_file = st.file_uploader(
            "Select Fyers Tradebook File",
            type=['xlsx', 'xls', 'csv'],
            help="Excel or CSV file containing headers: Name, Date & time, Side, Product type, Qty, Traded price, Segment, OMS order ID",
            key="fyers_tradebook_uploader"
        )
    with col_up2:
        st.write(" ")
        st.write(" ")
        force_sync = st.button("🔄 Sync Data", type="primary", use_container_width=True)

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        current_hash = hashlib.md5(file_bytes).hexdigest()
        
        try:
            parsed_df = parse_fyers_tradebook(uploaded_file)
            
            if parsed_df.empty:
                st.warning("⚠️ No valid trade records with OMS order ID were found in the uploaded file.")
            else:
                st.markdown("### 🔍 Parsed File Summary")
                m1, m2, m3, m4 = st.columns(4)
                
                total_records = len(parsed_df)
                unique_names = parsed_df['Name'].dropna().nunique() if 'Name' in parsed_df.columns else 0
                buy_count = (parsed_df['Side'].str.upper() == 'BUY').sum() if 'Side' in parsed_df.columns else 0
                sell_count = (parsed_df['Side'].str.upper() == 'SELL').sum() if 'Side' in parsed_df.columns else 0
                
                m1.metric("Total Trades Parsed", f"{total_records:,}")
                m2.metric("Unique Instruments", f"{unique_names}")
                m3.metric("Buy Orders", f"{buy_count}")
                m4.metric("Sell Orders", f"{sell_count}")

                st.markdown("#### Preview Data (First 50 Rows)")
                st.dataframe(parsed_df.head(50), use_container_width=True)

                if force_sync or st.session_state.get('fyers_processed_hash') != current_hash:
                    if force_sync:
                        with st.spinner("Upserting Fyers trade records into Supabase..."):
                            upserted_count, _ = save_to_fyers_trade_data(parsed_df)
                            st.session_state['fyers_processed_hash'] = current_hash
                            st.session_state['fyers_upload_status'] = f"Successfully synced {upserted_count:,} record(s) to FyersTradeData table!"
                            st.rerun()

                if st.session_state.get('fyers_upload_status'):
                    st.success(st.session_state.get('fyers_upload_status'))

        except Exception as e:
            st.error(f"❌ Error processing file: {e}")
            with st.expander("Show details"):
                st.exception(e)
    else:
        if 'fyers_processed_hash' in st.session_state:
            del st.session_state['fyers_processed_hash']
        if 'fyers_upload_status' in st.session_state:
            del st.session_state['fyers_upload_status']

with tab_explorer:
    st.subheader("Database Overview (public.FyersTradeData)")
    
    if st.session_state.get('db_migration_result'):
        res = st.session_state.get('db_migration_result')
        if res.get('success'):
            st.success(f"🎉 **TradeMaster Migration Status:** {res.get('msg')}")
        else:
            st.error(f"❌ **TradeMaster Migration Status:** {res.get('msg')}")

    col_ref, col_mig, _ = st.columns([1, 1, 3])
    with col_ref:
        if st.button("🔄 Refresh DB Data", use_container_width=True):
            st.rerun()
    with col_mig:
        if st.button("🚀 Migrate", type="primary", use_container_width=True):
            show_migrate_dialog()



    with st.spinner("Fetching data from FyersTradeData table..."):
        db_df = fetch_fyers_trade_data()

    if db_df.empty:
        st.info("No trade data found in `FyersTradeData` table yet. Upload a tradebook file in the 'Upload & Sync' tab to populate this table.")
    else:
        # Filters
        f1, f2, f3, f4 = st.columns(4)
        
        with f1:
            search_query = st.text_input("Search Name / Symbol", placeholder="e.g. NIFTY or RELIANCE")
            
        with f2:
            seg_options = sorted([str(x) for x in db_df['Segment'].dropna().unique()]) if 'Segment' in db_df.columns else []
            selected_segs = st.multiselect("Filter Segment", options=seg_options, default=seg_options)
            
        with f3:
            side_options = sorted([str(x) for x in db_df['Side'].dropna().unique()]) if 'Side' in db_df.columns else []
            selected_sides = st.multiselect("Filter Side", options=side_options, default=side_options)

        with f4:
            prod_options = sorted([str(x) for x in db_df['Product type'].dropna().unique()]) if 'Product type' in db_df.columns else []
            selected_prods = st.multiselect("Filter Product Type", options=prod_options, default=prod_options)

        filtered_db_df = db_df.copy()

        if search_query:
            filtered_db_df = filtered_db_df[filtered_db_df['Name'].astype(str).str.contains(search_query, case=False, na=False)]

        if selected_segs and 'Segment' in filtered_db_df.columns:
            filtered_db_df = filtered_db_df[filtered_db_df['Segment'].astype(str).isin(selected_segs)]

        if selected_sides and 'Side' in filtered_db_df.columns:
            filtered_db_df = filtered_db_df[filtered_db_df['Side'].astype(str).isin(selected_sides)]

        if selected_prods and 'Product type' in filtered_db_df.columns:
            filtered_db_df = filtered_db_df[filtered_db_df['Product type'].astype(str).isin(selected_prods)]

        st.markdown(f"**Showing {len(filtered_db_df):,} of {len(db_df):,} total records**")

        st.dataframe(
            filtered_db_df,
            use_container_width=True,
            column_config={
                "orderID": st.column_config.NumberColumn("OMS Order ID", format="%d"),
                "DateTime": st.column_config.DatetimeColumn("Date & Time", format="YYYY-MM-DD HH:mm:ss"),
                "Traded price": st.column_config.NumberColumn("Traded Price (₹)", format="%.2f"),
                "Qty": st.column_config.NumberColumn("Quantity", format="%.2f"),
            }
        )

        # Download CSV option
        csv_data = filtered_db_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Filtered Data as CSV",
            data=csv_data,
            file_name="fyers_tradedata_export.csv",
            mime="text/csv"
        )
