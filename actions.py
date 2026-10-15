"""
Real side-effect functions. Each one calls an external API.
Kept separate from graph node functions so they're easy to unit test standalone.
"""
import os
import smtplib
from email.mime.text import MIMEText
import requests
from dotenv import load_dotenv

load_dotenv()


def send_email(to_email: str, subject: str, body: str) -> str:
    """Simplest free option: Gmail SMTP with an App Password (no OAuth flow needed).
    Upgrade to the Gmail API + OAuth later if you need higher sending volume."""
    gmail_address = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, app_password)
        server.sendmail(gmail_address, [to_email], msg.as_string())

    return f"email_sent:{to_email}"


def create_notion_task(task: str, owner: str, due_date: str | None) -> str:
    token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_DATABASE_ID")

    properties = {
        "Task": {"title": [{"text": {"content": task}}]},
        "Owner": {"rich_text": [{"text": {"content": owner}}]},
    }
    if due_date:
        properties["Due"] = {"date": {"start": due_date}}

    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={"parent": {"database_id": db_id}, "properties": properties},
        timeout=10,
    )
    if not response.ok:
        # Surface Notion's actual reason instead of a generic "400 Bad Request"
        raise RuntimeError(f"Notion API error {response.status_code}: {response.text}")
    return f"notion_task_created:{response.json()['id']}"
