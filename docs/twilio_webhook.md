# Twilio Webhook Setup with Azure Functions
 
## Twilio Console Configuration
 
### Configuring the Webhook URL
 
1. Log in to the [Twilio Console](https://console.twilio.com/).
2. Navigate to **Phone Numbers → Manage → Active Numbers**.
3. Click on the phone number you want to configure.
4. Scroll down to the **Messaging** section.
5. Under **"A message comes in"**, set:
   - **Webhook** (dropdown on the left)
   - Your Azure Function URL, e.g. `https://your-app.azurewebsites.net/api/twiliohandler`
   - **HTTP POST** (dropdown on the right)
6. Click **Save configuration**.
 
### Webhook Method and Fallback
 
- **HTTP POST** is recommended. Twilio sends the SMS data as `application/x-www-form-urlencoded` form fields.
- **HTTP GET** is also supported — Twilio appends the data as query parameters — but POST is the standard choice.
- **Fallback URL** (optional): You can configure a secondary URL under the same section. If your primary webhook returns an error (non-2xx status), Twilio will retry the request to the fallback URL.
- **Status Callback URL** (optional): Set this to receive delivery status updates (sent, delivered, failed, etc.) for outgoing messages.
 
---
 
## TwiML Reference — Sending Messages
 
TwiML (Twilio Markup Language) is the XML format your webhook returns to tell Twilio what to do. Every response must be wrapped in a `<Response>` root element.
 
### Basic Reply
 
Send a single text message back to the sender:
 
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Thanks for reaching out! We'll get back to you shortly.</Message>
</Response>
```
 
### Multiple Messages
 
You can include multiple `<Message>` elements. Twilio sends them in order:
 
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Welcome to our service!</Message>
    <Message>Reply HELP for a list of commands.</Message>
</Response>
```
 
### Sending Media (MMS)
 
Attach an image or other media file using the `<Media>` element inside `<Message>`:
 
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>
        Here's a photo for you!
        <Media>https://example.com/image.jpg</Media>
    </Message>
</Response>
```
 
You can include multiple `<Media>` elements for multiple attachments (up to 10):
 
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>
        Check out these images:
        <Media>https://example.com/photo1.jpg</Media>
        <Media>https://example.com/photo2.jpg</Media>
    </Message>
</Response>
```
 
> **Note:** MMS is supported on US and Canadian phone numbers. International numbers will fall back to sending the media URL as a link.
 
### Sending to a Specific Number
 
Use the `to` attribute to send a message to a number other than the original sender:
 
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message to="+15559876543">This goes to a different number.</Message>
</Response>
```
 
### Redirecting to Another Endpoint
 
Hand off processing to a different URL using `<Redirect>`:
 
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">https://your-app.azurewebsites.net/api/other-handler</Redirect>
</Response>
```
 
Twilio will make a new request to that URL and use its TwiML response instead.
 
### Empty Response (No Reply)
 
If you want to accept the message but not reply, return an empty `<Response>`:
 
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response/>
```
 
This is useful when you just want to log or process the incoming message silently.
 
---
 
## Incoming Webhook Payload
 
When Twilio POSTs to your webhook, it sends `application/x-www-form-urlencoded` data. **Do not parse this as JSON** — use `req.form` in Azure Functions, not `req.get_json()`.
 
### Standard SMS Fields
 
| Field              | Description                                      | Example                |
|--------------------|--------------------------------------------------|------------------------|
| `MessageSid`       | Unique identifier for the message                | `SM1234567890abcdef`   |
| `AccountSid`       | Your Twilio account SID                          | `AC1234567890abcdef`   |
| `From`             | Sender's phone number (E.164 format)             | `+15551234567`         |
| `To`               | Your Twilio phone number that received the SMS   | `+15559876543`         |
| `Body`             | The text content of the message                  | `Hello there!`         |
| `NumSegments`      | Number of SMS segments                           | `1`                    |
| `FromCity`         | Sender's city (if available)                     | `Atlanta`              |
| `FromState`        | Sender's state (if available)                    | `GA`                   |
| `FromCountry`      | Sender's country                                 | `US`                   |
| `FromZip`          | Sender's zip code (if available)                 | `30344`                |
 
### Media Fields (MMS)
 
If the incoming message contains media (images, etc.), these additional fields are included:
 
| Field              | Description                                      |
|--------------------|--------------------------------------------------|
| `NumMedia`         | Number of media attachments (`0` for plain SMS)  |
| `MediaUrl0`        | URL of the first media attachment                |
| `MediaContentType0`| MIME type of the first attachment (e.g. `image/jpeg`) |
 
For multiple attachments, the index increments: `MediaUrl1`, `MediaContentType1`, etc.
 
---
 
## Security — Validating Twilio Requests
 
To verify that incoming requests are actually from Twilio (and not a third party hitting your public endpoint), validate the `X-Twilio-Signature` header using your Auth Token.
 
Install the Twilio helper library:
 
```bash
pip install twilio
```
 
Validation function:
 
```python
from twilio.request_validator import RequestValidator
import os
 
def is_valid_twilio_request(req) -> bool:
    validator = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"])
    signature = req.headers.get("X-Twilio-Signature", "")
    url = req.url
    params = dict(req.form)
    return validator.validate(url, params, signature)
```
 
Usage in your function:
 
```python
if not is_valid_twilio_request(req):
    return func.HttpResponse("Forbidden", status_code=403)
```
 
Store your `TWILIO_AUTH_TOKEN` in:
- **Local development:** `local.settings.json` under `Values`
- **Production:** Azure Portal → Function App → Configuration → Application Settings
