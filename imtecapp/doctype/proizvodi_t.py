import requests
from frappe.utils.background_jobs import enqueue
import xml.etree.ElementTree as ET
from imtecapp.imtecapp.doctype.proizvodi.eline.insert_new_data import (
    insert_data_from_for_insert_eline_data,
)
from imtecapp.imtecapp.doctype.proizvodi.sync_categorie import (
    find_prestashop_category_by_name,
    create_prestashop_category,
)
from imtecapp.imtecapp.doctype.proizvodi.sync_manufacturer import (
    find_prestashop_manufacturer_by_name,
    create_prestashop_manufacturer,
)
from frappe import _
import re
from prestapyt import PrestaShopWebServiceDict
import base64
import datetime
import os
import json
from concurrent.futures import ThreadPoolExecutor
from frappe.utils import now
from frappe.model.document import Document
import frappe
class Proizvodi(Document):
    pass
############################################################
#################### Sync Log Functions ####################
############################################################
def create_sync_log_record(sync_type):
    """Create a new Sync Log entry."""
    ### old function name create_sync_log()
    try:
        sync_log = frappe.get_doc(
            {
                "doctype": "Sync Log",
                "sync_type": sync_type,
                "sync_date": frappe.utils.now(),
                "status": "In Progress",
            }
        )
        sync_log.insert(ignore_permissions=True)
        frappe.db.commit()
        return sync_log
    except Exception as e:
        frappe.log_error(f"Failed to create sync log: {e}", "Sync Log Creation Error")
        frappe.throw(_("Unable to create sync log due to an error."))

def truncate_add_message_to_log(input_string, max_length):
    """Truncate long log messages."""
    ### old function name truncate_string()
    return input_string[:max_length]

def update_sync_log_record(sync_log, log_details, status="Success"):
    """Update Sync Log entry with log details and status."""
    ### old function name update_sync_log()
    max_log_length = 65535
    if len(log_details) > max_log_length:
        log_details = truncate_add_message_to_log(log_details, max_log_length)
        add_message_to_log(sync_log, "Log details truncated due to size limit.")

    sync_log.log_details = log_details
    sync_log.status = status

    try:
        sync_log.save(ignore_permissions=True)
        frappe.db.commit()
    except frappe.TimestampMismatchError:
        frappe.msgprint(
            _("Sync log was modified by another process, reloading and retrying...")
        )
        sync_log.reload()
        sync_log.log_details = log_details
        sync_log.status = status
        sync_log.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Failed to update sync log: {e}", "Sync Log Update Error")
        frappe.throw(_("Unable to update sync log due to an error."))

def add_message_to_log(sync_log, message):
    """Add message to sync log."""
    ### old function name log_message()
    if sync_log:
        if sync_log.log_details:
            sync_log.log_details += message + "\n"
        else:
            sync_log.log_details = message + "\n"
        sync_log.save(ignore_permissions=True)
        frappe.db.commit()

# PrestaShop API Handling
def retrieve_prestashop_settings():
    """Retrieve PrestaShop settings."""
    ### old function name get_prestashop_settings()
    presta_key_raw = "APXHV1BE9ZISZQMDFEYVE6HKXPXJIGBH"
    presta_key_encoded = base64.b64encode(presta_key_raw.encode("utf-8")).decode(
        "utf-8"
    )
    return {
        "presta_url": "https://test2.imtec.ba/api",
        "presta_key": presta_key_encoded,
    }

def generate_api_headers(settings):
    """Generate PrestaShop API headers."""
    ### old function name get_headers()
    return {
        "Authorization": f"Basic {settings['presta_key']}",
        "Content-Type": "application/xml",
    }

def sanitize_response_text(response_text):
    """Sanitize and clean response text from API."""
    ### old function name clean_response()
    clean_text = re.sub(r"^.*?(<\?xml)", r"\1", response_text, flags=re.DOTALL)
    return clean_text

# Product Sync Functions
def find_prestashop_product_by_reference(settings, reference, sync_log=None):
    """Find product in PrestaShop by reference."""
    ### old function name search_prestashop_product()
    url = f"{settings['presta_url']}/products"
    params = {"filter[reference]": reference}

    add_message_to_log(
        sync_log, f"Searching for product with reference {reference} using URL: {url}"
    )
    response = requests.get(url, params=params, headers=generate_api_headers(settings))

    add_message_to_log(sync_log, f"Response Status Code: {response.status_code}")
    add_message_to_log(sync_log, f"Response Text: {response.text}")

    if response.status_code == 200:
        try:
            sanitize_response_text_text = sanitize_response_text(response.text)
            root = ET.fromstring(sanitize_response_text_text)
            products = root.findall(".//product")
            if products:
                product_id = products[0].get("id")
                add_message_to_log(sync_log, f"Found product ID: {product_id}")
                return product_id
            else:
                add_message_to_log(sync_log, "No product found with the given reference.")
                return None
        except ET.ParseError as e:
            add_message_to_log(sync_log, f"Failed to parse XML from response: {e}")
            return None
    else:
        add_message_to_log(
            sync_log, f"Failed to search product. Status Code: {response.status_code}"
        )
        return None

