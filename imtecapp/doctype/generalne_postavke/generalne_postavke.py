# Copyright (c) 2024, Imtec and contributors
# For license information, please see license.txt

# import frappe

from frappe.model.document import Document
import frappe


class GeneralnePostavke(Document):
    pass


def get_prestashop_config():
    try:
        return frappe.get_single("Generalne Postavke")
    except frappe.DoesNotExistError:
        frappe.log_error("Generalne Postavke doctype is missing", "Configuration Error")
        return None
