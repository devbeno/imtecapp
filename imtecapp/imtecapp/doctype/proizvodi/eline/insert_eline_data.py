import frappe
import requests
import base64
import csv
import os
import hashlib

BATCH_SIZE = 1000
MAX_LENGTH = 255


def get_erpimtec_settings():
    settings = frappe.get_single("Generalne Postavke")
    return settings


def get_headers(settings):
    try:
        username = settings.username_erpimtec
        password = settings.get_password("password_erpimtec")
        if not username or not password:
            raise ValueError("USERNAME or PASSWORD environment variable is not set")

        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
        }
    except Exception as e:
        frappe.log_error(str(e), "API Request Failed")
        frappe.throw(str(e))


def get_api_url(api_name, settings):
    api_field_map = {
        "artikli": settings.api_artikli,
        "partneri": settings.api_partneri,
        "grupe": settings.api_grupe,
        "cijene": settings.api_cjenovnik,
        "cjenovnici": settings.api_cjenovnik_sa_stanjem,
    }
    return api_field_map.get(api_name, None)


def make_get_request(url, headers):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        frappe.log_error(
            f"HTTP error occurred: {http_err}, Status Code: {response.status_code}, Response: {response.text}",
            "API Request Failed",
        )
        return {}
    except Exception as err:
        frappe.log_error(f"Other error occurred: {err}", "API Request Failed")
        return {}


def generate_item_hash(item):
    """Generate a hash for the given item based on its critical fields."""
    try:
        hash_input = (
            f"{item.get('art_sifra', '')}{item.get('vpc', 0)}{item.get('aktivan', 0)}{item.get('stanje', 0)}"
            f"{item.get('art_naziv', '')}{item.get('kataloski', '')}{item.get('grupanaziv', '')}{item.get('proizvodjac', '')}"
        )
        return hashlib.md5(hash_input.encode()).hexdigest()
    except KeyError as e:
        frappe.log_error(
            f"Missing field during hash generation: {str(e)}", "Hash Generation Error"
        )
        return None


def normalize_and_sanitize_name(value, max_length=255):
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return truncate_string(value, max_length)


def truncate_string(value, max_length):
    if len(value) > max_length:
        return value[: max_length - 3] + "..."
    return value


def safe_strip(value):
    return value.strip() if isinstance(value, str) else value


def fetch_and_combine_data():
    combined_data = []
    api_names = ["artikli", "partneri", "grupe", "cijene", "cjenovnici"]
    settings = get_erpimtec_settings()
    headers = get_headers(settings)

    data_store = {}
    for api_name in api_names:
        url = get_api_url(api_name, settings)
        if not url:
            frappe.throw(f"Invalid API name: {api_name}")
        if api_name in ["cijene", "cjenovnici"]:
            headers["KorisnikX"] = settings.username_erpimtec
        response_data = make_get_request(url, headers)
        data_store[api_name] = response_data.get(api_name, [])

    artikli = data_store.get("artikli", [])
    partneri = data_store.get("partneri", [])
    grupe = data_store.get("grupe", [])
    cijene = data_store.get("cijene", [])
    cjenovnici = data_store.get("cjenovnici", [])

    partneri_map = {p["sifra"]: p for p in partneri}
    grupe_map = {g["agp_id"]: g for g in grupe}
    cijene_map = {c["art_sifra"]: c for c in cijene}
    cjenovnici_map = {c["skc_sifra"]: c for c in cjenovnici}

    for artikal in artikli:
        stanje = cjenovnici_map.get(artikal.get("art_sifra"), {}).get("stanje", 0)
        if isinstance(stanje, str):
            try:
                stanje = float(stanje)
                stanje = max(0, int(stanje))
            except ValueError:
                stanje = 0
        else:
            stanje = max(0, int(stanje))

        combined_entry = {
            "art_sifra": safe_strip(artikal.get("art_sifra", "")),
            "agp_id": safe_strip(artikal.get("art_grupa", "")),
            "sifra": safe_strip(artikal.get("proizvodjac", "")),
            "vpc": cijene_map.get(artikal.get("art_sifra"), {}).get("vpc", 0),
            "aktivan": (
                1
                if cijene_map.get(artikal.get("art_sifra"), {}).get("aktivan", False)
                else 0
            ),
            "stanje": stanje,
            "art_naziv": normalize_and_sanitize_name(
                safe_strip(artikal.get("art_naziv", "")), max_length=255
            ),
            "kataloski": safe_strip(artikal.get("kataloski", "")),
            "grupanaziv": normalize_and_sanitize_name(
                safe_strip(
                    grupe_map.get(artikal.get("art_grupa"), {}).get("agp_naziv", "")
                ),
                max_length=255,
            ),
            "proizvodjac": normalize_and_sanitize_name(
                safe_strip(
                    partneri_map.get(artikal.get("proizvodjac"), {}).get("p_naziv", "")
                ),
                max_length=255,
            ),
            "hash": generate_item_hash(
                {
                    "art_sifra": safe_strip(artikal.get("art_sifra", "")),
                    "vpc": cijene_map.get(artikal.get("art_sifra"), {}).get("vpc", 0),
                    "aktivan": (
                        1
                        if cijene_map.get(artikal.get("art_sifra"), {}).get(
                            "aktivan", False
                        )
                        else 0
                    ),
                    "stanje": stanje,
                    "art_naziv": normalize_and_sanitize_name(
                        safe_strip(artikal.get("art_naziv", "")), max_length=255
                    ),
                    "kataloski": safe_strip(artikal.get("kataloski", "")),
                    "grupanaziv": normalize_and_sanitize_name(
                        safe_strip(
                            grupe_map.get(artikal.get("art_grupa"), {}).get(
                                "agp_naziv", ""
                            )
                        ),
                        max_length=255,
                    ),
                    "proizvodjac": normalize_and_sanitize_name(
                        safe_strip(
                            partneri_map.get(artikal.get("proizvodjac"), {}).get(
                                "p_naziv", ""
                            )
                        ),
                        max_length=255,
                    ),
                }
            ),
        }
        combined_data.append(combined_entry)

    return combined_data


