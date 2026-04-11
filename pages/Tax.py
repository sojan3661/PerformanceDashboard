import streamlit as st
import pandas as pd
import plotly.express as px
from DataProcessing import get_processed_data

st.title("Tax Estimated Breakdown")
st.markdown("Estimation of your taxes based on realized trades across all Financial Years.")
st.divider()

with st.spinner("Loading data..."):
    try:
        cached_trades, _ = get_processed_data()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.stop()

if cached_trades.empty:
    st.info("No trades data available.")
    st.stop()

# Basic Date Checks and Holding Period
trade_df = cached_trades.copy()
trade_df['EnteredDate'] = pd.to_datetime(trade_df['EnteredDate'], errors='coerce')
trade_df['ExitedDate'] = pd.to_datetime(trade_df['ExitedDate'], errors='coerce')
trade_df['Holding_Days'] = (trade_df['ExitedDate'] - trade_df['EnteredDate']).dt.days

# Define Tax Segment
def get_tax_segment(row):
    segment = str(row.get('Segment', '')).strip()
    days = row.get('Holding_Days', -1)
    
    if segment in ['Options', 'Futures']:
        return 'Trading'
    elif segment == 'Equity & Mutual Fund':
        if pd.isna(days):
            return 'Short Term'
        if days > 365:
            return 'Long Term'
        else:
            return 'Short Term'
    else:
        return 'Trading'

trade_df['Tax_Segment'] = trade_df.apply(get_tax_segment, axis=1)

if 'P&L' not in trade_df.columns:
    if 'P&L Without Charge' in trade_df.columns:
        trade_df['P&L'] = trade_df['P&L Without Charge']
    else:
        st.warning("Missing P&L metric in the database.")
        st.stop()

trade_df['P&L'] = pd.to_numeric(trade_df['P&L'], errors='coerce').fillna(0)

# Tax rules per regime
def get_regime_and_rules(fy_str):
    if pd.isna(fy_str):
        return 'Old', 100000, {'Short Term': 0.15, 'Long Term': 0.10, 'Trading': 0.30}
    parts = fy_str.split('-')
    if len(parts) == 2 and parts[0].isdigit() and int(parts[0]) >= 2024:
        return 'New', 125000, {'Short Term': 0.20, 'Long Term': 0.125, 'Trading': 0.30}
    return 'Old', 100000, {'Short Term': 0.15, 'Long Term': 0.10, 'Trading': 0.30}

# Process every FY independently to compute exemption correctly
summary_data = []

unique_fys = trade_df['FY'].dropna().unique()
for fy in unique_fys:
    fy_df = trade_df[trade_df['FY'] == fy]
    regime, exemption, rates = get_regime_and_rules(fy)
    
    sfy = fy_df.groupby('Tax_Segment', as_index=False)['P&L'].sum()
    
    # Ensure all segments exist
    for seg in ['Short Term', 'Long Term', 'Trading']:
        if seg not in sfy['Tax_Segment'].values:
            new_row = pd.DataFrame([{'Tax_Segment': seg, 'P&L': 0.0}])
            sfy = pd.concat([sfy, new_row], ignore_index=True)
            
    # Calculate tax
    for _, row in sfy.iterrows():
        segment = row['Tax_Segment']
        pl = row['P&L']
        tax_to_pay = 0.0
        
        if pl > 0:
            if segment == 'Long Term':
                taxable_pl = max(0.0, pl - exemption)
                tax_to_pay = taxable_pl * rates[segment]
            else:
                tax_to_pay = pl * rates[segment]
                
        summary_data.append({
            'FY': str(fy),
            'Tax_Segment': segment,
            'P&L': pl,
            'Tax_To_Pay': tax_to_pay,
            'Regime': regime,
            'Tax_Rate': f"{rates[segment]*100}%",
            'Exemption': exemption
        })

master_df = pd.DataFrame(summary_data)

if master_df.empty:
    st.info("No recognized FY data to compute taxes.")
    st.stop()

# ----------------- Drilldown State Control -----------------
if "tax_selected_fy" not in st.session_state:
    st.session_state.tax_selected_fy = None

selected_fy = st.session_state.tax_selected_fy

