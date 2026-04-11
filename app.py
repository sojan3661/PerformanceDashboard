import streamlit as st

st.set_page_config(
    page_title="My Performance Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

performance_page = st.Page("pages/Performance.py", title="Performance", icon="📈", default=True)
tax_page = st.Page("pages/Tax.py", title="Tax", icon="📝")

pg = st.navigation([performance_page, tax_page])
pg.run()
