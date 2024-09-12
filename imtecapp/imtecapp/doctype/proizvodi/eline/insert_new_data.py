import frappe
import requests
import base64
import os
import hashlib
import json
import shutil
import time
from imtecapp.api import get_prestashop_mappings
from imtecapp.utils import (
    add_message_to_log,
    create_sync_log_record,
    update_sync_log_record,
    truncate_message
)
BATCH_SIZE = 1000

def get_erpimtec_settings():
    settings = frappe.get_single("Generalne Postavke")
    return settings


# def add_message_to_log(sync_log, message):
#     """Append a message to the Sync Log."""
#     if sync_log:
#         if sync_log.log_details:
#             sync_log.log_details += message + "\n"
#         else:
#             sync_log.log_details = message + "\n"
#         sync_log.save(ignore_permissions=True)
#         frappe.db.commit()

# def create_sync_log_record(operation_name):
#     # Create a new Sync Log entry
#     sync_log = frappe.get_doc({
#         "doctype": "Sync Log",
#         "operation_name": operation_name,
#         "start_time": frappe.utils.now(),
#         "status": "In Progress",
#     })
#     sync_log.insert(ignore_permissions=True)
#     frappe.db.commit()
#     return sync_log


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



# def insert_data_from_for_insert_eline_data():
#     try:
#         compare_and_create_for_insert_json()
#         directory_path = frappe.get_module_path("imtecapp", "data")
#         for_insert_json_path = os.path.join(directory_path, "for_insert_eline_data.json")

#         # Load the data from for_insert_eline_data.json
#         with open(for_insert_json_path, mode="r") as file:
#             data = json.load(file)

#         for item in data:
#             art_sifra = item["art_sifra"]
#             try:
#                 new_doc = frappe.get_doc({
#                     "doctype": "Proizvodi",
#                     "art_sifra": item.get("art_sifra", ""),
#                     "agp_id": item.get("agp_id", ""),
#                     "sifra": item.get("sifra", ""),
#                     "vpc": item.get("vpc", 0.0),
#                     "aktivan": item.get("aktivan", 0),
#                     "stanje": item.get("stanje", 0),
#                     "art_naziv": item.get("art_naziv", ""),
#                     "kataloski": item.get("kataloski", ""),
#                     "grupanaziv": item.get("grupanaziv", ""),
#                     "proizvodjac": item.get("proizvodjac", ""),
#                     "status": item.get("status", ""),
#                     "hash": item.get("hash", ""),
#                     # Add any additional fields that are required in your Proizvodi doctype:
#                     # "field_name": item.get("json_key", default_value),
#                 })
#                 new_doc.insert(ignore_permissions=True)
#                 add_message_to_log(sync_log, f"Inserted {art_sifra} into Proizvodi.")
#             except Exception as e:
#                 # Log the exact product that failed
#                 frappe.log_error(f"Failed to insert {art_sifra}: {str(e)}", "Insert Proizvodi Error")

#         # Commit the changes to the database
#         frappe.db.commit()

#     except Exception as e:
#         frappe.log_error(f"Error during data insert: {str(e)}", "Insert Proizvodi Error")





# def determine_status(current_data_map, new_item, prestashop_mappings):
#     """
#     Determine the status of the new item based on existing data and PrestaShop mappings.
#     """
#     art_sifra = new_item["art_sifra"]
#     new_hash = new_item["hash"]
#     status = None
    
#     # Check for existing record in current data
#     if art_sifra in current_data_map:
#         current_item = current_data_map[art_sifra]
#         current_hash = current_item["hash"]

#         if new_hash != current_hash:
#             status = "for_update"
#         else:
#             add_message_to_log(sync_log, f"Skipping {art_sifra} as it is already up to date.")
#             return None
#     else:
#         # Check category and manufacturer mappings in PrestaShop
#         agp_id = str(new_item.get("agp_id", ""))
#         grupanaziv = new_item.get("grupanaziv", "")
#         sifra = new_item.get("sifra", "")
#         proizvodjac = new_item.get("proizvodjac", "")

#         # Determine category status
#         category_match = any(
#             cat["agp_id"] == agp_id and cat["grupanaziv"] == grupanaziv
#             for cat in prestashop_mappings["categories"]
#         )

#         if not category_match:
#             # Check if agp_id matches but grupanaziv does not
#             agp_id_match = any(
#                 cat["agp_id"] == agp_id for cat in prestashop_mappings["categories"]
#             )

