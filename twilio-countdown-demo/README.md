## Twilio setup

1. Run this to set up .env file (skip if you already have it):
    ```bash
    cd $(git rev-parse --show-toplevel)/twilio-countdown-demo
    cp -n .template.env .env
    ```
1. For the account SID, go to the console and scroll down to 'Account Info': https://console.twilio.com/
    - Add to .env file variable `TWILIO_ACCOUNT_SID`
1. For the messaging ID, go here and grab the 'Test Service' Sid: https://console.twilio.com/us1/develop/sms/services
    - Add to .env file variable `TWILIO_MESSAGING_SERVICE_SID`
1. For Auth Token, go to: https://console.twilio.com/us1/account/keys-credentials/api-keys
    - Add to .env file variable `TWILIO_AUTH_TOKEN`

## Run Python Script

```bash
uv run python countdown.py
```
