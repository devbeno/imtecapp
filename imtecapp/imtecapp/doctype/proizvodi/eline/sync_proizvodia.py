import frappe
import requests
import base64
import csv
import os
import hashlib
import datetime

BATCH_SIZE = 1000
MAX_LENGTH = 255  # Assuming the max length for 'proizvodjac', 'art_naziv', and 'grupanaziv' is 255


# Helper functions
def get_erpimtec_settings():
    settings = frappe.get_single("Generalne Postavke")
    return settings


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


def normalize_and_sanitize_name(value, max_length=255):
    """Normalize, sanitize, and truncate a name."""
    if not isinstance(value, str):
        value = str(value)

    value = value.strip()

    return truncate_string(value, max_length)


def truncate_string(value, max_length):
    """Truncate a string to a maximum length and add an ellipsis if necessary."""
    if len(value) > max_length:
        return value[: max_length - 3] + "..."
    return value


def safe_strip(value):
    """Return the stripped string if the value is a string, else return the value as-is."""
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
        # Specify the order of columns to match the order needed for insertion
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
            "hash",  # Ensure the hash field is included
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
        if "hash" not in data:
            # Re-generate the hash if it's missing
            data["hash"] = generate_item_hash(data)

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
            try:
                frappe.db.bulk_insert("Proizvodi", fields=columns, values=batch_values)
                frappe.log_error(
                    f"Inserted batch of {len(batch_values)} items", "Processing Data"
                )
            except Exception as e:
                frappe.log_error(
                    f"Error during bulk insert: {str(e)}", "Data Insertion Error"
                )

    for i in range(0, len(to_update), BATCH_SIZE):
        batch_to_update = to_update[i : i + BATCH_SIZE]
        for doc_data in batch_to_update:
            try:
                doc = frappe.get_doc("Proizvodi", doc_data["name"])
                doc.update(doc_data)
                doc.save(ignore_permissions=True)
            except frappe.DoesNotExistError:
                frappe.log_error(
                    f"Proizvodi {doc_data['name']} not found", "Update Failed"
                )
            except Exception as e:
                frappe.log_error(
                    f"Error updating {doc_data['name']}: {str(e)}", "Update Failed"
                )

    frappe.db.commit()


def update_proizvodi():
    def normalize_and_sanitize_name(value, max_length=100):
        """Normalize, sanitize, and truncate a name."""
        if not isinstance(value, str):
            value = str(value)  # Ensure it's a string

        value = value.strip()

        # Truncate the string and add an ellipsis if needed
        return truncate_string(value, max_length)

    def truncate_string(value, max_length):
        """Truncate a string to a maximum length and add an ellipsis if necessary."""
        if len(value) > max_length:
            return value[: max_length - 3] + "..."
        return value

    # Fetch the new data from the source
    combined_data = fetch_and_combine_data()

    # Fetch the existing records with their hashes
    existing_proizvodi = frappe.get_all(
        "Proizvodi", fields=["name", "art_sifra", "hash"]
    )

    # Create a dictionary for easy lookup
    existing_proizvodi_map = {item["art_sifra"]: item for item in existing_proizvodi}

    to_insert = []
    to_update = []

    def generate_name(data):
        """Generate a unique name for the record."""
        if not data.get("name"):
            data["name"] = frappe.generate_hash(
                length=12
            )  # or another method to generate a unique name
        return data["name"]

    for item in combined_data:
        art_sifra = item["art_sifra"]
        new_hash = item["hash"]

        if art_sifra in existing_proizvodi_map:
            existing_hash = existing_proizvodi_map[art_sifra]["hash"]
            if new_hash != existing_hash:
                # Update the record if the hash has changed
                item["name"] = existing_proizvodi_map[art_sifra]["name"]
                if not item.get("modified_by"):
                    item["modified_by"] = (
                        frappe.session.user
                    )  # Set modified_by to current user
                to_update.append(item)
        else:
            # Insert a new record if the art_sifra is not found
            generate_name(item)  # Ensure name is generated
            if not item.get("owner"):
                item["owner"] = (
                    frappe.session.user
                )  # Set the owner field to the current user
            if not item.get("creation"):
                item["creation"] = (
                    datetime.datetime.now()
                )  # Set the creation field to the current time
            if not item.get("modified_by"):
                item["modified_by"] = (
                    frappe.session.user
                )  # Set modified_by to current user
            to_insert.append(item)

    # Bulk insert new records
    if to_insert:
        columns = list(to_insert[0].keys())
        values = [list(d.values()) for d in to_insert]
        for i in range(0, len(values), BATCH_SIZE):
            batch_values = values[i : i + BATCH_SIZE]
            try:
                frappe.db.bulk_insert("Proizvodi", fields=columns, values=batch_values)
                frappe.log_error(
                    f"Inserted batch of {len(batch_values)} items", "Processing Data"
                )
            except Exception as e:
                frappe.log_error(
                    f"Error during bulk insert: {str(e)}", "Data Insertion Error"
                )

    # Update existing records
    for item in to_update:
        try:
            frappe.db.set_value("Proizvodi", item["name"], item)
            frappe.log_error(f"Updated record: {item['art_sifra']}", "update_proizvodi")
        except Exception as e:
            frappe.log_error(
                f"Error updating record {item['name']}: {str(e)}",
                "update_proizvodi error",
            )

    frappe.db.commit()

    frappe.log_error("Proizvodi update completed successfully.", "update_proizvodi")

    # Sync with PS Proizvodi after updating Proizvodi
    sync_active_products_to_ps_proizvodi()