#             if agp_id_match:
#                 status = "for_rename"
#                 add_message_to_log(sync_log, f"Marked {art_sifra} as for_rename for category name change.")
#             else:
#                 status = "for_insert"
#                 add_message_to_log(sync_log, f"Marked {art_sifra} as for_insert for new category.")

#         # Determine manufacturer status
#         manufacturer_match = any(
#             man["agp_id"] == sifra and man["proizvodjac"] == proizvodjac
#             for man in prestashop_mappings["manufacturers"]
#         )

#         if not manufacturer_match:
#             # Check if agp_id (manufacturer's ID) matches but proizvodjac does not
#             agp_id_match = any(
#                 man["agp_id"] == sifra for man in prestashop_mappings["manufacturers"]
#             )

#             if agp_id_match:
#                 status = "for_rename"
#                 add_message_to_log(sync_log, f"Marked {art_sifra} as for_rename for manufacturer name change.")
#             else:
#                 status = "for_insert"
#                 add_message_to_log(sync_log, f"Marked {art_sifra} as for_insert for new manufacturer.")

#     return status

def determine_status(current_data_map, new_item):
    """
    Determine the status of the new item based on existing data.
    This function compares the new data with the current data and sets the status.
    """
    art_sifra = new_item["art_sifra"]
    new_hash = new_item["hash"]
    status = None

    # Check for existing record in current data
    if art_sifra in current_data_map:
        current_item = current_data_map[art_sifra]
        current_hash = current_item["hash"]

        # If the hash has changed, mark for update
        if new_hash != current_hash:
            status = "for_update"
        else:
            print(f"Skipping {art_sifra} as it is already up to date.")
            return None

        # Compare grupanaziv and proizvodjac to check if renaming is needed
        if new_item.get("grupanaziv") != current_item.get("grupanaziv"):
            status = "for_rename"
            print(f"Marked {art_sifra} as for_rename for category name change.")
        
        if new_item.get("proizvodjac") != current_item.get("proizvodjac"):
            status = "for_rename"
            print(f"Marked {art_sifra} as for_rename for manufacturer name change.")

    else:
        # If the item does not exist in current data, mark for insert
        status = "for_insert"
        print(f"Marked {art_sifra} as for_insert.")

    return status



def compare_and_create_for_insert_json():
    directory_path = frappe.get_module_path("imtecapp", "data")
    current_json_path = os.path.join(directory_path, "current_eline_data.json")
    new_json_path = os.path.join(directory_path, "new_eline_data.json")

    # Ensure the data directory exists
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    # Fetch all data from the "Proizvodi" doctype and save to current_eline_data.json
    proizvodi_data = frappe.get_all(
        "Proizvodi",
        fields=[
            "art_sifra", "agp_id", "sifra", "vpc", "aktivan",
            "stanje", "art_naziv", "kataloski", "grupanaziv", "proizvodjac", "hash"
        ]
    )

    # Save fetched data to current_eline_data.json
    save_to_json(proizvodi_data, current_json_path)

    # Fetch new data and generate new_eline_data.json
    fetch_and_combine_data(new_json_path)

    # Load current data
    with open(current_json_path, mode="r") as current_file:
        current_data = json.load(current_file)

    # Load new data
    with open(new_json_path, mode="r") as new_file:
        new_data = json.load(new_file)

    # Create a mapping of art_sifra to the current data entries
    current_data_map = {item["art_sifra"]: item for item in current_data}

    for_insert_data = []

    # Compare the data and prepare for insert, update, or rename
    for new_item in new_data:
        status = determine_status(current_data_map, new_item)
        if status:
            new_item["status"] = status
            for_insert_data.append(new_item)

    # Save the resulting list of items to for_insert_eline_data.json
    save_to_json(for_insert_data, "for_insert_eline_data.json")

    # After processing, move new_eline_data.json to current_eline_data.json
    shutil.move(new_json_path, current_json_path)




