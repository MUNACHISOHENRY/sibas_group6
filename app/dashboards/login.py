import streamlit as st

# Dummy backend – will be replaced by real imports later
import streamlit as st
from backend import authenticate

def login_section():
    c1,c2,c3 = st.columns([1,1.2,1])
    with c2:
        st.markdown("""
        <div style='background:#1e3a8a; padding:20px; border-radius:16px; box-shadow:0 2px 10px rgba(0,0,0,.3); text-align:center; margin-bottom:1rem;'>
        <h1 style='color:#ffffff;'>SIBAS</h1>
        <p style='color:#e2e8f0;'>Student Attendance & Eligibility System</p>
        </div>
        """, unsafe_allow_html=True)

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Sign In"):
            user = authenticate(username, password)   # now uses real DB
            if user:
                st.session_state["user_id"] = user["user_id"]
                st.session_state["role"] = user["role"]
                st.session_state["username"] = username
                st.rerun()
            st.error("Invalid credentials")