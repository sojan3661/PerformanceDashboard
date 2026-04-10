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
            yaxis=dict(fixedrange=False)  # enable zoom
        )

        # ---------------------------
        # CUSTOM TOOLTIP
        # ---------------------------
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
            filtered_df = filtered_df[filtered_df[col] == val]

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