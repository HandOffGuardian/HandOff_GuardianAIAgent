"""Repository-root Streamlit entry point."""

# Keep the project root on Python's import path when launched as ``streamlit
# run app.py``; Streamlit executes this file from its own runner context.
from src.ui.app import *  # noqa: F401,F403
