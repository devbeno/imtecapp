from frappe.model.document import Document
import frappe
from prestapyt import PrestaShopWebServiceDict, PrestaShopWebServiceError


def get_prestashop_client():
    config = get_prestashop_config()
    return PrestaShopWebServiceDict(f"{config.presta_url}", config.presta_key)


class PSProizvodi(Document):
    pass


def get_prestashop_config():
    return frappe.get_single("Generalne Postavke")


def get_prestashop_items():
    prestashop = get_prestashop_client()
    try:
        return prestashop.get('products')
    except PrestaShopWebServiceError as e:
        frappe.log_error(f"Failed to fetch products: {str(e)}", "PrestaShop API Error")
        return None


def post_prestashop_item(data):
    prestashop = get_prestashop_client()
    try:
        return prestashop.add('products', data)
    except PrestaShopWebServiceError as e:
        frappe.log_error(f"Failed to create product: {str(e)}", "PrestaShop API Error")
        return None


def put_prestashop_item(item_id, data):
    prestashop = get_prestashop_client()
    try:
        return prestashop.edit(f'products/{item_id}', data)
    except PrestaShopWebServiceError as e:
        frappe.log_error(f"Failed to update product: {str(e)}", "PrestaShop API Error")
        return None


def category_exists_in_prestashop(category_name):
    prestashop = get_prestashop_client()
    try:
        categories = prestashop.get('categories', options={'filter[name]': category_name})
        return bool(categories['categories']['category'])
    except PrestaShopWebServiceError as e:
        frappe.log_error(f"Failed to check category existence: {str(e)}", "PrestaShop API Error")
        return False


def manufacturer_exists_in_prestashop(manufacturer_name):
    prestashop = get_prestashop_client()
    try:
        manufacturers = prestashop.get('manufacturers', options={'filter[name]': manufacturer_name})
        return bool(manufacturers['manufacturers']['manufacturer'])
    except PrestaShopWebServiceError as e:
        frappe.log_error(f"Failed to check manufacturer existence: {str(e)}", "PrestaShop API Error")
        return False


def product_exists_in_prestashop(product_reference):
    prestashop = get_prestashop_client()
    try:
        products = prestashop.get('products', options={'filter[reference]': product_reference})
        return bool(products['products']['product'])
    except PrestaShopWebServiceError as e:
        frappe.log_error(f"Failed to check product existence: {str(e)}", "PrestaShop API Error")
        return False


def get_unique_categories():
    categories = frappe.get_all("Proizvodi", fields=["grupanaziv"], distinct=True)
    return [category["grupanaziv"] for category in categories]


def get_unique_manufacturers():
    manufacturers = frappe.get_all("Proizvodi", fields=["proizvodjac"], distinct=True)
    return [manufacturer["proizvodjac"] for manufacturer in manufacturers]


def sync_categories_to_prestashop():
    categories = get_unique_categories()
    prestashop = get_prestashop_client()

    for category in categories:
        category_name = truncate_with_ellipsis(category, 64)
        link_rewrite = category_name.lower().replace(" ", "-")

        category_data = {
            'category': {
                'id_parent': '2',
                'active': '1',
                'name': {'language': {'@id': '1', '#text': category_name}},
                'link_rewrite': {'language': {'@id': '1', '#text': link_rewrite}}
            }
        }

        if category_exists_in_prestashop(category_name):
            frappe.log_error(f"Category already exists: {category_name}", "Sync Info")
            continue

        try:
            response = prestashop.add('categories', category_data)
            frappe.db.sql(
                """
                UPDATE `tabPS Proizvodi`
                SET presta_category_id = %s
                WHERE category = %s
                """,
                (response['category']['id'], category),
            )
        except PrestaShopWebServiceError as e:
            frappe.log_error(f"Failed to create category: {str(e)}", "Category Sync Error")

    frappe.db.commit()


