import frappe
import json
import requests
import base64
import xml.etree.ElementTree as ET


def get_prestashop_settings():
    """Retrieve PrestaShop API settings from the Frappe database."""
    settings = frappe.get_single("Generalne Postavke")
    return {
        "presta_url": settings.presta_url.rstrip("/"),  # Ensure no trailing slash
        "presta_key": settings.presta_key,
    }


def generate_link_rewrite(product_name):
    """Generate a link_rewrite slug based on the product name."""
    return product_name.lower().replace(" ", "-")


def get_prestashop_resource(
    resource_type, filters=None, display="full", output_format="JSON"
):
    """Generalized function to retrieve resources from PrestaShop API."""
    try:
        settings = get_prestashop_settings()
        prestashop_url = f"{settings['presta_url']}/{resource_type}"

        params = {
            "display": display,
            "ws_key": settings["presta_key"],
            "output_format": output_format,
        }

        if filters:
            for key, value in filters.items():
                params[f"filter[{key}]"] = value

        response = requests.get(prestashop_url, params=params)
        return response.json()

    except Exception as e:
        frappe.logger().error(
            f"Error fetching {resource_type} from PrestaShop: {str(e)}"
        )
        return None


def insert_product_into_prestashop(product_data, settings):
    """Insert a new product into PrestaShop."""
    try:
        link_rewrite = generate_link_rewrite(product_data["name"])

        data = f"""
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
                <condition><![CDATA[new]]></condition>
            </product>
        </prestashop>
        """

        headers = {
            "Content-Type": "application/xml",
            "Authorization": f"Basic {base64.b64encode(settings['presta_key'].encode()).decode()}",
        }

        prestashop_url = f"{settings['presta_url']}/products"
        response = requests.post(prestashop_url, data=data, headers=headers)

        if response.status_code == 201:
            response_xml = ET.fromstring(response.content)
            prestashop_product_id = response_xml.find(".//id").text
            return {
                "status": "success",
                "message": "Product inserted successfully.",
                "prestashop_product_id": prestashop_product_id,
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to insert product. HTTP {response.status_code}: {response.content.decode('utf-8')}",
            }

    except Exception as e:
        frappe.logger().error(f"Error inserting product: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to insert product {product_data['name']}: {str(e)}",
        }


def update_stock_quantity(stock_id, quantity, settings):
    """Update the stock quantity for a given stock ID."""
    try:
        data = f"""
        <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
            <stock_available>
                <id><![CDATA[{stock_id}]]></id>
                <quantity><![CDATA[{quantity}]]></quantity>
            </stock_available>
        </prestashop>
        """

        prestashop_url = f"{settings['presta_url']}/stock_availables/{stock_id}"
        headers = {
            "Content-Type": "application/xml",
            "Authorization": f"Basic {base64.b64encode(settings['presta_key'].encode()).decode()}",
        }

        response = requests.patch(prestashop_url, data=data, headers=headers)
        if response.status_code in [200, 204]:
            return {
                "status": "success",
                "message": f"Stock quantity updated successfully for Stock ID {stock_id}.",
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to update stock for Stock ID {stock_id}. HTTP {response.status_code}: {response.content.decode('utf-8')}",
            }

    except Exception as e:
        frappe.logger().error(f"Error updating stock quantity: {str(e)}")
        return {
            "status": "error",
            "message": f"Error updating stock quantity for Stock ID {stock_id}: {str(e)}",
        }


