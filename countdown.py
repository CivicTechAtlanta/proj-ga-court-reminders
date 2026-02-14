import os
import time
from twilio.rest import Client

# Twilio setup
# For the account SID, go to the console and scroll down to 'Account Info':
# https://console.twilio.com/
# Then put it in your terminal:
# export TWILIO_ACCOUNT_SID='actual_sid_here'
account_sid = os.getenv('TWILIO_ACCOUNT_SID')

# For the messaging ID, go here and grab the 'Test Service' Sid:
# https://console.twilio.com/us1/develop/sms/services
# export TWILIO_MESSAGING_SERVICE_SID='actual_sid_here'
messaging_service_sid = os.getenv('TWILIO_MESSAGING_SERVICE_SID')

# AUTH TOKEN is here on the console:
# https://console.twilio.com/us1/account/keys-credentials/api-keys
# export TWILIO_AUTH_TOKEN='actual_token_here'
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

# This is our test number
to_number = '+18777804236'

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


send_reminder("You have an appointment in 30 seconds")
time.sleep(15)  # Wait 15 seconds

# Second reminder - 15 seconds
send_reminder("You have an appointment in 15 seconds")
time.sleep(15)  # Wait another 15 seconds

# Final reminder - starting now
send_reminder("Your appointment is starting")