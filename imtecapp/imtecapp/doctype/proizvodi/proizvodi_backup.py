import requests
import xml.etree.ElementTree as ET
import frappe
from frappe.model.document import Document
from imtecapp.imtecapp.doctype.proizvodi.eline.insert_new_data import insert_data_from_for_insert_eline_data
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


def generate_product_xml(product, prestashop_id=None):
    # Set the default category ID to prestashop_category_id from the product data
    default_category_id = product['prestashop_category_id']

    # Include root category (ID 2) and the prestashop_category_id from product
    categories_xml = f"""
    <category>
        <id>2</id>
    </category>
    <category>
        <id>{default_category_id}</id>
    </category>
    """

    # Create the XML payload
    xml_payload = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
        <product>
            {'<id>' + str(prestashop_id) + '</id>' if prestashop_id else ''}
            <reference><![CDATA[{product['art_sifra']}]]></reference>
            <name>
                <language id="1"><![CDATA[{product['art_naziv']}]]></language>
                <language id="2"><![CDATA[{product['art_naziv']}]]></language>
            </name>
            <id_category_default><![CDATA[{default_category_id}]]></id_category_default>
            <id_manufacturer><![CDATA[{product['prestashop_manufacturer_id']}]]></id_manufacturer>
            <price><![CDATA[{product['vpc']}]]></price>
            <active><![CDATA[{1 if product['aktivan'] else 0}]]></active>
            <available_for_order><![CDATA[{1 if product['stanje'] > 0 else 0}]]></available_for_order>
            <show_price><![CDATA[1]]></show_price>
            <id_tax_rules_group><![CDATA[1]]></id_tax_rules_group>
            <id_shop_default><![CDATA[1]]></id_shop_default>
            <visibility><![CDATA[both]]></visibility>
            <state><![CDATA[1]]></state>
            <minimal_quantity><![CDATA[1]]></minimal_quantity>
            <associations>
                <categories>
                    {categories_xml}
                </categories>
            </associations>
        </product>
    </prestashop>
    """.strip()

    return xml_payload


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


def sync_product_to_prestashop_manual(art_sifra):
    try:
        # Fetch product details from the local database using Frappe
        product = frappe.get_doc("Proizvodi", {"art_sifra": art_sifra})
        product_data = {
            "art_sifra": product.art_sifra,
            "art_naziv": product.art_naziv,
            "prestashop_category_id": product.prestashop_category_id,
            "prestashop_manufacturer_id": product.prestashop_manufacturer_id,
            "vpc": product.vpc,
            "aktivan": product.aktivan,
            "stanje": product.stanje,
            "prestashop_id": product.prestashop_id,
            "status": product.status,
        }

        # Get PrestaShop settings
        settings = get_prestashop_settings()

        # Step 1: Find the product ID by reference
        prestashop_id = search_prestashop_product(settings, product_data["art_sifra"])

        if prestashop_id:
            # Product exists, update it
            print(
                f"Product with reference {product_data['art_sifra']} already exists with ID {prestashop_id}. Updating it."
            )
            url = f"{settings['presta_url']}/products/{prestashop_id}"
            response = requests.put(
                url,
                headers=get_headers(settings),
                data=generate_product_xml(
                    product_data, prestashop_id
                ),  # Pass the ID here
            )

            if response.status_code in [200, 201]:
                print(f"Product {product_data['art_sifra']} synced successfully.")

                # Update stock quantity
                stock_available_id = get_stock_available_id(settings, prestashop_id)
                if stock_available_id:
                    update_stock_quantity(
                        settings, stock_available_id, product_data["stanje"]
                    )

            else:
                print(f"Failed to sync product. Status Code: {response.status_code}")
                print(f"Response: {response.text}")
        else:
            # Product doesn't exist, create it
            print(
                f"Product with reference {product_data['art_sifra']} does not exist. Creating it."
            )
            prestashop_id = create_prestashop_product(settings, product_data)
            if prestashop_id:
                # Update Frappe with the new prestashop_id
                product.prestashop_id = prestashop_id
                product.save()

                # Create stock entry for the new product
                update_stock_quantity(settings, prestashop_id, product_data["stanje"])

    except frappe.DoesNotExistError:
        print(f"Product with art_sifra {art_sifra} does not exist.")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")


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


# Call this function to sync all active products
# sync_all_active_products()

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
