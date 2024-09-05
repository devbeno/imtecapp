
import frappe
import base64
import json

def log_message(sync_log, message):
    """Append a message to the Sync Log."""
    if sync_log:
        if sync_log.log_details:
            sync_log.log_details += message + "\n"
        else:
            sync_log.log_details = message + "\n"
        sync_log.save(ignore_permissions=True)
        frappe.db.commit()

def truncate_string(input_string, max_length):
    """Truncate a string to a maximum length."""
    return input_string[:max_length]

def generate_link_rewrite(name):
    """Generate a URL-friendly version of the category name for PrestaShop."""
    import re
    link_rewrite = re.sub(r"\W+", "-", name.lower()).strip("-")
    return link_rewrite