def sync_data(json_file_path):
    """Sync product data and stock information from a JSON file with PrestaShop."""
    try:
        with open(json_file_path, "r") as json_file:
            data = json.load(json_file)

        products = data.get("products", [])
        stocks = data.get("stocks", [])
        settings = get_prestashop_settings()

        # Handle Products
        for product in products:
            product_reference = product.get("art_sifra")
            status = product.get("status")

            if status == "for_insert":
                existing_product = get_prestashop_resource(
                    "products", filters={"reference": product_reference}
                )
                if (
                    existing_product
                    and "products" in existing_product
                    and len(existing_product["products"]) > 0
                ):
                    print(
                        f"Product with reference {product_reference} already exists. Skipping insertion."
                    )
                else:
                    result = insert_product_into_prestashop(product, settings)
                    print(result["message"])

            elif status == "for_update":
                existing_product = get_prestashop_resource(
                    "products", filters={"reference": product_reference}
                )
                if (
                    existing_product
                    and "products" in existing_product
                    and len(existing_product["products"]) > 0
                ):
                    # Implement update logic if needed
                    print(f"Update logic can be implemented for {product_reference}")
                else:
                    print(
                        f"Product with reference {product_reference} does not exist for update. Consider inserting it."
                    )

            elif status == "on_presta":
                print(
                    f"Product with reference {product_reference} is already on PrestaShop. No action needed."
                )

        # Handle Stocks
        for stock in stocks:
            product_reference = stock.get("art_sifra")
            status = stock.get("status")

            if status == "for_stock":
                existing_product = get_prestashop_resource(
                    "products", filters={"reference": product_reference}
                )
                if (
                    existing_product
                    and "products" in existing_product
                    and len(existing_product["products"]) > 0
                ):
                    stock_associations = (
                        existing_product["products"][0]
                        .get("associations", {})
                        .get("stock_availables", [])
                    )
                    if (
                        stock_associations
                        and isinstance(stock_associations, list)
                        and len(stock_associations) > 0
                    ):
                        stock_id = stock_associations[0]["id"]
                        result = update_stock_quantity(
                            stock_id, stock["stanje"], settings
                        )
                        print(result["message"])
                    else:
                        print(
                            f"No stock associated with product {product_reference}. Cannot update stock."
                        )
                else:
                    print(
                        f"Product with reference {product_reference} not found for stock update."
                    )
            else:
                print(
                    f"Skipping stock update for product {product_reference} with status {status}."
                )

        return {"status": "success", "message": "Data synced successfully."}

    except Exception as e:
        frappe.logger().error(f"Error syncing data: {str(e)}")
        return {"status": "error", "message": f"Failed to sync data: {str(e)}"}


# import frappe
# import json
# import re
# from frappe.integrations.utils import make_post_request, make_get_request
# import xml.etree.ElementTree as ET
# import base64


# def get_prestashop_settings():
#     """Retrieve PrestaShop API settings from the Frappe database."""
#     settings = frappe.get_single("Generalne Postavke")
#     api_key = settings.presta_key
#     base64_api_key = base64.b64encode(api_key.encode()).decode()
#     return {
#         "presta_url": settings.presta_url,
#         "presta_key": base64_api_key,
#     }


# def generate_link_rewrite(name, max_length=128):
#     """Generate a URL-friendly version of the product name."""
#     name = re.sub(r"[<>;=#{}]", "", name)
#     link_rewrite = re.sub(r"\s+", "-", name.lower())
#     link_rewrite = re.sub(r"[^\w-]", "", link_rewrite)
#     return link_rewrite[:max_length]


# def get_product_by_reference(reference, settings):
#     """Retrieve a product by its reference code from PrestaShop."""
#     try:
#         prestashop_url = f"{settings['presta_url']}/products"
#         params = {
#             "filter[reference]": reference,
#             "display": "full",
#             "ws_key": settings["presta_key"],
#             "output_format": "JSON",
#         }
#         response = make_get_request(prestashop_url, params=params)

#         # Check if response is a string, indicating an unexpected result
#         if isinstance(response, str):
#             frappe.logger().error(
#                 f"Unexpected response while fetching product by reference: {response}"
#             )
#             return None

#         product_data = response.get("products", [])
#         if product_data:
#             return product_data[0]  # Return the first (and likely only) product match
#         return None
#     except Exception as e:
#         frappe.logger().error(f"Error fetching product by reference: {str(e)}")
#         return None


# def update_stock_quantity(stock_id, quantity, settings):
#     """Update the stock quantity for a given stock ID."""
#     try:
#         data = f"""
#         <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
#             <stock_available>
#                 <id><![CDATA[{stock_id}]]></id>
#                 <quantity><![CDATA[{quantity}]]></quantity>
#             </stock_available>
#         </prestashop>
#         """

#         prestashop_url = f"{settings['presta_url']}/stock_availables/{stock_id}"
#         headers = {
#             "Content-Type": "application/xml",
#             "Authorization": f"Basic {settings['presta_key']}",
#         }

#         response = make_post_request(
#             url=prestashop_url, data=data, headers=headers, method="PATCH"
#         )

#         # Check if response is a string, indicating an unexpected result
#         if isinstance(response, str):
#             frappe.logger().error(
#                 f"Unexpected response while updating stock: {response}"
#             )
#             return None

#         return response
#     except Exception as e:
#         frappe.logger().error(f"Error updating stock quantity: {str(e)}")
#         return None