def fetch_existing_product_info(settings, prestashop_id, sync_log=None):
    """Fetch existing product data from PrestaShop."""
    ### old function name get_existing_product_data()
    url = f"{settings['presta_url']}/products/{prestashop_id}"
    response = requests.get(url, headers=generate_api_headers(settings))

    add_message_to_log(
        sync_log,
        f"Fetching existing product data for ID {prestashop_id} using URL: {url}",
    )
    add_message_to_log(sync_log, f"Response Status Code: {response.status_code}")
    add_message_to_log(sync_log, f"Response Text: {response.text}")

    if response.status_code == 200:
        try:
            sanitize_response_text_text = sanitize_response_text(response.text)
            root = ET.fromstring(sanitize_response_text_text)
            product_data = {}

            # Handle categories in associations
            existing_categories = []
            associations = root.find(".//associations")
            if associations is not None:
                categories = associations.findall(".//category")
                existing_categories = [
                    cat.find("id").text
                    for cat in categories
                    if cat.find("id") is not None
                ]
            product_data["categories"] = existing_categories

            # Preserve existing values for fields that need to be retained
            for element in [
                "description",
                "description_short",
                "meta_description",
                "meta_keywords",
                "meta_title",
            ]:
                field = root.find(f".//{element}")
                if field is not None:
                    product_data[element] = {
                        "1": (
                            field.find("language[@id='1']").text
                            if field.find("language[@id='1']") is not None
                            else ""
                        ),
                        "2": (
                            field.find("language[@id='2']").text
                            if field.find("language[@id='2']") is not None
                            else ""
                        ),
                    }
                else:
                    # Provide default values if these fields are missing
                    product_data[element] = {"1": "", "2": ""}

            return product_data
        except ET.ParseError as e:
            add_message_to_log(sync_log, f"Failed to parse XML from response: {e}")
            return None
    else:
        add_message_to_log(
            sync_log,
            f"Failed to retrieve existing product data. Status Code: {response.status_code}",
        )
        return None

def create_seo_friendly_url(name):
    """Create SEO-friendly link rewrite for PrestaShop."""
    ### old function name generate_link_rewrite()
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    return name if name else "default-link-rewrite"

