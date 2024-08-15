import frappe
import requests
import re
from frappe import _
import xml.etree.ElementTree as ET
import os
import json


# Fetch Prestashop settings
def get_prestashop_settings():
    settings = frappe.get_single("Generalne Postavke")
    return {
        "presta_url": settings.presta_url,
        "presta_key": settings.presta_key,
    }


@frappe.whitelist(allow_guest=True)
def sync_categories():
    try:
        settings = get_prestashop_settings()

        # Fetch cleaned names from test_prestashop_names
        test_result = frappe.call("imtecapp.api.test_prestashop_names")
        cleaned_names = test_result.get("cleaned_names", {}).get("grupanaziv", [])

        if test_result.get("status") == "fail":
            frappe.throw(_("There are problematic names that need to be fixed first."))

        # Split categories into those that need inserting and those that need updating
        to_insert = []
        to_update = []

        for category in cleaned_names:
            prestashop_id = frappe.db.get_value(
                "Proizvodi", {"grupanaziv": category["name"]}, "prestashop_category_id"
            )
            if prestashop_id:
                to_update.append({"id": prestashop_id, **category})
            else:
                to_insert.append(category)

        # Insert new categories
        insert_categories_into_prestashop(to_insert, settings)

        # Update existing categories
        update_prestashop_categories(to_update, settings)

        return {"status": "success", "message": _("Categories synced successfully.")}

    except Exception as e:
        frappe.logger().error(f"Error syncing categories: {str(e)}")
        frappe.throw(_("Failed to sync categories: {0}").format(str(e)))


@frappe.whitelist(allow_guest=True)
def sync_manufacturers():
    try:
        settings = get_prestashop_settings()

        # Fetch cleaned names from test_prestashop_names
        test_result = frappe.call("imtecapp.api.test_prestashop_names")
        cleaned_names = test_result.get("cleaned_names", {}).get("proizvodjac", [])

        if test_result.get("status") == "fail":
            frappe.throw(_("There are problematic names that need to be fixed first."))

        # Split manufacturers into those that need inserting and those that need updating
        to_insert = []
        to_update = []

        for manufacturer in cleaned_names:
            prestashop_id = frappe.db.get_value(
                "Proizvodi",
                {"proizvodjac": manufacturer["name"]},
                "prestashop_manufacturer_id",
            )
            if prestashop_id:
                to_update.append({"id": prestashop_id, **manufacturer})
            else:
                to_insert.append(manufacturer)

        # Insert new manufacturers
        insert_manufacturers_into_prestashop(to_insert, settings)

        # Update existing manufacturers
        update_prestashop_manufacturers(to_update, settings)

        return {"status": "success", "message": _("Manufacturers synced successfully.")}

    except Exception as e:
        frappe.logger().error(f"Error syncing manufacturers: {str(e)}")
        frappe.throw(_("Failed to sync manufacturers: {0}").format(str(e)))


def insert_categories_into_prestashop(categories, settings):
    prestashop_url = f"{settings['presta_url']}/categories"
    headers = {"Content-Type": "application/xml"}

    for category in categories:
        data = f"""
        <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
            <category>
                <active><![CDATA[1]]></active>
                <id_parent><![CDATA[2]]></id_parent>
                <name>
                    <language id="1"><![CDATA[{category['name']}]]></language>
                    <language id="2"><![CDATA[{category['name']}]]></language>
                </name>
                <link_rewrite>
                    <language id="1"><![CDATA[{category['link_rewrite']}]]></language>
                    <language id="2"><![CDATA[{category['link_rewrite']}]]></language>
                </link_rewrite>
            </category>
        </prestashop>
        """
        try:
            response = requests.post(
                prestashop_url,
                data=data,
                headers=headers,
                auth=(settings["presta_key"], ""),
            )
            response.raise_for_status()
            response_xml = ET.fromstring(response.text)
            category_id = response_xml.find(".//id").text

            # Update Frappe with the new PrestaShop category ID
            frappe.db.set_value(
                "Proizvodi",
                {"grupanaziv": category["name"]},
                "prestashop_category_id",
                category_id,
            )
            frappe.db.commit()
            frappe.logger().info(
                f"Inserted category {category['name']} with ID {category_id}"
            )

        except requests.exceptions.RequestException as e:
            frappe.logger().error(
                f"Failed to insert category {category['name']}: {str(e)}"
            )


