import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_auth_value(key_name):
    """Flexible helper to read specific keys from authorization.txt"""
    try:
        if not os.path.exists("authorization.txt"):
            print(f"[!] Error: authorization.txt not found in {os.getcwd()}")
            return None
        with open("authorization.txt", "r") as f:
            for line in f:
                # Ignore empty lines or lines without '='
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == key_name:
                        return v.strip()
    except Exception as e:
        print(f"[!] Error reading authorization.txt: {e}")
    return None

def send_job_email(new_jobs, recipient_email="navehhadas@gmail.com"):
    if not new_jobs:
        return

    # 1. Fetch Credentials using the helper
    sender_email = get_auth_value("EMAIL_USER")
    app_password = get_auth_value("EMAIL_PASS")

    if not sender_email or not app_password:
        print("[!] Email error: Missing EMAIL_USER or EMAIL_PASS in authorization.txt")
        return

    count = len(new_jobs)
    subject = f"Job Agent: Found {count} New Jobs"
    
    # --- CONSTRUCT EMAIL BODY ---
    body = f"Job Agent found {count} new opportunities for you.\n\n"
    body += "Quick List:\n"
    for job in new_jobs:
        body += f"- {job['title']} at {job['company']}\n"
    
    body += "\n--- Detailed View ---\n\n"
    for job in new_jobs:
        body += f"TITLE: {job['title']}\n"
        body += f"COMPANY: {job['company']}\n"
        body += f"LOCATION: {job['location']}\n"
        body += f"LINK: {job['url']}\n"
        body += f"FOUND AT: {job['found_at']}\n"
        body += "-" * 30 + "\n"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.send_message(msg)
        print(f"Successfully sent email for {count} jobs.")
    except Exception as e:
        print(f"Failed to send email: {e}")