def build_product_xml_payload(product_data, prestashop_id=None):
    """Generate XML payload for PrestaShop product."""
    ### old function name generate_product_xml()
    default_category_id = product_data.get("prestashop_category_id", "")

    categories_xml = f"""
    <category>
        <id>2</id>
    </category>
    <category>
        <id>{default_category_id}</id>
    </category>
    """

    existing_categories = set(product_data.get("categories", []))
    for category_id in existing_categories:
        if category_id != "2" and category_id != str(default_category_id):
            categories_xml += f"""
            <category>
                <id>{category_id}</id>
            </category>
            """

    prname = product_data.get("art_naziv", "")
    link_rewrite = create_seo_friendly_url(prname)

    xml_payload = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
        <product>
            {'<id><![CDATA[' + str(prestashop_id) + ']]></id>' if prestashop_id else ''}
            <reference><![CDATA[{product_data['art_sifra']}]]></reference>
            <name>
                <language id="1"><![CDATA[{product_data['art_naziv']}]]></language>
                <language id="2"><![CDATA[{product_data['art_naziv']}]]></language>
            </name>
            <link_rewrite>
                <language id="1"><![CDATA[{link_rewrite}]]></language>
                <language id="2"><![CDATA[{link_rewrite}]]></language>
            </link_rewrite>
            <id_category_default><![CDATA[{default_category_id}]]></id_category_default>
            <id_manufacturer><![CDATA[{product_data['prestashop_manufacturer_id']}]]></id_manufacturer>
            <price><![CDATA[{product_data['vpc']}]]></price>
            <active><![CDATA[{1 if product_data['aktivan'] else 0}]]></active>
            <available_for_order><![CDATA[{1 if product_data['stanje'] > 0 else 0}]]></available_for_order>
            <show_price><![CDATA[1]]></show_price>
            <id_tax_rules_group><![CDATA[1]]></id_tax_rules_group>
            <id_shop_default><![CDATA[1]]></id_shop_default>
            <visibility><![CDATA[both]]></visibility>
            <state><![CDATA[1]]></state>
            <mpn><![CDATA[{product_data['kataloski']}]]></mpn>
            <minimal_quantity><![CDATA[1]]></minimal_quantity>
            <description>
                <language id="1"><![CDATA[{resolve_none(product_data.get('description', {}).get('1', ''))}]]></language>
                <language id="2"><![CDATA[{resolve_none(product_data.get('description', {}).get('2', ''))}]]></language>
            </description>
            <description_short><![CDATA[{resolve_none(product_data.get('description_short', {}).get('2', ''))}]]></description_short>
            <meta_description>
                <language id="1"><![CDATA[{resolve_none(product_data.get('meta_description', {}).get('1', ''))}]]></language>
                <language id="2"><![CDATA[{resolve_none(product_data.get('meta_description', {}).get('2', ''))}]]></language>
            </meta_description>
            <meta_keywords>
                <language id="1"><![CDATA[{resolve_none(product_data.get('meta_keywords', {}).get('1', ''))}]]></language>
                <language id="2"><![CDATA[{resolve_none(product_data.get('meta_keywords', {}).get('2', ''))}]]></language>
            </meta_keywords>
            <meta_title>
                <language id="1"><![CDATA[{resolve_none(product_data.get('meta_title', {}).get('1', ''))}]]></language>
                <language id="2"><![CDATA[{resolve_none(product_data.get('meta_title', {}).get('2', ''))}]]></language>
            </meta_title>
            <associations>
                <categories>
                    {categories_xml}
                </categories>
            </associations>
        </product>
    </prestashop>
    """.strip()

    return xml_payload

def sync_product_to_prestashop(art_sifra):
    """Sync product data to PrestaShop."""
    ### old function name sync_product_to_prestashop_manual()
    log_details = ""  # Initialize log accumulation for individual sync

    try:
        # Fetch the product document
        product = frappe.get_doc("Proizvodi", {"art_sifra": art_sifra})

        # Prepare new product data for syncing
        new_product_data = {
            "art_sifra": product.art_sifra,
            "art_naziv": product.art_naziv,
            "prestashop_category_id": product.prestashop_category_id,
            "prestashop_manufacturer_id": product.prestashop_manufacturer_id,
            "vpc": product.vpc,
            "aktivan": product.aktivan,
            "stanje": product.stanje,
            "kataloski": product.kataloski,
            "prestashop_id": product.prestashop_id,
            "status": product.status,
        }

        # Check and create category if needed
        new_prestashop_category_id = sync_category_to_prestashop(product.grupanaziv)
        new_product_data["prestashop_category_id"] = new_prestashop_category_id

        # Check and create manufacturer if needed
        new_prestashop_manufacturer_id = sync_manufacturer_to_prestashop(
            product.proizvodjac
        )
        new_product_data["prestashop_manufacturer_id"] = new_prestashop_manufacturer_id

        # Update the Proizvodi document with the new category and manufacturer IDs if they have changed
        if (
            product.prestashop_category_id != new_prestashop_category_id
            or product.prestashop_manufacturer_id != new_prestashop_manufacturer_id
        ):
            product.prestashop_category_id = new_prestashop_category_id
            product.prestashop_manufacturer_id = new_prestashop_manufacturer_id
            product.save(ignore_permissions=True)
            frappe.db.commit()  # Commit changes to the database

        # Sync product to PrestaShop
        settings = retrieve_prestashop_settings()
        prestashop_id = find_prestashop_product_by_reference(
            settings, new_product_data["art_sifra"]
        )

        if prestashop_id:
            existing_product_data = fetch_existing_product_info(settings, prestashop_id)
            if existing_product_data:
                # Use existing data to preserve certain fields if not provided
                for field in [
                    "description",
                    "description_short",
                    "meta_description",
                    "meta_keywords",
                    "meta_title",
                ]:
                    if field not in new_product_data or not new_product_data[field]:
                        new_product_data[field] = existing_product_data.get(
                            field, {"1": "", "2": ""}
                        )

                # Merge existing and new categories
                existing_categories = set(existing_product_data.get("categories", []))
                new_categories = set([new_product_data["prestashop_category_id"]])
                combined_categories = list(existing_categories.union(new_categories))
                new_product_data["categories"] = combined_categories

                xml_payload = build_product_xml_payload(new_product_data, prestashop_id)

                url = f"{settings['presta_url']}/products/{prestashop_id}"
                response = requests.put(
                    url, headers=generate_api_headers(settings), data=xml_payload.encode("utf-8")
                )

                if response.status_code in [200, 201]:
                    log_details += f"Product {new_product_data['art_sifra']} synced successfully.\n"
                    # Immediately update stock after successful product sync
                    stock_available_id = retrieve_stock_available_id(settings, prestashop_id)
                    if stock_available_id:
                        update_product_stock_quantity(
                            settings,
                            stock_available_id,
                            prestashop_id,
                            new_product_data["stanje"],
                        )
                else:
                    log_details += (
                        f"Failed to sync product. Status Code: {response.status_code}\n"
                    )
                    log_details += f"Response: {response.text}\n"
            else:
                log_details += "Failed to retrieve existing product data.\n"

        else:
            log_details += f"Product with reference {new_product_data['art_sifra']} does not exist. Creating it.\n"
            prestashop_id = add_new_product_to_prestashop(settings, new_product_data)
            if prestashop_id:
                product.prestashop_id = prestashop_id
                product.save(ignore_permissions=True)
                frappe.db.commit()
                # Immediately update stock after successful product creation
                update_product_stock_quantity(
                    settings, prestashop_id, new_product_data["stanje"]
                )

    except frappe.DoesNotExistError:
        log_details += f"Product with art_sifra {art_sifra} does not exist.\n"
    except Exception as e:
        log_details += f"An unexpected error occurred: {str(e)}\n"

    return log_details  # Return accumulated logs for each product sync

def add_new_product_to_prestashop(settings, product_data, sync_log=None):
    """Insert new product into PrestaShop."""
    ### old function name create_prestashop_product()
    url = f"{settings['presta_url']}/products"
    payload = build_product_xml_payload(product_data)
    headers = {
        "Content-Type": "application/xml",
        "Authorization": f"Basic {settings['presta_key']}",
    }

    response = requests.post(url, headers=headers, data=payload.encode("utf-8"))

    if response.status_code in [200, 201]:
        add_message_to_log(
            sync_log, f"Product {product_data['art_sifra']} created successfully."
        )
        try:
            root = ET.fromstring(response.text)
            product_id = root.find(".//product").get("id")
            return product_id
        except ET.ParseError as e:
            add_message_to_log(sync_log, f"Failed to parse XML from response: {e}")
            return None
    else:
        add_message_to_log(
            sync_log, f"Failed to create product. Status Code: {response.status_code}"
        )
        return None

def update_product_stock_quantity(settings, stock_available_id, product_id, quantity, sync_log=None):
    """Update PrestaShop product stock quantity."""
    ### old function name update_stock_quantity()
    url = f"{settings['presta_url']}/stock_availables/{stock_available_id}"

    payload = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
        <stock_available>
            <id>{stock_available_id}</id>
            <id_product>{product_id}</id_product>
            <id_product_attribute><![CDATA[0]]></id_product_attribute>
            <id_shop><![CDATA[1]]></id_shop>
            <id_shop_group><![CDATA[0]]></id_shop_group>
            <quantity><![CDATA[{quantity}]]></quantity>
            <depends_on_stock><![CDATA[0]]></depends_on_stock>
            <out_of_stock><![CDATA[2]]></out_of_stock>
        </stock_available>
    </prestashop>
    """.strip().encode(
        "utf-8"
    )

    headers = {
        "Content-Type": "application/xml",
        "Authorization": f"Basic {settings['presta_key']}",
    }

    response = requests.patch(url, headers=headers, data=payload)

    add_message_to_log(
        sync_log,
        f"Updating stock for stock_available ID {stock_available_id} to {quantity} using URL: {url}",
    )
    add_message_to_log(sync_log, f"Response Status Code: {response.status_code}")
    add_message_to_log(sync_log, f"Response Text: {response.text}")

    if response.status_code in [200, 201]:
        add_message_to_log(
            sync_log,
            f"Stock quantity for stock_available ID {stock_available_id} updated to {quantity}.",
        )
    else:
        add_message_to_log(
            sync_log,
            f"Failed to update stock quantity. Status Code: {response.status_code}",
        )

