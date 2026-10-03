import os
import time

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from streamlit_webrtc import webrtc_streamer, WebRtcMode

from services.auth.login_form import render_login_form
from services.state.session_defaults import initial_session_defaults
from services.config.workout_config import EXERCISE_OPTIONS, get_exercise_status_info
from services.ui.style_loader import load_css, inject_local_font, inject_webrtc_styles
from services.persistence.exercise_repo import init_db, get_users_exercises
from services.vision.exercise_video_processor import VideoProcessorClass
from services.tracking.metrics import sync_metrics_update
from services.coaching.llm import LLMCoach
from services.coaching.tts import TextToSpeech
from services.coaching.voice_pipeline import VoicePipeline, autoplay_audio

load_dotenv()  # reads GROQ_API_KEY from the .env file



def main():
    st.set_page_config(
        page_icon=":muscle:", 
        page_title="AI real-time Gym Coach", 
        initial_sidebar_state="expanded",
        layout="centered"
    )
    load_css(os.path.join(os.getcwd(),"static","style.css"))
    inject_local_font(os.path.join(os.getcwd(),"static","AdobeClean.otf"),"AdobeClean")
    
    init_db()  # Initialize the database tables if they don't exist
    if not render_login_form():
        return  # Stop execution if the user is not logged in
    
    initial_session_defaults()

    # AI voice coach (Groq LLM + gTTS). If no key is set the app still runs, just silently.
    if "voice_pipeline" not in st.session_state:
        try:
            api_key = os.environ.get("GROQ_API_KEY", "")
            if not api_key and hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
                api_key = st.secrets["GROQ_API_KEY"]

            groq_client = Groq(api_key=api_key)
            st.session_state.voice_pipeline = VoicePipeline(LLMCoach(groq_client), TextToSpeech())
        except Exception:
            st.session_state.voice_pipeline = None

    workout_started=st.session_state.get("workout_started")
    
    # for sidebar
    with st.sidebar:
        col1, col2 = st.columns([1, 4])  # adjust ratio
        with col1:
            st.image("icon.png", width=40)
        with col2:
            st.title("AI Gym Coach")

        
        if st.session_state.username:
            st.caption(f"Login as {st.session_state.username}")
            
        st.divider()
        st.subheader("Workout Plan")
        
        if not workout_started:
            st.selectbox("Exercise",options=EXERCISE_OPTIONS,key="plan_exercise")
            st.number_input("Sets",min_value=0,max_value=50,key="plan_sets",step=1)
            st.number_input("Reps per Set",min_value=0,max_value=50,key="plan_reps",step=1)

            st.markdown("")
            start_session_button=st.button("start Workout",width="stretch",key="start_session_button")
            
            if start_session_button:
                plan_exercise = st.session_state.get("plan_exercise")
                st.session_state.exercise_type = plan_exercise
                st.session_state.target_sets = int(st.session_state.get("plan_sets"))
                st.session_state.reps_per_set = int(st.session_state.get("plan_reps"))
                st.session_state.reps = 0
                st.session_state.sets_completed = 0
                st.session_state.current_set_reps = 0
                st.session_state.workout_started = True
                st.session_state.set_cycle_started_at = time.time()
                st.session_state.last_saved_sets_completed = 0
                st.session_state.last_notified_workout_complete = False
                st.session_state.audio_to_play = None
                st.session_state.coach_feedback = None

                if st.session_state.voice_pipeline:
                    result = st.session_state.voice_pipeline.process_event(
                        event="workout_started", exercise=plan_exercise, metrics={}
                    )
                    if result:
                        st.session_state.audio_to_play, st.session_state.coach_feedback = result

                st.rerun()
        else:
                exercise=st.session_state.get("plan_exercise")
                sets=st.session_state.get("plan_sets")
                reps=st.session_state.get("plan_reps")
                
                st.info(f"Current Plan: {exercise} - {sets} sets of {reps} reps")
                end_session_button=st.button("End Workout",width="stretch",key="end_session_button")
                
                if end_session_button:
                    st.session_state["workout_started"]=False

                    if st.session_state.voice_pipeline:
                        result = st.session_state.voice_pipeline.process_event(
                            event="workout_completed", exercise=exercise, metrics={}
                        )
                        if result:
                            st.session_state.audio_to_play, st.session_state.coach_feedback = result

                    st.rerun()
                    
        if workout_started:
            st.divider()
            st.subheader("Progress")
            
            exercise=st.session_state.get("plan_exercise")
            total_reps=st.session_state.get("reps")
            current_set_reps=st.session_state.get("current_set_reps")
            reps_per_set=st.session_state.get("plan_reps")
            sets_completed=st.session_state.get("sets_completed")
            target_sets=st.session_state.get("plan_sets")
            
            st.metric("Total Reps", f"{total_reps}")
            st.metric("Current Set Reps", f"{current_set_reps}/{reps_per_set}")
            st.metric("Sets Completed", f"{sets_completed}/{target_sets}")
            
            st.divider()
            
            status_title, status_fields = get_exercise_status_info(exercise)
            if status_fields:
                st.subheader(status_title)

                metric_labels = {
                    "knee_angle": ("Knee Angle", lambda value: f"{value:.2f}°"),
                    "back_angle": ("Back Angle", lambda value: f"{value:.2f}°"),
                    "depth_status": ("Depth Status", lambda value: str(value)),
                    "elbow_angle": ("Elbow Angle", lambda value: f"{value:.2f}°"),
                    "body_alignment": ("Body Alignment", lambda value: str(value)),
                    "hip_status": ("Hip Position", lambda value: str(value)),
                    "swing_status": ("Swing Detection", lambda value: str(value)),
                    "shoulder_status": ("Shoulder Stability", lambda value: str(value)),
                    "extension_status": ("Arm Extension", lambda value: str(value)),
                    "back_arch_status": ("Back Arch", lambda value: str(value)),
                    "front_knee_angle": ("Front Knee Angle", lambda value: f"{value:.2f}°"),
                    "torso_angle": ("Torso Angle", lambda value: f"{value:.2f}°"),
                    "balance_status": ("Balance Status", lambda value: str(value)),
                }

                for field in status_fields:
                    label, formatter = metric_labels[field]
                    value = st.session_state.get(field, "N/A")
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        st.metric(label, formatter(value))
                    else:
                        st.metric(label, str(value))

    st.title("AI Real-time GYM Coach")
    st.markdown("#### Real-time pose detection with proactive AI voice coaching")

    if st.session_state.get("audio_to_play"):
        autoplay_audio(st.session_state.audio_to_play)

    if st.session_state.get("coach_feedback"):
        st.success(f"🤖 **Coach:** {st.session_state.coach_feedback}")

    if not workout_started:
        st.markdown(
            """
            <div style="
                border:10px dashed #444;
                border-radius:0px;
                padding: 48px 32px;
                text-align:center;
                color:#888;
                margin-top:32px;
                margin-bottom:32px;
            ">
            <h2 style="color:#ccc; margin-bottom:8px;"> set you workout plan</h2>
            <p style="font-size:1.05rem;">
                choose your exercise, sets and reps in the sidebar,<br>
                then click <strong >start workout</strong> to activate the camera and start your session.
                </p>
            </div>
            """,
            unsafe_allow_html=True # allow HTML rendering
            
        )
    else:
        context=webrtc_streamer( #webrtc_streamer is a function from streamlit-webrtc that allows us to stream video and audio in real-time
            key="exercise-analysis",
            mode=WebRtcMode.SENDRECV, # SENDERECV mode allows us to send and receive video and audio streams
            video_processor_factory=VideoProcessorClass,
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}, 
            media_stream_constraints={
                "video":True,
                "audio":False
            },
            async_processing=True
        )

        sync_metrics_update(context)  # pull reps/angles from the video processor into session state

        if context.state.playing:
            time.sleep(0.25)
            st.rerun()

        inject_webrtc_styles()  # Inject custom styles for WebRTC components

    st.divider()
    st.markdown("#### Workout History")

    user_id = st.session_state.get("user_id", 0)

    if isinstance(user_id, int):
        history_rows = get_users_exercises(user_id)

        df = pd.DataFrame([
            {
                "Exercise": row["exercise_name"],
                "Reps": row["reps"],
                "Sets": row["sets"],
                "Time (sec)": row["time"],
                "Date": row["created_at"],
            }
            for row in history_rows
        ])

        if not df.empty:
            df["Date"] = pd.to_datetime(df["Date"]).dt.date
            agg_df = df.groupby(["Exercise", "Date"]).agg(
                {"Reps": "sum", "Sets": "sum", "Time (sec)": "sum"}
            ).reset_index()
            agg_df.index += 1
            st.table(agg_df, border="horizontal")
        else:
            st.info("No workout history found.")
                
          
        
if __name__=="__main__": #this is the entry point of the application
    main() 