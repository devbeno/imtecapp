import frappe
import json
import os
from prestapyt import PrestaShopWebServiceDict


def get_prestashop_settings():
    """Retrieve PrestaShop API settings from the Frappe database."""
    settings = frappe.get_single("Generalne Postavke")
    return {
        "presta_url": settings.presta_url.rstrip("/"),
        "presta_key": settings.presta_key,
    }


def sync_prestashop_from_json():
    """Sync products and stocks with PrestaShop using JSON data."""
    directory_path = frappe.get_module_path("imtecapp", "data")
    presta_products_path = os.path.join(directory_path, "presta_products.json")

    # Load JSON data from file
    with open(presta_products_path, "r") as f:
        json_data = json.load(f)

    # Proceed with syncing using the loaded JSON data
    sync_products_and_stocks_from_json(json_data)


def sync_products_and_stocks_from_json(json_data):
    """Sync products and stocks using JSON data."""
    settings = get_prestashop_settings()
    prestashop = PrestaShopWebServiceDict(
        settings["presta_url"], settings["presta_key"]
    )

    products = json_data.get("products", [])
    stocks = json_data.get("stocks", [])

    # Process products
    for product in products:
        process_product(prestashop, product)

    # Process stocks
    for stock in stocks:
        process_stock(prestashop, stock)


def process_product(prestashop, product):
    """Process individual product from JSON."""
    try:
        product_code = product["art_sifra"]
        product_name = product["name"]
        category_id = product["prestashop_cat_id"]
        manufacturer_id = product["prestashop_man_id"]
        price = product.get("vpc", 0)
        active = product.get("aktivan", 1)
        stock = product.get("stanje", 0)
        status = product["status"]

        if status == "for_insert":
            # Insert new product
            prestashop_pro_id = create_prestashop_product(prestashop, product)
            if prestashop_pro_id:
                update_frappe_with_prestashop_id(product_code, prestashop_pro_id)
        elif status == "for_update":
            # Update existing product
            existing_product = get_prestashop_product_by_reference(
                prestashop, product_code
            )
            if existing_product:
                prestashop_pro_id = existing_product["id"]
                update_prestashop_product(prestashop, prestashop_pro_id, product)

    except Exception as e:
        frappe.logger().error(f"Error processing product {product_code}: {str(e)}")
        print(f"Error processing product {product_code}: {str(e)}")


def process_stock(prestashop, stock):
    """Process individual stock from JSON."""
    try:
        product_code = stock["art_sifra"]
        quantity = stock["stanje"]
        status = stock["status"]

        if status == "for_stock":
            existing_product = get_prestashop_product_by_reference(
                prestashop, product_code
            )
            if existing_product:
                stock_id = existing_product["associations"]["stock_availables"][
                    "stock_available"
                ]["id"]
                update_prestashop_stock(prestashop, stock_id, quantity)

    except Exception as e:
        frappe.logger().error(
            f"Error processing stock for product {product_code}: {str(e)}"
        )
        print(f"Error processing stock for product {product_code}: {str(e)}")


def update_frappe_with_prestashop_id(product_code, prestashop_pro_id):
    """Update Frappe database with the PrestaShop product ID."""
    try:
        frappe.db.sql(
            """
            UPDATE `tabProizvodi`
            SET prestashop_pro_id = %s
            WHERE art_sifra = %s
            """,
            (prestashop_pro_id, product_code),
        )
        frappe.db.commit()
        print(f"Updated Frappe with PrestaShop product ID for {product_code}")
    except Exception as e:
        frappe.logger().error(
            f"Error updating Frappe for product {product_code}: {str(e)}"
        )
        print(f"Error updating Frappe for product {product_code}: {str(e)}")


def get_prestashop_product_by_reference(prestashop, reference):
    """Check if a product exists in PrestaShop by reference."""
    try:
        products = prestashop.get(
            "products", options={"filter[reference]": reference, "display": "full"}
        )
        if products and "products" in products:
            return products["products"][0]
        return None
    except Exception as e:
        frappe.logger().error(
            f"Error fetching product by reference from PrestaShop: {str(e)}"
        )
        return None


def create_prestashop_product(prestashop, product):
    """Create a new product in PrestaShop and return the ID."""
    try:
        new_product = {
            "product": {
                "name": {"language": {"attrs": {"id": "2"}, "value": product["name"]}},
                "price": product.get("vpc", 0),
                "id_category_default": product["prestashop_cat_id"],
                "id_manufacturer": product["prestashop_man_id"],
                "active": product.get("aktivan", 1),
                "reference": product["art_sifra"],
                "associations": {
                    "categories": {"category": [{"id": product["prestashop_cat_id"]}]}
                },
            }
        }
        response = prestashop.add("products", new_product)
        prestashop_id = response["prestashop"]["product"]["id"]
        return prestashop_id
    except Exception as e:
        frappe.logger().error(f"Error creating product in PrestaShop: {str(e)}")
        return None


def update_prestashop_product(prestashop, product_id, product):
    """Update an existing product in PrestaShop."""
    try:
        updated_product = {
            "product": {
                "id": product_id,
                "name": {"language": {"attrs": {"id": "2"}, "value": product["name"]}},
                "price": product.get("vpc", 0),
                "id_category_default": product["prestashop_cat_id"],
                "id_manufacturer": product["prestashop_man_id"],
                "active": product.get("aktivan", 1),
                "reference": product["art_sifra"],
                "associations": {
                    "categories": {"category": [{"id": product["prestashop_cat_id"]}]}
                },
            }
        }
        response = prestashop.edit("products", product_id, updated_product)
        print(f"Updated product: {product['name']} with ID {product_id}")
        return response
    except Exception as e:
        frappe.logger().error(f"Error updating product in PrestaShop: {str(e)}")
        return None


def update_prestashop_stock(prestashop, stock_id, quantity):
    """Update the stock quantity for a given stock ID in PrestaShop."""
    try:
        stock_data = {
            "stock_available": {
                "id": stock_id,
                "quantity": quantity,
            }
        }
        response = prestashop.edit("stock_availables", stock_id, stock_data)
        print(f"Updated stock for stock ID {stock_id} to {quantity}")
        return response
    except Exception as e:
        frappe.logger().error(f"Error updating stock in PrestaShop: {str(e)}")
        return None


# Example usage:
sync_prestashop_from_json()
