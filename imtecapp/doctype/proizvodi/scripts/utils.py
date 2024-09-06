# utils.py

import frappe
import re
import base64

def log_message(sync_log, message):
    if sync_log:
        if sync_log.log_details:
            sync_log.log_details += message + "\n"
        else:
            sync_log.log_details = message + "\n"
        sync_log.save(ignore_permissions=True)
        frappe.db.commit()

def create_sync_log(sync_type):
    try:
        sync_log = frappe.get_doc(
            {
                "doctype": "Sync Log",
                "sync_type": sync_type,
                "sync_date": frappe.utils.now(),
                "status": "In Progress",
            }
        )
        sync_log.insert(ignore_permissions=True)
        frappe.db.commit()
        return sync_log
    except Exception as e:
        frappe.log_error(f"Failed to create sync log: {e}", "Sync Log Creation Error")
        frappe.throw(_("Unable to create sync log due to an error."))

def truncate_string(input_string, max_length):
    return input_string[:max_length]

def clean_response(response_text):
    clean_text = re.sub(r"^.*?(<\?xml)", r"\1", response_text, flags=re.DOTALL)
    return clean_text

def generate_link_rewrite(name):
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    return name if name else "default-link-rewrite"

def handle_none(value):
    return value if value is not None else ""
