import os
import requests
import json
import smtplib
import datetime
from email.message import EmailMessage
from dotenv import load_dotenv
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Load environment variables from a .env file in the current directory
dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=dotenv_path, override=True)

# Grab secrets from environment
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# === 1. Send Email Utility ===
def send_email(to: str, subject: str, body: str) -> str:
    print(f"=== EMAIL SENDING ===")
    print("TO:", to)
    print("SUBJECT:", subject)
    print("BODY:", body)
    print("EMAIL_ADDRESS:", EMAIL_ADDRESS)
    print("EMAIL_PASSWORD:", EMAIL_PASSWORD if EMAIL_PASSWORD else "Not Set")

    # Check if email credentials are present
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return "[Email Config Error]: EMAIL_ADDRESS or EMAIL_PASSWORD not set."

    try:
        # Construct the email message
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to
        msg.set_content(body)

        # Send using Gmail SMTP server (SSL)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.ehlo()
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        return f"✅ Email sent to {to}."
    except Exception as e:
        print("[Email Error]:", e)
        return f"❌ Failed to send email: {str(e)}"

# === 1.5. Google Calendar Integration ===
def schedule_event(title: str, date: str, time: str, end_time: str = None, location: str = "", description: str = "") -> str:
    print(f"=== EVENT SCHEDULING ===")
    print("TITLE:", title)
    print("DATE:", date)
    print("TIME:", time)
    print("END TIME:", end_time)
    print("LOCATION:", location)
    print("DESCRIPTION:", description)

    # logic to fix date year if only DD-MM is passed and it’s in the past
    try:
        today = datetime.date.today()
        parsed_day = int(date.split("-")[2])
        parsed_month = int(date.split("-")[1])
        year = today.year
        target_date = datetime.date(year, parsed_month, parsed_day)
        if target_date < today:
            year += 1  # Move to next year if the date has already passed this year
        date = f"{year}-{parsed_month:02d}-{parsed_day:02d}"
    except:
        pass  # Fallback to original if already correct or invalid

    # Setup Google Calendar scopes and paths
    SCOPES = ['https://www.googleapis.com/auth/calendar.events']
    creds = None
    token_path = Path(__file__).resolve().parent / "token.json"
    credentials_path = Path(__file__).resolve().parent / "credentials.json"
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")  # Use 'primary' if not set

    try:
        # Use saved credentials if available
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(token_path)
        else:
            # Otherwise, launch auth flow
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token_file:
                token_file.write(creds.to_json())

        # Initialize Calendar service
        service = build('calendar', 'v3', credentials=creds)

        # Format start and end times
        start_dt = datetime.datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        if end_time:
            end_dt = datetime.datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")
        else:
            end_dt = start_dt + datetime.timedelta(minutes=30)

        # Build event payload
        event = {
            'summary': title,
            'location': location,
            'description': description,
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
        }

        # Push event to calendar
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()

        return (
            f"📅 Event '{title}' scheduled on {date} from {time} to {end_time or (start_dt + datetime.timedelta(minutes=30)).strftime('%H:%M')}.\n"
        )

    except Exception as e:
        print("[Calendar Error]:", e)
        return f"❌ Failed to schedule event: {str(e)}"

# === 2. Define Tool Descriptions for LLM ===

function_definitions = [
    {
        "name": "send_email",
        "description": "Send an email to someone with subject and body",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient's email"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "schedule_event",
        "description": "Schedule a calendar event with title, date, time, optional end_time, location, and description",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event title"},
                "date": {"type": "string", "description": "Event date in YYYY-MM-DD format"},
                "time": {"type": "string", "description": "Event start time in HH:MM format"},
                "end_time": {"type": "string", "description": "Event end time in HH:MM format (optional)"},
                "location": {"type": "string", "description": "Event location (optional)"},
                "description": {"type": "string", "description": "Event description (optional)"}
            },
            "required": ["title", "date", "time"]
        }
    }
]

# === 3. Core Agent Function ===
# Accepts a user prompt and decides whether to reply normally or trigger a tool
async def run_agent(user_input: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # System prompt + user message
    messages = [
        {
            "role": "system",
            "content": (
                "You are Chatty, a friendly assistant. Only call tools when the user "
                "explicitly asks you to send an email with recipient, subject, and body, "
                "or schedule an event with title, date, and time. "
                "If not, just continue chatting normally."
            )
        },
        {"role": "user", "content": user_input}
    ]

    # LLM payload with tool definitions and tool auto-calling enabled
    payload = {
        "model": "llama3-8b-8192",
        "messages": messages,
        "functions": function_definitions,
        "function_call": "auto",
        "temperature": 0.7
    }

    try:
        # Call Groq's OpenAI-compatible endpoint
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload
        )

        try:
            data = response.json()
        except Exception as e:
            print("[Groq API Response Error]:", e)
            print("Raw Response Text:", response.text)
            return "⚠️ Groq returned an invalid response. Check your API key or network connection."

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        function_name = None
        raw_args = "{}"

        # === 4. Check if the LLM decided to use a tool ===
        if "tool_calls" in message:
            tool_call = message["tool_calls"][0]
            function_name = tool_call.get("function", {}).get("name")
            raw_args = tool_call.get("function", {}).get("arguments", "{}")

        elif "function_call" in message:
            function_call = message["function_call"]
            function_name = function_call.get("name")
            raw_args = function_call.get("arguments", "{}")

        # === 5. Validate and Execute Tool Call ===
        if function_name and function_name in {"send_email", "schedule_event"}:
            try:
                arguments = json.loads(raw_args)

                # Double check that required args are present
                if function_name == "send_email":
                    if not all(k in arguments for k in ["to", "subject", "body"]):
                        raise ValueError("Incomplete function args for send_email")
                elif function_name == "schedule_event":
                    if not all(k in arguments for k in ["title", "date", "time"]):
                        raise ValueError("Incomplete function args for schedule_event")

            except Exception as e:
                print("[Invalid Function Call Blocked]:", raw_args)
                return "⚠️ Groq attempted a broken or hallucinated function call. Ignored."

            # Tool call is valid — go ahead and run the tool
            if function_name == "send_email":
                print("[Agent Debug] Calling send_email with:", arguments)
                return send_email(**arguments)

            elif function_name == "schedule_event":
                print("[Agent Debug] Calling schedule_event with:", arguments)
                return schedule_event(**arguments)

        # === 6. Fallback: Regular Text Reply ===
        if "content" in message:
            return message["content"]

        print("[Groq API Unknown Format]:", json.dumps(data, indent=2))
        return "🤖 Groq replied in an unknown format. Try again."

    except Exception as e:
        print("[Agent Runtime Error]:", e)
        return "⚠️ Something went wrong during agent processing."
