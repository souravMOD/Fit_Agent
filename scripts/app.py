import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import plotly.graph_objects as go
from src.agent.graph import agent
from src.database.meal_db import MealDatabase
from src.tools.agent_tools import set_current_user
from src.config import MEAL_IMAGES_DIR

MEAL_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
db = MealDatabase()


# --- Session Setup ---
if "user_id" not in st.session_state:
    st.session_state.user_id = db.get_or_create_user(telegram_id="streamlit_user", name="Sourav")
if "messages" not in st.session_state:
    st.session_state.messages = []


# --- Page Config ---
st.set_page_config(page_title="FitAgent", page_icon="💪", layout="wide")


# --- Sidebar: Daily Dashboard ---
with st.sidebar:
    st.title("📊 Today's Progress")

    summary = db.get_daily_summary(st.session_state.user_id)
    targets = db.get_user_targets(st.session_state.user_id)

    if targets:
        cal_pct = min(summary["total_calories"] / targets["calorie_target"], 1.0) if targets["calorie_target"] > 0 else 0
        st.metric("Calories", f"{summary['total_calories']} / {targets['calorie_target']} kcal")
        st.progress(cal_pct)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Protein", f"{summary['total_protein_g']}g", f"/ {targets['protein_target']}g")
        with col2:
            st.metric("Carbs", f"{summary['total_carbs_g']}g", f"/ {targets['carbs_target']}g")
        with col3:
            st.metric("Fat", f"{summary['total_fat_g']}g", f"/ {targets['fat_target']}g")

        st.markdown(f"**Meals today:** {summary['meal_count']}")

    st.markdown("---")
    st.subheader("📈 Weekly Trend")
    history = db.get_weekly_history(st.session_state.user_id)

    if history:
        fig = go.Figure()
        dates = [h["date"] for h in history]
        cals = [h["total_calories"] for h in history]

        fig.add_trace(go.Bar(x=dates, y=cals, name="Calories", marker_color="#4CAF50"))

        if targets:
            fig.add_hline(
                y=targets["calorie_target"],
                line_dash="dash",
                line_color="red",
                annotation_text="Target",
            )

        fig.update_layout(
            height=250,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_title="",
            yaxis_title="kcal",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data yet. Log your first meal!")


# --- Main Area: Chat ---
st.title("💪 FitAgent")
st.caption("Upload a meal photo or ask about your nutrition")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "image" in msg:
            st.image(msg["image"], width=300)
        st.markdown(msg["content"])

# Image upload
uploaded_file = st.file_uploader("📷 Upload meal photo", type=["jpg", "jpeg", "png"], key="uploader")

if uploaded_file and "last_uploaded" not in st.session_state:
    st.session_state.last_uploaded = uploaded_file.name

    # Save image
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = MEAL_IMAGES_DIR / f"meal_{timestamp}_{uploaded_file.name}"
    with open(image_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Add to chat history
    st.session_state.messages.append({
        "role": "user",
        "content": "I just ate this meal. Please analyze and log it.",
        "image": str(image_path),
    })

    # Run agent
    user_id = st.session_state.user_id
    set_current_user(user_id)
    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": f"User ID: {user_id}. I just ate this meal. Please analyze and log it. Image path: {image_path}"
        }]
    })

    # Get final response
    response = ""
    for msg in result["messages"]:
        if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_calls"):
            response = msg.content

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

elif not uploaded_file:
    if "last_uploaded" in st.session_state:
        del st.session_state.last_uploaded

# Text chat input
if prompt := st.chat_input("Ask about your nutrition..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    user_id = st.session_state.user_id
    set_current_user(user_id)
    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": f"User ID: {user_id}. {prompt}"
        }]
    })

    response = ""
    for msg in result["messages"]:
        if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_calls"):
            response = msg.content

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()