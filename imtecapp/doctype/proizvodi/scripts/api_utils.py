# api_utils.py

import frappe
import base64
import requests

def get_erpimtec_settings():
    settings = frappe.get_single("Generalne Postavke")
    return settings

def get_headers(settings):
    username = settings.username_erpimtec
    password = settings.get_password("password_erpimtec")
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    return {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/json",
    }

def get_api_url(api_name, settings):
    api_field_map = {
        "artikli": settings.api_artikli,
        "partneri": settings.api_partneri,
        "grupe": settings.api_grupe,
        "cijene": settings.api_cjenovnik,
        "cjenovnici": settings.api_cjenovnik_sa_stanjem,
    }
    return api_field_map.get(api_name)

def make_get_request(url, headers):
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