def sync_active_products_to_ps_proizvodi():
    active_products = frappe.get_all(
        "Proizvodi",
        filters={"aktivan": 1},  # Only fetch active products
        fields=[
            "art_sifra",
            "vpc",
            "stanje",
            "art_naziv",
            "grupanaziv",
            "proizvodjac",
            "aktivan",
        ],
    )

    for product in active_products:
        existing_ps_product = frappe.db.get_value(
            "PS Proizvodi",
            {"reference": product["art_sifra"]},
            [
                "name",
                "presta_product_id",
                "presta_category_id",
                "presta_manufacturer_id",
            ],
        )

        prestadata = get_erpimtec_settings()

        if existing_ps_product:
            # Update the existing PS Proizvodi record
            ps_product = frappe.get_doc("PS Proizvodi", existing_ps_product)
            ps_product.update(
                {
                    "price": product["vpc"],
                    "quantity": product["stanje"],
                    "category": product["grupanaziv"],
                    "manufacturer": product["proizvodjac"],
                    "active": product["aktivan"],  # Sync active status
                }
            )
            ps_product.save()

            # Update PrestaShop Product
            if product["aktivan"] == 1:
                update_prestashop_product(ps_product, prestadata)
            else:
                deactivate_prestashop_product(ps_product, prestadata)

        else:
            if product["aktivan"] == 1:
                # Create a new PS Proizvodi record
                new_ps_product = frappe.get_doc(
                    {
                        "doctype": "PS Proizvodi",
                        "reference": product["art_sifra"],
                        "price": product["vpc"],
                        "quantity": product["stanje"],
                        "category": product["grupanaziv"],
                        "manufacturer": product["proizvodjac"],
                        "active": 1,
                    }
                )
                new_ps_product.insert()
                create_prestashop_product(new_ps_product, prestadata)

    frappe.db.commit()
    frappe.log_error(
        "Sync from Proizvodi to PS Proizvodi completed.",
        "sync_active_products_to_ps_proizvodi",
    )


def create_prestashop_product(product, prestadata):
    presta_url = f"{prestadata.presta_url}/api/products"

    payload = {
        "product": {
            "reference": product.reference,
            "price": product.price,
            "active": 1,
            "quantity": product.quantity,
            "name": {"language": [{"id": 1, "value": product.name}]},
            "id_category_default": product.get("presta_category_id"),
            "id_manufacturer": product.get("presta_manufacturer_id"),
        }
    }

    response = requests.post(presta_url, json=payload, auth=(prestadata.presta_key, ""))

    if response.status_code == 201:
        presta_product_id = response.json().get("product").get("id")
        frappe.db.set_value(
            "PS Proizvodi", product.name, "presta_product_id", presta_product_id
        )
        frappe.db.commit()
        frappe.log_error(
            f"Created product in PrestaShop with ID {presta_product_id}",
            "create_prestashop_product",
        )
    else:
        frappe.log_error(
            f"Failed to create product in PrestaShop: {response.text}",
            "create_prestashop_product",
        )


def update_prestashop_product(product, prestadata):
    presta_url = f"{prestadata.presta_url}/api/products/{product.presta_product_id}"

    payload = {
        "product": {
            "id": product.presta_product_id,
            "reference": product.reference,
            "price": product.price,
            "active": 1,
            "quantity": product.quantity,
            "name": {"language": [{"id": 1, "value": product.name}]},
            "id_category_default": product.get("presta_category_id"),
            "id_manufacturer": product.get("presta_manufacturer_id"),
        }
    }

    response = requests.put(presta_url, json=payload, auth=(prestadata.presta_key, ""))

    if response.status_code == 200:
        frappe.log_error(
            f"Updated product in PrestaShop with ID {product.presta_product_id}",
            "update_prestashop_product",
        )
    else:
        frappe.log_error(
            f"Failed to update product in PrestaShop: {response.text}",
            "update_prestashop_product",
        )


def deactivate_prestashop_product(product, prestadata):
    presta_url = f"{prestadata.presta_url}/api/products/{product.presta_product_id}"

    payload = {
        "product": {
            "id": product.presta_product_id,
            "reference": product.reference,
            "active": 0,
        }
    }

    response = requests.put(presta_url, json=payload, auth=(prestadata.presta_key, ""))

    if response.status_code == 200:
        frappe.log_error(
            f"Deactivated product in PrestaShop with ID {product.presta_product_id}",
            "deactivate_prestashop_product",
        )
    else:
        frappe.log_error(
            f"Failed to deactivate product in PrestaShop: {response.text}",
            "deactivate_prestashop_product",
        )