def retrieve_stock_available_id(settings, prestashop_id, sync_log=None):
    """Retrieve stock available ID from PrestaShop."""
    ### old function name get_stock_available_id()
    url = f"{settings['presta_url']}/stock_availables"
    params = {"filter[id_product]": prestashop_id, "display": "full"}

    response = requests.get(url, params=params, headers=generate_api_headers(settings))

    add_message_to_log(
        sync_log,
        f"Fetching stock_available for product ID {prestashop_id} using URL: {url}",
    )
    add_message_to_log(sync_log, f"Response Status Code: {response.status_code}")
    add_message_to_log(sync_log, f"Response Text: {response.text}")

    if response.status_code == 200:
        try:
            sanitize_response_text_text = sanitize_response_text(response.text)
            root = ET.fromstring(sanitize_response_text_text)
            stock_availables = root.findall(".//stock_available")

            for stock_available in stock_availables:
                id_product_attribute = stock_available.find("id_product_attribute")

                if (
                    id_product_attribute is not None
                    and id_product_attribute.text == "0"
                ):
                    stock_available_id = stock_available.find("id").text
                    add_message_to_log(
                        sync_log,
                        f"Found stock_available ID: {stock_available_id} for product ID: {prestashop_id}",
                    )
                    return stock_available_id

            add_message_to_log(
                sync_log, "No suitable stock_available found for the given product ID."
            )
            return None
        except ET.ParseError as e:
            add_message_to_log(sync_log, f"Failed to parse XML from response: {e}")
            return None
    else:
        add_message_to_log(
            sync_log,
            f"Failed to retrieve stock_available. Status Code: {response.status_code}",
        )
        return None

