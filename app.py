import streamlit as st

st.set_page_config(
    page_title="My Performance Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

performance_page = st.Page("pages/Performance.py", title="Performance", icon="📈", default=True)
tax_page = st.Page("pages/Tax.py", title="Tax", icon="📝")
calculator_page = st.Page("pages/Calculator.py", title="Calculator", icon="🧮")
fyers_tradebook_page = st.Page("pages/FyersTradebook.py", title="Fyers Tradebook", icon="📄")
notes_page = st.Page("pages/Notes.py", title="Notes", icon="📌")

pg = st.navigation([performance_page, tax_page, calculator_page, fyers_tradebook_page, notes_page])
pg.run()