def update_prestashop_categories(categories, settings):
    prestashop_url = f"{settings['presta_url']}/categories"
    headers = {"Content-Type": "application/xml"}

    for category in categories:
        data = f"""
        <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
            <category>
                <id><![CDATA[{category['id']}]]></id>
                <active><![CDATA[1]]></active>
                <id_parent><![CDATA[2]]></id_parent>
                <name>
                    <language id="1"><![CDATA[{category['name']}]]></language>
                    <language id="2"><![CDATA[{category['name']}]]></language>
                </name>
                <link_rewrite>
                    <language id="1"><![CDATA[{category['link_rewrite']}]]></language>
                    <language id="2"><![CDATA[{category['link_rewrite']}]]></language>
                </link_rewrite>
            </category>
        </prestashop>
        """
        try:
            response = requests.put(
                f"{prestashop_url}/{category['id']}",
                data=data,
                headers=headers,
                auth=(settings["presta_key"], ""),
            )
            response.raise_for_status()
            frappe.logger().info(
                f"Updated category {category['name']} with ID {category['id']}"
            )

        except requests.exceptions.RequestException as e:
            frappe.logger().error(
                f"Failed to update category {category['name']} (ID {category['id']}): {str(e)}"
            )


def insert_manufacturers_into_prestashop(manufacturers, settings):
    prestashop_url = f"{settings['presta_url']}/manufacturers"
    headers = {"Content-Type": "application/xml"}

    for manufacturer in manufacturers:
        data = f"""
        <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
            <manufacturer>
                <name><![CDATA[{manufacturer['name']}]]></name>
                <active><![CDATA[1]]></active>
            </manufacturer>
        </prestashop>
        """
        try:
            response = requests.post(
                prestashop_url,
                data=data,
                headers=headers,
                auth=(settings["presta_key"], ""),
            )
            response.raise_for_status()
            response_xml = ET.fromstring(response.text)
            manufacturer_id = response_xml.find(".//id").text

            # Update Frappe with the new PrestaShop manufacturer ID
            frappe.db.set_value(
                "Proizvodi",
                {"proizvodjac": manufacturer["name"]},
                "prestashop_manufacturer_id",
                manufacturer_id,
            )
            frappe.db.commit()
            frappe.logger().info(
                f"Inserted manufacturer {manufacturer['name']} with ID {manufacturer_id}"
            )

        except requests.exceptions.RequestException as e:
            frappe.logger().error(
                f"Failed to insert manufacturer {manufacturer['name']}: {str(e)}"
            )


def update_prestashop_manufacturers(manufacturers, settings):
    prestashop_url = f"{settings['presta_url']}/manufacturers"
    headers = {"Content-Type": "application/xml"}

    for manufacturer in manufacturers:
        data = f"""
        <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
            <manufacturer>
                <id><![CDATA[{manufacturer['id']}]]></id>
                <name><![CDATA[{manufacturer['name']}]]></name>
                <active><![CDATA[1]]></active>
            </manufacturer>
        </prestashop>
        """
        try:
            response = requests.put(
                f"{prestashop_url}/{manufacturer['id']}",
                data=data,
                headers=headers,
                auth=(settings["presta_key"], ""),
            )
            response.raise_for_status()
            frappe.logger().info(
                f"Updated manufacturer {manufacturer['name']} with ID {manufacturer['id']}"
            )

        except requests.exceptions.RequestException as e:
            frappe.logger().error(
                f"Failed to update manufacturer {manufacturer['name']} (ID {manufacturer['id']}): {str(e)}"
            )


def fetch_existing_prestashop_data(endpoint, settings):
    url = f"{settings['presta_url']}/{endpoint}?display=full"
    frappe.logger().info(f"Requesting URL: {url}")

    try:
        response = requests.get(url, auth=(settings["presta_key"], ""))
        frappe.logger().info(f"Response Status Code: {response.status_code}")

        if response.status_code != 200:
            frappe.throw(
                _(
                    "Failed to fetch data from Prestashop API: Received status code {0}"
                ).format(response.status_code)
            )

        if not response.text.strip():
            frappe.throw(_("Failed to fetch data from Prestashop API: Empty response"))

        root = ET.fromstring(response.text)
        return parse_prestashop_data_from_xml(root)

    except requests.exceptions.RequestException as e:
        frappe.throw(_("Failed to fetch data from Prestashop API: {0}").format(str(e)))


