# import requests
# import xml.etree.ElementTree as ET
# import os
# import json
# import frappe
# import json


# # Fetch Prestashop settings
# def get_prestashop_settings():
#     settings = frappe.get_single("Generalne Postavke")
#     return {
#         "presta_url": settings.presta_url,
#         "presta_key": settings.presta_key,
#     }


# def sync_all(field_name, update_function, method="PUT"):
#     try:
#         directory_path = frappe.get_module_path("imtecapp", "data")
#         json_file_path = os.path.join(directory_path, "for_insert_eline_data.json")

#         with open(json_file_path, "r") as json_file:
#             products = json.load(json_file)

#         if not products:
#             frappe.logger().info(f"No products found for syncing {field_name}.")
#             return {
#                 "status": "success",
#                 "message": f"No products to sync {field_name}.",
#             }

#         settings = get_prestashop_settings()

#         for product in products:
#             if product.get("status") in ["for_insert", "for_update"]:
#                 update_function(product, settings, method)

#         return {
#             "status": "success",
#             "message": f"{field_name.capitalize()} synced successfully.",
#         }

#     except Exception as e:
#         frappe.logger().error(f"Error syncing {field_name}: {str(e)}")
#         frappe.throw(_(f"Failed to sync {field_name}: {{0}}").format(str(e)))


# def get_prestashop_id(product):
#     if not product.get("art_sifra"):
#         frappe.logger().error(f"Product {product} is missing 'art_sifra'.")
#         return None

#     prestashop_id = frappe.db.get_value(
#         "Proizvodi", {"art_sifra": product["art_sifra"]}, "prestashop_id"
#     )

#     if not prestashop_id:
#         frappe.logger().error(
#             f"PrestaShop ID not found for product: {product['art_sifra']}."
#         )

#     return prestashop_id


# def send_prestashop_request(url, data, field_name, art_sifra, settings, method):
#     headers = {
#         "Content-Type": "application/xml",
#         "Authorization": f"Basic {settings['presta_key']}",
#     }

#     try:
#         frappe.logger().info(
#             f"Sending {method} request for {field_name} update: {art_sifra}"
#         )
#         frappe.logger().debug(f"Data: {data}")

#         if method == "PATCH":
#             response = requests.patch(url, data=data, headers=headers)
#         else:
#             response = requests.put(url, data=data, headers=headers)

#         frappe.logger().info(f"Response Status Code: {response.status_code}")
#         frappe.logger().info(f"Response Text: {response.text}")
#         response.raise_for_status()

#     except requests.exceptions.RequestException as e:
#         frappe.logger().error(
#             f"Failed to update {field_name} for product {art_sifra}: {str(e)}"
#         )


# def get_prestashop_product_name(art_sifra):
#     test_result = frappe.call("imtecapp.api.test_prestashop_products_names")
#     products_data = test_result.get("cleaned_names", {}).get("products", [])
#     return next(
#         (prod["name"] for prod in products_data if prod["art_sifra"] == art_sifra), None
#     )


# ### Sync Functions


# def sync_all_stanje():
#     sync_all("stock levels", update_prestashop_stock_level, method="PATCH")


# def update_prestashop_stock_level(product, settings, method="PATCH"):
#     prestashop_id = get_prestashop_id(product)
#     if not prestashop_id:
#         return

#     prestashop_stock_url = f"{settings['presta_url']}/stock_availables/{prestashop_id}"

#     data = f"""
#     <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
#         <stock_available>
#             <id><![CDATA[{prestashop_id}]]></id>
#             <quantity><![CDATA[{product['stanje']}]]></quantity>
#         </stock_available>
#     </prestashop>
#     """

#     send_prestashop_request(
#         prestashop_stock_url,
#         data,
#         "stock level",
#         product["art_sifra"],
#         settings,
#         method,
#     )


# def sync_all_vpc():
#     sync_all("VPC", update_prestashop_vpc)


# def update_prestashop_vpc(product, settings, method="PUT"):
#     prestashop_id = get_prestashop_id(product)
#     if not prestashop_id:
#         return

#     prestashop_url = f"{settings['presta_url']}/products/{prestashop_id}"
#     data = f"""
#     <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
#         <product>
#             <id><![CDATA[{prestashop_id}]]></id>
#             <price><![CDATA[{product['vpc']}]]></price>
#         </product>
#     </prestashop>
#     """

#     send_prestashop_request(
#         prestashop_url, data, "VPC", product["art_sifra"], settings, method
#     )


# def sync_all_aktivan():
#     sync_all("active status", update_prestashop_active_status)


# def update_prestashop_active_status(product, settings, method="PUT"):
#     prestashop_id = get_prestashop_id(product)
#     if not prestashop_id:
#         return

#     prestashop_url = f"{settings['presta_url']}/products/{prestashop_id}"
#     data = f"""
#     <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
#         <product>
#             <id><![CDATA[{prestashop_id}]]></id>
#             <active><![CDATA[{1 if product['aktivan'] else 0}]]></active>
#         </product>
#     </prestashop>
#     """

#     send_prestashop_request(
#         prestashop_url, data, "active status", product["art_sifra"], settings, method
#     )


# def sync_all_art_naziv():
#     sync_all("product names", update_prestashop_product_name)


# def update_prestashop_product_name(product, settings, method="PUT"):
#     prestashop_id = get_prestashop_id(product)
#     if not prestashop_id:
#         return

#     product_name = get_prestashop_product_name(product["art_sifra"])
#     if not product_name:
#         frappe.logger().error(
#             f"Product name not found for art_sifra: {product['art_sifra']}"
#         )
#         return

#     prestashop_url = f"{settings['presta_url']}/products/{prestashop_id}"
#     data = f"""
#     <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
#         <product>
#             <id><![CDATA[{prestashop_id}]]></id>
#             <name>
#                 <language id="1"><![CDATA[{product_name}]]></language>
#                 <language id="2"><![CDATA[{product_name}]]></language>
#             </name>
#         </product>
#     </prestashop>
#     """

#     send_prestashop_request(
#         prestashop_url, data, "product name", product["art_sifra"], settings, method
#     )
