import requests
import streamlit as st
import webbrowser
import time

from pathlib import Path

LOGO_PATH = Path(__file__).parent / "images" / "yellowbrick_logo.png"
DEFAULT_DATABASE = "noaa"

def get_all_database_connections(api_url):
    try:
        response = requests.get(api_url)
        response_data = response.json()
        return {entry["alias"]: entry["id"] for entry in response_data} if response.status_code == 200 else {}
    except requests.exceptions.RequestException:
        return {}

def answer_question(api_url, db_connection_id, question, context):
    if context:
        instruction = "Please consider the following conversation history to provide a detailed and relevant answer to the user's question:"
        full_prompt = f"{instruction}\n\n{context}\n\nUser: {question}\nAssistant:"
    else:
        full_prompt = f"User: {question}\nAssistant:"
    
    request_body = {
        "llm_config": {
            "llm_name": "gpt-4o"
        },
        "prompt": {
            "text": full_prompt,
            "db_connection_id": db_connection_id,
        }
    }
    try:
        with requests.post(api_url, json=request_body, stream=True) as response:
            response.raise_for_status()
            full_response = ""
            for chunk in response.iter_content(chunk_size=2048):
                if chunk:
                    part = chunk.decode("utf-8")
                    full_response += part
                    yield part
                    time.sleep(0.1)
        st.session_state.detailed_conversation.append(("Assistant", full_response))
        final_answer = extract_final_answer(full_response)
        st.session_state.conversation.append(("Assistant", final_answer))
    except requests.exceptions.RequestException as e:
        st.error(f"Connection failed due to {e}.")
        return ""

def test_connection(url):
    try:
        response = requests.get(url)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def create_button_link(text, url):
    button_clicked = st.sidebar.button(text)
    if button_clicked:
        webbrowser.open_new_tab(url)

def find_key_by_value(dictionary, target_value):
    for key, value in dictionary.items():
        if value == target_value:
            return key
    return None

def extract_final_answer(response_text):
    parts = response_text.split("Final Answer:")
    return parts[-1].strip() if len(parts) > 1 else ""

WAITING_TIME_TEXTS = [
    ":wave: Hello. Please, give me a few moments and I'll be back with your answer.",
]

INTRODUCTION_TEXT = """
This app is a proof of concept using the Dataherald NL-2-SQL engine using a streamlit front-end and datasets from Yellowbrick's sample repo.
The data available includes: NOAA, GDELT, TPC-DS, NYC Taxi Rides and Premiership soccer matches.
"""
INTRO_EXAMPLE = """
A sample question you can ask against the NOAA database is: What was the longest dry spell in Cary, NC in 2024?
"""

st.set_page_config(page_title="Yellowbrick", page_icon="./images/yellowbrick_logo.png", layout="wide")

st.sidebar.title("Yellowbrick")
st.sidebar.write("Query your Yellowbrick databases in natural language.")
st.sidebar.page_link("https://www.yellowbrick.com/", label="Visit our website", icon="🌐")
st.sidebar.subheader("Connect to the engine")
HOST = st.sidebar.text_input("Engine URI", value="http://localhost")
st.session_state["HOST"] = HOST
if st.sidebar.button("Connect"):
    url = HOST + '/api/v1/heartbeat'
    if test_connection(url):
        st.sidebar.success("Connected to engine.")
    else:
        st.sidebar.error("Connection failed.")

st.sidebar.subheader("Reset chat history")
if st.sidebar.button("Reset"):
    st.session_state.conversation = []
    st.rerun()

if not test_connection(HOST + '/api/v1/heartbeat'):
    st.error("Could not connect to engine. Please connect to the engine on the left sidebar.")
    st.stop()

# Setup main page
st.image("images/yellowbrick_white.png", width=500)

database_connections = get_all_database_connections(HOST + '/api/v1/database-connections')
st.session_state["database_connections"] = database_connections
if "database_connection_id" not in st.session_state:
    st.session_state["database_connection_id"] = database_connections.get(DEFAULT_DATABASE, None)
db_name = find_key_by_value(database_connections, st.session_state["database_connection_id"])
st.warning(f"Connected to {db_name} database.")
st.info(INTRODUCTION_TEXT)
st.info(INTRO_EXAMPLE)

output_container = st.empty()
output_container = output_container.container()

if "conversation" not in st.session_state:
    st.session_state.conversation = []
    st.session_state.detailed_conversation = []

for speaker, text in st.session_state.detailed_conversation:
    if speaker == "User":
        output_container.chat_message("User").write(text)
    else:
        output_container.chat_message("Assistant").markdown(text)

context = "\n".join([f"{speaker}: {text}" for speaker, text in st.session_state.conversation])

user_input = st.chat_input("Ask your question")
if user_input:
    st.session_state.conversation.append(("User", user_input))
    st.session_state.detailed_conversation.append(("User", user_input))
    output_container.chat_message("User").write(user_input)
    answer_container = output_container.chat_message("Assistant")

    with st.spinner("Fetching the answer..."):
        st.write_stream(answer_question(HOST + '/api/v1/stream-sql-generation', st.session_state["database_connection_id"], user_input, context))

