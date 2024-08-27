import requests
from frappe.utils.background_jobs import enqueue
import xml.etree.ElementTree as ET
import frappe
from frappe.model.document import Document
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
from prestapyt import (
    PrestaShopWebServiceDict,
)
import base64
import datetime
import os
import json


class Proizvodi(Document):
    pass


def create_sync_log(sync_type):
    """Create a new Sync Log entry."""
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


def truncate_string(input_string, max_length):
    return input_string[:max_length]

def update_sync_log(sync_log, log_details, status="Success"):
    """Update the Sync Log entry with accumulated log details and final status."""
    max_log_length = 65535
    if len(log_details) > max_log_length:
        log_details = truncate_string(log_details, max_log_length)
        log_message(sync_log, "Log details truncated due to size limit.")

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


def log_message(sync_log, message):
    """Append a message to the Sync Log."""
    if sync_log:
        if sync_log.log_details:
            sync_log.log_details += message + "\n"
        else:
            sync_log.log_details = message + "\n"
        sync_log.save(ignore_permissions=True)
        frappe.db.commit()


def get_prestashop_settings():
    presta_key_raw = "APXHV1BE9ZISZQMDFEYVE6HKXPXJIGBH"
    presta_key_encoded = base64.b64encode(presta_key_raw.encode("utf-8")).decode(
        "utf-8"
    )
    return {
        "presta_url": "https://test2.imtec.ba/api",
        "presta_key": presta_key_encoded,
    }


def get_headers(settings):
    return {
        "Authorization": f"Basic {settings['presta_key']}",
        "Content-Type": "application/xml",
    }


def clean_response(response_text):
    clean_text = re.sub(r"^.*?(<\?xml)", r"\1", response_text, flags=re.DOTALL)
    return clean_text


def search_prestashop_product(settings, reference, sync_log=None):
    url = f"{settings['presta_url']}/products"
    params = {"filter[reference]": reference}

    log_message(
        sync_log, f"Searching for product with reference {reference} using URL: {url}"
    )
    response = requests.get(url, params=params, headers=get_headers(settings))

    log_message(sync_log, f"Response Status Code: {response.status_code}")
    log_message(sync_log, f"Response Text: {response.text}")

    if response.status_code == 200:
        try:
            clean_response_text = clean_response(response.text)
            root = ET.fromstring(clean_response_text)
            products = root.findall(".//product")
            if products:
                product_id = products[0].get("id")
                log_message(sync_log, f"Found product ID: {product_id}")
                return product_id
            else:
                log_message(sync_log, "No product found with the given reference.")
                return None
        except ET.ParseError as e:
            log_message(sync_log, f"Failed to parse XML from response: {e}")
            return None
    else:
        log_message(
            sync_log, f"Failed to search product. Status Code: {response.status_code}"
        )
        return None


def handle_none(value):
    return value if value is not None else ""


def get_existing_product_data(settings, prestashop_id, sync_log=None):
    url = f"{settings['presta_url']}/products/{prestashop_id}"
    response = requests.get(url, headers=get_headers(settings))

    log_message(
        sync_log,
        f"Fetching existing product data for ID {prestashop_id} using URL: {url}",
    )
    log_message(sync_log, f"Response Status Code: {response.status_code}")
    log_message(sync_log, f"Response Text: {response.text}")

    if response.status_code == 200:
        try:
            clean_response_text = clean_response(response.text)
            root = ET.fromstring(clean_response_text)
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
            log_message(sync_log, f"Failed to parse XML from response: {e}")
            return None
    else:
        log_message(
            sync_log,
            f"Failed to retrieve existing product data. Status Code: {response.status_code}",
        )
        return None


def generate_link_rewrite(name):
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    return name if name else "default-link-rewrite"


