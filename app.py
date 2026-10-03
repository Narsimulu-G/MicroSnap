"""Run from this directory: python -m streamlit run app.py"""
import os
import streamlit as st
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient
from twilio.http.http_client import TwilioHttpClient
from core import normalize_phone, validate_name, prepare_image, friendly_error
from prompts import WELCOME_MESSAGE_TEMPLATE
from services import make_content, generate_reply, generate_summary, send_whatsapp

st.set_page_config(page_title="MacroSnap · Meal companion", page_icon="🥗", layout="centered")


def setting(key, default=""):
    if key in os.environ:
        return os.environ[key].strip()
    try:
        return str(st.secrets.get(key, default)).strip()
    except FileNotFoundError:
        return default



@st.cache_resource
def gemini_client(api_key):
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60000))


@st.cache_resource
def twilio_client(sid, token):
    return TwilioClient(sid, token, http_client=TwilioHttpClient(timeout=30))


def reset_chat():
    for key in ("history", "messages", "summary", "sent_revision", "send_uncertain", "receipt"):
        st.session_state.pop(key, None)


key = setting("GEMINI_API_KEY")
model = setting("GEMINI_MODEL", "gemini-3.5-flash")
sid = setting("TWILIO_ACCOUNT_SID")
token = setting("TWILIO_AUTH_TOKEN")
sender = setting("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
mode = setting("WHATSAPP_MODE", "session")
content_sid = setting("TWILIO_CONTENT_SID")
whatsapp_ready = bool(sid and token and sender and mode in {"session", "template"}
                      and (mode != "template" or content_sid.startswith("HX")))

st.title("🥗 MacroSnap")
st.caption("A little clarity on every plate.")

with st.sidebar:
    st.header("Your meal companion")
    st.write("Describe a meal, attach a photo, then ask follow-up questions.")
    st.caption("Estimates depend on portions, ingredients and cooking methods.")
    st.divider()
    st.write("Gemini: " + ("Configured" if key else "Setup needed"))
    st.write("WhatsApp: " + ("Configured" if whatsapp_ready else "Optional setup needed"))
    if "profile" in st.session_state:
        profile = st.session_state.profile
        st.write(profile["name"])
        st.caption("WhatsApp ending " + profile["phone"][-4:])
        if st.button("Start a new conversation", use_container_width=True):
            reset_chat()
            st.rerun()
        if st.button("Change profile", use_container_width=True):
            reset_chat()
            del st.session_state.profile
            st.rerun()
    with st.expander("Privacy & estimates"):
        st.write("Messages and photos are sent to Google Gemini. Your name, phone number and summary are sent to Twilio/WhatsApp only when you choose Send. This app keeps chat in session memory, not a database. Reloading or restarting can clear it. Estimates are not medical advice.")

if not key:
    st.info("Add your Gemini API key to start chatting.")
    st.code('Copy-Item .streamlit\\secrets.toml.example .streamlit\\secrets.toml\nnotepad .streamlit\\secrets.toml', language="powershell")
    st.write("Fill in GEMINI_API_KEY, save the file, and restart Streamlit. Twilio is optional until you want to send a summary.")
    st.link_button("Get a Gemini API key", "https://aistudio.google.com/apikey")
    st.stop()

if "profile" not in st.session_state:
    st.subheader("Let's get to know you")
    st.write("One meal photo. A clearer picture of your nutrition.")
    with st.form("onboarding"):
        name = st.text_input("Your name", max_chars=60, placeholder="Narsimulu")
        phone = st.text_input("Your WhatsApp number", placeholder="+91XXXXXXXXXX", max_chars=25)
        consent = st.checkbox("I understand my messages and meal photos will be processed by Google Gemini.")
        submitted = st.form_submit_button("Start my conversation", type="primary", use_container_width=True)
    if submitted:
        try:
            profile = {"name": validate_name(name), "phone": normalize_phone(phone)}
            if not consent:
                raise ValueError("Please confirm before sending your messages and photos to Gemini.")
            st.session_state.profile = profile
            st.rerun()
        except ValueError as error:
            st.warning(str(error))
    st.stop()

profile = st.session_state.profile
st.session_state.setdefault("history", [])
st.session_state.setdefault("messages", [])
st.session_state.setdefault("summary", "")
revision = len(st.session_state.history)

with st.expander("📤 Conversation summary & WhatsApp", expanded=bool(st.session_state.summary)):
    if st.button("Generate summary", disabled=not revision, use_container_width=True):
        try:
            with st.spinner("Summarizing your meals…"):
                st.session_state.summary = generate_summary(gemini_client(key), model, st.session_state.history)
        except Exception as error:
            st.error(friendly_error(error))
    if st.session_state.summary:
        st.text(st.session_state.summary)
        st.download_button("Download summary", st.session_state.summary,
                           file_name="macrosnap-summary.txt", mime="text/plain")
        st.caption("Send to " + profile["phone"])
        if mode == "session":
            window_ok = st.checkbox("I sent a WhatsApp message to the Twilio sender in the last 24 hours.")
        else:
            window_ok = True
        already_sent = st.session_state.get("sent_revision") == revision
        uncertain = st.session_state.get("send_uncertain", False)
        if not whatsapp_ready:
            st.info("Add the Twilio settings in secrets.toml to enable sending. You can still download your summary.")
        if st.button("Send details to WhatsApp", type="primary", use_container_width=True,
                     disabled=not whatsapp_ready or not window_ok or already_sent or uncertain):
            try:
                with st.spinner("Submitting to WhatsApp…"):
                    result = send_whatsapp(twilio_client(sid, token), sender, profile["phone"],
                                           profile["name"], st.session_state.summary, mode, content_sid)
                st.session_state.sent_revision = revision
                st.session_state.receipt = (result.sid, result.status)
                st.rerun()
            except Exception as error:
                st.session_state.send_uncertain = True
                st.error(friendly_error(error, "Twilio"))
                st.warning("Check Twilio message logs before enabling another attempt.")
        if st.session_state.get("send_uncertain"):
            if st.checkbox("I checked Twilio logs and confirmed no message was accepted."):
                if st.button("Enable another send attempt"):
                    st.session_state.send_uncertain = False
                    st.rerun()
        if already_sent:
            receipt_sid, status = st.session_state.receipt
            st.success(f"Submitted to Twilio ({status}). Submission is not delivery confirmation.")
            st.caption("Message ID: " + receipt_sid)

with st.chat_message("assistant"):
    st.write(WELCOME_MESSAGE_TEMPLATE.format(name=profile["name"]))
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("image"):
            st.image(message["image"], width=320)
        if message.get("text"):
            st.write(message["text"])

if revision >= 60:
    st.info("This conversation has reached 30 exchanges. Download a summary and start a new conversation.")
user_input = st.chat_input("Describe your meal or attach a photo…", accept_file=True,
                           file_type=["jpg", "jpeg", "png"], max_chars=4000,
                           disabled=revision >= 60)
if user_input:
    text = user_input.text.strip()
    photo_bytes, mime = None, None
    try:
        if user_input.files:
            photo_bytes, mime = prepare_image(user_input.files[0].getvalue())
        if not text and not photo_bytes:
            st.stop()
        content = make_content(text, photo_bytes, mime)
        with st.spinner("Looking at your meal…"):
            answer, model_content = generate_reply(gemini_client(key), model,
                                                   st.session_state.history, content)
        st.session_state.history.extend([content, model_content])
        st.session_state.messages.extend([
            {"role": "user", "text": text, "image": photo_bytes},
            {"role": "assistant", "text": answer},
        ])
        st.session_state.summary = ""
        st.rerun()
    except ValueError as error:
        st.error(str(error))
    except Exception as error:
        st.error(friendly_error(error))
        st.caption("This turn was not saved. Please resubmit it when ready.")

