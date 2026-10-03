import streamlit as st
from services.persistence.exercise_repo import get_or_create_user

def render_login_form():
    if st.session_state.get("user_id") is not None:
        return True  # User is already logged in
    
    st.title("  AI real-time Gym Coach")
    st.markdown("### Welcome to the AI real-time Gym Coach..!")
    st.markdown("Please log in to continue")
    
    with st.form("login_form",clear_on_submit=False):
        username=st.text_input("Name(unique)",placeholder="your name e.g. GayatriAutade")
        submit_button=st.form_submit_button("Start session",width="stretch")
        
        if submit_button:
            if not username:
                st.warning("Please enter your name")
                return False
            user=get_or_create_user(username)
            
            st.session_state["username"]=user["username"]
            st.session_state["user_id"]=user["id"]
            
            st.rerun() # this will refresh the page and the user will be logged in
        
            
    
    
    
    return False