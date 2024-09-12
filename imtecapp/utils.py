# utils.py
import frappe
from frappe import _


def truncate_message(message: str, max_length: int = 140) -> str:
    """Truncate the log message intelligently, preserving key details."""
    if len(message) > max_length:
        # Split message into segments and preserve first and last parts
        start_segment = message[:int(max_length * 0.6)]  # 60% of the message from the start
        end_segment = message[-int(max_length * 0.3):]   # 30% of the message from the end
        return f"{start_segment}... (truncated)... {end_segment}"
    return message


def create_sync_log_record(sync_type):
    """Create a new Sync Log entry or handle existing In Progress log."""
    existing_log = frappe.db.get_value("Sync Log", {"sync_type": sync_type, "status": "In Progress"})
    
    if existing_log:
        # Optionally, return the existing log or update its status, instead of throwing an error
        frappe.msgprint(_("Sync log is already in progress for this operation. Please wait for it to complete."))
        return frappe.get_doc("Sync Log", existing_log)  # Return existing sync log
    
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


def add_message_to_log(sync_log, message):
    """Add a truncated message to the sync log."""
    try:
        truncated_message = truncate_message(message)  # Use the updated truncate_message function
        sync_log.append("messages", {"message": truncated_message})
        sync_log.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Failed to add message to sync log: {e}", "Sync Log Message Error")
        frappe.throw(_("Unable to add message to sync log due to an error."))


def update_sync_log_record(sync_log, log_details, status):
    """Update the sync log record with truncated details and status."""
    try:
        log_details = truncate_message(log_details)  # Use the updated truncate_message function
        sync_log.log_details = log_details
        sync_log.status = status
        sync_log.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Failed to update sync log: {e}", "Sync Log Update Error")
        frappe.throw(_("Unable to update sync log due to an error."))




# def create_sync_log_record(sync_type):
#     """Create a new Sync Log entry."""
#     try:
#         sync_log = frappe.get_doc(
#             {
#                 "doctype": "Sync Log",
#                 "sync_type": sync_type,
#                 "sync_date": frappe.utils.now(),
#                 "status": "In Progress",
#             }
#         )
#         sync_log.insert(ignore_permissions=True)
#         frappe.db.commit()
#         return sync_log
#     except Exception as e:
#         frappe.log_error(f"Failed to create sync log: {e}", "Sync Log Creation Error")
#         frappe.throw(_("Unable to create sync log due to an error."))