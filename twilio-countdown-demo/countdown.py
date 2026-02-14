import os
import time
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv('TWILIO_ACCOUNT_SID')

messaging_service_sid = os.getenv('TWILIO_MESSAGING_SERVICE_SID')

auth_token = os.getenv('TWILIO_AUTH_TOKEN')

to_number = f'+{os.getenv("TWILIO_TEST_NUMBER")}'

# Click here to see the message logs after running this script:
# https://console.twilio.com/us1/develop/sms/overview

client = Client(account_sid, auth_token)

def send_reminder(message):
    """Send a reminder message via Twilio"""
    try:
        message = client.messages.create(
            messaging_service_sid=messaging_service_sid,
            to=to_number,
            body=message
        )
        print(f"Message sent! SID: {message.sid}")
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

if __name__ == "__main__":
    send_reminder("You have an appointment in 30 seconds")
    time.sleep(15)  # Wait 15 seconds

    # Second reminder - 15 seconds
    send_reminder("You have an appointment in 15 seconds")
    time.sleep(15)  # Wait another 15 seconds

    # Final reminder - starting now
    send_reminder("Your appointment is starting")