# ------------------- LEVEL 1: ALL FY View -------------------
if selected_fy is None:
    st.subheader(f"All Financial Years Overview")
    
    # Aggregate by FY
    fy_agg = master_df.groupby('FY', as_index=False)[['P&L', 'Tax_To_Pay']].sum()
    fy_agg = fy_agg.sort_values('FY', ascending=True)
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("**Data Table**")
        st.dataframe(
            fy_agg,
            column_config={
                'FY': 'Financial Year',
                'P&L': st.column_config.NumberColumn('Total P&L', format="₹ %.2f"),
                'Tax_To_Pay': st.column_config.NumberColumn('Estimated Tax', format="₹ %.2f"),
            },
            use_container_width=True,
            hide_index=True
        )
        st.info("💡 **Click on a bar in the chart** to drill down into its Segment breakdown.")
        
    with col2:
        plot_df = fy_agg.melt(id_vars=['FY'], value_vars=['P&L', 'Tax_To_Pay'], var_name='Metric', value_name='Amount')
        plot_df['Metric'] = plot_df['Metric'].map({'P&L': 'Total P&L', 'Tax_To_Pay': 'Estimated Tax'})
        
        fig = px.bar(
            plot_df, 
            x='FY', 
            y='Amount', 
            color='Metric', 
            barmode='group',
            color_discrete_map={'Total P&L': '#2e7b32', 'Estimated Tax': '#d62728'},
            title="P&L vs Estimated Tax by Financial Year"
        )
        fig.update_layout(xaxis_title="Financial Year", yaxis_title="Amount (₹)", legend_title_text="Metric", clickmode="event+select")
        
        event = st.plotly_chart(
            fig, 
            use_container_width=True, 
            on_select="rerun", 
            selection_mode="points",
            key="fy_drilldown_click"
        )
        
        # Handle interaction selection
        points = []
        if event and hasattr(event, "selection"):
            points = getattr(event.selection, "points", [])
        elif isinstance(event, dict):
            points = event.get("selection", {}).get("points", [])
            
        if points:
            clicked_fy = points[0].get("x")
            if clicked_fy:
                st.session_state.tax_selected_fy = clicked_fy
                st.rerun()

# ------------------- LEVEL 2: Segment View for FY -------------------
else:
    if st.button("⬅️ Back to All FY Overview"):
        st.session_state.tax_selected_fy = None
        st.rerun()
        
    filtered_df = master_df[master_df['FY'] == selected_fy]
    
    if filtered_df.empty:
        st.info("No data for this FY.")
        st.stop()
        
    regime_display = "After FY 2024-25" if filtered_df.iloc[0]['Regime'] == 'New' else "Before FY 2023-24"
    exemption_amt = filtered_df.iloc[0]['Exemption']
    
    st.subheader(f"Tax Breakdown for {selected_fy} ({regime_display} Rules)")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("**Data Table**")
        st.dataframe(
            filtered_df[['Tax_Segment', 'P&L', 'Tax_Rate', 'Tax_To_Pay']],
            column_config={
                'Tax_Segment': 'Segment',
                'P&L': st.column_config.NumberColumn('Total P&L', format="₹ %.2f"),
                'Tax_Rate': 'Applied Tax Rate',
                'Tax_To_Pay': st.column_config.NumberColumn('Estimated Tax', format="₹ %.2f"),
            },
            use_container_width=True,
            hide_index=True
        )
        st.info(f"💡 **Long Term Gain Exemption used:** ₹{exemption_amt:,}")
        
    with col2:
        plot_df = filtered_df.melt(id_vars=['Tax_Segment'], value_vars=['P&L', 'Tax_To_Pay'], var_name='Metric', value_name='Amount')
        plot_df['Metric'] = plot_df['Metric'].map({'P&L': 'Total P&L', 'Tax_To_Pay': 'Estimated Tax'})

        fig = px.bar(
            plot_df, 
            x='Tax_Segment', 
            y='Amount', 
            color='Metric', 
            barmode='group',
            color_discrete_map={'Total P&L': '#2e7b32', 'Estimated Tax': '#d62728'},
            title=f"P&L vs Estimated Tax by Segment ({selected_fy})"
        )
        fig.update_layout(xaxis_title="Segment", yaxis_title="Amount (₹)", legend_title_text="Metric")
        
        st.plotly_chart(fig, use_container_width=True)