# Category and Manufacturer Sync Functions
def sync_category_to_prestashop(group_name, sync_log=None):
    """Sync category to PrestaShop."""
    ### old function name check_and_create_category()
    existing_category_id = frappe.db.get_value(
        "Proizvodi",
        {"grupanaziv": group_name, "prestashop_category_id": ["is", "set"]},
        "prestashop_category_id",
    )

    if existing_category_id:
        add_message_to_log(
            sync_log,
            f"Category '{group_name}' already has PrestaShop ID {existing_category_id}",
        )
        return existing_category_id
    else:
        prestashop_category_id = find_prestashop_category_by_name(group_name)
        if not prestashop_category_id:
            prestashop_category_id = create_prestashop_category(
                {"grupanaziv": group_name}
            )

        if prestashop_category_id:
            frappe.db.sql(
                """
                UPDATE `tabProizvodi`
                SET prestashop_category_id = %s
                WHERE grupanaziv = %s
                """,
                (prestashop_category_id, group_name),
            )
            frappe.db.commit()
            add_message_to_log(
                sync_log,
                f"Updated category '{group_name}' with PrestaShop ID {prestashop_category_id}",
            )
        else:
            add_message_to_log(sync_log, f"Failed to process category '{group_name}'")

        return prestashop_category_id

def sync_manufacturer_to_prestashop(manufacturer_name, sync_log=None):
    """Sync manufacturer to PrestaShop."""
    ### old function name check_and_create_manufacturer()
    existing_manufacturer_id = frappe.db.get_value(
        "Proizvodi",
        {"proizvodjac": manufacturer_name, "prestashop_manufacturer_id": ["is", "set"]},
        "prestashop_manufacturer_id",
    )

    if existing_manufacturer_id:
        add_message_to_log(
            sync_log,
            f"Manufacturer '{manufacturer_name}' already has PrestaShop ID {existing_manufacturer_id}",
        )
        return existing_manufacturer_id
    else:
        prestashop_manufacturer_id = find_prestashop_manufacturer_by_name(
            manufacturer_name
        )
        if not prestashop_manufacturer_id:
            prestashop_manufacturer_id = create_prestashop_manufacturer(
                {"proizvodjac": manufacturer_name}
            )

        if prestashop_manufacturer_id:
            frappe.db.sql(
                """
                UPDATE `tabProizvodi`
                SET prestashop_manufacturer_id = %s
                WHERE proizvodjac = %s
                """,
                (prestashop_manufacturer_id, manufacturer_name),
            )
            frappe.db.commit()
            add_message_to_log(
                sync_log,
                f"Updated manufacturer '{manufacturer_name}' with PrestaShop ID {prestashop_manufacturer_id}",
            )
        else:
            add_message_to_log(
                sync_log, f"Failed to process manufacturer '{manufacturer_name}'"
            )

        return prestashop_manufacturer_id

############################################################
##################### Helper Functions #####################
############################################################
def resolve_none(value):
    """Resolve None values to an empty string."""
    ### old function name handle_none()
    return value if value is not None else ""

def load_data_from_json(art_sifra: str) -> dict:
    """Load product data from for_insert_eline_data.json and update or insert into Proizvodi."""
    
    # Define the path to the JSON file
    directory_path = frappe.get_module_path("imtecapp", "data")
    for_insert_eline_data = os.path.join(directory_path, "for_insert_eline_data.json")

    # Check if the file exists
    if not os.path.exists(for_insert_eline_data):
        frappe.throw(_("The for_insert_eline_data.json file does not exist."))

    # Load the data from for_insert_eline_data.json
    with open(for_insert_eline_data, mode="r") as file:
        data = json.load(file)

    # Find the product with the specified art_sifra
    product_data = next((item for item in data if item["art_sifra"] == art_sifra), None)

    if not product_data:
        frappe.throw(_("No product found with art_sifra {0} in for_insert_eline_data.json").format(art_sifra))

    # Check if the product already exists in Proizvodi
    existing_product = frappe.db.exists("Proizvodi", {"art_sifra": art_sifra})

    if existing_product:
        # If the product exists, update it
        print(f"Product {art_sifra} already exists in Proizvodi. Updating data...")
        existing_doc = frappe.get_doc("Proizvodi", existing_product)
        existing_doc.update(product_data)
        existing_doc.save(ignore_permissions=True)
        frappe.msgprint(_("Product with art_sifra {0} has been updated.").format(art_sifra))
    else:
        # If the product does not exist, insert it
        print(f"Inserting new product with art_sifra {art_sifra} into Proizvodi...")
        new_doc = frappe.get_doc({
            "doctype": "Proizvodi",
            **product_data  # Spread the product data into the new document
        })
        new_doc.insert(ignore_permissions=True)
        frappe.msgprint(_("Product with art_sifra {0} has been inserted.").format(art_sifra))

    frappe.db.commit()

    # Update the last_sync_time in the Generalne Postavke doctype
    try:
        settings = frappe.get_single("Generalne Postavke")
        settings.last_sync_time = now()
        settings.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.msgprint(_("Last sync time updated successfully."))
    except Exception as e:
        frappe.log_error(str(e), _("Failed to update last_sync_time in Generalne Postavke"))
        frappe.throw(_("An error occurred while updating last sync time."))

    return product_data


