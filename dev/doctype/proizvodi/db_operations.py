
import frappe
from .utils import log_message, truncate_string

def create_sync_log(sync_type):
    """Create a new Sync Log entry."""
    try:
        sync_log = frappe.get_doc({
            "doctype": "Sync Log",
            "sync_type": sync_type,
            "sync_date": frappe.utils.now(),
            "status": "In Progress",
        })
        sync_log.insert(ignore_permissions=True)
        frappe.db.commit()
        return sync_log
    except Exception as e:
        frappe.log_error(f"Failed to create sync log: {e}", "Sync Log Creation Error")
        frappe.throw(_("Unable to create sync log due to an error."))

def update_sync_log(sync_log, log_details, status="Success"):
    """Update the Sync Log entry with accumulated log details and final status."""
    max_log_length = 65535
    if len(log_details) > max_log_length:
        log_details = truncate_string(log_details, max_log_length)
        log_message(sync_log, "Log details truncated due to size limit.")

    sync_log.log_details = log_details
    sync_log.status = status

    try:
        sync_log.save(ignore_permissions=True)
        frappe.db.commit()
    except frappe.TimestampMismatchError:
        frappe.msgprint(_("Another user modified this document, please try again."))
