import frappe
import json
import os


def generate_prestashop_json():
    """Generate JSON data for products and stocks."""
    # Fetch products from the Frappe database
    products = frappe.db.sql(
        """
        SELECT
            art_sifra,
            name,
            prestashop_cat_id,
            prestashop_man_id,
            vpc,
            aktivan,
            stanje
        FROM `tabProizvodi`
        WHERE prestashop_cat_id IS NOT NULL 
        AND prestashop_man_id IS NOT NULL
        AND aktivan = 1
    """,
        as_dict=True,
    )

    # Construct the JSON structure
    json_data = {"products": [], "stocks": []}

    for product in products:
        # Add each product to the products list
        json_data["products"].append(
            {
                "art_sifra": product["art_sifra"],
                "name": product["name"],
                "prestashop_cat_id": product["prestashop_cat_id"],
                "prestashop_man_id": product["prestashop_man_id"],
                "vpc": product["vpc"],
                "aktivan": product["aktivan"],
                "stanje": product["stanje"],
                "status": "for_insert",
            }
        )
        # "status": "for_insert" if product.get("stanje", 0) == 0 else "for_update"
        # Add stock information to the stocks list
        json_data["stocks"].append(
            {
                "art_sifra": product["art_sifra"],
                "stanje": product["stanje"],
                "status": "for_stock",
            }
        )

    # Define the path to save the JSON file
    directory_path = frappe.get_module_path("imtecapp", "data")
    presta_products_path = os.path.join(directory_path, "presta_products.json")

    # Save the JSON data to a file
    with open(presta_products_path, "w") as f:
        json.dump(json_data, f, indent=4)

    print(f"JSON data saved successfully to {presta_products_path}")


# Example usage:
generate_prestashop_json()
