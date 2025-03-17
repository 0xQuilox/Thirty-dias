import imaplib
import email
from textblob import TextBlob
import sys

# Ensure UTF-8 encoding for stdout (useful for Termux or non-UTF-8 environments)
sys.stdout.reconfigure(encoding='utf-8')

def check_phishing(email_content):
    """
    Analyze email content for phishing indicators.
    Works with any Unicode text.
    """
    try:
        blob = TextBlob(email_content)
        # Check for negative sentiment or phishing keywords
        if (blob.sentiment.polarity < 0 or 
            any(keyword in email_content.lower() for keyword in ["urgent", "click here", "verify now"])):
            return True
    except Exception as e:
        print(f"Error analyzing content: {e}")
    return False

def main():
    # Get email and password from user (supports any characters)
    username = input("Enter your email address: ").strip()
    password = input("Enter your password (or app password): ").strip()

    # Connect to IMAP server with UTF-8 support
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')  # Default to Gmail; modify if needed
        mail._encoding = 'utf-8'  # Force UTF-8 encoding for IMAP commands
    except Exception as e:
        print(f"Failed to connect to IMAP server: {e}")
        return

    # Attempt login with robust error handling
    try:
        mail.login(username, password)
        print("Login successful!")
    except imaplib.IMAP4.error as e:
        print(f"Login failed: {e}")
        print("If using Gmail, ensure you use an App Password (required for 2FA).")
        return
    except Exception as e:
        print(f"Unexpected login error: {e}")
        return

    # Select inbox (or modify to another folder)
    try:
        mail.select('inbox')
    except imaplib.IMAP4.error as e:
        print(f"Failed to select inbox: {e}")
        return

    # Search all emails
    try:
        _, data = mail.search(None, 'ALL')
        if not data[0]:  # Check if inbox is empty
            print("No emails found in inbox.")
            mail.close()
            mail.logout()
            return
    except Exception as e:
        print(f"Error searching emails: {e}")
        return

    # Process each email
    for num in data[0].split():
        try:
            _, msg_data = mail.fetch(num, '(RFC822)')
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Handle email payload (body) with flexible decoding
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        payload = part.get_payload(decode=True)
                        if payload:
                            # Decode with UTF-8, fall back to latin1 if needed
                            try:
                                email_content = payload.decode('utf-8', errors='ignore')
                            except UnicodeDecodeError:
                                email_content = payload.decode('latin1', errors='ignore')
                            if check_phishing(email_content):
                                subject = msg.get('Subject', 'No Subject')
                                print(f"Potential phishing email: {subject}")
                            break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    try:
                        email_content = payload.decode('utf-8', errors='ignore')
                    except UnicodeDecodeError:
                        email_content = payload.decode('latin1', errors='ignore')
                    if check_phishing(email_content):
                        subject = msg.get('Subject', 'No Subject')
                        print(f"Potential phishing email: {subject}")

        except Exception as e:
            print(f"Error processing email #{num}: {e}")
            continue

    # Clean up
    try:
        mail.close()
        mail.logout()
        print("Disconnected from server.")
    except Exception as e:
        print(f"Error during logout: {e}")

if __name__ == "__main__":
    main()
