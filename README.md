# MacroSnap 🥗

A Python Streamlit nutrition chat app built from your workshop guide. Describe food or attach a meal photo, ask follow-up questions, preview a summary, download it, or send it to your WhatsApp through Twilio.

## 1. Run on Windows / VS Code

Use Python 3.11 or newer (3.12 recommended). Extract the ZIP and open the `macrosnap` folder in VS Code. In its PowerShell terminal run each command:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
notepad .streamlit\secrets.toml
```

Fill in `GEMINI_API_KEY` and save. Then:

```powershell
.\venv\Scripts\python.exe -m streamlit run app.py
```

Open http://localhost:8501. These commands use the virtual environment directly, so PowerShell activation and execution-policy changes are unnecessary. Do not use `source venv/bin/activate` in PowerShell. If you already created `secrets.toml`, edit it; do not copy over it again.

For macOS/Linux:

```bash
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml and add your key.
venv/bin/python -m streamlit run app.py
```

## 2. Gemini setup

1. Get a key at https://aistudio.google.com/apikey.
2. Put it in `.streamlit/secrets.toml` as `GEMINI_API_KEY = "your-real-key"`.
3. The default model follows your guide: `gemini-3.5-flash`. Override `GEMINI_MODEL` if your account requires another text-and-image model.
4. Restart Streamlit after changing configuration. Billing/quota depends on your account.

No API keys are included. With no key the app shows setup help instead of crashing. Twilio is optional for chatting and downloading summaries. Environment variables with the same names take precedence over secrets.

## 3. WhatsApp sandbox (simplest testing path)

1. Sign up at https://www.twilio.com/try-twilio and open the WhatsApp sandbox in the Console.
2. Copy Account SID and Auth Token into the matching secrets settings.
3. Set `TWILIO_WHATSAPP_FROM` to the exact sender shown in your Console, including `whatsapp:`.
4. From **your own WhatsApp number**, send the sandbox join message shown by Twilio. Follow any rejoin instructions in the Console.
5. Send a fresh message, such as `hello`, to the sandbox sender. This opens the 24-hour customer-service window.
6. Leave `WHATSAPP_MODE = "session"`. No Content SID is needed in this mode.
7. Restart the app, enter that same recipient number with its country code, chat, generate a summary, check the 24-hour confirmation, and click Send.

The uploaded guide claims any app-button send requires a template. The actual distinction is the customer-service window: free-form messages are supported within 24 hours of a user message. Outside that window an approved template is required. Custom templates are not the appropriate sandbox path; use the session mode for arbitrary meal summaries.

## 4. Approved template mode (production sender)

Register a WhatsApp sender through Twilio and create/obtain approval for a suitable template in Content Template Builder. Template approval is controlled by WhatsApp and is not guaranteed. The code expects `{{1}}` = name and `{{2}}` = summary. An example to submit for review is:

> Hello {{1}}, your requested MacroSnap nutrition summary is ready: {{2}}. Nutrition values are approximate estimates.

Set `WHATSAPP_MODE = "template"`, set the approved `TWILIO_CONTENT_SID` (HX...), and set your registered sender. The app uses `content_sid` plus JSON `content_variables`. Do not use the sandbox's unrelated pre-approved templates for nutrition content. Follow WhatsApp opt-in and template requirements for production use.

A successful API request means **submitted to Twilio**, not delivered to the recipient. Check Twilio message logs for delivery/failure status. Repeated clicks for the same conversation revision are disabled within the current session. There are no automatic send retries. After an uncertain failure, check logs before retrying. This is not durable deduplication across restarts.

## 5. Try it

- Enter your name and number, then acknowledge Gemini processing.
- Type: `I ate 2 medium rotis, 1 katori dal and 1 cup curd. Estimate calories and macros.`
- Attach a JPG/PNG food photo, optionally with portion information.
- Ask: `The dal had one teaspoon of ghee. Update the estimate.`
- Generate a summary. Check that the correction is not counted as a second meal.
- Download it, or send it to your own joined WhatsApp number.

Images are validated, resized and re-encoded without original metadata before sending. Limit: 5 MB and 20 megapixels. Chat is limited to 30 exchanges per session to bound memory and API context use. Summaries use the entire successful conversation but do not mutate it. Failed turns are not stored. Summaries are AI-generated and should be reviewed for arithmetic and omissions.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit onboarding, chat, summary preview, send flow |
| `prompts.py` | Assistant personality and summary instructions |
| `core.py` | Number/name/image validation and safe error messages |
| `services.py` | Gemini requests and Twilio sending |
| `requirements.txt` | Runtime dependency ranges |
| `.streamlit/secrets.toml.example` | Empty credential template |
| `.streamlit/config.toml` | Green theme and upload limit |
| `tests/test_app.py` | Validation, mocked service and startup checks |

## Testing

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use mocks and do not contact Gemini or send WhatsApp messages. Live integration requires your credentials and sandbox enrollment.

## Deployment

Push the project to a private or public GitHub repository without secrets. On https://share.streamlit.io select the repo and `app.py`. Use Python 3.12. Paste your secret settings into the deployment's Secrets panel. A public app with your keys can incur API costs; add access control before sharing broadly. This workshop app has no user authentication or persistent database.

## Privacy and limitations

Meal text/photos are sent to Google; name, number and summary are sent to Twilio/WhatsApp only after a Send action. Chat lives in Streamlit session memory and can disappear after reload/restart. The app does not write conversations to disk. Provider retention is governed by their policies. Nutrition estimates cannot measure hidden oil, portion weight or ingredients; they are not medical advice. Do not commit `.streamlit/secrets.toml` or paste tokens into support chats.

## Troubleshooting

- **Module not found:** install requirements with the same `venv\Scripts\python.exe` used to start the app.
- **Model unavailable:** change `GEMINI_MODEL` to a supported model for your account.
- **Quota/rate limit:** check Google AI Studio usage and billing.
- **WhatsApp disabled:** complete Twilio settings and generate a summary first.
- **63015:** join/rejoin the sandbox using the recipient's WhatsApp number.
- **63016:** message the sender again to reopen the session, or use an approved production template.
- **Queued but no message:** inspect Twilio logs; API acceptance is not delivery.

## Official references

- Gemini SDK: https://googleapis.github.io/python-genai/
- Gemini model: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash
- Streamlit chat: https://docs.streamlit.io/develop/api-reference/chat/st.chat_input
- Twilio sandbox: https://www.twilio.com/docs/whatsapp/sandbox
- WhatsApp templates: https://www.twilio.com/docs/whatsapp/tutorial/send-whatsapp-notification-messages-templates
