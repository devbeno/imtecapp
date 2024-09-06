# data_sync.py

import frappe
import os
import json
import hashlib
from .api_utils import get_headers, get_api_url, get_erpimtec_settings, make_get_request

BATCH_SIZE = 1000

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

def save_to_json(data, filename):
    directory_path = frappe.get_module_path("imtecapp", "data")
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    json_path = os.path.join(directory_path, filename)

    with open(json_path, mode="w") as file:
        json.dump(data, file, indent=4)

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

    # Fetch the Prestashop mappings
    mappings = get_prestashop_mappings()
    category_map = {cat["agp_id"]: cat for cat in mappings["categories"]}
    manufacturer_map = {man["agp_id"]: man for man in mappings["manufacturers"]}

    for_insert_data = []

    # Compare the data and prepare for insert, update, or rename
    for new_item in new_data:
        art_sifra = new_item["art_sifra"]
        new_hash = new_item["hash"]

        if art_sifra in current_data_map:
            current_item = current_data_map[art_sifra]
            current_hash = current_item["hash"]

            if new_hash != current_hash:
                new_item["status"] = "for_update"
                print(f"Marked {art_sifra} as for_update because the hash has changed.")
                for_insert_data.append(new_item)
            else:
                print(f"Skipping {art_sifra} as it is already up to date.")
        else:
            # New item logic
            agp_id = str(new_item["agp_id"])
            sifra = new_item["sifra"]

            if agp_id in category_map:
                prestashop_category = category_map[agp_id]
                if prestashop_category["grupanaziv"] != new_item["grupanaziv"]:
                    new_item["status"] = "for_rename"
                    print(f"Marked {art_sifra} as for_rename for category mismatch.")
                else:
                    new_item["status"] = "for_insert"
                    print(f"Marked {art_sifra} as for_insert for new category.")
            elif sifra in manufacturer_map:
                prestashop_manufacturer = manufacturer_map[sifra]
                if prestashop_manufacturer["proizvodjac"] != new_item["proizvodjac"]:
                    new_item["status"] = "for_rename"
                    print(f"Marked {art_sifra} as for_rename for manufacturer mismatch.")
                else:
                    new_item["status"] = "for_insert"
                    print(f"Marked {art_sifra} as for_insert for new manufacturer.")
            else:
                new_item["status"] = "for_insert"
                print(f"Marked {art_sifra} as for_insert because it does not exist in current data.")
            for_insert_data.append(new_item)

    # Save the resulting list of items to for_insert_eline_data.json
    save_to_json(for_insert_data, "for_insert_eline_data.json")

    # After processing, move new_eline_data.json to current_eline_data.json
    shutil.move(new_json_path, current_json_path)

def insert_data_from_for_insert_eline_data():
    compare_and_create_for_insert_json()
    directory_path = frappe.get_module_path("imtecapp", "data")
    for_insert_json_path = os.path.join(directory_path, "for_insert_eline_data.json")

    # Load the data from for_insert_eline_data.json
    with open(for_insert_json_path, mode="r") as file:
        data = json.load(file)

    for item in data:
        art_sifra = item["art_sifra"]

        new_doc = frappe.get_doc({
            "doctype": "Proizvodi",
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
            "hash": item.get("hash", ""),
        })
        new_doc.insert(ignore_permissions=True)
        log_message(sync_log, f"Inserted {art_sifra} into Proizvodi.")

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

    frappe.db.commit()

def fetch_and_insert_current_eline_data():
    start_time = time.time()
    print("Starting data fetch and insert process...")

    directory_path = frappe.get_module_path("imtecapp", "data")
    current_json_path = os.path.join(directory_path, "current_eline_data.json")

    print("Fetching and combining data...")
    fetch_and_combine_data("current_eline_data.json")
    print(
        "Data fetched and combined in {:.2f} seconds".format(time.time() - start_time)
    )

    print("Loading data from JSON file...")
    with open(current_json_path, mode="r") as file:
        data = json.load(file)
    print("Data loaded in {:.2f} seconds".format(time.time() - start_time))

    print("Fetching all existing art_sifra from Proizvodi...")
    existing_art_sifras = set(frappe.get_all("Proizvodi", pluck="art_sifra"))
    print(
        "Fetched existing art_sifra in {:.2f} seconds".format(time.time() - start_time)
    )

    to_insert = []

    for item in data:  # Since data is a list of products
        art_sifra = item["art_sifra"]

        if art_sifra not in existing_art_sifras:
            item["name"] = frappe.generate_hash(
                length=10
            )  # Generate a unique name for the new document
            to_insert.append(item)

    print(
        "Data prepared for insertion in {:.2f} seconds".format(time.time() - start_time)
    )

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

    frappe.db.commit()

    print(
        "Data inserted and committed in {:.2f} seconds".format(time.time() - start_time)
    )

    frappe.msgprint(
        "Data fetched and inserted successfully from current_eline_data.json."
    )

def manual_insert_product_from_json(art_sifra):
    directory_path = frappe.get_module_path("imtecapp", "data")
    current_json_path = os.path.join(directory_path, "current_eline_data.json")

    if not os.path.exists(current_json_path):
        frappe.throw(_("The current_eline_data.json file does not exist."))

    with open(current_json_path, mode="r") as file:
        data = json.load(file)

    product_data = next((item for item in data if item["art_sifra"] == art_sifra), None)

    if not product_data:
        frappe.throw(
            _("No product found with art_sifra {0} in current_eline_data.json").format(
                art_sifra
            )
        )

    existing_product = frappe.db.exists("Proizvodi", {"art_sifra": art_sifra})

    if existing_product:
        log_details = sync_product_to_prestashop_manual(art_sifra, sync_log=sync_log)
        frappe.msgprint(_("Product with art_sifra {0} updated.").format(art_sifra))
    else:
        new_doc = frappe.get_doc(
            {
                "doctype": "Proizvodi",
                "art_sifra": product_data["art_sifra"],
                "agp_id": product_data["agp_id"],
                "sifra": product_data["sifra"],
                "vpc": product_data["vpc"],
                "aktivan": product_data["aktivan"],
                "stanje": product_data["stanje"],
                "art_naziv": product_data["art_naziv"],
                "kataloski": product_data["kataloski"],
                "grupanaziv": product_data["grupanaziv"],
                "proizvodjac": product_data["proizvodjac"],
                "hash": product_data["hash"],
            }
        )
        new_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        sync_product_to_prestashop_manual(art_sifra, sync_log=sync_log)
        frappe.msgprint(
            _("Product with art_sifra {0} successfully inserted and synced.").format(
                art_sifra
            )
        )
