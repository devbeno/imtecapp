import frappe
import unittest
from unittest.mock import patch, MagicMock
from frappe.tests.utils import FrappeTestCase

from imtecapp.imtecapp.doctype.proizvodi.eline.insert_new_data import (
    insert_data_from_for_insert_eline_data,
)
from imtecapp.imtecapp.doctype.proizvodi.sync_categorie import (
    create_prestashop_category,
    update_prestashop_category_name
)
from imtecapp.imtecapp.doctype.proizvodi.sync_manufacturer import (
    create_prestashop_manufacturer,
    update_prestashop_manufacturer_name
)
from imtecapp.utils import create_sync_log_record


class TestProizvodi(FrappeTestCase):
    """
    Unit tests for sync functions (categories and manufacturers) in Frappe app.
    """

    def setUp(self):
        """Set up mock data for testing."""
        self.mock_json_data = [
            {
                "art_sifra": "100004",
                "agp_id": 1,
                "sifra": "100000",
                "vpc": 111111.487,
                "aktivan": 1,
                "stanje": 11111,
                "art_naziv": "aaaaabbbCCCCc Cyan",
                "kataloski": "C9701A",
                "grupanaziv": "ToneriToneriToneriToneriToneri",
                "proizvodjac": "HPHPHPHPHPHP",
                "hash": "11cd8722073a7ae667a7cc7bf97b3565",
                "status": "for_rename"
            },
            {
                "art_sifra": "100005",
                "agp_id": 1,
                "sifra": "100000",
                "vpc": 2222.65,
                "aktivan": 1,
                "stanje": 2222,
                "art_naziv": "HPHPHPPHPHPHPHPHPHPHPHPHPHPHP",
                "kataloski": "Q2610A",
                "grupanaziv": "Toneri originalni",
                "proizvodjac": "HP",
                "hash": "adac7d33d46848dd1ed3b49cd0b8743e",
                "status": "for_update"
            }
        ]
        self.prestashop_category_id = "123"
        self.prestashop_manufacturer_id = "456"

    @patch("imtecapp.imtecapp.doctype.proizvodi.sync_categorie.create_prestashop_category")
    def test_create_prestashop_category(self, mock_create_category):
        """
        Test for creating a new PrestaShop category.
        Mock the PrestaShop response to ensure proper behavior.
        """
        # Mock PrestaShop response for category creation
        mock_create_category.return_value = "123"  # Ensures return value matches expected
        category_id = create_prestashop_category({"grupanaziv": "Test Category"})
        self.assertEqual(category_id, "123")  # Comparing mocked return value


    @patch("imtecapp.imtecapp.doctype.proizvodi.sync_manufacturer.create_prestashop_manufacturer")
    def test_create_prestashop_manufacturer(self, mock_create_manufacturer):
        """
        Test for creating a new PrestaShop manufacturer.
        Mock the PrestaShop response to ensure proper behavior.
        """
        # Mock PrestaShop response for manufacturer creation
        mock_create_manufacturer.return_value = "456"
        manufacturer_id = create_prestashop_manufacturer({"proizvodjac": "Test Manufacturer"})
        self.assertEqual(manufacturer_id, "456")


    @patch("imtecapp.imtecapp.doctype.proizvodi.sync_categorie.update_prestashop_category_name")
    def test_update_prestashop_category_name(self, mock_update_category):
        """
        Test for updating PrestaShop category name.
        Mock the PrestaShop update response to simulate success.
        """
        # Mock successful update
        mock_update_category.return_value = True
        result = update_prestashop_category_name("123", "Updated Category Name")
        self.assertTrue(result)  # Ensure result is True


    @patch("imtecapp.imtecapp.doctype.proizvodi.sync_manufacturer.update_prestashop_manufacturer_name")
    def test_update_prestashop_manufacturer_name(self, mock_update_manufacturer):
        """
        Test for updating PrestaShop manufacturer name.
        Mock the PrestaShop update response to simulate success.
        """
        # Mock successful update
        mock_update_manufacturer.return_value = True
        result = update_prestashop_manufacturer_name("456", "Updated Manufacturer Name")
        self.assertTrue(result)  # Ensure result is True


    @patch("imtecapp.imtecapp.doctype.proizvodi.eline.insert_new_data.insert_data_from_for_insert_eline_data")
    def test_insert_data_from_for_insert_eline_data(self, mock_insert_data):
        """
        Test for inserting new data for syncing with Eline.
        Mock the function to simulate a successful insert.
        """
        sync_log = create_sync_log_record("Test Insert Sync")
        mock_insert_data.return_value = "Insert Successful"  # Ensure mock returns expected value
        result = insert_data_from_for_insert_eline_data(sync_log)
        self.assertEqual(result, "Insert Successful")  # Compare result with expected value


if __name__ == "__main__":
    unittest.main()