def generate_product_xml(product_data, prestashop_id=None):
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
    link_rewrite = generate_link_rewrite(prname)

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
                <language id="1"><![CDATA[{handle_none(product_data.get('description', {}).get('1', ''))}]]></language>
                <language id="2"><![CDATA[{handle_none(product_data.get('description', {}).get('2', ''))}]]></language>
            </description>
            <description_short><![CDATA[{handle_none(product_data.get('description_short', {}).get('2', ''))}]]></description_short>
            <meta_description>
                <language id="1"><![CDATA[{handle_none(product_data.get('meta_description', {}).get('1', ''))}]]></language>
                <language id="2"><![CDATA[{handle_none(product_data.get('meta_description', {}).get('2', ''))}]]></language>
            </meta_description>
            <meta_keywords>
                <language id="1"><![CDATA[{handle_none(product_data.get('meta_keywords', {}).get('1', ''))}]]></language>
                <language id="2"><![CDATA[{handle_none(product_data.get('meta_keywords', {}).get('2', ''))}]]></language>
            </meta_keywords>
            <meta_title>
                <language id="1"><![CDATA[{handle_none(product_data.get('meta_title', {}).get('1', ''))}]]></language>
                <language id="2"><![CDATA[{handle_none(product_data.get('meta_title', {}).get('2', ''))}]]></language>
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


