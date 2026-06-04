import streamlit as st
from utils.user_db import init_user_db, load_user, save_user
import re

st.set_page_config(page_title="SeedSage | Login", page_icon="🌱", layout="centered")

init_user_db()

if "user" not in st.session_state:
    st.session_state.user = None

# Redirect if already logged in
if st.session_state.user:
    st.switch_page("pages/1_Dashboard.py")
    st.stop()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Lora:wght@400;600&family=DM+Sans:wght@300;400;500&display=swap');
    .stApp { background-color: #f4f7f2; }
    .login-hero { text-align: center; padding: 3rem 0 2rem; }
    .login-hero h1 { font-size: 3rem; color: #2e7d32; margin-bottom: 0.3rem; font-family: 'Lora', serif; }
    .login-hero p { color: #6a737d; font-size: 1.1rem; font-family: 'DM Sans', sans-serif; }
    div[data-testid="stForm"] { background: white; border-radius: 20px; padding: 2rem; box-shadow: 0 4px 20px rgba(0,0,0,0.06); border: 1px solid #e6ede4; }
    div[data-testid="stFormSubmitButton"] > button { background-color: #2e7d32 !important; color: white !important; border: none !important; border-radius: 10px !important; padding: 0.6rem 2rem !important; font-size: 1rem !important; width: 100% !important; }
    div[data-testid="stFormSubmitButton"] > button:hover { background-color: #1b5e20 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="login-hero">
    <h1>🌱 SeedSage</h1>
    <p>AI-Powered Garden Planning for UK Growers</p>
</div>
""", unsafe_allow_html=True)

with st.form("login_form"):
    name = st.text_input("👤 Your Name")
    postcode = st.text_input("📍 UK Postcode", placeholder="e.g. SW1A 1AA")
    submit = st.form_submit_button("Enter My Garden →")

if submit:
    if not name or not postcode:
        st.warning("Please provide both your name and a UK postcode.")
        st.stop()

    # Basic validation
    if not re.match(r"^[A-Za-z0-9 ]{2,50}$", name):
        st.warning("Invalid name.")
        st.stop()

    postcode = postcode.strip().upper()

    saved = load_user(name, postcode)

    if saved:
        user_data = {
            "name": name,
            "postcode": postcode,
            "plants": saved.get("plants", {}),
            "plans": saved.get("plans", {}),
            "journal": saved.get("journal", []),
        }
        st.success(f"Welcome back, {name}!")
    else:
        user_data = {
            "name": name,
            "postcode": postcode,
            "plants": {},
            "plans": {},
            "journal": [],
        }
        st.success(f"Welcome, {name}!")

    st.session_state.user = user_data
    st.switch_page("pages/1_Dashboard.py")