def load_all_data_from_json() -> list:
    """Load the entire for_insert_eline_data.json file."""
    directory_path = frappe.get_module_path("imtecapp", "data")
    for_insert_eline_data = os.path.join(directory_path, "for_insert_eline_data.json")

    if not os.path.exists(for_insert_eline_data):
        frappe.throw(_("The for_insert_eline_data.json file does not exist."))

    with open(for_insert_eline_data, mode="r") as file:
        data = json.load(file)

    return data  # Return the entire JSON content


# Specialized Sync Operations
def synchronize_all_products_for_update(witheline: bool = False):
    """Synchronize all products marked for update."""
    log_details = ""  # Initialize log accumulation for overall sync
    sync_log = create_sync_log_record("Sync All Products for Update")

    try:
        # Insert or update products based on `for_insert_eline_data.json`
        if witheline:
            try:
                log_details += "Inserting or updating data from for_insert_eline_data.json...\n"
                insert_data_from_for_insert_eline_data(sync_log)  # Pass sync_log here
                log_details += "Data insertion or update completed.\n"
            except Exception as e:
                log_details += f"Error while inserting or updating data: {str(e)}\n"
                update_sync_log_record(sync_log, log_details, status="Failed")
                return  # Exit early since there was an error
        else:
            log_details += "Skipping Eline data insert.\n"

        # Continue with the rest of the process
        log_details += "Fetching products marked for update...\n"
        products_for_update = frappe.get_all(
            "Proizvodi", filters={"status": "for_update"}, fields=["art_sifra"]
        )
        log_details += f"Found {len(products_for_update)} products for update.\n"

        for product in products_for_update:
            try:
                result = sync_product_to_prestashop(product["art_sifra"])
                log_details += f"Product {product['art_sifra']} sync result: {result}\n"
            except Exception as e:
                log_details += f"Failed to sync product {product['art_sifra']}: {str(e)}\n"
                frappe.log_error(f"Failed to sync product {product['art_sifra']}: {str(e)}", "Product Sync Error")

        # **Process products marked for insert**
        log_details += "Fetching products marked for insert...\n"
        products_for_insert = frappe.get_all(
            "Proizvodi", filters={"status": "for_insert"}, fields=["art_sifra"]
        )
        log_details += f"Found {len(products_for_insert)} products for insert.\n"

        for product in products_for_insert:
            try:
                result = insert_product_to_prestashop(product["art_sifra"])
                log_details += f"Product {product['art_sifra']} sync result: {result}\n"
            except Exception as e:
                log_details += f"Failed to insert product {product['art_sifra']}: {str(e)}\n"
                frappe.log_error(f"Failed to insert product {product['art_sifra']}: {str(e)}", "Product Insert Error")

        # **Process products marked for rename**
        log_details += "Fetching products marked for rename...\n"
        products_for_rename = frappe.get_all(
            "Proizvodi", filters={"status": "for_rename"}, fields=["art_sifra"]
        )
        log_details += f"Found {len(products_for_rename)} products for rename.\n"

        for product in products_for_rename:
            try:
                result = rename_prestashop_product_by_reference(product["art_sifra"])
                log_details += f"Product {product['art_sifra']} sync result: {result}\n"
            except Exception as e:
                log_details += f"Failed to rename product {product['art_sifra']}: {str(e)}\n"
                frappe.log_error(f"Failed to rename product {product['art_sifra']}: {str(e)}", "Product Rename Error")

        # Update log with the accumulated details after all products are processed
        update_sync_log_record(sync_log, log_details, status="Success")

    except Exception as e:
        log_details += f"An unexpected error occurred: {str(e)}\n"
        update_sync_log_record(sync_log, log_details, status="Failed")

    return log_details


def manual_json_product_insert(art_sifra):
    """Manually insert product from JSON."""
    ### old function name manual_insert_product_from_json()
    # Define the path to the directory and the file
    directory_path = frappe.get_module_path("imtecapp", "data")
    current_json_path = os.path.join(directory_path, "current_eline_data.json")

    # Check if the file exists
    if not os.path.exists(current_json_path):
        frappe.throw(_("The current_eline_data.json file does not exist."))

    # Load the data from current_eline_data.json
    with open(current_json_path, mode="r") as file:
        data = json.load(file)

    # Find the product with the specified art_sifra
    product_data = next((item for item in data if item["art_sifra"] == art_sifra), None)

    if not product_data:
        frappe.throw(
            _("No product found with art_sifra {0} in current_eline_data.json").format(
                art_sifra
            )
        )

    # Check if the product already exists in Proizvodi
    existing_product = frappe.db.exists("Proizvodi", {"art_sifra": art_sifra})

    if existing_product:
        # If the product exists, update it using the sync function
        log_details = sync_product_to_prestashop(art_sifra)
        frappe.msgprint(_("Product with art_sifra {0} updated.").format(art_sifra))
    else:
        # If the product does not exist, create it
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

        # After inserting, sync the new product to PrestaShop
        sync_product_to_prestashop(art_sifra)
        frappe.msgprint(
            _("Product with art_sifra {0} successfully inserted and synced.").format(
                art_sifra
            )
        )