def check_and_create_category(group_name, sync_log=None):
    """Check if the category exists in PrestaShop; if not, create it."""
    existing_category_id = frappe.db.get_value(
        "Proizvodi",
        {"grupanaziv": group_name, "prestashop_category_id": ["is", "set"]},
        "prestashop_category_id",
    )

    if existing_category_id:
        log_message(
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
            log_message(
                sync_log,
                f"Updated category '{group_name}' with PrestaShop ID {prestashop_category_id}",
            )
        else:
            log_message(sync_log, f"Failed to process category '{group_name}'")

        return prestashop_category_id


def check_and_create_manufacturer(manufacturer_name, sync_log=None):
    """Check if the manufacturer exists in PrestaShop; if not, create it."""
    existing_manufacturer_id = frappe.db.get_value(
        "Proizvodi",
        {"proizvodjac": manufacturer_name, "prestashop_manufacturer_id": ["is", "set"]},
        "prestashop_manufacturer_id",
    )

    if existing_manufacturer_id:
        log_message(
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
            log_message(
                sync_log,
                f"Updated manufacturer '{manufacturer_name}' with PrestaShop ID {prestashop_manufacturer_id}",
            )
        else:
            log_message(
                sync_log, f"Failed to process manufacturer '{manufacturer_name}'"
            )

        return prestashop_manufacturer_id


@frappe.whitelist()
def sync_product_to_prestashop_manual(art_sifra, sync_log=None):
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
        new_prestashop_category_id = check_and_create_category(product.grupanaziv, sync_log)
        new_product_data["prestashop_category_id"] = new_prestashop_category_id

        # Check and create manufacturer if needed
        new_prestashop_manufacturer_id = check_and_create_manufacturer(
            product.proizvodjac, sync_log
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
        settings = get_prestashop_settings()
        prestashop_id = search_prestashop_product(
            settings, new_product_data["art_sifra"], sync_log=sync_log
        )

        if prestashop_id:
            existing_product_data = get_existing_product_data(settings, prestashop_id, sync_log=sync_log)
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

                xml_payload = generate_product_xml(new_product_data, prestashop_id)

                url = f"{settings['presta_url']}/products/{prestashop_id}"
                response = requests.put(
                    url, headers=get_headers(settings), data=xml_payload.encode("utf-8")
                )

                if response.status_code in [200, 201]:
                    log_details += f"Product {new_product_data['art_sifra']} synced successfully.\n"
                    # Immediately update stock after successful product sync
                    stock_available_id = get_stock_available_id(settings, prestashop_id, sync_log=sync_log)
                    if stock_available_id:
                        update_stock_quantity(
                            settings,
                            stock_available_id,
                            prestashop_id,
                            new_product_data["stanje"],
                            sync_log=sync_log
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
            prestashop_id = create_prestashop_product(settings, new_product_data, sync_log=sync_log)
            if prestashop_id:
                product.prestashop_id = prestashop_id
                product.save(ignore_permissions=True)
                frappe.db.commit()
                # Immediately update stock after successful product creation
                update_stock_quantity(
                    settings, prestashop_id, new_product_data["stanje"], sync_log=sync_log
                )

    except frappe.DoesNotExistError:
        log_details += f"Product with art_sifra {art_sifra} does not exist.\n"
    except Exception as e:
        log_details += f"An unexpected error occurred: {str(e)}\n"

    log_message(sync_log, log_details)  # Log details for each product sync
    return log_details  # Return accumulated logs for each product sync


def create_prestashop_product(settings, product_data, sync_log=None):
    url = f"{settings['presta_url']}/products"
    payload = generate_product_xml(product_data)
    headers = {
        "Content-Type": "application/xml",
        "Authorization": f"Basic {settings['presta_key']}",
    }

    response = requests.post(url, headers=headers, data=payload.encode("utf-8"))

    if response.status_code in [200, 201]:
        log_message(
            sync_log, f"Product {product_data['art_sifra']} created successfully."
        )
        try:
            root = ET.fromstring(response.text)
            product_id = root.find(".//product").get("id")
            return product_id
        except ET.ParseError as e:
            log_message(sync_log, f"Failed to parse XML from response: {e}")
            return None
    else:
        log_message(
            sync_log, f"Failed to create product. Status Code: {response.status_code}"
        )
        return None


def get_stock_available_id(settings, prestashop_id, sync_log=None):
    url = f"{settings['presta_url']}/stock_availables"
    params = {"filter[id_product]": prestashop_id, "display": "full"}

    response = requests.get(url, params=params, headers=get_headers(settings))

    log_message(
        sync_log,
        f"Fetching stock_available for product ID {prestashop_id} using URL: {url}",
    )
    log_message(sync_log, f"Response Status Code: {response.status_code}")
    log_message(sync_log, f"Response Text: {response.text}")

    if response.status_code == 200:
        try:
            clean_response_text = clean_response(response.text)
            root = ET.fromstring(clean_response_text)
            stock_availables = root.findall(".//stock_available")

            for stock_available in stock_availables:
                id_product_attribute = stock_available.find("id_product_attribute")

                if (
                    id_product_attribute is not None
                    and id_product_attribute.text == "0"
                ):
                    stock_available_id = stock_available.find("id").text
                    log_message(
                        sync_log,
                        f"Found stock_available ID: {stock_available_id} for product ID: {prestashop_id}",
                    )
                    return stock_available_id

            log_message(
                sync_log, "No suitable stock_available found for the given product ID."
            )
            return None
        except ET.ParseError as e:
            log_message(sync_log, f"Failed to parse XML from response: {e}")
            return None
    else:
        log_message(
            sync_log,
            f"Failed to retrieve stock_available. Status Code: {response.status_code}",
        )
        return None


def update_stock_quantity(
    settings, stock_available_id, product_id, quantity, sync_log=None
):
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

    log_message(
        sync_log,
        f"Updating stock for stock_available ID {stock_available_id} to {quantity} using URL: {url}",
    )
    log_message(sync_log, f"Response Status Code: {response.status_code}")
    log_message(sync_log, f"Response Text: {response.text}")

    if response.status_code in [200, 201]:
        log_message(
            sync_log,
            f"Stock quantity for stock_available ID {stock_available_id} updated to {quantity}.",
        )
    else:
        log_message(
            sync_log,
            f"Failed to update stock quantity. Status Code: {response.status_code}",
        )


@frappe.whitelist()
def get_sync_progress():
    # Fetch the latest sync progress document
    sync_progress = frappe.get_all(
        "Sync Progress",
        fields=["total_records", "processed_records", "status"],
        order_by="modified desc",
        limit=1,
    )
    if sync_progress:
        return sync_progress[0]
    else:
        return {"total_records": 0, "processed_records": 0, "status": "Not Started"}


def sync_product(art_sifra, sync_log=None):
    """
    Sync a single product to PrestaShop.
    """
    try:
        sync_product_to_prestashop_manual(art_sifra, sync_log=sync_log)
        # Mark as synced
        frappe.db.set_value(
            "Proizvodi", {"art_sifra": art_sifra}, "status", "on_presta"
        )
    except Exception as e:
        frappe.log_error(
            f"Failed to sync product {art_sifra}: {str(e)}", "Product Sync Error"
        )


@frappe.whitelist()
def enqueue_sync_all_active_products():
    """
    Enqueue the task to sync all active products to PrestaShop in the background.
    """
    # Create a new Sync Progress document
    sync_progress = frappe.get_doc(
        {
            "doctype": "Sync Progress",
            "total_records": frappe.db.count(
                "Proizvodi",
                {
                    "aktivan": 1,
                    "agp_id": ["!=", ""],  # Check for non-empty string
                    "sifra": ["!=", ""],
                },
            ),
            "processed_records": 0,
            "status": "In Progress",
        }
    )
    sync_progress.insert()
    frappe.db.commit()  # Ensure it is committed to the database

    # Enqueue the background job without batch size
    enqueue(
        method=sync_all_active_products,
        queue="long",
        timeout=2500,
        job_name="Sync All Active Products",
        sync_progress_name=sync_progress.name,
    )
    frappe.msgprint(_("The sync operation has been started in the background."))


def sync_all_active_products(sync_progress_name=None):
    """
    Sync all active products to PrestaShop without batch processing.
    """
    try:
        # Fetch all active products without batching
        active_products = frappe.get_all(
            "Proizvodi",
            filters={
                "aktivan": 1,
                "status": ["!=", "on_presta"],
                "agp_id": ["is", "set"],
                "sifra": ["is", "set"],
            },
            fields=["art_sifra"],
        )

        total_records = len(active_products)
        processed_count = 0

        # Fetch Sync Progress document
        if sync_progress_name:
            sync_progress = frappe.get_doc("Sync Progress", sync_progress_name)
        else:
            frappe.throw(_("Sync Progress name is required."))

        sync_progress.total_records = total_records
        sync_progress.processed_records = processed_count
        sync_progress.status = "In Progress"
        sync_progress.save()

        # Process each product without batching
        for product in active_products:
            try:
                sync_product_to_prestashop_manual(product["art_sifra"], sync_log=sync_progress)

                # Update status to "on_presta" after successful sync
                frappe.db.set_value(
                    "Proizvodi", product["art_sifra"], "status", "on_presta"
                )

                processed_count += 1
                sync_progress.processed_records = processed_count
                sync_progress.save()
            except Exception as e:
                frappe.log_error(
                    f"Sync failed for product {product['art_sifra']}: {str(e)}",
                    "Product Sync Error",
                )

        # Mark sync as completed
        sync_progress.status = "Completed"
        sync_progress.save()

    except frappe.DoesNotExistError as e:
        frappe.log_error(
            f"Sync Progress document not found: {str(e)}", "Sync Progress Error"
        )
        frappe.throw(
            _("Sync Progress document not found. Please check the progress name.")
        )

    except Exception as e:
        # Update Sync Progress document in case of an error
        sync_progress.status = "Failed"
        sync_progress.save()
        frappe.log_error(f"Sync failed: {str(e)}", "Sync All Active Products Error")
        frappe.throw(
            _("Failed to sync some products. Please check the logs for more details.")
        )


@frappe.whitelist()
def sync_all_products_for_update():
    log_details = ""  # Initialize log accumulation for overall sync
    sync_log = create_sync_log("Sync All Products for Update")

    # Debugging print statement
    print(
        "Starting sync_all_products function...",
        file=open("/home/frappe/frappe-bench/logs/sync.debug.log", "a"),
    )

    try:
        # Insert or update products based on `for_insert_eline_data.json`
        try:
            log_details += "Inserting or updating data from for_insert_eline_data.json...\n"
            insert_data_from_for_insert_eline_data()
            log_details += "Data insertion or update completed.\n"
        except Exception as e:
            log_details += f"Error while inserting or updating data: {str(e)}\n"
            update_sync_log(sync_log, log_details, status="Failed")
            return  # Exit early since there was an error

        # Fetch products that are marked for update
        log_details += "Fetching products marked for update...\n"
        products_for_update = frappe.get_all(
            "Proizvodi", filters={"status": "for_update"}, fields=["art_sifra"]
        )

        log_details += f"Found {len(products_for_update)} products for update.\n"

        for product in products_for_update:
            try:
                result = sync_product_to_prestashop_manual(product["art_sifra"], sync_log=sync_log)
                log_details += f"Product {product['art_sifra']} sync result: {result}\n"
            except Exception as e:
                log_details += f"Failed to sync product {product['art_sifra']}: {str(e)}\n"
                frappe.log_error(f"Failed to sync product {product['art_sifra']}: {str(e)}", "Product Sync Error")

            # Debugging print statement
            print(
                f"Processed product {product['art_sifra']}",
                file=open("/home/frappe/frappe-bench/logs/sync.debug.log", "a"),
            )

        # Fetch products that are marked for insert
        log_details += "Fetching products marked for insert...\n"
        products_for_insert = frappe.get_all(
            "Proizvodi", filters={"status": "for_insert"}, fields=["art_sifra"]
        )

        log_details += f"Found {len(products_for_insert)} products for insert.\n"

        for product in products_for_insert:
            try:
                result = sync_product_to_prestashop_insert(product["art_sifra"], sync_log=sync_log)
                log_details += f"Product {product['art_sifra']} sync result: {result}\n"
            except Exception as e:
                log_details += f"Failed to insert product {product['art_sifra']}: {str(e)}\n"
                frappe.log_error(f"Failed to insert product {product['art_sifra']}: {str(e)}", "Product Insert Error")

            # Debugging print statement
            print(
                f"Processed product {product['art_sifra']} for insert",
                file=open("/home/frappe/frappe-bench/logs/sync.debug.log", "a"),
            )

        # Fetch products that are marked for rename
        log_details += "Fetching products marked for rename...\n"
        products_for_rename = frappe.get_all(
            "Proizvodi", filters={"status": "for_rename"}, fields=["art_sifra"]
        )

        log_details += f"Found {len(products_for_rename)} products for rename.\n"

        for product in products_for_rename:
            try:
                result = sync_product_to_prestashop_rename(product["art_sifra"], sync_log=sync_log)
                log_details += f"Product {product['art_sifra']} sync result: {result}\n"
            except Exception as e:
                log_details += f"Failed to rename product {product['art_sifra']}: {str(e)}\n"
                frappe.log_error(f"Failed to rename product {product['art_sifra']}: {str(e)}", "Product Rename Error")

            # Debugging print statement
            print(
                f"Processed product {product['art_sifra']} for rename",
                file=open("/home/frappe/frappe-bench/logs/sync.debug.log", "a"),
            )

        # Update log with the accumulated details after all products are processed
        update_sync_log(sync_log, log_details, status="Success")

    except Exception as e:
        log_details += f"An unexpected error occurred: {str(e)}\n"
        update_sync_log(sync_log, log_details, status="Failed")

        # Debugging print statement
        print(
            f"Error occurred: {str(e)}",
            file=open("/home/frappe/frappe-bench/logs/sync.debug.log", "a"),
        )

    print(
        "Completed sync_all_products function.",
        file=open("/home/frappe/frappe-bench/logs/sync.debug.log", "a"),
    )

@frappe.whitelist()
def sync_all_stanje_products(batch_size=500):
    log_details = ""
    sync_log = create_sync_log("Sync All Active Products")

    try:
        # Start index for batching
        start = 0
        # Count total active products
        total_records = frappe.db.count("Proizvodi", {"stanje": ["!=", 0]})

        while start < total_records:
            # Fetch the next batch of active products with limit and offset
            stanje_products = frappe.get_all(
                "Proizvodi",
                filters={"stanje": ["!=", 0]},
                fields=["art_sifra"],
                limit=batch_size,
                start=start,
            )

            # Process each product in the current batch
            for product in stanje_products:
                # Sync each product to PrestaShop and collect the log details
                result = sync_product_to_prestashop_manual(product["art_sifra"], sync_log=sync_log)
                log_details += result + "\n"

            # Update the sync log with the accumulated log details after each batch
            update_sync_log(sync_log, log_details, status="In Progress")

            # Increment the start index for the next batch
            start += batch_size

        # Final update to sync log after all products are processed
        update_sync_log(sync_log, log_details, status="Success")

    except Exception as e:
        log_details += f"An unexpected error occurred: {str(e)}\n"
        update_sync_log(sync_log, log_details, status="Failed")


@frappe.whitelist()
def manual_insert_product_from_json(art_sifra):
    """
    Manually add or update a product from current_eline_data.json based on the provided art_sifra.
    """
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
        log_details = sync_product_to_prestashop_manual(art_sifra, sync_log=sync_log)
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
        sync_product_to_prestashop_manual(art_sifra, sync_log=sync_log)
        frappe.msgprint(
            _("Product with art_sifra {0} successfully inserted and synced.").format(
                art_sifra
            )
        )


@frappe.whitelist()
def reset_products_status():
    frappe.db.sql("""UPDATE tabProizvodi SET status = ''""")
    frappe.db.commit()


def sync_product_to_prestashop_insert(art_sifra, sync_log=None):
    """
    Insert a product into PrestaShop based on its art_sifra.
    """
    log_details = ""  # Initialize log accumulation for individual insert

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
            "hash": product.hash,
        }

        # Check and create category if needed
        new_prestashop_category_id = check_and_create_category(product.grupanaziv, sync_log)
        new_product_data["prestashop_category_id"] = new_prestashop_category_id

        # Check and create manufacturer if needed
        new_prestashop_manufacturer_id = check_and_create_manufacturer(product.proizvodjac, sync_log)
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
        settings = get_prestashop_settings()
        prestashop_id = search_prestashop_product(settings, new_product_data["art_sifra"], sync_log=sync_log)

        if prestashop_id:
            # If product exists, update it instead of inserting
            log_details += f"Product {art_sifra} already exists in PrestaShop with ID {prestashop_id}. Updating product.\n"
            existing_product_data = get_existing_product_data(settings, prestashop_id, sync_log=sync_log)
            if existing_product_data:
                # Update the product in PrestaShop
                xml_payload = generate_product_xml(new_product_data, prestashop_id)
                url = f"{settings['presta_url']}/products/{prestashop_id}"
                response = requests.put(url, headers=get_headers(settings), data=xml_payload.encode("utf-8"))

                if response.status_code in [200, 201]:
                    log_details += f"Product {art_sifra} updated successfully in PrestaShop.\n"
                else:
                    log_details += f"Failed to update product {art_sifra}. Status Code: {response.status_code}, Response: {response.text}\n"
            else:
                log_details += f"Failed to retrieve existing product data for {art_sifra}.\n"
        else:
            # If product does not exist, insert it
            log_details += f"Product with reference {new_product_data['art_sifra']} does not exist. Creating it.\n"
            prestashop_id = create_prestashop_product(settings, new_product_data, sync_log=sync_log)
            if prestashop_id:
                product.prestashop_id = prestashop_id
                product.status = "on_presta"
                product.save(ignore_permissions=True)
                frappe.db.commit()  # Commit changes to the database
                log_details += f"Product {art_sifra} inserted successfully into PrestaShop with ID {prestashop_id}.\n"
            else:
                log_details += f"Failed to insert product {art_sifra} into PrestaShop. Check response and product data for issues.\n"

    except frappe.DoesNotExistError:
        log_details += f"Product with art_sifra {art_sifra} does not exist in ERPNext.\n"
    except Exception as e:
        log_details += f"An unexpected error occurred while inserting product {art_sifra}: {str(e)}\n"

    log_message(sync_log, log_details)  # Log details for each product insert
    return log_details  # Return accumulated logs for each product insert



def sync_product_to_prestashop_rename(art_sifra, sync_log="Rename Items"):
    """
    Rename a category or manufacturer in PrestaShop based on the product's current state in ERPNext.
    """
    log_details = ""  # Initialize log accumulation for individual rename

    try:
        # Fetch the product document
        product = frappe.get_doc("Proizvodi", {"art_sifra": art_sifra})

        # Get PrestaShop settings
        settings = get_prestashop_settings()

        # Determine if we are renaming a category or a manufacturer
        if product.grupanaziv:
            # Fetch the current category mapping
            current_category = frappe.db.get_value(
                "Proizvodi",
                {"art_sifra": art_sifra},
                ["prestashop_category_id", "grupanaziv"],
                as_dict=True
            )
            
            if current_category and current_category["prestashop_category_id"]:
                # Generate the XML payload to rename the category
                xml_payload = f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
                    <category>
                        <id>{current_category["prestashop_category_id"]}</id>
                        <name>
                            <language id="1"><![CDATA[{product.grupanaziv}]]></language>
                            <language id="2"><![CDATA[{product.grupanaziv}]]></language>
                        </name>
                    </category>
                </prestashop>
                """.strip()

                # Make a PUT request to update the category name in PrestaShop
                url = f"{settings['presta_url']}/categories/{current_category['prestashop_category_id']}"
                response = requests.put(url, headers=get_headers(settings), data=xml_payload.encode("utf-8"))

                if response.status_code in [200, 201]:
                    log_details += f"Category renamed to {product.grupanaziv} successfully in PrestaShop.\n"
                else:
                    log_details += f"Failed to rename category. Status Code: {response.status_code}, Response: {response.text}\n"

        if product.proizvodjac:
            # Fetch the current manufacturer mapping
            current_manufacturer = frappe.db.get_value(
                "Proizvodi",
                {"art_sifra": art_sifra},
                ["prestashop_manufacturer_id", "proizvodjac"],
                as_dict=True
            )
            
            if current_manufacturer and current_manufacturer["prestashop_manufacturer_id"]:
                # Generate the XML payload to rename the manufacturer
                xml_payload = f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
                    <manufacturer>
                        <id>{current_manufacturer["prestashop_manufacturer_id"]}</id>
                        <name><![CDATA[{product.proizvodjac}]]></name>
                    </manufacturer>
                </prestashop>
                """.strip()

                # Make a PUT request to update the manufacturer name in PrestaShop
                url = f"{settings['presta_url']}/manufacturers/{current_manufacturer['prestashop_manufacturer_id']}"
                response = requests.put(url, headers=get_headers(settings), data=xml_payload.encode("utf-8"))

                if response.status_code in [200, 201]:
                    log_details += f"Manufacturer renamed to {product.proizvodjac} successfully in PrestaShop.\n"
                else:
                    log_details += f"Failed to rename manufacturer. Status Code: {response.status_code}, Response: {response.text}\n"

    except frappe.DoesNotExistError:
        log_details += f"Product with art_sifra {art_sifra} does not exist in ERPNext.\n"
    except Exception as e:
        log_details += f"An unexpected error occurred while renaming product {art_sifra}: {str(e)}\n"

    log_message(sync_log, log_details)  # Log details for each product rename
    return log_details  # Return accumulated logs for each product rename






def rename_category(group_name, new_name, sync_log=None):
    """
    Rename a category in PrestaShop if needed.
    
    :param group_name: The current group name in the ERP system.
    :param new_name: The new name to be set in PrestaShop.
    :param sync_log: The sync log document to append log messages to.
    """
    existing_category_id = frappe.db.get_value(
        "Proizvodi",
        {"grupanaziv": group_name, "prestashop_category_id": ["is", "set"]},
        "prestashop_category_id",
    )

    if existing_category_id:
        # Fetch current category details from PrestaShop to compare names
        settings = get_prestashop_settings()
        url = f"{settings['presta_url']}/categories/{existing_category_id}"
        response = requests.get(url, headers=get_headers(settings))

        if response.status_code == 200:
            try:
                clean_response_text = clean_response(response.text)
                root = ET.fromstring(clean_response_text)
                current_name = root.find(".//name/language").text

                if current_name != new_name:
                    # Rename the category if the name differs
                    rename_payload = f"""
                    <?xml version="1.0" encoding="UTF-8"?>
                    <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
                        <category>
                            <id>{existing_category_id}</id>
                            <name>
                                <language id="1"><![CDATA[{new_name}]]></language>
                                <language id="2"><![CDATA[{new_name}]]></language>
                            </name>
                        </category>
                    </prestashop>
                    """.strip()

                    rename_response = requests.put(url, headers=get_headers(settings), data=rename_payload.encode("utf-8"))

                    if rename_response.status_code in [200, 201]:
                        log_message(sync_log, f"Category '{group_name}' renamed to '{new_name}' in PrestaShop.")
                        frappe.db.sql(
                            """
                            UPDATE `tabProizvodi`
                            SET grupanaziv = %s
                            WHERE prestashop_category_id = %s
                            """,
                            (new_name, existing_category_id),
                        )
                        frappe.db.commit()
                    else:
                        log_message(sync_log, f"Failed to rename category '{group_name}' in PrestaShop. Status Code: {rename_response.status_code}")
                else:
                    log_message(sync_log, f"Category '{group_name}' name already matches the new name '{new_name}'. No rename needed.")
            except ET.ParseError as e:
                log_message(sync_log, f"Failed to parse XML from response: {e}")
        else:
            log_message(sync_log, f"Failed to fetch category '{group_name}' details from PrestaShop. Status Code: {response.status_code}")
    else:
        log_message(sync_log, f"No existing PrestaShop category ID found for '{group_name}'.")


def rename_manufacturer(manufacturer_name, new_name, sync_log=None):
    """
    Rename a manufacturer in PrestaShop if needed.
    
    :param manufacturer_name: The current manufacturer name in the ERP system.
    :param new_name: The new name to be set in PrestaShop.
    :param sync_log: The sync log document to append log messages to.
    """
    existing_manufacturer_id = frappe.db.get_value(
        "Proizvodi",
        {"proizvodjac": manufacturer_name, "prestashop_manufacturer_id": ["is", "set"]},
        "prestashop_manufacturer_id",
    )

    if existing_manufacturer_id:
        # Fetch current manufacturer details from PrestaShop to compare names
        settings = get_prestashop_settings()
        url = f"{settings['presta_url']}/manufacturers/{existing_manufacturer_id}"
        response = requests.get(url, headers=get_headers(settings))

        if response.status_code == 200:
            try:
                clean_response_text = clean_response(response.text)
                root = ET.fromstring(clean_response_text)
                current_name = root.find(".//name").text

                if current_name != new_name:
                    # Rename the manufacturer if the name differs
                    rename_payload = f"""
                    <?xml version="1.0" encoding="UTF-8"?>
                    <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
                        <manufacturer>
                            <id>{existing_manufacturer_id}</id>
                            <name><![CDATA[{new_name}]]></name>
                        </manufacturer>
                    </prestashop>
                    """.strip()

                    rename_response = requests.put(url, headers=get_headers(settings), data=rename_payload.encode("utf-8"))

                    if rename_response.status_code in [200, 201]:
                        log_message(sync_log, f"Manufacturer '{manufacturer_name}' renamed to '{new_name}' in PrestaShop.")
                        frappe.db.sql(
                            """
                            UPDATE `tabProizvodi`
                            SET proizvodjac = %s
                            WHERE prestashop_manufacturer_id = %s
                            """,
                            (new_name, existing_manufacturer_id),
                        )
                        frappe.db.commit()
                    else:
                        log_message(sync_log, f"Failed to rename manufacturer '{manufacturer_name}' in PrestaShop. Status Code: {rename_response.status_code}")
                else:
                    log_message(sync_log, f"Manufacturer '{manufacturer_name}' name already matches the new name '{new_name}'. No rename needed.")
            except ET.ParseError as e:
                log_message(sync_log, f"Failed to parse XML from response: {e}")
        else:
            log_message(sync_log, f"Failed to fetch manufacturer '{manufacturer_name}' details from PrestaShop. Status Code: {response.status_code}")
    else:
        log_message(sync_log, f"No existing PrestaShop manufacturer ID found for '{manufacturer_name}'.")
