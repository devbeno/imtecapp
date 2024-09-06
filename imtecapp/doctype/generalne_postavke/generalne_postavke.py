# generalne_postavke.py

from frappe.model.document import Document
import frappe

class GeneralnePostavke(Document):
    """A class representing the Generalne Postavke DocType."""
    pass

def get_prestashop_config():
    """
    Fetch the PrestaShop configuration settings from the 'Generalne Postavke' doctype.

    Returns:
        Document: The 'Generalne Postavke' document containing the PrestaShop configuration settings.
                  Returns None if the document is missing.
    """
    try:
        settings = frappe.get_single("Generalne Postavke")
        if not settings:
            frappe.log_error("The 'Generalne Postavke' document is missing or could not be retrieved.", "Configuration Error")
            frappe.throw(_("PrestaShop configuration settings are missing. Please ensure 'Generalne Postavke' is properly set up."))
        return settings
    except frappe.DoesNotExistError:
        frappe.log_error("The 'Generalne Postavke' doctype does not exist in the system.", "Configuration Error")
        frappe.throw(_("PrestaShop configuration settings are missing. Please ensure 'Generalne Postavke' is properly set up."))
    except Exception as e:
        frappe.log_error(f"An unexpected error occurred while retrieving 'Generalne Postavke': {str(e)}", "Configuration Error")
        frappe.throw(_("An unexpected error occurred. Please check the logs for more details."))

