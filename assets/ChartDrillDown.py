import streamlit as st
import pandas as pd
import plotly.express as px


class ChartGenerator:
    """
    Utility class responsible for generating Plotly bar charts.

    Features:
    - Conditional coloring (Positive = Green, Negative = Red)
    - Sorting preservation even with color grouping
    - Custom tooltips
    - Clean UI (legend hidden)
    - Zoom enabled on Y-axis
    """

    @staticmethod
    def create_bar_chart(
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        title: str = "",
        tooltip_cols: list = None,
        category_order: list = None
    ):
        """
        Creates a Plotly bar chart with conditional coloring and custom tooltips.

        Args:
            df (pd.DataFrame):
                Input dataframe (already aggregated if needed).

            x_col (str):
                Column name for X-axis (categorical).

            y_col (str):
                Column name for Y-axis (numeric).

            title (str, optional):
                Chart title.

            tooltip_cols (list, optional):
                Columns to display in tooltip.
                Example: ["P&L", "Marks"]

            category_order (list, optional):
                Custom order for X-axis categories.

        Returns:
            plotly.graph_objects.Figure:
                Configured Plotly bar chart.
        """

        df = df.copy()

        # ---------------------------
        # CONDITIONAL COLORING
        # ---------------------------
        df["_color"] = df[y_col].apply(
            lambda x: "Positive" if x >= 0 else "Negative"
        )

        # ---------------------------
        # PRESERVE SORT ORDER
        # ---------------------------
        if category_order:
            category_order_final = category_order
        else:
            category_order_final = df[x_col].tolist()

        # ---------------------------
        # CREATE BAR CHART
        # ---------------------------
        hover_data_dict = {"_color": False, x_col: False}
        if tooltip_cols:
            for col in tooltip_cols:
                hover_data_dict[col] = True
        else:
            hover_data_dict[y_col] = True

        fig = px.bar(
            df,
            x=x_col,
            y=y_col,
            title=title,
            color="_color",
            color_discrete_map={
                "Positive": "green",
                "Negative": "red"
            },
            category_orders={x_col: category_order_final},
            hover_data=hover_data_dict
        )

        # ---------------------------
        # CLEAN UI SETTINGS
        # ---------------------------
        fig.update_layout(
            showlegend=False,             # hide Positive/Negative legend
            yaxis=dict(fixedrange=False), # enable zoom
            xaxis=dict(type='category')   # force X-axis to categorical to avoid decimal ticks
        )

        # ---------------------------
        # CUSTOM TOOLTIP
        # ---------------------------
        for trace in fig.data:
            if trace.hovertemplate:
                trace.hovertemplate = trace.hovertemplate.replace("=", ": ")

        return fig

    @staticmethod
    def create_line_chart(
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        title: str = "",
        tooltip_cols: list = None,
        category_order: list = None
    ):
        """
        Creates a Plotly line chart with markers.

        Args:
            df (pd.DataFrame): Input dataframe (already aggregated).
            x_col (str): Column name for X-axis (categorical).
            y_col (str): Column name for Y-axis (numeric).
            title (str, optional): Chart title.
            tooltip_cols (list, optional): Columns to display in tooltip.
            category_order (list, optional): Custom order for X-axis categories.

        Returns:
            plotly.graph_objects.Figure: Configured Plotly line chart.
        """
        df = df.copy()

        if category_order:
            df[x_col] = df[x_col].astype(str)
            cat_list = [str(c) for c in category_order]
            df[x_col] = pd.Categorical(df[x_col], categories=cat_list, ordered=True)
            df = df.sort_values(by=x_col)
            category_order_final = cat_list
        else:
            category_order_final = df[x_col].tolist()

        hover_data_dict = {x_col: False}
        if tooltip_cols:
            for col in tooltip_cols:
                hover_data_dict[col] = True
        else:
            hover_data_dict[y_col] = True

        fig = px.line(
            df,
            x=x_col,
            y=y_col,
            title=title,
            category_orders={x_col: category_order_final},
            hover_data=hover_data_dict,
            markers=True
        )

        fig.update_traces(
            line=dict(color='#6366F1', width=3),
            marker=dict(size=8, color='#4F46E5', symbol='circle')
        )

        fig.update_layout(
            showlegend=False,
            yaxis=dict(fixedrange=False),
            xaxis=dict(type='category')
        )

        for trace in fig.data:
            if trace.hovertemplate:
                trace.hovertemplate = trace.hovertemplate.replace("=", ": ")

        return fig