def insert_data_from_for_insert_eline_data(sync_log, batch_size=100):
    compare_and_create_for_insert_json()
    directory_path = frappe.get_module_path("imtecapp", "data")
    for_insert_json_path = os.path.join(directory_path, "for_insert_eline_data.json")

    # Load the data from for_insert_eline_data.json
    with open(for_insert_json_path, mode="r") as file:
        data = json.load(file)

    total_products = len(data)
    print(f"Starting the sync for {total_products} products...")

    to_insert = []  # This will store all records to be inserted in bulk

    for i in range(0, total_products, batch_size):
        batch = data[i:i + batch_size]
        start_time = time.time()

        for item in batch:
            # Add 'name' field by using Frappe's method to generate it
            name = frappe.generate_hash(length=10)  # Optionally use a custom naming convention
            to_insert.append({
                "name": name,
                "art_sifra": item.get("art_sifra", ""),
                "agp_id": item.get("agp_id", ""),
                "sifra": item.get("sifra", ""),
                "vpc": item.get("vpc", 0.0),
                "aktivan": item.get("aktivan", 0),
                "stanje": item.get("stanje", 0),
                "art_naziv": item.get("art_naziv", ""),
                "kataloski": item.get("kataloski", ""),
                "grupanaziv": item.get("grupanaziv", ""),
                "proizvodjac": item.get("proizvodjac", ""),
                "status": item.get("status", ""),
                "hash": item.get("hash", "")
            })

        # Bulk insert after processing the batch
        if to_insert:
            for j in range(0, len(to_insert), batch_size):
                batch_insert = to_insert[j:j + batch_size]
                try:
                    frappe.db.bulk_insert(
                        "Proizvodi",
                        fields=list(batch_insert[0].keys()),
                        values=[list(d.values()) for d in batch_insert],
                    )

                    # Log the progress
                    print(
                        "Inserted batch {} of {} in {:.2f} seconds".format(
                            j // batch_size + 1,
                            (total_products // batch_size) + 1,
                            time.time() - start_time,
                        )
                    )
                except Exception as e:
                    log_details = f"Failed to insert batch: {str(e)}"
                    update_sync_log_record(sync_log, log_details, status="Failed")  # Ensure status="Failed" is provided

            # Clear the `to_insert` list after inserting the current batch
            to_insert.clear()

    # Final commit to ensure all records are saved
    frappe.db.commit()
    print("All products have been synced and committed to the database.")
    add_message_to_log(sync_log, "All products inserted successfully.")
    update_sync_log_record(sync_log, "All products inserted successfully.", status="Success")  # Ensure status="Success" is provided




















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


def fetch_and_insert_current_eline_data():
    start_time = time.time()
    print("Starting data fetch and insert process...")

    # Define the path to the directory and the file
    directory_path = frappe.get_module_path("imtecapp", "data")
    current_json_path = os.path.join(directory_path, "current_eline_data.json")

    # Fetch and combine data, and save it to current_eline_data.json
    print("Fetching and combining data...")
    fetch_and_combine_data("current_eline_data.json")
    print(
        "Data fetched and combined in {:.2f} seconds".format(time.time() - start_time)
    )

    # Load the data from current_eline_data.json
    print("Loading data from JSON file...")
    with open(current_json_path, mode="r") as file:
        data = json.load(file)
    print("Data loaded in {:.2f} seconds".format(time.time() - start_time))

    # Fetch all existing art_sifra in one go
    print("Fetching all existing art_sifra from Proizvodi...")
    existing_art_sifras = set(frappe.get_all("Proizvodi", pluck="art_sifra"))
    print(
        "Fetched existing art_sifra in {:.2f} seconds".format(time.time() - start_time)
    )

    to_insert = []

    for item in data:  # Since data is a list of products
        art_sifra = item["art_sifra"]

        # Check if the record already exists in Proizvodi
        if art_sifra not in existing_art_sifras:
            # If it doesn't exist, prepare it for insertion
            item["name"] = frappe.generate_hash(
                length=10
            )  # Generate a unique name for the new document
            to_insert.append(item)

    print(
        "Data prepared for insertion in {:.2f} seconds".format(time.time() - start_time)
    )

    # Insert new records in batches
    if to_insert:
        for i in range(0, len(to_insert), BATCH_SIZE):
            batch_to_insert = to_insert[i : i + BATCH_SIZE]
            frappe.db.bulk_insert(
                "Proizvodi",
                fields=list(batch_to_insert[0].keys()),
                values=[list(d.values()) for d in batch_to_insert],
            )
            print(
                "Inserted batch {} of {} in {:.2f} seconds".format(
                    i // BATCH_SIZE + 1,
                    len(to_insert) // BATCH_SIZE + 1,
                    time.time() - start_time,
                )
            )

    # Commit the changes to the database
    frappe.db.commit()

    print(
        "Data inserted and committed in {:.2f} seconds".format(time.time() - start_time)
    )

    frappe.msgprint(
        "Data fetched and inserted successfully from current_eline_data.json."
    )
