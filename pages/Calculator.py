import streamlit as st
import pandas as pd
from DataProcessing import get_processed_data

st.set_page_config(
    page_title="Calculator | Performance Dashboard",
    page_icon="🧮",
    layout="wide"
)

st.title("🧮 Payout & P&L Calculator")
st.markdown("Calculate payout allocations based on net P&L after charges for selected Financial Years and Months.")
st.divider()

# Load processed data
with st.spinner("Fetching performance data..."):
    try:
        cached_trades, _ = get_processed_data()
    except Exception as e:
        st.error(f"Error loading trade data: {e}")
        st.stop()

if cached_trades.empty:
    st.info("No trade data available in database. Upload trade files on the Performance page to begin.")
    st.stop()

trade_df = cached_trades.copy()

# Month ordering
FY_MONTH_ORDER = [
    "April", "May", "June",
    "July", "August", "September",
    "October", "November", "December",
    "January", "February", "March"
]

# Extract available FYs and Months
available_fys = sorted([str(fy) for fy in trade_df['FY'].dropna().unique() if str(fy).strip()])
fy_options = ["All FY"] + available_fys

# Filters Section
st.header("1. Select Period")
col_fy, col_month = st.columns(2)

with col_fy:
    selected_fy = st.selectbox(
        "Financial Year (FY)",
        options=fy_options,
        index=len(fy_options) - 1 if len(fy_options) > 1 else 0,
        key="calc_selected_fy"
    )

# Filter trade dataframe by FY first to suggest relevant months
filtered_by_fy = trade_df.copy()
if selected_fy != "All FY":
    filtered_by_fy = filtered_by_fy[filtered_by_fy['FY'] == selected_fy]

available_months_in_fy = [m for m in FY_MONTH_ORDER if m in filtered_by_fy['Month'].unique()]
month_options = ["All Months"] + (available_months_in_fy if available_months_in_fy else FY_MONTH_ORDER)

with col_month:
    selected_month = st.selectbox(
        "Month",
        options=month_options,
        index=0,
        key="calc_selected_month"
    )

# Apply Month filter
filtered_df = filtered_by_fy.copy()
if selected_month != "All Months":
    filtered_df = filtered_df[filtered_df['Month'] == selected_month]

# Calculate Net P&L metrics for selected period
trade_count = len(filtered_df)
gross_pl = filtered_df['P&L Without Charge'].sum() if 'P&L Without Charge' in filtered_df.columns else 0.0
charges = (filtered_df['EnteredTradeCharges'].sum() + filtered_df['ExitedTradeCharges'].sum()) if 'EnteredTradeCharges' in filtered_df.columns and 'ExitedTradeCharges' in filtered_df.columns else 0.0
net_pl_after_charge = filtered_df['P&L'].sum() if 'P&L' in filtered_df.columns else 0.0

st.write("")
st.subheader("Period Summary")
metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

metric_col1.metric("Total Trades", f"{trade_count}")
metric_col2.metric("Gross P&L", f"₹ {gross_pl:,.2f}")
metric_col3.metric("Total Charges", f"₹ {charges:,.2f}")

if net_pl_after_charge > 0:
    metric_col4.metric("Net P&L (After Charge)", f"₹ {net_pl_after_charge:,.2f}", delta="Positive P&L", delta_color="normal")
else:
    metric_col4.metric("Net P&L (After Charge)", f"₹ {net_pl_after_charge:,.2f}", delta="Non-Positive", delta_color="inverse")

st.divider()

# Purpose and Percentage Management
st.header("2. Purpose & Percentage Allocation")
st.markdown("Add one or more payout purposes with their assigned percentage.")

# Initialize session state for entries
if "calc_entries" not in st.session_state or not st.session_state.calc_entries:
    st.session_state.calc_entries = [
        {"purpose": "Profit Allocation 1", "percentage": 10.0}
    ]

# Callback handlers for dynamic entries
def add_entry():
    st.session_state.calc_entries.append({"purpose": f"Purpose {len(st.session_state.calc_entries) + 1}", "percentage": 10.0})

def remove_entry(index):
    if len(st.session_state.calc_entries) > 1:
        st.session_state.calc_entries.pop(index)

# Render input rows
for i, entry in enumerate(st.session_state.calc_entries):
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        st.session_state.calc_entries[i]["purpose"] = st.text_input(
            f"Purpose #{i+1}",
            value=entry["purpose"],
            key=f"purpose_{i}"
        )
    with c2:
        st.session_state.calc_entries[i]["percentage"] = st.number_input(
            f"Percentage (%) #{i+1}",
            min_value=0.0,
            max_value=100.0,
            value=float(entry["percentage"]),
            step=1.0,
            format="%.2f",
            key=f"percentage_{i}"
        )
    with c3:
        st.write("")
        st.write("")
        if len(st.session_state.calc_entries) > 1:
            st.button("🗑️ Remove", key=f"remove_{i}", on_click=remove_entry, args=(i,))

col_add, col_reset = st.columns([1, 4])
with col_add:
    st.button("➕ Add Purpose", on_click=add_entry, use_container_width=True)

st.divider()

# Calculation Section
st.header("3. Calculate Payouts")

calculate_clicked = st.button("📊 Calculate", type="primary", use_container_width=True)

if calculate_clicked or "has_calculated" in st.session_state:
    st.session_state.has_calculated = True
    
    st.subheader("Calculation Results")
    
    if net_pl_after_charge > 0:
        total_allocated_pct = sum(item["percentage"] for item in st.session_state.calc_entries)
        
        results = []
        total_payout = 0.0
        
        for item in st.session_state.calc_entries:
            purpose_text = item["purpose"].strip() or "Unspecified Purpose"
            pct = item["percentage"]
            payout_amt = net_pl_after_charge * (pct / 100.0)
            total_payout += payout_amt
            
            results.append({
                "Purpose": purpose_text,
                "Percentage (%)": f"{pct:.2f}%",
                "Payout Amount (₹)": payout_amt
            })
            
        results_df = pd.DataFrame(results)
        
        st.success(f"✅ Net P&L after charge is positive (**₹ {net_pl_after_charge:,.2f}**). Payout table generated below:")
        
        st.dataframe(
            results_df,
            column_config={
                "Purpose": st.column_config.TextColumn("Purpose", help="Target purpose for payout allocation"),
                "Percentage (%)": st.column_config.TextColumn("Percentage", help="Allocated percentage of Net P&L"),
                "Payout Amount (₹)": st.column_config.NumberColumn("Payout Amount", format="₹ %.2f", help="Calculated payout amount based on percentage")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Summary Statistics
        res_col1, res_col2, res_col3, res_col4 = st.columns(4)
        res_col1.metric("Net P&L (After Charge)", f"₹ {net_pl_after_charge:,.2f}")
        res_col2.metric("Total Percentage", f"{total_allocated_pct:.2f}%")
        res_col3.metric("Total Payout", f"₹ {total_payout:,.2f}")
        remaining_pl = net_pl_after_charge - total_payout
        res_col4.metric("Remaining P&L", f"₹ {remaining_pl:,.2f}")
        
        if total_allocated_pct > 100.0:
            st.warning(f"⚠️ Total allocated percentage ({total_allocated_pct:.2f}%) exceeds 100%. Total payout exceeds net P&L.")
            
    else:
        st.warning(f"⚠️ Net P&L after charge for selected period ({selected_fy}, {selected_month}) is **₹ {net_pl_after_charge:,.2f}**.\n\nSince Net P&L after charge is not positive (<= 0), no payout table is generated.")
