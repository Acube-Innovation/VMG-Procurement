# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe


def get_settings():
	"""Return the VMG Procurement Settings single document.

	Served from frappe's document cache (request-local first, then redis), so
	repeated calls within one request never hit the database. The cache is
	invalidated automatically when the settings are saved.

	Usage in later steps:
	        from vmg_procurement.utils.settings import get_settings
	        settings = get_settings()
	"""
	return frappe.get_cached_doc("VMG Procurement Settings")
