from imtecapp.req_utils import (
    make_get_request,
    make_post_request,
    make_patch_request,
    create_request_log,
)

import frappe
import json
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

        response = make_get_request(prestashop_url, params=params)
        return response

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
        response = make_post_request(prestashop_url, data=data, headers=headers)

        if response.status_code == 201:
            response_xml = ET.fromstring(response)
            prestashop_product_id = response_xml.find(".//id").text
            return {
                "status": "success",
                "message": "Product inserted successfully.",
                "prestashop_product_id": prestashop_product_id,
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to insert product. HTTP {response.status_code}: {response}",
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

        response = make_patch_request(prestashop_url, data=data, headers=headers)
        if response.status_code in [200, 204]:
            return {
                "status": "success",
                "message": f"Stock quantity updated successfully for Stock ID {stock_id}.",
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to update stock for Stock ID {stock_id}. HTTP {response.status_code}: {response}",
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
