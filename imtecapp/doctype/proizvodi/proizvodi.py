import frappe
from frappe.model.document import Document

class Proizvodi(Document):
    def validate(self):
        # Example: Check if the product code already exists
        if frappe.db.exists("Proizvodi", {"art_sifra": self.art_sifra}):
            frappe.throw("A product with this code already exists.")

    def before_save(self):
        # Example: Generate a hash for the product data
        if not self.hash:
            self.hash = self.generate_hash()
        
    def generate_hash(self):
        # Example: Generate a unique hash for the product data
        data = f"{self.art_sifra}{self.art_naziv}"
        return frappe.generate_hash(data, length=10)

@frappe.whitelist()
def sync_single_product(art_sifra):
    # Custom method to sync a single product with PrestaShop
    product = frappe.get_doc("Proizvodi", {"art_sifra": art_sifra})
    product.sync_with_prestashop()
    frappe.msgprint(f"Product {art_sifra} synced successfully.")