# def insert_product_into_prestashop(product_data, settings):
#     """Insert a new product into PrestaShop."""
#     try:
#         link_rewrite = generate_link_rewrite(product_data["name"])

#         # Construct the XML data
#         data = f"""
#         <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
#             <product>
#                 <id_category_default><![CDATA[{product_data['prestashop_category_id']}]]></id_category_default>
#                 <reference><![CDATA[{product_data['art_sifra']}]]></reference>
#                 <name>
#                     <language id="1"><![CDATA[{product_data['name']}]]></language>
#                 </name>
#                 <link_rewrite>
#                     <language id="1"><![CDATA[{link_rewrite}]]></language>
#                 </link_rewrite>
#                 <price><![CDATA[{product_data['vpc']}]]></price>
#                 <active><![CDATA[{1 if product_data['aktivan'] else 0}]]></active>
#                 <condition><![CDATA[new]]></condition>
#             </product>
#         </prestashop>
#         """

#         headers = {
#             "Content-Type": "application/xml",
#             "Authorization": f"Basic {settings['presta_key']}",
#         }

#         prestashop_url = f"{settings['presta_url']}/products"
#         response = make_post_request(url=prestashop_url, data=data, headers=headers)

#         # Extract the XML content from the response
#         xml_start = response.find("<?xml")
#         if xml_start != -1:
#             response_xml = response[xml_start:]
#             try:
#                 parsed_response = ET.fromstring(response_xml)
#                 prestashop_product_id = parsed_response.find(".//id").text
#                 return {
#                     "status": "success",
#                     "message": "Product inserted successfully.",
#                     "prestashop_product_id": prestashop_product_id,
#                     "stock_id": None,
#                 }
#             except ET.ParseError as parse_error:
#                 frappe.logger().error(f"XML Parsing Error: {str(parse_error)}")
#                 return {
#                     "status": "error",
#                     "message": f"Failed to insert product {product_data['name']}: XML parsing error: {str(parse_error)}",
#                     "prestashop_product_id": None,
#                     "stock_id": None,
#                 }
#         else:
#             frappe.logger().error("Failed to find XML content in the response")
#             return {
#                 "status": "error",
#                 "message": "Failed to find XML content in the response",
#                 "prestashop_product_id": None,
#                 "stock_id": None,
#             }

#     except Exception as e:
#         frappe.logger().error(f"Error: {str(e)}")
#         return {
#             "status": "error",
#             "message": f"Failed to insert product {product_data['name']}: {str(e)}",
#             "prestashop_product_id": None,
#             "stock_id": None,
#         }


# def sync_data(json_file_path):
#     """Sync product data from a JSON file with PrestaShop."""
#     try:
#         with open(json_file_path, "r") as json_file:
#             products_data = json.load(json_file)

#         if not products_data:
#             frappe.logger().info("No products found in the JSON file.")
#             return {"status": "error", "message": "No products found in the JSON file."}

#         settings = get_prestashop_settings()

#         for product in products_data:
#             product_reference = product.get("art_sifra")

#             if product.get("status") == "for_stock":
#                 existing_product = get_product_by_reference(product_reference, settings)
#                 if existing_product:
#                     stock_id = existing_product["associations"]["stock_availables"][0][
#                         "id"
#                     ]
#                     update_stock_quantity(stock_id, product["stanje"], settings)
#                     print(
#                         f"Updated stock for product {product_reference} with Stock ID {stock_id}"
#                     )
#                 else:
#                     print(
#                         f"Product with reference {product_reference} not found for stock update."
#                     )
#             else:
#                 existing_product = get_product_by_reference(product_reference, settings)
#                 if existing_product:
#                     print(
#                         f"Product with reference {product_reference} already exists. Skipping insertion."
#                     )
#                 else:
#                     result = insert_product_into_prestashop(product, settings)
#                     print(f"Product: {product['name']}")
#                     print(f"PrestaShop Product ID: {result['prestashop_product_id']}")
#                     print(f"Stock ID: {result['stock_id']}")
#                     print(f"Status: {result['status']}")
#                     print(f"Message: {result['message']}")
#                     print("-" * 40)

#         return {"status": "success", "message": "Data synced successfully."}

#     except Exception as e:
#         frappe.logger().error(f"Error syncing data: {str(e)}")
#         return {"status": "error", "message": f"Failed to sync data: {str(e)}"}
