import frappe
import unittest

class TestProizvodi(unittest.TestCase):

    def setUp(self):
        # Setup any initial data needed for the tests
        self.test_product = frappe.get_doc({
            "doctype": "Proizvodi",
            "art_sifra": "TEST123",
            "art_naziv": "Test Product",
            "agp_id": "GRP001",
            "sifra": "MAN001",
            "vpc": 100.0,
            "aktivan": 1,
            "stanje": 10,
            "kataloski": "KAT001",
            "grupanaziv": "Group Test",
            "proizvodjac": "Manufacturer Test",
            "hash": "hashvalue123"
        })
        self.test_product.insert()

    def tearDown(self):
        # Cleanup any data created during the tests
        frappe.delete_doc("Proizvodi", self.test_product.name)

    def test_create_proizvodi(self):
        # Test creating a new Proizvodi record
        product = frappe.get_doc({
            "doctype": "Proizvodi",
            "art_sifra": "NEW123",
            "art_naziv": "New Product",
            "agp_id": "GRP002",
            "sifra": "MAN002",
            "vpc": 150.0,
            "aktivan": 1,
            "stanje": 5,
            "kataloski": "KAT002",
            "grupanaziv": "Group New",
            "proizvodjac": "Manufacturer New",
            "hash": "hashvalue456"
        })
        product.insert()
        self.assertTrue(frappe.db.exists("Proizvodi", {"art_sifra": "NEW123"}))

    def test_update_proizvodi(self):
        # Test updating an existing Proizvodi record
        self.test_product.art_naziv = "Updated Product"
        self.test_product.save()
        updated_product = frappe.get_doc("Proizvodi", self.test_product.name)
        self.assertEqual(updated_product.art_naziv, "Updated Product")

    def test_delete_proizvodi(self):
        # Test deleting a Proizvodi record
        self.test_product.delete()
        self.assertFalse(frappe.db.exists("Proizvodi", self.test_product.name))

    def test_sync_with_prestashop(self):
        # Mock the sync method for testing without actual API calls
        original_sync_method = frappe.get_doc("Proizvodi", self.test_product.name).sync_with_prestashop
        
        try:
            frappe.get_doc("Proizvodi", self.test_product.name).sync_with_prestashop = lambda: {"status": "success"}
            response = frappe.get_doc("Proizvodi", self.test_product.name).sync_with_prestashop()
            self.assertIsNotNone(response)
            self.assertEqual(response.get("status"), "success")
        finally:
            # Restore the original method
            frappe.get_doc("Proizvodi", self.test_product.name).sync_with_prestashop = original_sync_method

if __name__ == '__main__':
    unittest.main()