def parse_prestashop_data_from_xml(root):
    items = []
    for item in root.findall(".//category"):
        item_id = item.find("id")
        item_name_element = item.find("name")

        if item_id is not None and item_name_element is not None:
            item_name_language = item_name_element.find(".//language")
            item_name = (
                item_name_language.text if item_name_language is not None else None
            )

            if item_name:
                items.append({"id": item_id.text, "name": item_name})
            else:
                frappe.logger().warning(
                    f"Warning: Missing 'language' element in 'name': {ET.tostring(item, encoding='unicode')}"
                )
        else:
            frappe.logger().warning(
                f"Warning: Missing 'id' or 'name' in the item: {ET.tostring(item, encoding='unicode')}"
            )

    return items


@frappe.whitelist(allow_guest=True)
def test_prestashop_names():
    # Fetch existing categories and manufacturers from PrestaShop
    settings = get_prestashop_settings()

    # Fetch categories
    existing_categories = fetch_existing_prestashop_data("categories", settings)
    existing_category_map = {
        clean_name(cat["name"]).lower(): cat["id"] for cat in existing_categories
    }

    # Fetch manufacturers
    existing_manufacturers = fetch_existing_prestashop_data("manufacturers", settings)
    existing_manufacturer_map = {
        clean_name(man["name"]).lower(): man["id"] for man in existing_manufacturers
    }

    # Get unique fields from your ERPNext doctype
    unique_fields = get_unique_fields()

    # Ensure that cat_name and man_name are strings before processing
    cleaned_names = {
        "grupanaziv": [
            {
                "name": cat_name["name"] if isinstance(cat_name, dict) else cat_name,
                "prestashop_category_id": existing_category_map.get(
                    clean_name(
                        cat_name["name"] if isinstance(cat_name, dict) else cat_name
                    ).lower()
                ),
            }
            for cat_name in unique_fields["grupanaziv"]
        ],
        "proizvodjac": [
            {
                "name": man_name["name"] if isinstance(man_name, dict) else man_name,
                "prestashop_manufacturer_id": existing_manufacturer_map.get(
                    clean_name(
                        man_name["name"] if isinstance(man_name, dict) else man_name
                    ).lower()
                ),
            }
            for man_name in unique_fields["proizvodjac"]
        ],
    }

    return {"cleaned_names": cleaned_names, "status": "pass"}


# Utility functions
def clean_name(name, max_length=128):
    if not isinstance(name, str):
        return name
    name = name.strip().lower()
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[^\w\s-]", "", name)
    name = name.capitalize()

    if len(name) > max_length:
        name = name[:max_length]
        if " " in name:
            name = name[: name.rfind(" ")]

    return name


def generate_link_rewrite(name, max_length=128):
    name = re.sub(r"[<>;=#{}]", "", name)
    link_rewrite = re.sub(r"\s+", "-", name.lower())
    link_rewrite = re.sub(r"[^\w-]", "", link_rewrite)
    return link_rewrite[:max_length]


@frappe.whitelist(allow_guest=True)
def get_unique_fields():
    try:
        unique_values = {"grupanaziv": [], "proizvodjac": []}

        grupanaziv_values = frappe.get_all(
            "Proizvodi",
            fields=["distinct grupanaziv"],
            order_by="grupanaziv asc",
        )
        unique_values["grupanaziv"] = [
            {"name": entry["grupanaziv"]}
            for entry in grupanaziv_values
            if entry["grupanaziv"]
        ]

        proizvodjac_values = frappe.get_all(
            "Proizvodi",
            fields=["distinct proizvodjac"],
            order_by="proizvodjac asc",
        )
        unique_values["proizvodjac"] = [
            {"name": entry["proizvodjac"]}
            for entry in proizvodjac_values
            if entry["proizvodjac"]
        ]

        return unique_values
    except Exception as e:
        frappe.log_error(message=str(e), title="API Error: get_unique_fields")
        frappe.throw("Failed to retrieve unique fields: {0}".format(str(e)))


# Uncomment to reset values if needed:
# frappe.db.sql("UPDATE `tabProizvodi` SET prestashop_id = ''")
# frappe.db.sql("UPDATE `tabProizvodi` SET prestashop_manufacturer_id = ''")


def clean_product_name(name, max_length=128):
    if not isinstance(name, str):
        return name
    name = name.strip()
    # Preserve uppercase, numbers, spaces, and specific characters
    name = re.sub(r"[^\w\s\-\+,.\(\)]+", "", name)

    if len(name) > max_length:
        name = name[:max_length]
        if " " in name:
            name = name[: name.rfind(" ")]

    return name


