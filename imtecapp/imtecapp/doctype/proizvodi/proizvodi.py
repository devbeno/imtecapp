import requests
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


class Proizvodi(Document):
    pass


def create_sync_log(sync_type):
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


def truncate_string(input_string, max_length):
    return input_string[:max_length]


def update_sync_log(sync_log, log_details, status="Success"):
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


def log_message(sync_log, message):
    """Append a message to the Sync Log."""
    if sync_log:
        sync_log.log_details += message + "\n"
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


def sync_product_to_prestashop_manual(art_sifra):
    log_details = ""  # Initialize log accumulation for individual sync

    try:
        product = frappe.get_doc("Proizvodi", {"art_sifra": art_sifra})
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

        new_product_data["prestashop_category_id"] = check_and_create_category(
            product.grupanaziv
        )
        new_product_data["prestashop_manufacturer_id"] = check_and_create_manufacturer(
            product.proizvodjac
        )

        settings = get_prestashop_settings()
        prestashop_id = search_prestashop_product(
            settings, new_product_data["art_sifra"]
        )

        if prestashop_id:
            existing_product_data = get_existing_product_data(settings, prestashop_id)
            if existing_product_data:
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
                    stock_available_id = get_stock_available_id(settings, prestashop_id)
                    if stock_available_id:
                        update_stock_quantity(
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
            prestashop_id = create_prestashop_product(settings, new_product_data)
            if prestashop_id:
                product.prestashop_id = prestashop_id
                product.save()
                # Immediately update stock after successful product creation
                update_stock_quantity(
                    settings, prestashop_id, new_product_data["stanje"]
                )

    except frappe.DoesNotExistError:
        log_details += f"Product with art_sifra {art_sifra} does not exist.\n"
    except Exception as e:
        log_details += f"An unexpected error occurred: {str(e)}\n"

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
def sync_all_active_products(batch_size=500):
    log_details = ""
    sync_log = create_sync_log("Sync All Active Products")

    try:
        active_products = frappe.get_all(
            "Proizvodi",
            filters={
                "aktivan": 1
                # "prestashop_category_id": ["is", "set"],
                # "prestashop_manufacturer_id": ["is", "set"],
            },
            fields=["art_sifra"],
            limit=batch_size,
        )

        for product in active_products:
            result = sync_product_to_prestashop_manual(product.art_sifra)
            log_details += result + "\n"

        update_sync_log(sync_log, log_details, status="Success")

    except Exception as e:
        log_details += f"An unexpected error occurred: {str(e)}\n"
        update_sync_log(sync_log, log_details, status="Failed")


@frappe.whitelist()
def sync_all_products_for_update():
    # Initialize log accumulation
    log_details = ""
    sync_log = create_sync_log("Sync All Products for Update")

    insert_data_from_for_insert_eline_data()

    try:
        products_for_update = frappe.get_all(
            "Proizvodi", filters={"status": "for_update"}, fields=["art_sifra"]
        )

        for product in products_for_update:
            result = sync_product_to_prestashop_manual(product.art_sifra)
            log_details += result + "\n"  # Accumulate logs for each product sync

        # Update log with the accumulated details after all products are processed
        update_sync_log(sync_log, log_details, status="Success")

    except Exception as e:
        log_details += f"An unexpected error occurred: {str(e)}\n"
        update_sync_log(sync_log, log_details, status="Failed")


@frappe.whitelist()
def reset_products_status():
    frappe.db.sql("""UPDATE tabProizvodi SET status = ''""")
    frappe.db.commit()
