import hashlib
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.title("My Performance Dashboard")
st.divider()

st.header("File Upload Data")
st.markdown("Upload your Trade Details Excel file below. It extracts and merges data from Fyers, AngelOne, Upstox, and Zerodha sheets into the TradeMaster format.")

from tradeMaster import build_trademaster
from chargesMaster import build_charges_dataframe
from DataProcessing import get_processed_data
from assets.ChartDrillDown import ChartDrillDown

uploaded_file = st.file_uploader(
    "Choose a Trade Details Excel file", 
    type=['xlsx', 'xls'], 
    help="Upload your Trade Details.xlsx file containing Fyers, AngelOne, Upstox, and/or Zerodha sheets",
    key="trade_details_file_uploader"
)

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    current_file_hash = hashlib.md5(file_bytes).hexdigest()
    
    if st.session_state.get('processed_file_hash') != current_file_hash:
        with st.spinner('Processing Trade & Charges data and updating database...'):
            try:
                xls = pd.ExcelFile(uploaded_file)
                
                trademaster_df = build_trademaster(xls)
                res_tm_msg = ""
                if not trademaster_df.empty:
                    from config.db import save_to_trademaster
                    res_tm = save_to_trademaster(trademaster_df)
                    inserted_count, updated_count = res_tm if isinstance(res_tm, tuple) else (res_tm, 0)
                    msg_parts = []
                    if inserted_count > 0:
                        msg_parts.append(f"added {inserted_count} new record(s)")
                    if updated_count > 0:
                        msg_parts.append(f"updated {updated_count} existing record(s)")
                    if msg_parts:
                        res_tm_msg = f"Successfully {' and '.join(msg_parts)} in the TradeMaster database!"
                    else:
                        res_tm_msg = "All trades in this file were already up-to-date in the database."
                else:
                    res_tm_msg = "No relevant Fyers, AngelOne, Upstox, or Zerodha trade data found."

                charges_df = build_charges_dataframe(xls)
                res_chg_msg = ""
                if not charges_df.empty:
                    from config.db import save_to_charges
                    res_chg = save_to_charges(charges_df)
                    inserted_charges, updated_charges = res_chg if isinstance(res_chg, tuple) else (res_chg, 0)
                    chg_parts = []
                    if inserted_charges > 0:
                        chg_parts.append(f"added {inserted_charges} new record(s)")
                    if updated_charges > 0:
                        chg_parts.append(f"updated {updated_charges} existing record(s)")
                    if chg_parts:
                        res_chg_msg = f"Successfully {' and '.join(chg_parts)} in the Charges database!"
                    else:
                        res_chg_msg = "All charges in this file were already up-to-date in the database."
                else:
                    res_chg_msg = "No relevant Charges data found."

                # Clear cache so get_processed_data fetches updated DB data immediately
                get_processed_data.clear()

                st.session_state['processed_file_hash'] = current_file_hash
                st.session_state['upload_summary'] = {
                    'filename': uploaded_file.name,
                    'tm_records': len(trademaster_df),
                    'tm_msg': res_tm_msg,
                    'chg_records': len(charges_df),
                    'chg_msg': res_chg_msg,
                    'error': None
                }
                
                st.rerun()

            except Exception as e:
                import traceback
                st.session_state['upload_summary'] = {
                    'filename': uploaded_file.name,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }

    summary = st.session_state.get('upload_summary')
    if summary:
        if summary.get('error'):
            st.error(f"An error occurred while processing '{summary.get('filename')}': {summary.get('error')}")
            with st.expander("Show stack trace"):
                st.code(summary.get('traceback', ''))
        else:
            st.success(f"File **'{summary.get('filename')}'** uploaded and processed successfully!")
            st.info(f"📈 TradeMaster: {summary.get('tm_msg')} ({summary.get('tm_records', 0)} record(s) parsed)")
            st.info(f"📉 Charges: {summary.get('chg_msg')} ({summary.get('chg_records', 0)} record(s) parsed)")

else:
    if 'processed_file_hash' in st.session_state:
        del st.session_state['processed_file_hash']
    if 'upload_summary' in st.session_state:
        del st.session_state['upload_summary']

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

st.header("📊 Performance Drill Down")

drilldown_segment_options = []
if not cached_trades.empty and 'Segment' in cached_trades.columns:
    drilldown_segment_options = sorted([str(x) for x in cached_trades['Segment'].dropna().unique().tolist()])

