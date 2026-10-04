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
# FILE LOCATIONS
# =========================================================

# Local development:
#     C:\Users\Lohit\OneDrive\Desktop\CHARGE_PILOT\
#
# Render Secret Files:
#     /etc/secrets/


def get_secret_file(filename):
    """
    Return the correct path for a secret file.

    Priority:
    1. Render Secret Files
    2. Local project folder
    """

    render_path = os.path.join(
        "/etc/secrets",
        filename
    )

    local_path = os.path.join(
        os.path.dirname(
            os.path.abspath(__file__)
        ),
        filename
    )

    # Render
    if os.path.exists(render_path):
        return render_path

    # Local
    if os.path.exists(local_path):
        return local_path

    return None


# =========================================================
# GET GMAIL SERVICE
# =========================================================

def get_gmail_service():

    print()
    print("=" * 60)
    print("CHARGEPILOT GMAIL SERVICE")
    print("=" * 60)

    creds = None

    # -----------------------------------------------------
    # FIND TOKEN
    # -----------------------------------------------------

    token_path = get_secret_file(
        "token.json"
    )

    credentials_path = get_secret_file(
        "credentials.json"
    )

    print()

    if token_path:
        print(
            f"✓ Gmail token found: {token_path}"
        )
    else:
        print(
            "⚠ Gmail token.json not found."
        )

    if credentials_path:
        print(
            f"✓ Gmail credentials found: "
            f"{credentials_path}"
        )
    else:
        print(
            "⚠ Gmail credentials.json not found."
        )

    # -----------------------------------------------------
    # LOAD EXISTING TOKEN
    # -----------------------------------------------------

    if token_path:

        try:

            creds = Credentials.from_authorized_user_file(
                token_path,
                SCOPES
            )

            print(
                "✓ Existing Gmail authorization loaded."
            )

        except Exception as error:

            print(
                f"⚠ Could not load token.json: {error}"
            )

            creds = None

    # -----------------------------------------------------
    # REFRESH EXPIRED TOKEN
    # -----------------------------------------------------

    if (
        creds
        and creds.expired
        and creds.refresh_token
    ):

        try:

            print(
                "🔄 Gmail token expired."
            )

            print(
                "🔄 Refreshing Gmail authorization..."
            )

            creds.refresh(
                Request()
            )

            print(
                "✓ Gmail token refreshed successfully."
            )

        except Exception as error:

            print(
                f"❌ Gmail token refresh failed: {error}"
            )

            creds = None

    # -----------------------------------------------------
    # CHECK VALID CREDENTIALS
    # -----------------------------------------------------

    if creds and creds.valid:

        print(
            "✓ Gmail credentials are valid."
        )

    # -----------------------------------------------------
    # FIRST-TIME LOCAL AUTHENTICATION
    # -----------------------------------------------------

    if not creds or not creds.valid:

        # -------------------------------------------------
        # RENDER ENVIRONMENT
        # -------------------------------------------------

        if os.path.exists("/etc/secrets"):

            raise RuntimeError(
                "Gmail authorization is not available on Render. "
                "Authorize Gmail locally first and upload the "
                "generated token.json to Render Secret Files."
            )

        # -------------------------------------------------
        # LOCAL ENVIRONMENT
        # -------------------------------------------------

        if not credentials_path:

            raise FileNotFoundError(
                "credentials.json not found.\n\n"
                "For local development, place your Google OAuth "
                "credentials file here:\n"
                f"{os.path.dirname(os.path.abspath(__file__))}"
                "\n\n"
                "For Render, upload credentials.json and "
                "token.json under Secret Files."
            )

        print()
        print(
            "🔐 Starting Gmail OAuth authentication..."
        )

        print(
            "🌐 A browser window will open for Google login."
        )

        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_path,
            SCOPES
        )

        creds = flow.run_local_server(
            port=0
        )

        # -------------------------------------------------
        # SAVE TOKEN LOCALLY
        # -------------------------------------------------

        local_token_path = os.path.join(
            os.path.dirname(
                os.path.abspath(__file__)
            ),
            "token.json"
        )

        with open(
            local_token_path,
            "w",
            encoding="utf-8"
        ) as token_file:

            token_file.write(
                creds.to_json()
            )

        print()
        print(
            f"✓ Gmail authorization completed."
        )

        print(
            f"✓ Token saved to: {local_token_path}"
        )

    # -----------------------------------------------------
    # BUILD GMAIL API SERVICE
    # -----------------------------------------------------

    try:

        service = build(
            "gmail",
            "v1",
            credentials=creds
        )

        print(
            "✓ Gmail API service created successfully."
        )

        print(
            "=" * 60
        )

        return service

    except Exception as error:

        print(
            f"❌ Failed to create Gmail service: {error}"
        )

        raise


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

    # -----------------------------------------------------
    # SENDER
    # -----------------------------------------------------

    sender_email = os.getenv(
        "GMAIL_SENDER_EMAIL"
    )

    if sender_email:

        message["From"] = sender_email

    # -----------------------------------------------------
    # RECIPIENT
    # -----------------------------------------------------

    message["To"] = to_email

    # -----------------------------------------------------
    # SUBJECT
    # -----------------------------------------------------

    message["Subject"] = subject

    # -----------------------------------------------------
    # BODY
    # -----------------------------------------------------

    message.set_content(
        body
    )

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
        .decode("utf-8")
    )

    # -----------------------------------------------------
    # GET GMAIL SERVICE
    # -----------------------------------------------------

    service = get_gmail_service()

    # -----------------------------------------------------
    # SEND EMAIL
    # -----------------------------------------------------

    try:

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

    except Exception as error:

        print(
            f"❌ Gmail send error: {error}"
        )

        raise

    # -----------------------------------------------------
    # SUCCESS
    # -----------------------------------------------------

    print()
    print(
        "✓ Email sent successfully."
    )

    print(
        f"✓ Recipient: {to_email}"
    )

    print(
        f"✓ Message ID: {result.get('id')}"
    )

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

    print(
        "Email service loaded successfully."
    )

    print(
        "send_email_with_attachment() is available."
    )

    print()

    print(
        "Local credentials:",
        get_secret_file("credentials.json")
    )

    print(
        "Gmail token:",
        get_secret_file("token.json")
    )

    print()
    print("=" * 60)