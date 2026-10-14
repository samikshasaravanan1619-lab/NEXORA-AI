# NEXORA-AI
NEXORA – An intelligent business automation dashboard for predictive analytics, inventory monitoring, cybersecurity alerts, sales pipeline management, and multilingual advertisement generation using Python and Streamlit.
NEXORA — Sales Pipeline Autopilot Update

WHAT'S NEW
1. Lead management from manually entered or authorized sources
2. Transparent lead scoring (fit 0–40, engagement 0–30, buying intent 0–30)
3. Consent-aware personalized outreach drafts (draft only; no auto-send)
4. Follow-up date tracking and due/overdue counts
5. Rule-based reply classification with human-review fallback
6. CRM pipeline stages and CSV export
7. Duplicate checks, opt-out handling, consent checks, and human approval reminders

RUN ON WINDOWS
1. Extract this ZIP into a folder.
2. Open that folder in VS Code.
3. In the terminal, run:  py -m pip install -r requirements.txt
4. Then run:  py -m streamlit run app.py
5. Open the local URL printed in the terminal (usually http://localhost:8501).

DATA
The app creates nexora.db in the same folder as app.py. Keep a backup of this file to preserve records.

IMPORTANT PROTOTYPE LIMITS
- This is a hackathon prototype, not a connected live CRM.
- Leads are entered manually or from sources you are authorized to use; there is no scraping.
- Outreach is drafted only; the app does not send email or messages.
- Reply classification uses simple keyword rules, so a human must review results.
- Lead scores are transparent prioritization aids, not validated predictions of conversion.
- Consent and opt-out fields are user-entered; they do not independently verify legal permission.
