import aiohttp
import asyncio
import base64
import xml.etree.ElementTree as ET
from tqdm import tqdm
import frappe

api_url = "APXHV1BE9ZISZQMDFEYVE6HKXPXJIGBH"
api_url = "http://test2.imtec.ba/api"


class PrestaShopAPI:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.auth_header = {
            "Authorization": "Basic "
            + base64.b64encode(f"{self.api_key}:".encode()).decode(),
            "Content-Type": "application/xml",
        }

    def _send_request(self, session, method, resource, data=None):
        url = f"{self.api_url}/{resource}"
        with session.request(
            method, url, headers=self.auth_header, data=data
        ) as response:
            if response.status >= 400:

    def create_product(self, session, product_data):
        return await self._send_request(session, "POST", "products", product_data)

    def update_product(self, session, product_id, product_data):
        return await self._send_request(
            session, "PUT", f"products/{product_id}", product_data
        )

    def get_product(self, session, product_id):
        return await self._send_request(session, "GET", f"products/{product_id}")

    def get_all_product_ids(self, session):
        response = await self._send_request(session, "GET", "products")
        product_ids = []
        try:
            root = ET.fromstring(response)
            products = root.findall(".//product")
            if products:
                product_ids = [
                    product.find("id").text
                    for product in products
                    if product.find("id") is not None
                ]
            else:
                print("No products found in the XML response.")
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
        except Exception as e:
            print(f"Error parsing product IDs: {e}")
        return product_ids

    def get_all_category_ids(self, session):
        response = await self._send_request(session, "GET", "categories")
        print("Categories Response:", response)  # Add this line
        category_ids = []
        try:
            root = ET.fromstring(response)
            categories = root.findall(".//category")
            if categories:
                category_ids = [
                    category.find("id").text
                    for category in categories
                    if category.find("id") is not None
                ]
            else:
                print("No categories found in the XML response.")
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
        except Exception as e:
            print(f"Error parsing category IDs: {e}")
        return category_ids

    def get_all_manufacturer_ids(self, session):
        response = await self._send_request(session, "GET", "manufacturers")
        manufacturer_ids = []
        try:
            root = ET.fromstring(response)
            manufacturers = root.findall(".//manufacturer")
            if manufacturers:
                manufacturer_ids = [
                    manufacturer.find("id").text
                    for manufacturer in manufacturers
                    if manufacturer.find("id") is not None
                ]
            else:
                print("No manufacturers found in the XML response.")
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
        except Exception as e:
            print(f"Error parsing manufacturer IDs: {e}")
        return manufacturer_ids

    def delete_product(self, session, product_id):
        return await self._send_request(session, "DELETE", f"products/{product_id}")

    def delete_category(self, session, category_id):
        return await self._send_request(session, "DELETE", f"categories/{category_id}")

    def delete_manufacturer(self, session, manufacturer_id):
        return await self._send_request(
            session, "DELETE", f"manufacturers/{manufacturer_id}"
        )


def remove_all_categories():
    print("Starting removal of all categories")
    settings = frappe.get_single("Generalne Postavke")
    api = PrestaShopAPI(settings.presta_url, settings.presta_key)

    with aiohttp.ClientSession() as session:
        category_ids = await api.get_all_category_ids(session)
        print(f"All Category IDs: {category_ids}")  # Log all category IDs

        if not category_ids:
            print("No categories found to delete")
            return

        # Protected categories (root and default)
        protected_category_ids = {"1", "2"}
        category_ids = [
            cid for cid in category_ids if cid not in protected_category_ids
        ]

        if not category_ids:
            print("No categories found to delete after excluding protected ones")
            return

        progress = tqdm(total=len(category_ids), desc="Deleting categories")
        delete_tasks = [
            api.delete_category(session, category_id) for category_id in category_ids
        ]
        responses = await asyncio.gather(*delete_tasks)

        for response in responses:
            progress.update(1)
        progress.close()
        print("All eligible categories have been removed from PrestaShop")


def remove_all_categories():
    print("Starting removal of all categories")
    settings = frappe.get_single("Generalne Postavke")
    api = PrestaShopAPI(settings.presta_url, settings.presta_key)

    with aiohttp.ClientSession() as session:
        category_ids = await api.get_all_category_ids(session)
        if not category_ids:
            print("No categories found to delete")
            return

        # Protecting root categories and default categories
        protected_category_ids = {"1", "2"}  # Update with the correct IDs if necessary
        category_ids = [
            cid for cid in category_ids if cid not in protected_category_ids
        ]

        progress = tqdm(total=len(category_ids), desc="Deleting categories")
        delete_tasks = [
            api.delete_category(session, category_id) for category_id in category_ids
        ]
        responses = await asyncio.gather(*delete_tasks)

        for response in responses:
            progress.update(1)
        progress.close()
        print("All non-protected categories have been removed from PrestaShop")


def remove_all_manufacturers():
    print("Starting removal of all manufacturers")
    settings = frappe.get_single("Generalne Postavke")
    api = PrestaShopAPI(settings.presta_url, settings.presta_key)

    with aiohttp.ClientSession() as session:
        manufacturer_ids = await api.get_all_manufacturer_ids(session)
        if not manufacturer_ids:
            print("No manufacturers found to delete")
            return

        progress = tqdm(total=len(manufacturer_ids), desc="Deleting manufacturers")
        delete_tasks = [
            api.delete_manufacturer(session, manufacturer_id)
            for manufacturer_id in manufacturer_ids
        ]
        responses = await asyncio.gather(*delete_tasks)

        for response in responses:
            progress.update(1)
        progress.close()
        print("All manufacturers have been removed from PrestaShop")


def clear_proizvodi_fields():
    frappe.db.sql(
        """
        UPDATE `tabProizvodi`
        SET id_presta_manufacturer = NULL,
            id_presta_category = NULL,
            presta_stock_id = NULL,
            presta_product_id = NULL
    """
    )
    frappe.db.commit()
    print("Cleared fields in Proizvodi")


def run_remove_all():
    remove_all_categories()
    remove_all_manufacturers()
    # remove_all_products()
    # clear_proizvodi_fields()
    return {"status": "Completed"}



