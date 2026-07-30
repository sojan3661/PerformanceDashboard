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
        key_prefix: str = "calendar_view",
        enable_download: bool = True
    ):
        """
        Renders a Calendar View for trading performance.
        
        Features:
        - FY Selector buttons with total P&L and green/red conditional styling.
        - Month-by-month calendar grid for the selected Financial Year (April - March).
        - Color-coded daily P&L (Green for P&L > 0, Red for P&L < 0).
        - Detailed trade drill-down for selected dates.
        """
        import calendar

        if df.empty:
            st.info("No trade data available for the Calendar View.")
            return

        df_cal = df.copy()

        # Determine date column
        date_col = None
        for col in ['ExitedDate', 'exiteddate', 'Date', 'date', 'EnteredDate', 'entereddate']:
            if col in df_cal.columns:
                date_col = col
                break

        if not date_col:
            st.error("No date column found in dataset for Calendar View.")
            return

        df_cal['CleanDate'] = pd.to_datetime(df_cal[date_col], errors='coerce').dt.date
        df_cal = df_cal.dropna(subset=['CleanDate'])

        if df_cal.empty:
            st.info("No valid dates found in dataset.")
            return

        # Ensure FY column exists
        def calc_fy(d):
            if pd.isna(d): return None
            y = d.year
            return f"{y}-{y+1}" if d.month >= 4 else f"{y-1}-{y}"

        if 'FY' not in df_cal.columns or df_cal['FY'].isna().all():
            df_cal['FY'] = df_cal['CleanDate'].apply(calc_fy)
        else:
            df_cal['FY'] = df_cal['FY'].astype(str)

        # Calculate FY summary P&L
        fy_summary = df_cal.groupby('FY')['P&L'].sum().to_dict()
        fy_list = sorted([str(x) for x in fy_summary.keys()])

        if not fy_list:
            st.info("No Financial Year data found.")
            return

        # Initialize session state for selected FY
        selected_fy_key = f"{key_prefix}_selected_fy"
        if selected_fy_key not in st.session_state or st.session_state[selected_fy_key] not in fy_list:
            st.session_state[selected_fy_key] = fy_list[-1]  # Default to latest FY

        selected_fy = st.session_state[selected_fy_key]

        # Inject CSS for FY Buttons
        st.markdown("""
        <style>
        div[data-testid="stButton"] button[key*="_fy_pos_"] {
            background-color: rgba(46, 125, 50, 0.12) !important;
            color: #2e7b32 !important;
            border: 2px solid #2e7b32 !important;
            font-weight: 700 !important;
            border-radius: 10px !important;
            padding: 0.6rem 0.8rem !important;
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
            border-radius: 10px !important;
            padding: 0.6rem 0.8rem !important;
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
        </style>
        """, unsafe_allow_html=True)

        st.markdown("##### 🗓️ Financial Year Selection")

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

        # Filter dataset for selected FY
        fy_df = df_cal[df_cal['FY'] == selected_fy].copy()

        # Key Metrics Banner for Selected FY
        st.markdown("---")
        total_pnl = fy_df['P&L'].sum() if not fy_df.empty else 0.0
        daily_pnl_series = fy_df.groupby('CleanDate')['P&L'].sum() if not fy_df.empty else pd.Series(dtype=float)
        trading_days = len(daily_pnl_series)
        win_days = (daily_pnl_series > 0).sum()
        loss_days = (daily_pnl_series < 0).sum()
        win_rate = (win_days / trading_days * 100) if trading_days > 0 else 0.0
        max_gain = daily_pnl_series.max() if trading_days > 0 else 0.0
        max_loss = daily_pnl_series.min() if trading_days > 0 else 0.0

        mcol1, mcol2, mcol3, mcol4 = st.columns(4)
        with mcol1:
            st.metric("Total FY P&L", f"₹{total_pnl:,.2f}", delta=f"{total_pnl:,.2f}")
        with mcol2:
            st.metric("Traded Days", f"{trading_days} Days", delta=f"{win_days} W / {loss_days} L ({win_rate:.1f}%)")
        with mcol3:
            st.metric("Best Day", f"₹{max_gain:,.2f}")
        with mcol4:
            st.metric("Worst Day", f"₹{max_loss:,.2f}")

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
            min_year = fy_df['CleanDate'].min().year if not fy_df.empty else 2024
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

        # Map daily P&L
        daily_pnl_map = daily_pnl_series.to_dict()

        # Month Filter Tabs / Selectbox
        month_options = ["All 12 Months"] + [m[0] for m in fy_months]
        selected_month_view = st.selectbox(
            "Filter Calendar by Month",
            options=month_options,
            key=f"{key_prefix}_month_select"
        )

        def render_month_card(month_name, month_num, year, cell_height="46px"):
            cal = calendar.monthcalendar(year, month_num)
            headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            
            month_dates = [pd.to_datetime(f"{year}-{month_num:02d}-{day:02d}").date() for week in cal for day in week if day != 0]
            month_pnl = sum([daily_pnl_map.get(d, 0.0) for d in month_dates])
            
            badge_html = ""
            if month_pnl > 0:
                badge_html = f'<span style="color: #2e7d32; font-size: 13px; font-weight: bold; margin-left: 6px;">(+₹{month_pnl:,.2f})</span>'
            elif month_pnl < 0:
                badge_html = f'<span style="color: #c62828; font-size: 13px; font-weight: bold; margin-left: 6px;">(-₹{abs(month_pnl):,.2f})</span>'
            
            html_lines = []
            html_lines.append('<div style="background-color: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 12px; padding: 12px; margin-bottom: 16px; font-family: system-ui, -apple-system, sans-serif;">')
            html_lines.append(f'<div style="font-size: 15px; font-weight: 700; color: #e0e0e0; text-align: center; margin-bottom: 10px; display: flex; align-items: center; justify-content: center;">')
            html_lines.append(f'<span>{month_name} {year}</span> {badge_html}')
            html_lines.append('</div>')
            html_lines.append('<div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; text-align: center; font-size: 11px; font-weight: 600; color: #9e9e9e; margin-bottom: 6px;">')
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
                        pnl = daily_pnl_map.get(date_obj, None)
                        
                        if pnl is not None:
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
                            
                            html_lines.append(f'<div style="height: {cell_height}; background-color: {bg_color}; border: 1px solid {border_color}; color: {text_color}; border-radius: 8px; padding: 4px 2px; font-size: 11px; display: flex; flex-direction: column; justify-content: center; align-items: center;" title="{date_obj}: Realized P&L = ₹{pnl:,.2f}">')
                            html_lines.append(f'<div style="font-weight: 700; font-size: 12px;">{day}</div>')
                            html_lines.append(f'<div style="font-size: 10px; font-weight: 600; opacity: 0.95;">{pnl_str}</div>')
                            html_lines.append('</div>')
                        else:
                            html_lines.append(f'<div style="height: {cell_height}; background-color: rgba(255, 255, 255, 0.02); color: #757575; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.04); padding: 4px 2px; font-size: 11px; display: flex; flex-direction: column; justify-content: center; align-items: center;">')
                            html_lines.append(f'<div style="font-weight: 400; font-size: 11px;">{day}</div>')
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
            csv = fy_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"⬇️ Download {selected_fy} Data",
                data=csv,
                file_name=f"FY_{selected_fy}_trades.csv",
                mime="text/csv",
                key=f"{key_prefix}_download_btn"
            )