@frappe.whitelist(allow_guest=True)
def test_prestashop_products_names():
    # Fetch existing products from PrestaShop
    settings = get_prestashop_settings()
    existing_products = fetch_existing_prestashop_data("products", settings)
    existing_product_map = {
        clean_product_name(prod["name"]).lower(): prod["id"]
        for prod in existing_products
    }

    # Get unique product data from Frappe
    unique_products = frappe.get_all(
        "Proizvodi",
        fields=[
            "art_sifra",
            "art_naziv",
            "prestashop_category_id",
            "prestashop_manufacturer_id",
            "vpc",
            "aktivan",
            "stanje",
        ],
        filters={"aktivan": 1},
        order_by="art_naziv asc",
    )

    cleaned_names = {
        "products": [
            {
                "art_sifra": prod["art_sifra"],
                "name": clean_product_name(
                    prod["art_naziv"]
                ),  # Use clean_product_name as name
                "prestashop_id": existing_product_map.get(
                    clean_product_name(prod["art_naziv"]).lower()
                ),
                "prestashop_category_id": prod["prestashop_category_id"],
                "prestashop_manufacturer_id": prod["prestashop_manufacturer_id"],
                "vpc": prod["vpc"],
                "aktivan": prod["aktivan"],
                "stanje": prod["stanje"],
                "status": (
                    "for_update"
                    if existing_product_map.get(
                        clean_product_name(prod["art_naziv"]).lower()
                    )
                    else "for_insert"
                ),
            }
            for prod in unique_products
        ]
    }

    return {
        "total": len(unique_products),
        "cleaned_names": cleaned_names,
        "status": "pass",
    }


@frappe.whitelist(allow_guest=True)
def sync_products():
    try:
        settings = get_prestashop_settings()
        frappe.logger().info("Fetched settings successfully.")

        # Fetch cleaned names and product data from test_prestashop_products_names
        test_result = frappe.call("imtecapp.api.test_prestashop_products_names")
        frappe.logger().info(f"Test result: {test_result}")

        cleaned_names = test_result.get("cleaned_names", {}).get("products", [])
        if not cleaned_names:
            frappe.throw("No products found for syncing.")

        to_insert = []
        to_update = []

        for product in cleaned_names:
            if isinstance(product, dict):
                if product.get("prestashop_id"):
                    product["id"] = product["prestashop_id"]
                    to_update.append(product)
                else:
                    to_insert.append(product)

        frappe.logger().info(
            f"Products to insert: {len(to_insert)}, to update: {len(to_update)}"
        )

        # Insert new products into PrestaShop
        insert_products_into_prestashop(to_insert, settings)

        # Update existing products in PrestaShop
        update_prestashop_products(to_update, settings)

        return {"status": "success", "message": _("Products synced successfully.")}

    except Exception as e:
        frappe.logger().error(f"Error syncing products: {str(e)}")
        frappe.throw(_("Failed to sync products: {0}").format(str(e)))