def save_to_csv(data):
    directory_path = frappe.get_module_path("imtecapp", "data")
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    csv_path = os.path.join(directory_path, "eline_data.csv")

    with open(csv_path, mode="w", newline="") as file:
        fieldnames = [
            "art_sifra",
            "agp_id",
            "sifra",
            "vpc",
            "aktivan",
            "stanje",
            "art_naziv",
            "kataloski",
            "grupanaziv",
            "proizvodjac",
            "hash",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    frappe.log_error(f"Data saved to CSV successfully at {csv_path}.", "CSV Export")


def insert_data_from_csv():
    directory_path = frappe.get_module_path("imtecapp", "data")
    csv_path = os.path.join(directory_path, "eline_data.csv")

    with open(csv_path, mode="r") as file:
        reader = csv.DictReader(file)
        combined_data = list(reader)

    to_insert = []
    to_update = []

    for data in combined_data:
        # Generate the hash for the current data
        data_hash = generate_item_hash(data)
        if not data_hash:
            frappe.log_error(
                f"Failed to generate hash for item: {data['art_sifra']}",
                "Hash Generation Error",
            )
            continue

        data["hash"] = data_hash

        existing_doc = frappe.db.get_value(
            "Proizvodi", {"art_sifra": data["art_sifra"]}, ["name", "hash"]
        )
        if existing_doc:
            existing_name, existing_hash = existing_doc
            if existing_hash != data["hash"]:
                data["name"] = existing_name
                to_update.append(data)
        else:
            data["name"] = data["art_sifra"]
            to_insert.append(data)

    if to_insert:
        columns = list(to_insert[0].keys())
        values = [list(d.values()) for d in to_insert]
        for i in range(0, len(values), BATCH_SIZE):
            batch_values = values[i : i + BATCH_SIZE]
            frappe.db.bulk_insert("Proizvodi", fields=columns, values=batch_values)
            frappe.log_error(
                f"Inserted batch of {len(batch_values)} items", "Processing Data"
            )

    if to_update:
        for item in to_update:
            try:
                frappe.db.set_value("Proizvodi", item["name"], item)
                frappe.log_error(
                    f"Updated record: {item['art_sifra']}", "update_proizvodi"
                )
            except Exception as e:
                frappe.log_error(
                    f"Error updating record {item['name']}: {str(e)}", "Update Failed"
                )

    frappe.db.commit()


def update_proizvodi():
    combined_data = fetch_and_combine_data()
    save_to_csv(combined_data)
    insert_data_from_csv()


def update_and_sync():
    update_proizvodi()
    return "HopCup!"
