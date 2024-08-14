

# @frappe.whitelist(allow_guest=True)
# def trigger_sync():
#     from imtecapp.config.prestashop import sync_active_products_to_ps_proizvodi
#     sync_active_products_to_ps_proizvodi()

# import frappe


# @frappe.whitelist(allow_guest=True)
# def sync_ps_proizvodi(data=None):
#     frappe.log_error(
#         f"Webhook received with raw data: {frappe.request.data}", "sync_ps_proizvodi"
#     )
#     if not data:
#         frappe.log_error("No data provided", "sync_ps_proizvodi")
#         return {"status": "error", "message": "No data provided"}
#     try:
#         data = frappe.parse_json(data)

#         if data.get("aktivan") == 1:
#             existing_product_name = frappe.db.exists(
#                 "PS Proizvodi", {"reference": data["art_sifra"]}
#             )

#             if not existing_product_name:
#                 ps_product = frappe.get_doc(
#                     {
#                         "doctype": "PS Proizvodi",
#                         "name": data["art_sifra"],
#                         "reference": data["art_sifra"],
#                         "price": data["vpc"],
#                         "active": data["aktivan"],
#                         "quantity": data["stanje"],
#                         "category": data["grupanaziv"],
#                         "manufacturer": data["proizvodjac"],
#                     }
#                 )
#                 ps_product.insert()
#                 frappe.log_error("Created new product", "sync_ps_proizvodi")
#             else:
#                 ps_product = frappe.get_doc("PS Proizvodi", existing_product_name)
#                 ps_product.update(
#                     {
#                         "reference": data["art_sifra"],
#                         "price": data["vpc"],
#                         "active": data["aktivan"],
#                         "quantity": data["stanje"],
#                         "category": data["grupanaziv"],
#                         "manufacturer": data["proizvodjac"],
#                     }
#                 )
#                 ps_product.save()
#                 frappe.log_error("Updated existing product", "sync_ps_proizvodi")

#             frappe.db.commit()
#             return {"status": "success", "message": "Product synced successfully"}
#         else:
#             frappe.log_error("Product is not active", "sync_ps_proizvodi")
#             return {"status": "error", "message": "Product is not active"}

#     except Exception as e:
#         frappe.log_error(f"Error during sync: {str(e)}", "sync_ps_proizvodi")
#         return {"status": "error", "message": str(e)}
