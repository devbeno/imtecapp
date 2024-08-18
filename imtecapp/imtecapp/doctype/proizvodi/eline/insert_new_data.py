import frappe
import requests
import base64
import os
import hashlib
import json
from datetime import datetime

BATCH_SIZE = 1000


def create_log(operation, art_sifra, hash_value, status, message):
    log_entry = frappe.get_doc(
        {
            "doctype": "Data Logs",
            "timestamp": datetime.now(),
            "operation": operation,
            "art_sifra": art_sifra,
            "hash": hash_value,
            "status": status,
            "message": json.dumps({"status": status, **message}),
        }
    )
    log_entry.insert(ignore_permissions=True)
    frappe.db.commit()


def create_batch_log(operation, status, message):
    log_entry = frappe.get_doc(
        {
            "doctype": "Data Logs",
            "timestamp": datetime.now(),
            "operation": operation,
            "status": status,
            "message": json.dumps({"status": status, **message}),
        }
    )
    log_entry.insert(ignore_permissions=True)
    frappe.db.commit()


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
        create_log(
            "Error",
            None,
            None,
            "Failure",
            {"detail": "API Request Failed", "error": str(e)},
        )
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
        create_log(
            "Error",
            None,
            None,
            "Failure",
            {
                "detail": "HTTP error occurred",
                "status_code": response.status_code,
                "response_text": response.text,
                "error": str(http_err),
            },
        )
        return {}
    except Exception as err:
        create_log(
            "Error",
            None,
            None,
            "Failure",
            {"detail": "Other error occurred", "error": str(err)},
        )
        return {}


def generate_item_hash(item):
    try:
        # Normalize the data
        normalized_data = {
            "art_sifra": item.get("art_sifra", "").strip().lower(),
            "vpc": float(item.get("vpc", 0)),
            "aktivan": bool(item.get("aktivan", 0)),
            "stanje": int(item.get("stanje", 0)),
            "art_naziv": item.get("art_naziv", "").strip().lower(),
            "kataloski": item.get("kataloski", "").strip().lower(),
            "grupanaziv": item.get("grupanaziv", "").strip().lower(),
            "proizvodjac": item.get("proizvodjac", "").strip().lower(),
        }
        # Serialize to JSON and hash
        hash_input = json.dumps(normalized_data, sort_keys=True)
        return hashlib.md5(hash_input.encode()).hexdigest()
    except KeyError as e:
        create_log(
            "Error",
            item.get("art_sifra", None),
            None,
            "Failure",
            {"detail": "Missing field during hash generation", "error": str(e)},
        )
        return None


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
            "art_sifra": artikal.get("art_sifra", ""),
            "agp_id": artikal.get("art_grupa", ""),
            "sifra": artikal.get("proizvodjac", ""),
            "vpc": cijene_map.get(artikal.get("art_sifra"), {}).get("vpc", 0),
            "aktivan": (
                1
                if cijene_map.get(artikal.get("art_sifra"), {}).get("aktivan", False)
                else 0
            ),
            "stanje": stanje,
            "art_naziv": artikal.get("art_naziv", ""),
            "kataloski": artikal.get("kataloski", ""),
            "grupanaziv": grupe_map.get(artikal.get("art_grupa"), {}).get(
                "agp_naziv", ""
            ),
            "proizvodjac": partneri_map.get(artikal.get("proizvodjac"), {}).get(
                "p_naziv", ""
            ),
            "hash": generate_item_hash(
                {
                    "art_sifra": artikal.get("art_sifra", ""),
                    "vpc": cijene_map.get(artikal.get("art_sifra"), {}).get("vpc", 0),
                    "aktivan": (
                        1
                        if cijene_map.get(artikal.get("art_sifra"), {}).get(
                            "aktivan", False
                        )
                        else 0
                    ),
                    "stanje": stanje,
                    "art_naziv": artikal.get("art_naziv", ""),
                    "kataloski": artikal.get("kataloski", ""),
                    "grupanaziv": grupe_map.get(artikal.get("art_grupa"), {}).get(
                        "agp_naziv", ""
                    ),
                    "proizvodjac": partneri_map.get(artikal.get("proizvodjac"), {}).get(
                        "p_naziv", ""
                    ),
                }
            ),
        }
        combined_data.append(combined_entry)

    return combined_data


def save_to_json(data, filename):
    directory_path = frappe.get_module_path("imtecapp", "data")
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    json_path = os.path.join(directory_path, filename)

    with open(json_path, mode="w") as file:
        json.dump(data, file, indent=4)


def ensure_current_json_exists():
    directory_path = frappe.get_module_path("imtecapp", "data")
    current_json_path = os.path.join(directory_path, "current_eline_data.json")

    if not os.path.exists(current_json_path):
        combined_data = fetch_and_combine_data()
        save_to_json(combined_data, "current_eline_data.json")


def compare_and_create_for_insert_json():
    directory_path = frappe.get_module_path("imtecapp", "data")
    current_json_path = os.path.join(directory_path, "current_eline_data.json")
    new_json_path = os.path.join(directory_path, "new_eline_data.json")

    with open(current_json_path, mode="r") as current_file:
        current_data = json.load(current_file)

    with open(new_json_path, mode="r") as new_file:
        new_data = json.load(new_file)

    current_data_map = {item["art_sifra"]: item for item in current_data}

    for_insert_data = []

    for new_item in new_data:
        art_sifra = new_item["art_sifra"]
        new_hash = new_item["hash"]

        if art_sifra in current_data_map:
            current_item = current_data_map[art_sifra]
            current_hash = current_item["hash"]

            if new_hash != current_hash:
                new_item["status"] = "for_update"
                for_insert_data.append(new_item)
        else:
            new_item["status"] = "for_insert"
            for_insert_data.append(new_item)

    save_to_json(for_insert_data, "for_insert_eline_data.json")


