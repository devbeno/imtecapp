import requests
import xml.etree.ElementTree as ET
import frappe
from frappe.model.document import Document
from imtecapp.imtecapp.doctype.proizvodi.eline.insert_new_data import (
    insert_data_from_for_insert_eline_data,
)
from frappe import _


class Proizvodi(Document):
    pass


def get_prestashop_settings():
    return {
        "presta_url": "https://test2.imtec.ba/api",
        "presta_key": "QVBYSFYxQkU5WklTWlFNREZFWVZFNkhLWFBYSklHQkg6",
    }


def get_headers(settings):
    return {
        "Authorization": f"Basic {settings['presta_key']}",
        "Content-Type": "application/xml",
    }


def search_prestashop_product(settings, reference):
    url = f"{settings['presta_url']}/products"
    params = {"filter[reference]": reference}

    print(f"Searching for product with reference {reference} using URL: {url}")
    response = requests.get(url, params=params, headers=get_headers(settings))

    print(f"Response Status Code: {response.status_code}")
    print(f"Response Text: {response.text}")

    if response.status_code == 200:
        try:
            root = ET.fromstring(response.text)
            products = root.findall(".//product")
            if products:
                product_id = products[0].get("id")
                print(f"Found product ID: {product_id}")
                return product_id
            else:
                print("No product found with the given reference.")
                return None
        except ET.ParseError as e:
            print(f"Failed to parse XML from response: {e}")
            return None
    else:
        print(f"Failed to search product. Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        return None


def get_existing_product_data(settings, prestashop_id):
    url = f"{settings['presta_url']}/products/{prestashop_id}"
    response = requests.get(url, headers=get_headers(settings))

    if response.status_code == 200:
        try:
            root = ET.fromstring(response.text)
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
            print(f"Failed to parse XML from response: {e}")
            return None
    else:
        print(
            f"Failed to retrieve existing product data. Status Code: {response.status_code}"
        )
        return None


def generate_product_xml(product_data, prestashop_id=None):
    # Set the default category ID to prestashop_category_id from the product data
    default_category_id = product_data.get("prestashop_category_id", "")

    # Start with the mandatory categories (root and default category)
    categories_xml = f"""
    <category>
        <id>2</id>
    </category>
    <category>
        <id>{default_category_id}</id>
    </category>
    """

    # Add any additional categories from the product data, preserving existing ones
    existing_categories = set(product_data.get("categories", []))
    for category_id in existing_categories:
        if category_id != "2" and category_id != str(default_category_id):
            categories_xml += f"""
            <category>
                <id>{category_id}</id>
            </category>
            """

    # Create the full XML payload including all required fields
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
                <language id="1"><![CDATA[{product_data.get('description', {}).get('1', '')}]]></language>
                <language id="2"><![CDATA[{product_data.get('description', {}).get('2', '')}]]></language>
            </description>
            <description_short><![CDATA[{product_data.get('description_short', {}).get('2', '')}]]></description_short>
            <meta_description>
                <language id="1"><![CDATA[{product_data.get('meta_description', {}).get('1', '')}]]></language>
                <language id="2"><![CDATA[{product_data.get('meta_description', {}).get('2', '')}]]></language>
            </meta_description>
            <meta_keywords>
                <language id="1"><![CDATA[{product_data.get('meta_keywords', {}).get('1', '')}]]></language>
                <language id="2"><![CDATA[{product_data.get('meta_keywords', {}).get('2', '')}]]></language>
            </meta_keywords>
            <meta_title>
                <language id="1"><![CDATA[{product_data.get('meta_title', {}).get('1', '')}]]></language>
                <language id="2"><![CDATA[{product_data.get('meta_title', {}).get('2', '')}]]></language>
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


def sync_product_to_prestashop_manual(art_sifra):
    try:
        # Fetch product details from the local database using Frappe
        product = frappe.get_doc("Proizvodi", {"art_sifra": art_sifra})
        new_product_data = {
            "art_sifra": product.art_sifra,
            "art_naziv": product.art_naziv,
            "prestashop_category_id": product.prestashop_category_id,  # Default category
            "prestashop_manufacturer_id": product.prestashop_manufacturer_id,
            "vpc": product.vpc,
            "aktivan": product.aktivan,
            "stanje": product.stanje,
            "kataloski": product.kataloski,
            "prestashop_id": product.prestashop_id,
            "status": product.status,
        }

        # Get PrestaShop settings
        settings = get_prestashop_settings()

        # Step 1: Find the product ID by reference
        prestashop_id = search_prestashop_product(
            settings, new_product_data["art_sifra"]
        )

        if prestashop_id:
            # Retrieve existing product data from PrestaShop
            existing_product_data = get_existing_product_data(settings, prestashop_id)

            if existing_product_data:
                # Preserve meta and description fields if not provided in new_product_data
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

                # Merge categories from admin panel with existing ones
                existing_categories = set(existing_product_data.get("categories", []))
                new_categories = set([new_product_data["prestashop_category_id"]])
                combined_categories = list(existing_categories.union(new_categories))
                new_product_data["categories"] = combined_categories

                # Generate XML payload with the updated data
                xml_payload = generate_product_xml(new_product_data, prestashop_id)

                # Update product on PrestaShop
                url = f"{settings['presta_url']}/products/{prestashop_id}"
                response = requests.put(
                    url, headers=get_headers(settings), data=xml_payload.encode("utf-8")
                )

                if response.status_code in [200, 201]:
                    print(
                        f"Product {new_product_data['art_sifra']} synced successfully."
                    )
                    # Update stock quantity
                    stock_available_id = get_stock_available_id(settings, prestashop_id)
                    if stock_available_id:
                        update_stock_quantity(
                            settings, stock_available_id, new_product_data["stanje"]
                        )
                else:
                    print(
                        f"Failed to sync product. Status Code: {response.status_code}"
                    )
                    print(f"Response: {response.text}")
            else:
                print("Failed to retrieve existing product data.")

        else:
            # Product doesn't exist, create it
            print(
                f"Product with reference {new_product_data['art_sifra']} does not exist. Creating it."
            )
            prestashop_id = create_prestashop_product(settings, new_product_data)
            if prestashop_id:
                # Update Frappe with the new prestashop_id
                product.prestashop_id = prestashop_id
                product.save()

                # Create stock entry for the new product
                update_stock_quantity(
                    settings, prestashop_id, new_product_data["stanje"]
                )

    except frappe.DoesNotExistError:
        print(f"Product with art_sifra {art_sifra} does not exist.")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")


def create_prestashop_product(settings, product_data):
    url = f"{settings['presta_url']}/products"
    payload = generate_product_xml(product_data)
    headers = {
        "Content-Type": "application/xml",
        "Authorization": f"Basic {settings['presta_key']}",
    }

    response = requests.post(url, headers=headers, data=payload.encode("utf-8"))

    if response.status_code in [200, 201]:
        print(f"Product {product_data['art_sifra']} created successfully.")
        # Parse the response to get the new product ID
        try:
            root = ET.fromstring(response.text)
            product_id = root.find(".//product").get("id")
            return product_id
        except ET.ParseError as e:
            print(f"Failed to parse XML from response: {e}")
            return None
    else:
        print(f"Failed to create product. Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        return None


def get_stock_available_id(settings, prestashop_id):
    url = f"{settings['presta_url']}/stock_availables"
    params = {"filter[id_product]": prestashop_id}

    response = requests.get(url, params=params, headers=get_headers(settings))

    if response.status_code == 200:
        try:
            root = ET.fromstring(response.text)
            stock_availables = root.findall(".//stock_available")
            if stock_availables:
                stock_available_id = stock_availables[0].get("id")
                print(f"Found stock_available ID: {stock_available_id}")
                return stock_available_id
            else:
                print("No stock_available found for the given product ID.")
                return None
        except ET.ParseError as e:
            print(f"Failed to parse XML from response: {e}")
            return None
    else:
        print(
            f"Failed to retrieve stock_available. Status Code: {response.status_code}"
        )
        print(f"Response: {response.text}")
        return None


def update_stock_quantity(settings, stock_available_id, quantity):
    url = f"{settings['presta_url']}/stock_availables/{stock_available_id}"

    payload = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
        <stock_available>
            <id>{stock_available_id}</id>
            <quantity>{quantity}</quantity>
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

    if response.status_code in [200, 201]:
        print(
            f"Stock quantity for stock_available ID {stock_available_id} updated to {quantity}."
        )
    else:
        print(f"Failed to update stock quantity. Status Code: {response.status_code}")
        print(f"Response: {response.text}")


def sync_all_active_products():
    try:
        # Fetch all active products from Frappe
        active_products = frappe.get_all(
            "Proizvodi",
            filters={
                "aktivan": 1,
                "prestashop_category_id": ["is", "set"],
                "prestashop_manufacturer_id": ["is", "set"],
            },
            fields=["art_sifra"],
        )

        for product in active_products:
            sync_product_to_prestashop_manual(product.art_sifra)

    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")


@frappe.whitelist()
def sync_all_products_for_update():
    insert_data_from_for_insert_eline_data()
    try:
        # Fetch all products from Frappe where status is "for_update"
        products_for_update = frappe.get_all(
            "Proizvodi", filters={"status": "for_update"}, fields=["art_sifra"]
        )

        for product in products_for_update:
            sync_product_to_prestashop_manual(product.art_sifra)

    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")


@frappe.whitelist()
def reset_products_status():
    frappe.db.sql("""UPDATE tabProizvodi SET status = ''""")
    frappe.db.commit()