class ChartDrillDown:
    """
    Provides hierarchical drill-down functionality using Plotly + Streamlit.

    Features:
    - Multi-level drill-down
    - Click-based navigation
    - Back navigation
    - Level-specific tooltips
    - Sorting support
    - CSV download
    """

    @staticmethod
    def drill_down_chart(
        df: pd.DataFrame,
        level_config: list,
        key_prefix: str = "chart",
        enable_download: bool = True,
        metric_col: str = "P&L",
        sort_config: dict = None
    ):
        """
        Renders a drill-down interactive bar chart.

        Args:
            df (pd.DataFrame):
                Source dataset.

            level_config (list[dict]):
                Defines hierarchy levels.

                Each level supports:
                    - name (str): Display name
                    - group_col (str): Column used for grouping
                    - tooltip (list): Tooltip fields for that level

                Example:
                    [
                        {"name": "Total", "group_col": "Total", "tooltip": ["P&L"]},
                        {"name": "Exam", "group_col": "Exam", "tooltip": ["P&L", "Marks"]},
                        {"name": "Subject", "group_col": "Subject", "tooltip": ["P&L", "Marks", "Grade"]}
                    ]

            key_prefix (str, optional):
                Unique identifier for session state.

            enable_download (bool, optional):
                Enables CSV download button.

            metric_col (str, optional):
                Numeric column used for aggregation.

            sort_config (dict, optional):
                Sorting rules per level.

                Types:
                    - "asc" / "desc"
                    - "label_asc" / "label_desc"
                    - "custom"

        Returns:
            None
        """

        # ---------------------------
        # INITIALIZE SESSION STATE
        # ---------------------------
        for i in range(len(level_config)):
            key = f"{key_prefix}_level_{i}"
            if key not in st.session_state:
                st.session_state[key] = None

        # ---------------------------
        # DETERMINE CURRENT LEVEL
        # ---------------------------
        current_level = 0
        for i in range(len(level_config)):
            if st.session_state[f"{key_prefix}_level_{i}"] is None:
                current_level = i
                break
        else:
            # Prevent going beyond last level
            current_level = len(level_config) - 1

        # ---------------------------
        # APPLY FILTERS BASED ON SELECTION
        # ---------------------------
        filtered_df = df.copy()
        for i in range(current_level):
            col = level_config[i]["group_col"]
            val = st.session_state[f"{key_prefix}_level_{i}"]
            
            # Type-safe filter comparison
            col_series = filtered_df[col]
            if pd.api.types.is_integer_dtype(col_series):
                try:
                    val = int(float(val))
                except (ValueError, TypeError):
                    pass
                filtered_df = filtered_df[col_series == val]
            elif pd.api.types.is_float_dtype(col_series):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    pass
                filtered_df = filtered_df[col_series == val]
            else:
                filtered_df = filtered_df[col_series.astype(str) == str(val)]

        # ---------------------------
        # BACK NAVIGATION
        # ---------------------------
        if current_level > 0:
            if st.button("⬅️ Back"):
                st.session_state[f"{key_prefix}_level_{current_level-1}"] = None
                st.rerun()

        # ---------------------------
        # CURRENT LEVEL CONFIG
        # ---------------------------
        is_final = current_level == len(level_config) - 1
        config = level_config[current_level]
        group_col = config["group_col"]

        # ---------------------------
        # AGGREGATION (SUPPORT TOOLTIP FIELDS)
        # ---------------------------
        agg_dict = {metric_col: "sum"}

        tooltip_cols = config.get("tooltip", [metric_col])

        for col in tooltip_cols:
            if col != metric_col and col in filtered_df.columns:
                if pd.api.types.is_numeric_dtype(filtered_df[col]):
                    agg_dict[col] = "sum"
                else:
                    agg_dict[col] = "first"

        summary = (
            filtered_df
            .groupby(group_col, as_index=False)
            .agg(agg_dict)
        )

        summary[metric_col] = summary[metric_col].round(2)

        # ---------------------------
        # SORTING LOGIC
        # ---------------------------
        category_order = None

        if sort_config and group_col in sort_config:
            sconf = sort_config[group_col]
            stype = sconf.get("type")

            if stype == "custom":
                category_order = sconf.get("order")

            elif stype in ["asc", "desc"]:
                summary = summary.sort_values(
                    by=metric_col,
                    ascending=(stype == "asc")
                )

            elif stype in ["label_asc", "label_desc"]:
                summary = summary.sort_values(
                    by=group_col,
                    ascending=(stype == "label_asc")
                )

        # ---------------------------
        # GENERATE CHART
        # ---------------------------
        fig = ChartGenerator.create_bar_chart(
            summary,
            x_col=group_col,
            y_col=metric_col,
            title=f"{config['name']} View" + (" (Final)" if is_final else ""),
            tooltip_cols=tooltip_cols,
            category_order=category_order
        )

        # ---------------------------
        # DISPLAY CHART
        # ---------------------------
        event = st.plotly_chart(
            fig,
            use_container_width=True,
            on_select="rerun",
            selection_mode="points",
            key=f"{key_prefix}_{current_level}"
        )

        # ---------------------------
        # STOP AT FINAL LEVEL
        # ---------------------------
        if is_final:
            st.info("Final level reached - no further drill-down")
            return

        # ---------------------------
        # HANDLE CLICK EVENT
        # ---------------------------
        selected = None
        points = []

        if event and hasattr(event, "selection"):
            points = getattr(event.selection, "points", [])
        elif isinstance(event, dict):
            points = event.get("selection", {}).get("points", [])

        if points:
            selected = points[0].get("x")

        if selected:
            st.session_state[f"{key_prefix}_level_{current_level}"] = selected
            st.rerun()

        # ---------------------------
        # DOWNLOAD OPTION
        # ---------------------------
        if enable_download:
            csv = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download Data",
                data=csv,
                file_name=f"{config['name']}_data.csv",
                mime="text/csv"
            )

    @staticmethod
    def drill_down_line_chart(
        df: pd.DataFrame,
        level_config: list,
        key_prefix: str = "line_chart",
        enable_download: bool = True,
        metric_col: str = "Charge",
        sort_config: dict = None
    ):
        """
        Renders a drill-down interactive line chart.

        Args:
            df (pd.DataFrame): Source dataset.
            level_config (list[dict]): Defines hierarchy levels.
            key_prefix (str, optional): Unique identifier for session state.
            enable_download (bool, optional): Enables CSV download button.
            metric_col (str, optional): Numeric column used for aggregation.
            sort_config (dict, optional): Sorting rules per level.
        """
        # ---------------------------
        # INITIALIZE SESSION STATE
        # ---------------------------
        for i in range(len(level_config)):
            key = f"{key_prefix}_level_{i}"
            if key not in st.session_state:
                st.session_state[key] = None

        # ---------------------------
        # DETERMINE CURRENT LEVEL
        # ---------------------------
        current_level = 0
        for i in range(len(level_config)):
            if st.session_state[f"{key_prefix}_level_{i}"] is None:
                current_level = i
                break
        else:
            current_level = len(level_config) - 1

        # ---------------------------
        # APPLY FILTERS BASED ON SELECTION
        # ---------------------------
        filtered_df = df.copy()
        for i in range(current_level):
            col = level_config[i]["group_col"]
            val = st.session_state[f"{key_prefix}_level_{i}"]
            
            col_series = filtered_df[col]
            if pd.api.types.is_integer_dtype(col_series):
                try:
                    val = int(float(val))
                except (ValueError, TypeError):
                    pass
                filtered_df = filtered_df[col_series == val]
            elif pd.api.types.is_float_dtype(col_series):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    pass
                filtered_df = filtered_df[col_series == val]
            else:
                filtered_df = filtered_df[col_series.astype(str) == str(val)]

        # ---------------------------
        # BACK NAVIGATION
        # ---------------------------
        if current_level > 0:
            if st.button("⬅️ Back", key=f"{key_prefix}_back_btn"):
                st.session_state[f"{key_prefix}_level_{current_level-1}"] = None
                st.rerun()

        # ---------------------------
        # CURRENT LEVEL CONFIG
        # ---------------------------
        is_final = current_level == len(level_config) - 1
        config = level_config[current_level]
        group_col = config["group_col"]

        # ---------------------------
        # AGGREGATION
        # ---------------------------
        agg_dict = {metric_col: "sum"}
        tooltip_cols = config.get("tooltip", [metric_col])

        for col in tooltip_cols:
            if col != metric_col and col in filtered_df.columns:
                if pd.api.types.is_numeric_dtype(filtered_df[col]):
                    agg_dict[col] = "sum"
                else:
                    agg_dict[col] = "first"

        summary = (
            filtered_df
            .groupby(group_col, as_index=False)
            .agg(agg_dict)
        )

        summary[metric_col] = summary[metric_col].round(2)

        # ---------------------------
        # SORTING LOGIC
        # ---------------------------
        category_order = None

        if sort_config and group_col in sort_config:
            sconf = sort_config[group_col]
            stype = sconf.get("type")

            if stype == "custom":
                category_order = sconf.get("order")
            elif stype in ["asc", "desc"]:
                summary = summary.sort_values(
                    by=metric_col,
                    ascending=(stype == "asc")
                )
            elif stype in ["label_asc", "label_desc"]:
                summary = summary.sort_values(
                    by=group_col,
                    ascending=(stype == "label_asc")
                )

        # For line charts, if not sorted by anything specific, default sorting by label (chronological/sequential order) is preferred
        if not category_order and (not sort_config or group_col not in sort_config):
            summary = summary.sort_values(by=group_col, ascending=True)

        # ---------------------------
        # GENERATE CHART
        # ---------------------------
        fig = ChartGenerator.create_line_chart(
            summary,
            x_col=group_col,
            y_col=metric_col,
            title=f"{config['name']} View" + (" (Final)" if is_final else ""),
            tooltip_cols=tooltip_cols,
            category_order=category_order
        )

        # ---------------------------
        # DISPLAY CHART
        # ---------------------------
        event = st.plotly_chart(
            fig,
            use_container_width=True,
            on_select="rerun",
            selection_mode="points",
            key=f"{key_prefix}_{current_level}"
        )

        # ---------------------------
        # STOP AT FINAL LEVEL
        # ---------------------------
        if is_final:
            st.info("Final level reached - no further drill-down")
            return

        # ---------------------------
        # HANDLE CLICK EVENT
        # ---------------------------
        selected = None
        points = []

        if event and hasattr(event, "selection"):
            points = getattr(event.selection, "points", [])
        elif isinstance(event, dict):
            points = event.get("selection", {}).get("points", [])

        if points:
            selected = points[0].get("x")

        if selected:
            st.session_state[f"{key_prefix}_level_{current_level}"] = selected
            st.rerun()

        # ---------------------------
        # DOWNLOAD OPTION
        # ---------------------------
        if enable_download:
            csv = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download Data",
                data=csv,
                file_name=f"{config['name']}_data.csv",
                mime="text/csv",
                key=f"{key_prefix}_download_btn"
            )

    @staticmethod
    def drill_down_calendar_view(
        df: pd.DataFrame,
        charges_df: pd.DataFrame = None,
        key_prefix: str = "calendar_view",
        enable_download: bool = True
    ):
        """
        Renders a Calendar View for trading performance with Net P&L Post Charges.
        
        Features:
        - FY Selector buttons with total Net P&L Post Charges (Green if >= 0, Red if < 0).
        - Month-by-month calendar grid for the selected Financial Year (April - March).
        - Color-coded daily Net P&L Post Charges (Green for Net P&L > 0, Red for Net P&L < 0).
        - Detailed tooltip showing Net P&L, Gross P&L, and Charges per day.
        """
        import calendar

        if df.empty and (charges_df is None or charges_df.empty):
            st.info("No trade or charges data available for the Calendar View.")
            return

        # Process trade dataset
        df_cal = df.copy() if not df.empty else pd.DataFrame()

        # Date column for realized trades (ExitedDate)
        date_col = 'ExitedDate' if 'ExitedDate' in df_cal.columns else ('exiteddate' if 'exiteddate' in df_cal.columns else ('Date' if 'Date' in df_cal.columns else 'date'))

        if not df_cal.empty and date_col in df_cal.columns:
            df_cal['CleanDate'] = pd.to_datetime(df_cal[date_col], errors='coerce').dt.date
            df_cal = df_cal.dropna(subset=['CleanDate'])

        # Helper to calculate FY
        def calc_fy(d):
            if pd.isna(d): return None
            y = d.year
            return f"{y}-{y+1}" if d.month >= 4 else f"{y-1}-{y}"

        if not df_cal.empty:
            if 'FY' not in df_cal.columns or df_cal['FY'].isna().all():
                df_cal['FY'] = df_cal['CleanDate'].apply(calc_fy)
            else:
                df_cal['FY'] = df_cal['FY'].astype(str)

            if 'P&L Without Charge' in df_cal.columns:
                df_cal['Gross_PNL'] = df_cal['P&L Without Charge']
            else:
                df_cal['Gross_PNL'] = df_cal['P&L']

            # Trade level total charges (EnteredTradeCharges + ExitedTradeCharges)
            entered_chg = df_cal['EnteredTradeCharges'] if ('EnteredTradeCharges' in df_cal.columns) else 0.0
            exited_chg = df_cal['ExitedTradeCharges'] if ('ExitedTradeCharges' in df_cal.columns) else 0.0
            df_cal['Trade_Charges'] = entered_chg + exited_chg
            df_cal['Net_PNL'] = df_cal['P&L']  # Sell Value - Buy Value - EnteredTradeCharges - ExitedTradeCharges

        # Standalone charges from charges_df (charges on dates where no trades entered or exited)
        standalone_chg = pd.DataFrame()
        if charges_df is not None and not charges_df.empty:
            c_df = charges_df.copy()
            c_date_col = 'Date' if 'Date' in c_df.columns else ('date' if 'date' in c_df.columns else None)
            if c_date_col:
                c_df['CleanDate'] = pd.to_datetime(c_df[c_date_col], errors='coerce').dt.date
                c_df = c_df.dropna(subset=['CleanDate'])
                c_df['Charge'] = pd.to_numeric(c_df.get('Charge', 0), errors='coerce').fillna(0)
                c_df['FY'] = c_df['CleanDate'].apply(calc_fy)
                
                # Standalone charges where no trades entered or exited
                if 'TotalTradeCount' in c_df.columns:
                    standalone_chg = c_df[c_df['TotalTradeCount'] == 0].copy()
                elif 'EnteredTradeCount' in c_df.columns and 'ExitedTradeCount' in c_df.columns:
                    standalone_chg = c_df[(c_df['EnteredTradeCount'] == 0) & (c_df['ExitedTradeCount'] == 0)].copy()

        # Combine FY list from trades and standalone charges
        fy_set = set()
        if not df_cal.empty and 'FY' in df_cal.columns:
            fy_set.update(df_cal['FY'].dropna().unique())
        if not standalone_chg.empty and 'FY' in standalone_chg.columns:
            fy_set.update(standalone_chg['FY'].dropna().unique())
        
        fy_list = sorted([str(x) for x in fy_set if x])

        if not fy_list:
            st.info("No Financial Year data found.")
            return

        # Pre-compute net P&L post charges per FY for FY buttons
        fy_summary = {}
        for fy_val in fy_list:
            fy_trades = df_cal[df_cal['FY'] == fy_val] if not df_cal.empty else pd.DataFrame()
            fy_st_chg = standalone_chg[standalone_chg['FY'] == fy_val] if not standalone_chg.empty else pd.DataFrame()
            
            trade_net = fy_trades['Net_PNL'].sum() if not fy_trades.empty else 0.0
            st_chg_sum = fy_st_chg['Charge'].sum() if not fy_st_chg.empty else 0.0
            
            fy_summary[fy_val] = trade_net - st_chg_sum

        # Initialize session state for selected FY
        selected_fy_key = f"{key_prefix}_selected_fy"
        if selected_fy_key not in st.session_state or st.session_state[selected_fy_key] not in fy_list:
            st.session_state[selected_fy_key] = fy_list[-1]  # Default to latest FY

        selected_fy = st.session_state[selected_fy_key]

        # Inject CSS for FY Buttons, Metrics, and Instant Day Tooltips
        st.markdown("""
        <style>
        div[data-testid="stMetricLabel"] p {
            font-size: 0.78rem !important;
            font-weight: 600 !important;
        }

        div[data-testid="stMetricValue"] div {
            font-size: 1.1rem !important;
            font-weight: 700 !important;
        }

        div[data-testid="stMetricDelta"] div {
            font-size: 0.75rem !important;
        }

        div[data-testid="stButton"] button[key*="_fy_pos_"] {
            background-color: rgba(46, 125, 50, 0.12) !important;
            color: #2e7b32 !important;
            border: 2px solid #2e7b32 !important;
            font-weight: 700 !important;
            font-size: 11.5px !important;
            border-radius: 8px !important;
            padding: 0.4rem 0.5rem !important;
            transition: all 0.2s ease-in-out !important;
            width: 100% !important;
        }

        div[data-testid="stButton"] button[key*="_fy_pos_"]:hover {
            background-color: #2e7b32 !important;
            color: #ffffff !important;
            box-shadow: 0 4px 12px rgba(46, 125, 50, 0.35) !important;
        }

        div[data-testid="stButton"] button[key*="_fy_neg_"] {
            background-color: rgba(198, 40, 40, 0.12) !important;
            color: #c62828 !important;
            border: 2px solid #c62828 !important;
            font-weight: 700 !important;
            font-size: 11.5px !important;
            border-radius: 8px !important;
            padding: 0.4rem 0.5rem !important;
            transition: all 0.2s ease-in-out !important;
            width: 100% !important;
        }

        div[data-testid="stButton"] button[key*="_fy_neg_"]:hover {
            background-color: #c62828 !important;
            color: #ffffff !important;
            box-shadow: 0 4px 12px rgba(198, 40, 40, 0.35) !important;
        }

        div[data-testid="stButton"] button[key*="_selected"] {
            border-width: 3px !important;
            box-shadow: 0 0 12px rgba(99, 102, 241, 0.6) !important;
            transform: scale(1.02) !important;
        }

        /* Instant Day Cell Popover Tooltip */
        .cal-day-cell {
            position: relative !important;
            cursor: pointer !important;
            overflow: visible !important;
        }

        .cal-day-cell[data-tooltip]:hover::after {
            content: attr(data-tooltip) !important;
            position: absolute !important;
            bottom: 112% !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            background-color: #11111b !important;
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.25) !important;
            padding: 6px 10px !important;
            border-radius: 8px !important;
            font-size: 11px !important;
            font-weight: 500 !important;
            line-height: 1.4 !important;
            white-space: pre-line !important;
            z-index: 999999 !important;
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.6) !important;
            pointer-events: none !important;
            width: max-content !important;
            min-width: 140px !important;
            text-align: left !important;
        }

        .cal-day-cell[data-tooltip]:hover::before {
            content: '' !important;
            position: absolute !important;
            bottom: 100% !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            border-width: 5px !important;
            border-style: solid !important;
            border-color: #11111b transparent transparent transparent !important;
            z-index: 999999 !important;
            pointer-events: none !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("##### 🗓️ Financial Year Selection (P&L Post Charges)")

        # Display FY buttons
        cols = st.columns(min(len(fy_list), 6))
        for i, fy_val in enumerate(fy_list):
            fy_pnl = fy_summary.get(fy_val, 0.0)
            is_pos = (fy_pnl >= 0)
            is_sel = (fy_val == selected_fy)
            
            status_tag = "pos" if is_pos else "neg"
            sel_tag = "_selected" if is_sel else ""
            btn_key = f"{key_prefix}_fy_{status_tag}_{fy_val}{sel_tag}"
            
            pnl_sign = "+" if fy_pnl >= 0 else "-"
            icon = "🟢" if fy_pnl >= 0 else "🔴"
            btn_label = f"{icon} FY {fy_val} ({pnl_sign}₹{abs(fy_pnl):,.2f})"

            col_idx = i % len(cols)
            with cols[col_idx]:
                if st.button(btn_label, key=btn_key, use_container_width=True):
                    st.session_state[selected_fy_key] = fy_val
                    st.rerun()

        # Filter trade and standalone charge data for selected FY
        fy_df = df_cal[df_cal['FY'] == selected_fy].copy() if not df_cal.empty else pd.DataFrame()
        fy_st = standalone_chg[standalone_chg['FY'] == selected_fy].copy() if not standalone_chg.empty else pd.DataFrame()

        trade_gross_map = fy_df.groupby('CleanDate')['Gross_PNL'].sum().to_dict() if not fy_df.empty else {}
        trade_chg_map = fy_df.groupby('CleanDate')['Trade_Charges'].sum().to_dict() if not fy_df.empty else {}
        st_chg_map = fy_st.groupby('CleanDate')['Charge'].sum().to_dict() if not fy_st.empty else {}

        all_fy_dates = set(trade_gross_map.keys()).union(set(st_chg_map.keys()))
        daily_net_map = {}
        daily_gross_map = {}
        daily_charge_map = {}

        for d in all_fy_dates:
            g = trade_gross_map.get(d, 0.0)
            c = trade_chg_map.get(d, 0.0) + st_chg_map.get(d, 0.0)
            daily_gross_map[d] = g
            daily_charge_map[d] = c
            daily_net_map[d] = g - c

        # Parse Start & End Year from selected_fy (e.g. "2023-2024" or "2023-24")
        parts = str(selected_fy).split('-')
        try:
            start_year = int(parts[0])
            if len(parts) > 1:
                y2_str = parts[1]
                end_year = int(y2_str) if len(y2_str) == 4 else (2000 + int(y2_str) if len(y2_str) == 2 else start_year + 1)
            else:
                end_year = start_year + 1
        except Exception:
            min_year = min([d.year for d in all_fy_dates]) if all_fy_dates else 2024
            start_year = min_year
            end_year = min_year + 1

        # FY Months sequence (Indian FY: April to March)
        fy_months = [
            ("April", 4, start_year),
            ("May", 5, start_year),
            ("June", 6, start_year),
            ("July", 7, start_year),
            ("August", 8, start_year),
            ("September", 9, start_year),
            ("October", 10, start_year),
            ("November", 11, start_year),
            ("December", 12, start_year),
            ("January", 1, end_year),
            ("February", 2, end_year),
            ("March", 3, end_year)
        ]

        # Month Filter Tabs / Selectbox
        st.markdown("---")
        month_options = ["All 12 Months"] + [m[0] for m in fy_months]
        selected_month_view = st.selectbox(
            "Filter Calendar by Month",
            options=month_options,
            key=f"{key_prefix}_month_select"
        )

        # Filter active dates by selected month
        if selected_month_view == "All 12 Months":
            active_dates = all_fy_dates
            header_scope = f"Full FY Overview ({selected_fy})"
        else:
            target_m = next((m for m in fy_months if m[0] == selected_month_view), None)
            if target_m:
                active_dates = {d for d in all_fy_dates if d.month == target_m[1] and d.year == target_m[2]}
            else:
                active_dates = all_fy_dates
            header_scope = f"{selected_month_view} Overview ({selected_fy})"

        # Dynamic Metric Banner Calculations for selected scope
        total_net_pnl = sum([daily_net_map[d] for d in active_dates]) if active_dates else 0.0
        total_gross_pnl = sum([daily_gross_map[d] for d in active_dates]) if active_dates else 0.0
        total_charges = sum([daily_charge_map[d] for d in active_dates]) if active_dates else 0.0

        traded_dates_list = [d for d in active_dates if (daily_gross_map.get(d, 0) != 0 or daily_charge_map.get(d, 0) != 0)]
        trading_days = len(traded_dates_list)
        
        win_pnls = [daily_net_map[d] for d in traded_dates_list if daily_net_map[d] > 0]
        loss_pnls = [daily_net_map[d] for d in traded_dates_list if daily_net_map[d] < 0]
        
        win_days = len(win_pnls)
        loss_days = len(loss_pnls)
        win_rate = (win_days / trading_days * 100) if trading_days > 0 else 0.0
        
        avg_win = (sum(win_pnls) / win_days) if win_days > 0 else 0.0
        avg_loss = (sum(loss_pnls) / loss_days) if loss_days > 0 else 0.0
        
        max_gain = max([daily_net_map[d] for d in active_dates]) if active_dates else 0.0
        max_loss = min([daily_net_map[d] for d in active_dates]) if active_dates else 0.0

        # Display Metrics Banner
        st.markdown(f"###### 📊 Performance Metrics — {header_scope}")
        mcol1, mcol2, mcol3, mcol4, mcol5, mcol6 = st.columns(6)
        with mcol1:
            st.metric("Net P&L (Post Charges)", f"₹{total_net_pnl:,.2f}", delta=f"{total_net_pnl:,.2f}")
        with mcol2:
            st.metric("Total Charges", f"₹{total_charges:,.2f}")
        with mcol3:
            st.metric("Gross P&L", f"₹{total_gross_pnl:,.2f}")
        with mcol4:
            st.metric("Traded Days", f"{trading_days} Days", delta=f"{win_days} W / {loss_days} L ({win_rate:.1f}%)")
        with mcol5:
            loss_str = f"-₹{abs(avg_loss):,.0f}" if avg_loss != 0 else "₹0"
            st.metric("Avg Win / Loss", f"+₹{avg_win:,.0f} / {loss_str}", delta=f"Win: +₹{avg_win:,.0f} | Loss: {loss_str}")
        with mcol6:
            st.metric("Best / Worst Day", f"₹{max_gain:,.0f} / ₹{max_loss:,.0f}")

        def render_month_card(month_name, month_num, year, cell_height="46px"):
            cal = calendar.monthcalendar(year, month_num)
            headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            
            month_dates = [pd.to_datetime(f"{year}-{month_num:02d}-{day:02d}").date() for week in cal for day in week if day != 0]
            month_pnl = sum([daily_net_map.get(d, 0.0) for d in month_dates if d in daily_net_map])
            
            badge_html = ""
            if month_pnl > 0:
                badge_html = f'<span style="color: #2e7d32; font-size: 11.5px; font-weight: bold; margin-left: 5px;">(+₹{month_pnl:,.2f})</span>'
            elif month_pnl < 0:
                badge_html = f'<span style="color: #c62828; font-size: 11.5px; font-weight: bold; margin-left: 5px;">(-₹{abs(month_pnl):,.2f})</span>'
            
            html_lines = []
            html_lines.append('<div style="background-color: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 12px; padding: 10px; margin-bottom: 14px; font-family: system-ui, -apple-system, sans-serif;">')
            html_lines.append(f'<div style="font-size: 13.5px; font-weight: 700; color: #e0e0e0; text-align: center; margin-bottom: 8px; display: flex; align-items: center; justify-content: center;">')
            html_lines.append(f'<span>{month_name} {year}</span> {badge_html}')
            html_lines.append('</div>')
            html_lines.append('<div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; text-align: center; font-size: 10px; font-weight: 600; color: #9e9e9e; margin-bottom: 5px;">')
            for h in headers:
                html_lines.append(f'<div>{h}</div>')
            html_lines.append('</div>')
            html_lines.append('<div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; text-align: center;">')
            
            for week in cal:
                for day in week:
                    if day == 0:
                        html_lines.append(f'<div style="height: {cell_height}; background: transparent;"></div>')
                    else:
                        date_obj = pd.to_datetime(f"{year}-{month_num:02d}-{day:02d}").date()
                        pnl = daily_net_map.get(date_obj, None)
                        gross_val = daily_gross_map.get(date_obj, 0.0)
                        chg_val = daily_charge_map.get(date_obj, 0.0)
                        
                        if pnl is not None and (gross_val != 0 or chg_val != 0):
                            if pnl > 0:
                                bg_color = "#1b5e20" # Green
                                border_color = "#2e7b32"
                                text_color = "#ffffff"
                                pnl_str = f"+₹{pnl:,.0f}" if abs(pnl) < 10000 else f"+₹{pnl/1000:.1f}k"
                            elif pnl < 0:
                                bg_color = "#b71c1c" # Red
                                border_color = "#c62828"
                                text_color = "#ffffff"
                                pnl_str = f"-₹{abs(pnl):,.0f}" if abs(pnl) < 10000 else f"-₹{pnl/1000:.1f}k"
                            else:
                                bg_color = "#424242"
                                border_color = "#616161"
                                text_color = "#e0e0e0"
                                pnl_str = "₹0"
                            
                            date_title = date_obj.strftime('%d %b %Y')
                            net_sign = "+" if pnl > 0 else ("-" if pnl < 0 else "")
                            gross_sign = "+" if gross_val > 0 else ("-" if gross_val < 0 else "")
                            
                            tooltip_clean = f"{date_title}\nGross P&L: {gross_sign}₹{abs(gross_val):,.2f}\nCharges: ₹{chg_val:,.2f}\nNet P&L: {net_sign}₹{abs(pnl):,.2f}"
                            title_text = f"{date_title}&#10;Gross P&L: {gross_sign}₹{abs(gross_val):,.2f}&#10;Charges: ₹{chg_val:,.2f}&#10;Net P&L: {net_sign}₹{abs(pnl):,.2f}"
                            
                            html_lines.append(f'<div class="cal-day-cell" data-tooltip="{tooltip_clean}" title="{title_text}" style="height: {cell_height}; background-color: {bg_color}; border: 1px solid {border_color}; color: {text_color}; border-radius: 6px; padding: 3px 2px; font-size: 10px; display: flex; flex-direction: column; justify-content: center; align-items: center;">')
                            html_lines.append(f'<div style="font-weight: 700; font-size: 11px;">{day}</div>')
                            html_lines.append(f'<div style="font-size: 9.5px; font-weight: 600; opacity: 0.95;">{pnl_str}</div>')
                            html_lines.append('</div>')
                        else:
                            html_lines.append(f'<div style="height: {cell_height}; background-color: rgba(255, 255, 255, 0.02); color: #757575; border-radius: 6px; border: 1px solid rgba(255, 255, 255, 0.04); padding: 3px 2px; font-size: 10px; display: flex; flex-direction: column; justify-content: center; align-items: center;">')
                            html_lines.append(f'<div style="font-weight: 400; font-size: 10px;">{day}</div>')
                            html_lines.append('</div>')
            html_lines.append('</div></div>')
            return "".join(html_lines)

        if selected_month_view == "All 12 Months":
            # Display 3 months per row
            for r in range(0, 12, 3):
                row_months = fy_months[r:r+3]
                m_cols = st.columns(len(row_months))
                for idx, (m_name, m_num, m_yr) in enumerate(row_months):
                    with m_cols[idx]:
                        if hasattr(st, "html"):
                            st.html(render_month_card(m_name, m_num, m_yr, "46px"))
                        else:
                            st.markdown(render_month_card(m_name, m_num, m_yr, "46px"), unsafe_allow_html=True)
        else:
            # Display single selected month
            target_month = next((m for m in fy_months if m[0] == selected_month_view), None)
            if target_month:
                if hasattr(st, "html"):
                    st.html(render_month_card(target_month[0], target_month[1], target_month[2], "60px"))
                else:
                    st.markdown(render_month_card(target_month[0], target_month[1], target_month[2], "60px"), unsafe_allow_html=True)

        if enable_download:
            csv = fy_df.to_csv(index=False).encode("utf-8") if not fy_df.empty else "".encode("utf-8")
            st.download_button(
                label=f"⬇️ Download {selected_fy} Data",
                data=csv,
                file_name=f"FY_{selected_fy}_trades.csv",
                mime="text/csv",
                key=f"{key_prefix}_download_btn"
            )