import os
import base64

from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from email.message import EmailMessage


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()


# =========================================================
# GMAIL CONFIGURATION
# =========================================================

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]


# =========================================================
# GET GMAIL SERVICE
# =========================================================

def get_gmail_service():

    creds = None

    # -----------------------------------------------------
    # LOAD EXISTING TOKEN
    # -----------------------------------------------------

    if os.path.exists("token.json"):

        creds = Credentials.from_authorized_user_file(
            "token.json",
            SCOPES
        )

    # -----------------------------------------------------
    # REFRESH EXPIRED TOKEN
    # -----------------------------------------------------

    if (
        creds
        and creds.expired
        and creds.refresh_token
    ):

        creds.refresh(Request())

    # -----------------------------------------------------
    # FIRST-TIME AUTHENTICATION
    # -----------------------------------------------------

    if not creds or not creds.valid:

        if not os.path.exists("credentials.json"):

            raise FileNotFoundError(
                "credentials.json not found. "
                "Please add your Gmail OAuth credentials "
                "to the ChargePilot project folder."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            SCOPES
        )

        creds = flow.run_local_server(
            port=0
        )

        # Save authentication token
        with open(
            "token.json",
            "w"
        ) as token:

            token.write(
                creds.to_json()
            )

    # -----------------------------------------------------
    # BUILD GMAIL API SERVICE
    # -----------------------------------------------------

    service = build(
        "gmail",
        "v1",
        credentials=creds
    )

    return service


# =========================================================
# SEND EMAIL WITH PDF ATTACHMENT
# =========================================================

def send_email_with_attachment(
    to_email,
    pdf_path,
    subject="ChargePilot EV Journey Plan",
    body=None
):

    # -----------------------------------------------------
    # VALIDATE EMAIL
    # -----------------------------------------------------

    if not to_email:

        raise ValueError(
            "Recipient email is required."
        )

    # -----------------------------------------------------
    # VALIDATE PDF PATH
    # -----------------------------------------------------

    if not pdf_path:

        raise ValueError(
            "PDF path is required."
        )

    # -----------------------------------------------------
    # CHECK PDF EXISTS
    # -----------------------------------------------------

    if not os.path.exists(pdf_path):

        raise FileNotFoundError(
            f"PDF file not found: {pdf_path}"
        )

    # -----------------------------------------------------
    # DEFAULT EMAIL BODY
    # -----------------------------------------------------

    if body is None:

        body = """
Hello,

Your ChargePilot AI-powered EV Journey Plan
is attached to this email.

The report contains:

- Route information
- EV battery analysis
- Charging station recommendations
- Charging cost
- Charging time
- AI journey recommendation
- Restaurant information

Thank you for using ChargePilot.

Safe travels!

ChargePilot AI
"""

    # -----------------------------------------------------
    # CREATE EMAIL MESSAGE
    # -----------------------------------------------------

    message = EmailMessage()

    # Sender
    sender_email = os.getenv(
        "GMAIL_SENDER_EMAIL"
    )

    if sender_email:

        message["From"] = sender_email

    # Recipient
    message["To"] = to_email

    # Subject
    message["Subject"] = subject

    # Body
    message.set_content(body)

    # -----------------------------------------------------
    # READ PDF
    # -----------------------------------------------------

    with open(
        pdf_path,
        "rb"
    ) as pdf_file:

        pdf_data = pdf_file.read()

    # -----------------------------------------------------
    # ATTACH PDF
    # -----------------------------------------------------

    message.add_attachment(
        pdf_data,
        maintype="application",
        subtype="pdf",
        filename=os.path.basename(
            pdf_path
        )
    )

    # -----------------------------------------------------
    # ENCODE EMAIL FOR GMAIL API
    # -----------------------------------------------------

    encoded_message = (
        base64.urlsafe_b64encode(
            message.as_bytes()
        )
        .decode()
    )

    # -----------------------------------------------------
    # GET GMAIL SERVICE
    # -----------------------------------------------------

    service = get_gmail_service()

    # -----------------------------------------------------
    # SEND EMAIL
    # -----------------------------------------------------

    result = (
        service.users()
        .messages()
        .send(
            userId="me",
            body={
                "raw": encoded_message
            }
        )
        .execute()
    )

    # -----------------------------------------------------
    # RETURN RESULT
    # -----------------------------------------------------

    return {
        "success": True,
        "message_id": result.get("id"),
        "message": "Email sent successfully."
    }


# =========================================================
# DIRECT FILE TEST
# =========================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("CHARGEPILOT EMAIL SERVICE")
    print("=" * 60)
    print()
    print("Email service loaded successfully.")
    print(
        "send_email_with_attachment() is available."
    )
    print()
    print("=" * 60)