selected_drilldown_segment = st.multiselect(
    "Filter by Segment", 
    options=drilldown_segment_options, 
    default=drilldown_segment_options,
    key="drilldown_segment_filter"
)

drilldown_df = cached_trades.copy()
if not drilldown_df.empty:
    exit_date_col = 'ExitedDate' if 'ExitedDate' in drilldown_df.columns else 'exiteddate'
    if exit_date_col in drilldown_df.columns:
        drilldown_df['Week'] = pd.to_datetime(drilldown_df[exit_date_col]).dt.isocalendar().week
else:
    drilldown_df['Week'] = pd.Series(dtype='int32')

if not drilldown_df.empty and 'Segment' in drilldown_df.columns and selected_drilldown_segment:
    drilldown_df = drilldown_df[drilldown_df['Segment'].astype(str).isin(selected_drilldown_segment)]


FY_MONTH_ORDER = [
    "April", "May", "June",
    "July", "August", "September",
    "October", "November", "December",
    "January", "February", "March"
]

col_toggle1, col_toggle2 = st.columns([2, 1])
with col_toggle1:
    view_mode = st.radio(
        "View Mode",
        options=["📊 Drill Down Chart", "📅 Calendar View"],
        horizontal=True,
        key="performance_view_toggle"
    )

if view_mode == "📊 Drill Down Chart":
    ChartDrillDown.drill_down_chart(
        df=drilldown_df,
        level_config=[
            {"name": "FY", "group_col": "FY", "tooltip": ["P&L", "P&L Without Charge"]},
            {"name": "Quarter", "group_col": "Quarter", "tooltip": ["P&L", "P&L Without Charge"]},
            {"name": "Month", "group_col": "Month", "tooltip": ["P&L", "P&L Without Charge"]},
            {"name": "Week", "group_col": "Week", "tooltip": ["P&L", "P&L Without Charge"]},
            {"name": "Day", "group_col": "Day", "tooltip": ["P&L", "P&L Without Charge"]},
            {"name": "Instrument", "group_col": "Instrument", "tooltip": ["P&L", "P&L Without Charge"]},
            
        ],
        metric_col="P&L",
        sort_config={
            "FY": {"type": "label_asc"},
            "Quarter": {"type": "label_asc"},
            "Month": {"type": "custom", "order": FY_MONTH_ORDER},
            "Week": {"type": "label_asc"},
            "Day": {"type": "label_asc"},
        }
    )
else:
    ChartDrillDown.drill_down_calendar_view(
        df=drilldown_df,
        charges_df=cached_charges,
        key_prefix="perf_calendar"
    )

st.divider()

st.header("📉 Charges Drill Down")

if not cached_charges.empty:
    ChartDrillDown.drill_down_line_chart(
        df=cached_charges,
        level_config=[
            {"name": "FY", "group_col": "FY", "tooltip": ["Charge"]},
            {"name": "Month", "group_col": "Month", "tooltip": ["Charge"]},
            {"name": "Day", "group_col": "Day", "tooltip": ["Charge"]},
        ],
        key_prefix="charges_chart",
        metric_col="Charge",
        sort_config={
            "FY": {"type": "label_asc"},
            "Month": {"type": "custom", "order": FY_MONTH_ORDER},
            "Day": {"type": "label_asc"},
        }
    )
else:
    st.info("No charges data available in database.")

st.divider()
st.header("🏆 Top & Bottom Trades")

col_filter1, col_filter2, col_filter3 = st.columns(3)

with col_filter1:
    top_n = st.slider("Trades count (n)", min_value=1, max_value=100, value=10)
    
fy_options = []
if not cached_trades.empty and 'FY' in cached_trades.columns:
    fy_options = sorted([str(x) for x in cached_trades['FY'].dropna().unique().tolist()])

segment_options = []
if not cached_trades.empty and 'Segment' in cached_trades.columns:
    segment_options = sorted([str(x) for x in cached_trades['Segment'].dropna().unique().tolist()])

with col_filter2:
    selected_fy = st.multiselect("Filter by FY", options=fy_options, default=fy_options)

with col_filter3:
    selected_segment = st.multiselect("Filter by Segment", options=segment_options, default=segment_options)