def reset_all_product_statuses():
    """Reset product statuses in Frappe."""
    ### old function name reset_products_status()
    frappe.db.sql("""UPDATE tabProizvodi SET status = ''""")
    frappe.db.commit()

def insert_product_to_prestashop(art_sifra):
    """Insert product to PrestaShop based on art_sifra."""
    log_details = ""  # Initialize log accumulation for individual insert
    sync_log = create_sync_log_record("Insert Product")  # Proper sync_log object

    try:
        # Fetch the product document
        product = frappe.get_doc("Proizvodi", {"art_sifra": art_sifra})

        # Prepare new product data for inserting
        new_product_data = {
            "art_sifra": product.art_sifra,
            "art_naziv": product.art_naziv,
            "prestashop_category_id": product.prestashop_category_id,
            "prestashop_manufacturer_id": product.prestashop_manufacturer_id,
            "vpc": product.vpc,
            "aktivan": product.aktivan,
            "stanje": product.stanje,
            "kataloski": product.kataloski,
        }

        # Check and create category if needed
        new_prestashop_category_id = sync_category_to_prestashop(product.grupanaziv, sync_log)
        new_product_data["prestashop_category_id"] = new_prestashop_category_id

        # Check and create manufacturer if needed
        new_prestashop_manufacturer_id = sync_manufacturer_to_prestashop(product.proizvodjac, sync_log)
        new_product_data["prestashop_manufacturer_id"] = new_prestashop_manufacturer_id

        # Update the Proizvodi document with the new category and manufacturer IDs if they have changed
        if (
            product.prestashop_category_id != new_prestashop_category_id
            or product.prestashop_manufacturer_id != new_prestashop_manufacturer_id
        ):
            product.prestashop_category_id = new_prestashop_category_id
            product.prestashop_manufacturer_id = new_prestashop_manufacturer_id
            product.save(ignore_permissions=True)
            frappe.db.commit()  # Commit changes to the database

        # Check if the product already exists in PrestaShop
        settings = retrieve_prestashop_settings()
        prestashop_id = find_prestashop_product_by_reference(settings, new_product_data["art_sifra"], sync_log=sync_log)

        if prestashop_id:
            # If product exists, update it instead of inserting
            log_details += f"Product {art_sifra} already exists in PrestaShop with ID {prestashop_id}. Updating product.\n"
            existing_product_data = fetch_existing_product_info(settings, prestashop_id, sync_log=sync_log)
            if existing_product_data:
                # Update the product in PrestaShop
                xml_payload = build_product_xml_payload(new_product_data, prestashop_id)
                url = f"{settings['presta_url']}/products/{prestashop_id}"
                response = requests.put(url, headers=generate_api_headers(settings), data=xml_payload.encode("utf-8"))

                if response.status_code in [200, 201]:
                    log_details += f"Product {art_sifra} updated successfully in PrestaShop.\n"
                else:
                    log_details += f"Failed to update product {art_sifra}. Status Code: {response.status_code}, Response: {response.text}\n"
            else:
                log_details += f"Failed to retrieve existing product data for {art_sifra}.\n"
        else:
            # If product does not exist, insert it
            log_details += f"Product with reference {new_product_data['art_sifra']} does not exist. Creating it.\n"
            prestashop_id = add_new_product_to_prestashop(settings, new_product_data, sync_log)
            if prestashop_id:
                product.prestashop_id = prestashop_id
                product.status = "on_presta"
                product.save(ignore_permissions=True)
                frappe.db.commit()  # Commit changes to the database
                log_details += f"Product {art_sifra} inserted successfully into PrestaShop with ID {prestashop_id}.\n"
            else:
                log_details += f"Failed to insert product {art_sifra} into PrestaShop.\n"

    except frappe.DoesNotExistError:
        log_details += f"Product with art_sifra {art_sifra} does not exist in ERPNext.\n"
    except Exception as e:
        log_details += f"An unexpected error occurred while inserting product {art_sifra}: {str(e)}\n"

    update_sync_log_record(sync_log, log_details)  # Update sync log with accumulated details
    return log_details  # Return accumulated logs for each product insert