def update_proizvodi():
    ensure_current_json_exists()
    combined_data = fetch_and_combine_data()
    save_to_json(combined_data, "new_eline_data.json")
    compare_and_create_for_insert_json()

    # Copy the new_eline_data.json to current_eline_data.json instead of replacing it
    directory_path = frappe.get_module_path("imtecapp", "data")
    current_json_path = os.path.join(directory_path, "current_eline_data.json")
    new_json_path = os.path.join(directory_path, "new_eline_data.json")

    # Copy the contents of new_eline_data.json to current_eline_data.json
    with open(new_json_path, "r") as new_file:
        new_data = new_file.read()

    with open(current_json_path, "w") as current_file:
        current_file.write(new_data)


def manual_proizvodi():
    ensure_current_json_exists()

    # Just compare the existing new_eline_data.json with current_eline_data.json
    compare_and_create_for_insert_json()

    # Copy the new_eline_data.json to current_eline_data.json instead of replacing it
    directory_path = frappe.get_module_path("imtecapp", "data")
    current_json_path = os.path.join(directory_path, "current_eline_data.json")
    new_json_path = os.path.join(directory_path, "new_eline_data.json")

    # Copy the contents of new_eline_data.json to current_eline_data.json
    with open(new_json_path, "r") as new_file:
        new_data = new_file.read()

    with open(current_json_path, "w") as current_file:
        current_file.write(new_data)


def insert_data_from_json(json_path, assume_insert=True):
    with open(json_path, mode="r") as file:
        combined_data = json.load(file)

    to_insert = []
    to_update = []

    for item in combined_data:
        art_sifra = item["art_sifra"]
        status = item.pop("status", "for_insert" if assume_insert else "for_update")

        existing_doc_name = frappe.db.exists("Proizvodi", {"art_sifra": art_sifra})

        if existing_doc_name:
            if status == "for_update":
                item["status"] = status  # Ensure status field is updated
                to_update.append(item)
        else:
            if status == "for_insert":
                item["name"] = frappe.generate_hash(length=10)
                item["status"] = status
                to_insert.append(item)

    inserted_items = []
    updated_items = []

    if to_insert:
        for i in range(0, len(to_insert), BATCH_SIZE):
            batch_to_insert = to_insert[i : i + BATCH_SIZE]
            frappe.db.bulk_insert(
                "Proizvodi",
                fields=list(batch_to_insert[0].keys()),
                values=[list(d.values()) for d in batch_to_insert],
            )
            inserted_items.extend([item["art_sifra"] for item in batch_to_insert])

    if to_update:
        for item in to_update:
            frappe.db.set_value("Proizvodi", {"art_sifra": item["art_sifra"]}, item)
            updated_items.append(item["art_sifra"])

    if inserted_items:
        create_batch_log(
            "Insert", "for_insert", {"message": f"Inserted items: {inserted_items}"}
        )
    if updated_items:
        create_batch_log(
            "Update", "for_update", {"message": f"Updated items: {updated_items}"}
        )

    frappe.db.commit()


def clear_and_update_status():
    # Clear the 'status' field for all records in 'Proizvodi'
    # frappe.db.sql("UPDATE `tabProizvodi` SET status = ''")
    # frappe.db.sql(
    #     """
    #     UPDATE `tabProizvodi`
    #     SET status = ''
    #     WHERE status != 'on_presta'
    # """
    # )
    # Load the for_insert_eline_data.json file
    directory_path = frappe.get_module_path("imtecapp", "data")
    for_insert_json_path = os.path.join(directory_path, "for_insert_eline_data.json")

    with open(for_insert_json_path, mode="r") as file:
        for_insert_data = json.load(file)

    # Update the 'status' field in Proizvodi based on the for_insert_eline_data.json
    for item in for_insert_data:
        art_sifra = item["art_sifra"]
        status = item["status"]
        frappe.db.set_value("Proizvodi", {"art_sifra": art_sifra}, "status", status)

    frappe.db.commit()


def manual_insert_from_current():
    directory_path = frappe.get_module_path("imtecapp", "data")
    current_json_path = os.path.join(directory_path, "current_eline_data.json")
    insert_data_from_json(current_json_path, assume_insert=True)


def manual_testing_no_download():
    manual_proizvodi()
    insert_data_from_json(
        os.path.join(
            frappe.get_module_path("imtecapp", "data"), "for_insert_eline_data.json"
        )
    )
    clear_and_update_status()
    return "HopCup!"


def download_new_eline_data():
    combined_data = (
        fetch_and_combine_data()
    )  # Fetches and combines data from the external API
    save_to_json(
        combined_data, "new_eline_data.json"
    )  # Saves the combined data to new_eline_data.json
    return "New eline data downloaded successfully."


def update_and_sync():
    update_proizvodi()
    insert_data_from_json(
        os.path.join(
            frappe.get_module_path("imtecapp", "data"), "for_insert_eline_data.json"
        )
    )
    clear_and_update_status()
    return "HopCup!"