if not cached_trades.empty and "P&L" in cached_trades.columns and "Instrument" in cached_trades.columns:
    
    # Apply filters
    filtered_trades = cached_trades.copy()
    if 'FY' in filtered_trades.columns and selected_fy:
        filtered_trades = filtered_trades[filtered_trades['FY'].astype(str).isin(selected_fy)]
    if 'Segment' in filtered_trades.columns and selected_segment:
        filtered_trades = filtered_trades[filtered_trades['Segment'].astype(str).isin(selected_segment)]
        
    # Get Top trades (only considering P&L > 0) and Bottom trades (only considering P&L < 0)
    positive_trades = filtered_trades[filtered_trades["P&L"] > 0]
    negative_trades = filtered_trades[filtered_trades["P&L"] < 0]
    
    top_trades = positive_trades.nlargest(top_n, "P&L").copy()
    bottom_trades = negative_trades.nsmallest(top_n, "P&L").copy()

    # Sort values so the best/worst trades appear at the top of their respective charts
    top_trades = top_trades.sort_values(by="P&L", ascending=True)
    bottom_trades = bottom_trades.sort_values(by="P&L", ascending=False)
    
    # Create unique IDs for the Y-axis to prevent grouping of identical instruments
    top_trades["Unique_ID"] = top_trades.index.astype(str) + "_" + top_trades["Instrument"].astype(str)
    bottom_trades["Unique_ID"] = bottom_trades.index.astype(str) + "_" + bottom_trades["Instrument"].astype(str)
    
    hover_cols = [col for col in ["Instrument", "P&L", "P&L Without Charge"] if col in cached_trades.columns]

    col_top, col_bottom = st.columns(2)

    with col_top:
        st.subheader(f"Top {top_n} Trades")
        fig_top = px.bar(
            top_trades,
            x="P&L",
            y="Unique_ID",
            orientation='h',
            hover_data=hover_cols,
            color_discrete_sequence=['#2e7b32']
        )
        fig_top.update_layout(yaxis_title="Instrument", xaxis_title="P&L", showlegend=False)
        fig_top.update_yaxes(tickmode='array', tickvals=top_trades["Unique_ID"], ticktext=top_trades["Instrument"])
        st.plotly_chart(fig_top, use_container_width=True)


    with col_bottom:
        st.subheader(f"Bottom {top_n} Trades")
        fig_bottom = px.bar(
            bottom_trades,
            x="P&L",
            y="Unique_ID",
            orientation='h',
            hover_data=hover_cols,
            color_discrete_sequence=['#c62828']
        )
        fig_bottom.update_layout(yaxis_title="Instrument", xaxis_title="P&L", showlegend=False)
        fig_bottom.update_yaxes(tickmode='array', tickvals=bottom_trades["Unique_ID"], ticktext=bottom_trades["Instrument"])
        st.plotly_chart(fig_bottom, use_container_width=True)

    # ---------------------------
    # SYMBOL PERFORMANCE
    # ---------------------------
    st.divider()
    st.header("📈 Symbol Performance")

    if not filtered_trades.empty:
        # Clean up Symbol column to ensure casing and whitespace consistency
        trades_for_symbol = filtered_trades.copy()
        trades_for_symbol["Symbol"] = trades_for_symbol["Symbol"].astype(str).str.strip().str.upper()
        
        # Group by Symbol and sum P&L
        symbol_perf = trades_for_symbol.groupby("Symbol", as_index=False)["P&L"].sum()
        
        # Sort values so higher values are at the top of the chart
        symbol_perf = symbol_perf.sort_values(by="P&L", ascending=True)
        
        # Add conditional coloring column
        symbol_perf["Color"] = symbol_perf["P&L"].apply(lambda x: "Positive" if x >= 0 else "Negative")
        
        fig_symbol = px.bar(
            symbol_perf,
            x="P&L",
            y="Symbol",
            orientation='h',
            color="Color",
            color_discrete_map={
                "Positive": "#2e7b32",  # Green
                "Negative": "#c62828"   # Red
            },
            hover_data={"Symbol": True, "P&L": ":.2f", "Color": False}
        )
        
        # Responsive height based on number of symbols to prevent overlapping labels
        chart_height = max(400, len(symbol_perf) * 25)
        
        fig_symbol.update_layout(
            yaxis_title="Symbol",
            xaxis_title="P&L",
            showlegend=False,
            height=chart_height
        )
        
        st.plotly_chart(fig_symbol, use_container_width=True)
    else:
        st.info("No trade data available for the selected filters.")
