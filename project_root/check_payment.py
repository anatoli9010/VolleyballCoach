import json
import ssl
import urllib.request
import urllib.error

def send_sms(phone_number: str, message: str) -> bool:
    """Изпраща SMS съобщение чрез външно API."""

    url = "https://sms-api.example.com/send"
    api_key = "your-api-key"

    data = json.dumps({
        "to": phone_number,
        "message": message
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    req = urllib.request.Request(url, data=data, headers=headers)

    context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, context=context) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(f"✅ SMS изпратен успешно. SID: {result.get('sid')}")
            return True

    except urllib.error.HTTPError as e:
        try:
            error_content = e.read().decode("utf-8") if e.fp else ''
            error_msg = json.loads(error_content).get("message", str(e)) if error_content else str(e)
        except Exception:
            error_msg = str(e)
        print(f"⚠️ HTTP грешка при изпращане на SMS: {error_msg}")

    except Exception as e:
        print(f"⚠️ Неочаквана грешка: {str(e)}")

    return False
