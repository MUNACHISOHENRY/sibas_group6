import streamlit as st

# ---------- PAGE CONFIG + CSS ----------
st.set_page_config(page_title="SIBAS", page_icon="🎓", layout="wide")

st.markdown("""
<style>
.main {
    background:#f6f8fc;
}
.block-container {
    padding-top:1rem;
}
section[data-testid="stSidebar"]{
    background:#1e3a8a;
}
section[data-testid="stSidebar"] *{
    color:white !important;
}
.metric-card{
    background:white;
    padding:20px;
    border-radius:16px;
    box-shadow:0 2px 10px rgba(0,0,0,.08);
}
.header-card{
    background:white;
    padding:20px;
    border-radius:16px;
    box-shadow:0 2px 10px rgba(0,0,0,.08);
    margin-bottom:1rem;
}
.stButton button{
    border-radius:10px;
    width:100%;
}
</style>
""", unsafe_allow_html=True)

# Import dashboard functions
from app.dashboards.login import login_section
from app.dashboards.admin import admin_dashboard
from app.dashboards.lecturer import lecturer_dashboard
from app.dashboards.student import student_dashboard

# ---------- MAIN ----------
if "user_id" not in st.session_state:
    login_section()
else:
    # Shared sidebar
    st.sidebar.title("SIBAS")
    st.sidebar.write(f'Logged in as **{st.session_state["username"]}**')

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    role = st.session_state["role"]

    if role == "Administrator":
        admin_dashboard()
    elif role == "Lecturer":
        lecturer_dashboard()
    elif role == "Student":
        student_dashboard()