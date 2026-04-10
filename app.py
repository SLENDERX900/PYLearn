import streamlit as st

from dashboard_tabs import render_learning_hub_tab, render_project_builder_tab
from memory_db import init_db
from shared_ui import (
    render_dependency_block,
    render_memory_panel,
    render_model_setup_block,
    render_sidebar_learning_profile,
)

st.set_page_config(page_title="Python Mentor Platform", page_icon=":snake:", layout="wide")
init_db()

st.title("Python Mentor Platform")
st.caption("Local-first Python learning copilot for solo builders. Choose a section below.")

with st.sidebar:
    level, style = render_sidebar_learning_profile("dash")
    st.divider()
    render_dependency_block()
    st.divider()
    render_model_setup_block("dash")

section = st.radio(
    "Main section",
    ["Learning Hub", "Project Builder", "Memory"],
    horizontal=True,
    key="dash_main_section",
)

if section == "Learning Hub":
    render_learning_hub_tab(level, style)
elif section == "Project Builder":
    render_project_builder_tab(level, style)
else:
    render_memory_panel("memory_tab", leading_divider=False)

st.divider()
st.caption("Built for a team of one. Ship one tiny feature daily.")
