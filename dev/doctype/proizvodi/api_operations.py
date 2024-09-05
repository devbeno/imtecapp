
import requests
import base64

def get_headers(settings):
    """Generate headers for API requests."""
    username = settings.username_erpimtec
    password = settings.get_password("password_erpimtec")
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    return {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/json",
    }

def make_get_request(url, headers):
    """Make a GET request to the given URL with the provided headers."""
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
