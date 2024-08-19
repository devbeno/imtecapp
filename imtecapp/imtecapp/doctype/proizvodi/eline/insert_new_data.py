import frappe
import requests
import base64
import os
import hashlib
import json
import shutil

BATCH_SIZE = 1000


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


def generate_item_hash(item):
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
    hash_input = json.dumps(normalized_data, sort_keys=True)
    return hashlib.md5(hash_input.encode()).hexdigest()


def save_to_json(data, filename):
    directory_path = frappe.get_module_path("imtecapp", "data")
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    json_path = os.path.join(directory_path, filename)

    with open(json_path, mode="w") as file:
        json.dump(data, file, indent=4)


def fetch_and_combine_data(filename):
    combined_data = []
    api_names = ["artikli", "partneri", "grupe", "cijene", "cjenovnici"]
    settings = get_erpimtec_settings()
    headers = get_headers(settings)

    data_store = {}
    for api_name in api_names:
        url = get_api_url(api_name, settings)
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

    save_to_json(combined_data, filename)


def compare_and_create_for_insert_json():
    directory_path = frappe.get_module_path("imtecapp", "data")
    current_json_path = os.path.join(directory_path, "current_eline_data.json")
    new_json_path = os.path.join(directory_path, "new_eline_data.json")

    # Ensure current_eline_data.json exists
    if not os.path.exists(current_json_path):
        raise FileNotFoundError(f"No such file or directory: {current_json_path}")

    # Load current data
    with open(current_json_path, mode="r") as current_file:
        current_data = json.load(current_file)

    # Fetch new data and generate new_eline_data.json
    fetch_and_combine_data(new_json_path)

    # Load new data
    with open(new_json_path, mode="r") as new_file:
        new_data = json.load(new_file)

    # Create a mapping of art_sifra to the current data entries
    current_data_map = {item["art_sifra"]: item for item in current_data}

    for_insert_data = []

    for new_item in new_data:
        art_sifra = new_item["art_sifra"]
        new_hash = new_item["hash"]

        if art_sifra in current_data_map:
            current_item = current_data_map[art_sifra]
            current_hash = current_item["hash"]

            if new_hash != current_hash:
                # If the hashes differ, mark the item for update
                new_item["status"] = "for_update"
                for_insert_data.append(new_item)
        else:
            # If the item doesn't exist in current data, mark it for insert
            new_item["status"] = "for_insert"
            for_insert_data.append(new_item)

    # Save the resulting list of items to for_insert_eline_data.json
    save_to_json(for_insert_data, "for_insert_eline_data.json")

    # After processing, move new_eline_data.json to current_eline_data.json
    shutil.move(new_json_path, current_json_path)


def insert_data_from_for_insert_eline_data():
    directory_path = frappe.get_module_path("imtecapp", "data")
    for_insert_json_path = os.path.join(directory_path, "for_insert_eline_data.json")

    # Load the data from for_insert_eline_data.json
    with open(for_insert_json_path, mode="r") as file:
        data = json.load(file)

    for item in data:
        art_sifra = item["art_sifra"]
        # Directly update the record in Proizvodi based on art_sifra
        frappe.db.set_value("Proizvodi", {"art_sifra": art_sifra}, item)

    # Commit the changes to the database
    frappe.db.commit()


def insert_data_from_current_eline_data():
    directory_path = frappe.get_module_path("imtecapp", "data")
    current_json_path = os.path.join(directory_path, "current_eline_data.json")

    # Load the data from current_eline_data.json
    with open(current_json_path, mode="r") as file:
        data = json.load(file)

    to_insert = []

    for item in data:  # Since data is a list of products
        art_sifra = item["art_sifra"]

        # Check if the record already exists in Proizvodi
        existing_doc_name = frappe.db.exists("Proizvodi", {"art_sifra": art_sifra})

        if not existing_doc_name:
            # If it doesn't exist, prepare it for insertion
            item["name"] = frappe.generate_hash(
                length=10
            )  # Generate a unique name for the new document
            to_insert.append(item)

    # Insert new records in batches
    if to_insert:
        for i in range(0, len(to_insert), BATCH_SIZE):
            batch_to_insert = to_insert[i : i + BATCH_SIZE]
            frappe.db.bulk_insert(
                "Proizvodi",
                fields=list(batch_to_insert[0].keys()),
                values=[list(d.values()) for d in batch_to_insert],
            )

    # Commit the changes to the database
    frappe.db.commit()
