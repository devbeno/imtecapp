import requests
import base64
import xml.etree.ElementTree as ET
from tqdm import tqdm
import frappe


class PrestaShopAPI:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.auth_header = {
            "Authorization": "Basic "
            + base64.b64encode(f"{self.api_key}:".encode()).decode(),
            "Content-Type": "application/xml",
        }

    def _send_request(self, method, resource, data=None):
        url = f"{self.api_url}/{resource}"
        response = requests.request(method, url, headers=self.auth_header, data=data)
        if response.status_code >= 400:
            raise Exception(f"Error {response.status_code}: {response.text}")
        return response.text

    def get_all_category_ids(self):
        response = self._send_request("GET", "categories")
        print(f"Categories Response: {response}")
        category_ids = []
        try:
            root = ET.fromstring(response)
            categories = root.findall(".//category")
            category_ids = [category.get("id") for category in categories]
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
        except Exception as e:
            print(f"Error parsing category IDs: {e}")
        return category_ids

    def get_all_manufacturer_ids(self):
        response = self._send_request("GET", "manufacturers")
        print(f"Manufacturers Response: {response}")
        manufacturer_ids = []
        try:
            root = ET.fromstring(response)
            manufacturers = root.findall(".//manufacturer")
            manufacturer_ids = [
                manufacturer.get("id") for manufacturer in manufacturers
            ]
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
        except Exception as e:
            print(f"Error parsing manufacturer IDs: {e}")
        return manufacturer_ids

    def get_all_supplier_ids(self):
        response = self._send_request("GET", "suppliers")
        print(f"Suppliers Response: {response}")
        supplier_ids = []
        try:
            root = ET.fromstring(response)
            suppliers = root.findall(".//supplier")
            supplier_ids = [supplier.get("id") for supplier in suppliers]
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
        except Exception as e:
            print(f"Error parsing supplier IDs: {e}")
        return supplier_ids

    def get_all_shop_ids(self):
        response = self._send_request("GET", "shops")
        print(f"Shops Response: {response}")
        shop_ids = []
        try:
            root = ET.fromstring(response)
            shops = root.findall(".//shop")
            shop_ids = [shop.get("id") for shop in shops]
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
        except Exception as e:
            print(f"Error parsing shop IDs: {e}")
        return shop_ids

    def get_all_product_ids(self):
        response = self._send_request("GET", "products")
        print(f"Products Response: {response}")
        product_ids = []
        try:
            root = ET.fromstring(response)
            products = root.findall(".//product")
            product_ids = [product.get("id") for product in products]
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
        except Exception as e:
            print(f"Error parsing product IDs: {e}")
        return product_ids

    def delete_category(self, category_id):
        return self._send_request("DELETE", f"categories/{category_id}")

    def delete_manufacturer(self, manufacturer_id):
        return self._send_request("DELETE", f"manufacturers/{manufacturer_id}")

    def delete_supplier(self, supplier_id):
        return self._send_request("DELETE", f"suppliers/{supplier_id}")

    def delete_shop(self, shop_id):
        return self._send_request("DELETE", f"shops/{shop_id}")

    def delete_product(self, product_id):
        return self._send_request("DELETE", f"products/{product_id}")


def remove_all_categories():
    print("Starting removal of all categories")
    settings = frappe.get_single("Generalne Postavke")
    api = PrestaShopAPI(settings.presta_url, settings.presta_key)

    category_ids = api.get_all_category_ids()
    print(f"All Category IDs: {category_ids}")

    if not category_ids:
        print("No categories found to delete")
        return

    protected_category_ids = {"1", "2"}  # Protect root and default categories
    category_ids = [cid for cid in category_ids if cid not in protected_category_ids]

    progress = tqdm(total=len(category_ids), desc="Deleting categories")
    for category_id in category_ids:
        api.delete_category(category_id)
        progress.update(1)
    progress.close()
    print("All eligible categories have been removed from PrestaShop")


def remove_all_manufacturers():
    print("Starting removal of all manufacturers")
    settings = frappe.get_single("Generalne Postavke")
    api = PrestaShopAPI(settings.presta_url, settings.presta_key)

    manufacturer_ids = api.get_all_manufacturer_ids()
    print(f"All Manufacturer IDs: {manufacturer_ids}")

    if not manufacturer_ids:
        print("No manufacturers found to delete")
        return

    progress = tqdm(total=len(manufacturer_ids), desc="Deleting manufacturers")
    for manufacturer_id in manufacturer_ids:
        api.delete_manufacturer(manufacturer_id)
        progress.update(1)
    progress.close()
    print("All manufacturers have been removed from PrestaShop")


def remove_all_suppliers():
    print("Starting removal of all suppliers")
    settings = frappe.get_single("Generalne Postavke")
    api = PrestaShopAPI(settings.presta_url, settings.presta_key)

    supplier_ids = api.get_all_supplier_ids()
    print(f"All Supplier IDs: {supplier_ids}")

    if not supplier_ids:
        print("No suppliers found to delete")
        return

    progress = tqdm(total=len(supplier_ids), desc="Deleting suppliers")
    for supplier_id in supplier_ids:
        api.delete_supplier(supplier_id)
        progress.update(1)
    progress.close()
    print("All suppliers have been removed from PrestaShop")


def remove_all_shops():
    print("Starting removal of all shops")
    settings = frappe.get_single("Generalne Postavke")
    api = PrestaShopAPI(settings.presta_url, settings.presta_key)

    shop_ids = api.get_all_shop_ids()
    print(f"All Shop IDs: {shop_ids}")

    if not shop_ids:
        print("No shops found to delete")
        return

    progress = tqdm(total=len(shop_ids), desc="Deleting shops")
    for shop_id in shop_ids:
        api.delete_shop(shop_id)
        progress.update(1)
    progress.close()
    print("All shops have been removed from PrestaShop")


def remove_all_products():
    print("Starting removal of all products")
    settings = frappe.get_single("Generalne Postavke")
    api = PrestaShopAPI(settings.presta_url, settings.presta_key)

    product_ids = api.get_all_product_ids()
    print(f"All Product IDs: {product_ids}")

    if not product_ids:
        print("No products found to delete")
        return

    progress = tqdm(total=len(product_ids), desc="Deleting products")
    for product_id in product_ids:
        api.delete_product(product_id)
        progress.update(1)
    progress.close()
    print("All products have been removed from PrestaShop")


def run_remove_all():
    remove_all_categories()
    remove_all_manufacturers()
    remove_all_products()
    clear_prestashop_category_ids()
    return {"status": "Completed"}


@frappe.whitelist()
def clear_prestashop_category_ids():
    """Set all prestashop_category_id fields in Proizvodi to an empty string."""
    frappe.db.sql(
        """
        UPDATE `tabProizvodi`
        SET prestashop_category_id = ''
    """
    )
    frappe.db.sql(
        """
        UPDATE `tabProizvodi`
        SET prestashop_manufacturer_id = ''
    """
    )
    frappe.db.sql(
        """
        UPDATE `tabProizvodi`
        SET prestashop_id = ''
    """
    )
    frappe.db.sql(
        """
        UPDATE `tabProizvodi`
        SET status = ''
    """
    )
    frappe.db.commit()
    print("All prestashop_category_id fields have been cleared in Proizvodi.")
