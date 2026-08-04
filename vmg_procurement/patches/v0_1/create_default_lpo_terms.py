# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe

TERMS_NAME = "VMG Standard LPO Terms"

TERMS_HTML = (
	"<ol>"
	"<li>Order Acknowledgement to be done within 48 hours, otherwise it will be"
	" considered as accepted.</li>"
	"<li>Goods must be delivered with a Delivery Note quoting this LPO number.</li>"
	"<li>The original invoice must be submitted together with a copy of the LPO"
	" and the signed Delivery Note.</li>"
	"<li>Prices are in AED and inclusive of delivery unless stated otherwise.</li>"
	"</ol>"
)


def execute():
	"""Seed the standard LPO terms (F04 default clause) and point the settings
	default at them. Never overwrites client changes."""
	if not frappe.db.exists("Terms and Conditions", TERMS_NAME):
		frappe.get_doc(
			{
				"doctype": "Terms and Conditions",
				"title": TERMS_NAME,
				"buying": 1,
				"selling": 0,
				"hr": 0,
				"terms": TERMS_HTML,
			}
		).insert(ignore_permissions=True)

	if not frappe.db.get_single_value("VMG Procurement Settings", "default_terms"):
		frappe.db.set_single_value("VMG Procurement Settings", "default_terms", TERMS_NAME)