def insert_products_into_prestashop(products, settings):
    prestashop_url = f"{settings['presta_url']}/products"
    headers = {
        "Content-Type": "application/xml",
        "Authorization": f"Basic {settings['presta_key']}",
    }

    if not products:
        frappe.logger().error("No products to insert.")
        return

    for product in products:
        try:
            frappe.logger().info(f"Preparing to insert product: {product['name']}")

            if not product.get("name") or not product.get("art_sifra"):
                frappe.logger().error(
                    f"Product {product} is missing 'name' or 'art_sifra'"
                )
                continue

            link_rewrite = generate_link_rewrite(product["name"])
            data = f"""
            <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
                <product>
                    <id_category_default><![CDATA[{product['prestashop_category_id']}]]></id_category_default>
                    <reference><![CDATA[{product['art_sifra']}]]></reference>
                    <name>
                        <language id="1"><![CDATA[{product['name']}]]></language>
                        <language id="2"><![CDATA[{product['name']}]]></language>
                    </name>
                    <link_rewrite>
                        <language id="1"><![CDATA[{link_rewrite}]]></language>
                        <language id="2"><![CDATA[{link_rewrite}]]></language>
                    </link_rewrite>
                    <price><![CDATA[{product['vpc']}]]></price>
                    <active><![CDATA[{1 if product['aktivan'] else 0}]]></active>
                    <id_manufacturer><![CDATA[{product['prestashop_manufacturer_id']}]]></id_manufacturer>
                    <state><![CDATA[1]]></state>
                    <visibility><![CDATA[both]]></visibility>
                    <available_for_order><![CDATA[1]]></available_for_order>
                    <show_price><![CDATA[1]]></show_price>
                    <condition><![CDATA[new]]></condition>
                    <associations>
                        <categories>
                            <category>
                                <id><![CDATA[{product['prestashop_category_id']}]]></id>
                            </category>
                        </categories>
                    </associations>
                </product>
            </prestashop>
            """

            frappe.logger().info(f"Sending POST request for product: {product['name']}")
            frappe.logger().debug(f"Data: {data}")
            response = requests.post(
                prestashop_url,
                data=data,
                headers=headers,
                auth=(settings["presta_key"], ""),
            )
            frappe.logger().info(f"Response Status Code: {response.status_code}")
            frappe.logger().info(f"Response Text: {response.text}")
            response.raise_for_status()

            response_xml = ET.fromstring(response.text)
            product_id = response_xml.find(".//id").text

            frappe.logger().info(f"Product inserted with ID: {product_id}")

            frappe.db.set_value(
                "Proizvodi",
                {"art_sifra": product["art_sifra"]},
                {"prestashop_id": product_id, "status": "on_presta"},
            )
            frappe.db.commit()

        except requests.exceptions.RequestException as e:
            frappe.logger().error(
                f"Failed to insert product {product['name']}: {str(e)}"
            )

        except Exception as e:
            frappe.logger().error(
                f"General error inserting product {product}: {str(e)}"
            )


def update_prestashop_products(products, settings):
    headers = {
        "Content-Type": "application/xml",
        "Authorization": f"Basic {settings['presta_key']}",
    }

    if not products:
        frappe.logger().error("No products to update.")
        return

    for product in products:
        try:
            prestashop_url = f"{settings['presta_url']}/products/{product['id']}"
            link_rewrite = generate_link_rewrite(product["name"])
            data = f"""
            <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
                <product>
                    <id><![CDATA[{product['id']}]]></id>
                    <id_category_default><![CDATA[{product['prestashop_category_id']}]]></id_category_default>
                    <reference><![CDATA[{product['art_sifra']}]]></reference>
                    <name>
                        <language id="1"><![CDATA[{product['name']}]]></language>
                        <language id="2"><![CDATA[{product['name']}]]></language>
                    </name>
                    <link_rewrite>
                        <language id="1"><![CDATA[{link_rewrite}]]></language>
                        <language id="2"><![CDATA[{link_rewrite}]]></language>
                    </link_rewrite>
                    <price><![CDATA[{product['vpc']}]]></price>
                    <active><![CDATA[{1 if product['aktivan'] else 0}]]></active>
                    <id_manufacturer><![CDATA[{product['prestashop_manufacturer_id']}]]></id_manufacturer>
                    <state><![CDATA[1]]></state>
                    <visibility><![CDATA[both]]></visibility>
                    <available_for_order><![CDATA[1]]></available_for_order>
                    <show_price><![CDATA[1]]></show_price>
                    <condition><![CDATA[new]]></condition>
                    <associations>
                        <categories>
                            <category>
                                <id><![CDATA[{product['prestashop_category_id']}]]></id>
                            </category>
                        </categories>
                    </associations>
                </product>
            </prestashop>
            """

            frappe.logger().info(
                f"Sending PUT request for product: {product['name']} with ID {product['id']}"
            )
            frappe.logger().debug(f"Data: {data}")
            response = requests.put(
                prestashop_url,
                data=data,
                headers=headers,
                auth=(settings["presta_key"], ""),
            )
            frappe.logger().info(f"Response Status Code: {response.status_code}")
            frappe.logger().info(f"Response Text: {response.text}")
            response.raise_for_status()

            frappe.db.set_value(
                "Proizvodi",
                {"art_sifra": product["art_sifra"]},
                {"prestashop_id": product["id"], "status": "on_presta"},
            )
            frappe.db.commit()

        except requests.exceptions.RequestException as e:
            frappe.logger().error(
                f"Failed to update product {product['name']} with ID {product['id']}: {str(e)}"
            )

        except Exception as e:
            frappe.logger().error(f"General error updating product {product}: {str(e)}")