def sync_manufacturers_to_prestashop():
    manufacturers = get_unique_manufacturers()
    prestashop = get_prestashop_client()

    for manufacturer in manufacturers:
        manufacturer_name = truncate_with_ellipsis(manufacturer, 64)

        if manufacturer_exists_in_prestashop(manufacturer_name):
            frappe.log_error(f"Manufacturer already exists: {manufacturer_name}", "Sync Info")
            continue

        manufacturer_data = {
            "manufacturer": {
                "name": manufacturer_name,
                "link_rewrite": manufacturer_name.lower().replace(" ", "-"),
            }
        }
        try:
            response = prestashop.add('manufacturers', manufacturer_data)
            frappe.db.sql(
                """
                UPDATE `tabPS Proizvodi`
                SET presta_manufacturer_id = %s
                WHERE manufacturer = %s
                """,
                (response['manufacturer']['id'], manufacturer),
            )
        except PrestaShopWebServiceError as e:
            frappe.log_error(f"Failed to create manufacturer: {str(e)}", "Manufacturer Sync Error")

    frappe.db.commit()


def sync_products_to_prestashop():
    products = frappe.get_all(
        "PS Proizvodi",
        filters={"active": 1},
        fields=[
            "name",
            "reference",
            "price",
            "quantity",
            "presta_category_id",
            "presta_manufacturer_id",
            "presta_product_id",
            "active",
        ],
    )
    prestashop = get_prestashop_client()

    for product in products:
        art_naziv = frappe.db.get_value(
            "Proizvodi", {"art_sifra": product["reference"]}, "art_naziv"
        )

        if not art_naziv:
            log_error_with_truncation(
                f"Product name not found for reference: {product['reference']}",
                "Sync Error",
            )
            continue

        if not product.get("presta_category_id"):
            log_error_with_truncation(
                f"Skipping product {product['reference']} due to missing category",
                "Sync Error",
            )
            continue

        if not product.get("presta_manufacturer_id"):
            log_error_with_truncation(
                f"Skipping product {product['reference']} due to missing manufacturer",
                "Sync Error",
            )
            continue

        if product_exists_in_prestashop(product["reference"]):
            frappe.log_error(f"Product already exists: {product['reference']}", "Sync Info")
            continue

        if product.get("presta_product_id"):
            update_prestashop_product(product, art_naziv)
        else:
            create_prestashop_product(product, art_naziv)


def create_prestashop_product(product, art_naziv):
    product_data = {
        "product": {
            "name": art_naziv,
            "price": product.get("price", 0.0),
            "quantity": product.get("quantity", 0),
            "active": product.get("active", 1),
            "id_category_default": product.get("presta_category_id"),
            "id_manufacturer": product.get("presta_manufacturer_id"),
        }
    }
    prestashop = get_prestashop_client()
    try:
        response = prestashop.add('products', product_data)
        frappe.db.set_value(
            "PS Proizvodi", product["name"], "presta_product_id", response['product']['id']
        )
        frappe.db.commit()
    except PrestaShopWebServiceError as e:
        frappe.log_error(f"Failed to create product: {product.get('reference')}", "Sync Error")


def update_prestashop_product(product, art_naziv):
    product_data = {
        "product": {
            "name": art_naziv,
            "price": product["price"],
            "quantity": product["quantity"],
            "active": product["active"],
        }
    }
    prestashop = get_prestashop_client()
    try:
        prestashop.edit(f'products/{product["presta_product_id"]}', product_data)
    except PrestaShopWebServiceError as e:
        frappe.log_error(f"Failed to update product: {product['reference']}", "Sync Error")


def log_error_with_truncation(message, error_type="Sync Error"):
    max_length = 140
    if len(message) > max_length:
        chunks = [
            message[i:i + max_length] for i in range(0, len(message), max_length)
        ]
        for chunk in chunks:
            frappe.log_error(chunk, error_type)
    else:
        frappe.log_error(message, error_type)


def truncate_with_ellipsis(value, max_length=64):
    if len(value) > max_length:
        return value[:max_length - 3] + "..."
    return value


@frappe.whitelist()
def sync_all_to_prestashop():
    try:
        config = get_prestashop_config()
        if config.first_time_insert:
            sync_categories_to_prestashop()
            sync_manufacturers_to_prestashop()
            frappe.db.set_value("Generalne Postavke", None, "first_time_insert", 0)
            frappe.db.commit()

        sync_products_to_prestashop()
        frappe.log_error(
            "Sync from PS Proizvodi to PrestaShop completed successfully.",
            "Sync Success",
        )
    except Exception as e:
        frappe.log_error(f"Error during sync: {str(e)}", "Sync Error")


@frappe.whitelist()
def sync_cat():
    sync_categories_to_prestashop()


@frappe.whitelist()
def sync_man():
    sync_manufacturers_to_prestashop()
