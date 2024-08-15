import frappe
import json
import re


# Function to fetch ERPImtec settings
def get_prestashop_settings():
    return frappe.get_single("Generalne Postavke")


def generate_link_rewrite(name, max_length=128):
    name = re.sub(r"[<>;=#{}]", "", name)
    link_rewrite = re.sub(r"\s+", "-", name.lower())
    link_rewrite = re.sub(r"[^\w-]", "", link_rewrite)
    return link_rewrite[:max_length]


product_data = f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
            <product>
                <id_category_default><![CDATA[1217]]></id_category_default>
                <name>
                    <language id="1"><![CDATA[Tesla klima Inverter TA71FFLL-2432IA, A+++A++ klasa 7,3kW (3+2 god garancije do 31.10)]]></language>
                    <language id="2"><![CDATA[Tesla klima Inverter TA71FFLL-2432IA, A+++A++ klasa 7,3kW (3+2 god garancije do 31.10)]]></language>
                </name>
                <link_rewrite>
                    <language id="1"><![CDATA[tesla-klima-inverter-ta71ffll-2432ia-aa-klasa-73kw-32-god-garancije-do-3110]]></language>
                    <language id="2"><![CDATA[tesla-klima-inverter-ta71ffll-2432ia-aa-klasa-73kw-32-god-garancije-do-3110]]></language>
                </link_rewrite>
                <price><![CDATA[1195.726]]></price>
                <active><![CDATA[1]]></active>
                <quantity><![CDATA[0]]></quantity>
                <id_manufacturer><![CDATA[339]]></id_manufacturer>
            </product>
        </prestashop>
        """


def insert_product_into_prestashop():
    try:
        # Fetch PrestaShop settings
        settings = get_prestashop_settings()

        # PrestaShop product insertion URL
        prestashop_url = f"{settings['presta_url']}/products"

        # Prepare headers
        headers = {
            "Content-Type": "application/xml",
            "Authorization": f"Basic {settings['presta_key']}",
        }

        # Prepare the XML data for the product
        link_rewrite = generate_link_rewrite(product_data["name"])
        product_data = f"""
        <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
            <product>
                <id_category_default><![CDATA[{product_data['prestashop_category_id']}]]></id_category_default>
                <reference><![CDATA[{product_data['art_sifra']}]]></reference>
                <name>
                    <language id="1"><![CDATA[{product_data['name']}]]></language>
                    <language id="2"><![CDATA[{product_data['name']}]]></language>
                </name>
                <link_rewrite>
                    <language id="1"><![CDATA[{link_rewrite}]]></language>
                    <language id="2"><![CDATA[{link_rewrite}]]></language>
                </link_rewrite>
                <price><![CDATA[{product_data['vpc']}]]></price>
                <active><![CDATA[{1 if product_data['aktivan'] else 0}]]></active>
                <id_manufacturer><![CDATA[{product_data['prestashop_manufacturer_id']}]]></id_manufacturer>
                <state><![CDATA[1]]></state>
                <visibility><![CDATA[both]]></visibility>
                <available_for_order><![CDATA[1]]></available_for_order>
                <show_price><![CDATA[1]]></show_price>
                <condition><![CDATA[new]]></condition>
                <associations>
                    <categories>
                        <category>
                            <id><![CDATA[{product_data['prestashop_category_id']}]]></id>
                        </category>
                    </categories>
                </associations>
            </product>
        </prestashop>
        """

        # Make the POST request using frappe.make_post_request
        response = frappe.make_post_request(
            url=prestashop_url, headers=headers, data=data
        )

        # Check for successful response
        if response.status_code == 201:
            response_xml = ET.fromstring(response.text)
            product_id = response_xml.find(".//id").text

            # Update Frappe with the new PrestaShop product ID and status
            frappe.db.set_value(
                "Proizvodi",
                {"art_sifra": product_data["art_sifra"]},
                {"prestashop_id": product_id, "status": "on_presta"},
            )
            frappe.db.commit()

            frappe.logger().info(f"Product inserted with ID: {product_id}")
            return {"status": "success", "message": "Product inserted successfully."}
        else:
            frappe.logger().error(f"Failed to insert product: {response.text}")
            return {
                "status": "error",
                "message": f"Failed to insert product: {response.text}",
            }

    except Exception as e:
        frappe.logger().error(f"General error inserting product: {str(e)}")
        return {
            "status": "error",
            "message": f"General error inserting product: {str(e)}",
        }


def insert_products_from_json(json_file_path):
    try:
        # Load the JSON file containing the product data
        with open(json_file_path, mode="r") as file:
            products_data = json.load(file)

        # Insert each product into PrestaShop
        for product in products_data.get("products", []):
            insert_product_into_prestashop(product)

        return {"status": "success", "message": "All products inserted successfully."}

    except Exception as e:
        frappe.logger().error(f"Failed to insert products from JSON: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to insert products from JSON: {str(e)}",
        }


# import frappe
# import logging
# from prestapyt import PrestaShopWebServiceDict

# # Configure logging
# logging.basicConfig(level=logging.INFO)


# # Function to fetch ERPImtec settings
# def get_erpimtec_settings():
#     return frappe.get_single("Generalne Postavke")


# # Function to get PrestaShop client
# def get_prestashop_client(settings):
#     return PrestaShopWebServiceDict(settings.presta_url, settings.presta_key)


# # Function to get unique categories from Proizvodi
# def get_unique_categories():
#     categories = frappe.get_all("Proizvodi", fields=["grupanaziv"], distinct=True)
#     return [category["grupanaziv"] for category in categories]


# # Function to get unique manufacturers from Proizvodi
# def get_unique_manufacturers():
#     manufacturers = frappe.get_all("Proizvodi", fields=["proizvodjac"], distinct=True)
#     return [manufacturer["proizvodjac"] for manufacturer in manufacturers]


# # Function to truncate a string and add ellipsis if it exceeds the specified length
# def truncate_with_ellipsis(value, max_length=64):
#     if len(value) > max_length:
#         return value[: max_length - 3] + "..."
#     return value


# # Function to insert categories into PrestaShop
# def insert_categories_into_prestashop():
#     settings = get_erpimtec_settings()
#     prestashop = get_prestashop_client(settings)
#     categories = get_unique_categories()

#     for category in categories:
#         if category:
#             data = {
#                 "category": {
#                     "id_parent": "2",  # Adjust the parent ID as necessary
#                     "active": "1",
#                     "name": {
#                         "language": [
#                             {
#                                 "attrs": {"id": "1"},
#                                 "value": truncate_with_ellipsis(category),
#                             }
#                         ]
#                     },
#                     "link_rewrite": {
#                         "language": [
#                             {
#                                 "attrs": {"id": "1"},
#                                 "value": truncate_with_ellipsis(
#                                     category.lower().replace(" ", "-")
#                                 ),
#                             }
#                         ]
#                     },
#                 }
#             }
#             try:
#                 logging.info(f"Sending data for category: {data}")
#                 response = prestashop.add("categories", data)
#                 category_id = response["category"]["id"]

#                 # Update Frappe with PrestaShop ID
#                 frappe.db.set_value(
#                     "Proizvodi",
#                     {"grupanaziv": category},
#                     "id_presta_category",
#                     category_id,
#                 )
#                 frappe.db.commit()

#                 logging.info(f"Inserted category {category} with ID {category_id}")
#                 print(f"Inserted category {category} with ID {category_id}")
#             except Exception as e:
#                 logging.error(f"Failed to insert category {category}: {e}")


# # Function to insert manufacturers into PrestaShop
# def insert_manufacturers_into_prestashop():
#     settings = get_erpimtec_settings()
#     prestashop = get_prestashop_client(settings)
#     manufacturers = get_unique_manufacturers()

#     for manufacturer in manufacturers:
#         if manufacturer:
#             truncated_name = truncate_with_ellipsis(manufacturer)
#             data = {
#                 "manufacturer": {
#                     "name": truncated_name,
#                     "active": "1",
#                 }
#             }
#             try:
#                 logging.info(f"Sending data for manufacturer: {data}")
#                 response = prestashop.add("manufacturers", data)
#                 manufacturer_id = response["manufacturer"]["id"]

#                 # Update Frappe with PrestaShop ID
#                 frappe.db.set_value(
#                     "Proizvodi",
#                     {"proizvodjac": manufacturer},
#                     "id_presta_manufacturer",
#                     manufacturer_id,
#                 )
#                 frappe.db.commit()

#                 logging.info(
#                     f"Inserted manufacturer {truncated_name} with ID {manufacturer_id}"
#                 )
#                 print(
#                     f"Inserted manufacturer {truncated_name} with ID {manufacturer_id}"
#                 )
#             except Exception as e:
#                 logging.error(f"Failed to insert manufacturer {manufacturer}: {e}")