def rename_prestashop_product_by_reference(art_sifra):
    """Rename a product in PrestaShop by reference."""
    ### old function name sync_product_to_prestashop_rename()
    log_details = ""  # Initialize log accumulation for individual rename
    sync_log = create_sync_log_record("Rename Product")  # Proper sync_log object

    try:
        # Fetch the product document
        product = frappe.get_doc("Proizvodi", {"art_sifra": art_sifra})

        # Prepare new product data for renaming
        new_product_data = {
            "art_sifra": product.art_sifra,
            "art_naziv": product.art_naziv,
            "prestashop_category_id": product.prestashop_category_id,
            "prestashop_manufacturer_id": product.prestashop_manufacturer_id,
            "vpc": product.vpc,
            "aktivan": product.aktivan,
            "stanje": product.stanje,
            "kataloski": product.kataloski,
        }

        # Check and create category if needed
        new_prestashop_category_id = sync_category_to_prestashop(product.grupanaziv, sync_log)
        new_product_data["prestashop_category_id"] = new_prestashop_category_id

        # Check and create manufacturer if needed
        new_prestashop_manufacturer_id = sync_manufacturer_to_prestashop(product.proizvodjac, sync_log)
        new_product_data["prestashop_manufacturer_id"] = new_prestashop_manufacturer_id

        # Update category and manufacturer IDs if they have changed
        if (
            product.prestashop_category_id != new_prestashop_category_id
            or product.prestashop_manufacturer_id != new_prestashop_manufacturer_id
        ):
            product.prestashop_category_id = new_prestashop_category_id
            product.prestashop_manufacturer_id = new_prestashop_manufacturer_id
            product.save(ignore_permissions=True)
            frappe.db.commit()  # Commit changes to the database

        # Fetch product from PrestaShop
        settings = retrieve_prestashop_settings()
        prestashop_id = find_prestashop_product_by_reference(settings, new_product_data["art_sifra"], sync_log=sync_log)

        if prestashop_id:
            # Generate XML payload for the updated product
            xml_payload = build_product_xml_payload(new_product_data, prestashop_id)
            url = f"{settings['presta_url']}/products/{prestashop_id}"
            response = requests.put(url, headers=generate_api_headers(settings), data=xml_payload.encode("utf-8"))

            if response.status_code in [200, 201]:
                log_details += f"Product {art_sifra} renamed successfully in PrestaShop.\n"
            else:
                log_details += f"Failed to rename product {art_sifra}. Status Code: {response.status_code}, Response: {response.text}\n"

        else:
            log_details += f"Product {art_sifra} does not exist in PrestaShop.\n"

    except Exception as e:
        log_details += f"An error occurred while renaming product {art_sifra}: {str(e)}\n"

    update_sync_log_record(sync_log, log_details)  # Update sync log with accumulated details
    return log_details  # Return accumulated logs for each product rename

def sync_all_products_with_stock():
    """Sync all products with non-zero stock to PrestaShop."""
    ### old function name sync_all_stanje_products()
    try:
        # Fetch all products with stanje != 0 and aktivan = 1
        stanje_products = frappe.get_all(
            "Proizvodi",
            filters={"stanje": ["!=", 0], "aktivan": 1},
            fields=["art_sifra", "art_naziv", "prestashop_category_id", "prestashop_manufacturer_id", "vpc", "kataloski", "stanje"]
        )

        # Log the total number of products being synced
        total_products = len(stanje_products)
        frappe.log_error(f"Starting sync for {total_products} products.", "Product Sync Start")

        # Loop through each product and check if it needs to be renamed or updated
        for product in stanje_products:
            try:
                # Check if the product requires renaming or updating
                existing_prestashop_id = find_prestashop_product_by_reference(retrieve_prestashop_settings(), product["art_sifra"])

                if existing_prestashop_id:
                    # If product exists, check if renaming is needed
                    log_details = rename_prestashop_product_by_reference(product["art_sifra"])
                    frappe.log_error(f"Product {product['art_sifra']} renamed successfully.", "Product Rename Success")
                else:
                    # Otherwise, sync it as a new product
                    sync_product_to_prestashop(product["art_sifra"])
                    frappe.log_error(f"Product {product['art_sifra']} synced successfully.", "Product Sync Success")

            except Exception as product_error:
                # Log specific product failure
                frappe.log_error(f"Error syncing product {product['art_sifra']}: {str(product_error)}", "Product Sync Error")

    except Exception as e:
        # Log if the entire sync process fails
        frappe.log_error(f"Error syncing products: {str(e)}", "Sync All Stanje Products Error")
        frappe.throw(_("An error occurred during syncing. Please check the logs."))



def sync_active_products_to_prestashop():
    """Sync all products where aktivan = 1 to PrestaShop."""
    
    # Fetch all products with aktivan = 1
    active_products = frappe.get_all(
        "Proizvodi",
        filters={"aktivan": 1},
        fields=["art_sifra"]
    )

    # Log details for synchronization
    log_details = "Starting sync for active products...\n"

    # Loop through each active product and sync it to PrestaShop
    for product in active_products:
        try:
            result = sync_product_to_prestashop(product["art_sifra"])
            log_details += f"Product {product['art_sifra']} synced successfully.\n"
        except Exception as e:
            log_details += f"Failed to sync product {product['art_sifra']}: {str(e)}\n"
            frappe.log_error(f"Error syncing product {product['art_sifra']}: {str(e)}", "Product Sync Error")

    # Optionally log the overall result
    frappe.log_error(log_details, "Active Products Sync Log")