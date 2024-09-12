import frappe
import logging
from prestapyt import PrestaShopWebServiceDict

# Configure logging
logging.basicConfig(level=logging.INFO)


# Function to fetch ERPImtec settings
def get_erpimtec_settings():
    return frappe.get_single("Generalne Postavke")


# Function to get PrestaShop client
def get_prestashop_client(settings):
    return PrestaShopWebServiceDict(settings.presta_url, settings.presta_key)


# Function to get unique categories from Proizvodi
def get_unique_categories():
    categories = frappe.get_all("Proizvodi", fields=["grupanaziv"], distinct=True)
    return [category["grupanaziv"] for category in categories]


# Function to get unique manufacturers from Proizvodi
def get_unique_manufacturers():
    manufacturers = frappe.get_all("Proizvodi", fields=["proizvodjac"], distinct=True)
    return [manufacturer["proizvodjac"] for manufacturer in manufacturers]


# Function to truncate a string and add ellipsis if it exceeds the specified length
def truncate_with_ellipsis(value, max_length=64):
    if len(value) > max_length:
        return value[: max_length - 3] + "..."
    return value


# Function to insert categories into PrestaShop
def insert_categories_into_prestashop():
    settings = get_erpimtec_settings()
    prestashop = get_prestashop_client(settings)
    categories = get_unique_categories()

    for category in categories:
        if category:
            data = {
                "category": {
                    "id_parent": "2",  # Adjust the parent ID as necessary
                    "active": "1",
                    "name": {
                        "language": [
                            {
                                "attrs": {"id": "1"},
                                "value": truncate_with_ellipsis(category),
                            }
                        ]
                    },
                    "link_rewrite": {
                        "language": [
                            {
                                "attrs": {"id": "1"},
                                "value": truncate_with_ellipsis(
                                    category.lower().replace(" ", "-")
                                ),
                            }
                        ]
                    },
                }
            }
            try:
                logging.info(f"Sending data for category: {data}")
                response = prestashop.add("categories", data)
                category_id = response["category"]["id"]

                # Update Frappe with PrestaShop ID
                frappe.db.set_value(
                    "Proizvodi",
                    {"grupanaziv": category},
                    "id_presta_category",
                    category_id,
                )
                frappe.db.commit()

                logging.info(f"Inserted category {category} with ID {category_id}")
                print(f"Inserted category {category} with ID {category_id}")
            except Exception as e:
                logging.error(f"Failed to insert category {category}: {e}")


# Function to insert manufacturers into PrestaShop
def insert_manufacturers_into_prestashop():
    settings = get_erpimtec_settings()
    prestashop = get_prestashop_client(settings)
    manufacturers = get_unique_manufacturers()

    for manufacturer in manufacturers:
        if manufacturer:
            truncated_name = truncate_with_ellipsis(manufacturer)
            data = {
                "manufacturer": {
                    "name": truncated_name,
                    "active": "1",
                }
            }
            try:
                logging.info(f"Sending data for manufacturer: {data}")
                response = prestashop.add("manufacturers", data)
                manufacturer_id = response["manufacturer"]["id"]

                # Update Frappe with PrestaShop ID
                frappe.db.set_value(
                    "Proizvodi",
                    {"proizvodjac": manufacturer},
                    "id_presta_manufacturer",
                    manufacturer_id,
                )
                frappe.db.commit()

                logging.info(
                    f"Inserted manufacturer {truncated_name} with ID {manufacturer_id}"
                )
                print(
                    f"Inserted manufacturer {truncated_name} with ID {manufacturer_id}"
                )
            except Exception as e:
                logging.error(f"Failed to insert manufacturer {manufacturer}: {e}")
