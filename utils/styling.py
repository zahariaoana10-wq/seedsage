# utils/styling.py
import streamlit as st

def apply_garden_style():
    """
    Applies the custom CSS necessary to replicate the visual hierarchy
    of the design seen in image_2.png
    """
    st.markdown("""
        <style>
            /* Apply general background and font smoothing */
            .stApp {
                background-color: #f7f9fc;
            }

            /* Custom Styling for the Main Dashboard Header */
            h1 {
                color: #2e7d32; /* GardenGro Green from image_2.png */
                font-family: 'Helvetica Neue', sans-serif;
                font-weight: 700;
                margin-bottom: 0.1rem;
            }
            .subtitle {
                color: #6a737d;
                font-size: 1.1rem;
                margin-top: -10px;
                margin-bottom: 2rem;
            }

            /* Sidebar Navigation Styling */
            section[data-testid="stSidebar"] {
                background-color: #f0f2f5 !important;
                border-right: 1px solid #e6e9ef;
            }
            .sidebar-title {
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 1.5rem;
                color: #2e7d32;
                margin-bottom: 1rem;
                margin-top: 1rem;
            }

            /* Main Container (Simulating the 'Card' layout from image_2.png) */
            .main-container {
                background-color: white;
                padding: 30px;
                border-radius: 20px;
                box-shadow: 0px 4px 12px rgba(0,0,0,0.05);
            }

            /* Styling for the Plant Overview Cards (Tomatoes, Basil, etc.) */
            .plant-card {
                background-color: white;
                border-radius: 15px;
                border: 1px solid #e6e9ef;
                padding: 15px;
                margin-bottom: 15px;
                box-shadow: 0px 2px 5px rgba(0,0,0,0.03);
            }
            .plant-card h4 {
                color: #2e7d32;
                margin: 0;
            }
            .plant-status {
                font-weight: 600;
                color: #4caf50; /* Thriving/Healthy Green */
                margin-top: -5px;
                font-size: 0.9rem;
            }
            .plant-metrics {
                display: flex;
                justify-content: space-between;
                color: #6a737d;
                font-size: 0.85rem;
                margin-top: 10px;
            }

            /* Replicating the 'Action Buttons' row (Add New Plant, etc.) */
            .action-btn-container {
                display: flex;
                gap: 10px;
                margin-bottom: 1rem;
            }
            div.stButton > button {
                border-radius: 10px;
                background-color: white;
                color: #2e7d32;
                border: 1px solid #e6e9ef;
            }
            div.stButton > button:hover {
                background-color: #2e7d32 !important;
                color: white !important;
            }
            /* Styling for the specific 'Add New Plant' Green Button */
            div[data-testid="stFormSubmitButton"] > button {
                background-color: #2e7d32 !important;
                color: white !important;
                width: 100%;
            }

        </style>
    """, unsafe_allow_html=True)