# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import json

import frappe


def execute():
	"""Dashboard chart + number card for budget utilisation on the workspace."""
	if not frappe.db.exists("Dashboard Chart", "VMG Budget Utilisation by Project"):
		frappe.get_doc(
			{
				"doctype": "Dashboard Chart",
				"chart_name": "VMG Budget Utilisation by Project",
				"chart_type": "Custom",
				"source": "VMG Budget Utilisation by Project",
				"type": "Bar",
				"is_public": 1,
				"filters_json": "{}",
			}
		).insert(ignore_permissions=True)

	if not frappe.db.exists("Number Card", "VMG Active Project Budgets"):
		doc = frappe.get_doc(
			{
				"doctype": "Number Card",
				"label": "Active Project Budgets",
				"type": "Document Type",
				"document_type": "VMG Project Budget",
				"function": "Count",
				"filters_json": json.dumps(
					[
						["VMG Project Budget", "docstatus", "=", 1],
						["VMG Project Budget", "status", "=", "Active"],
					]
				),
				"is_public": 1,
				"show_percentage_stats": 0,
			}
		).insert(ignore_permissions=True)
		if doc.name != "VMG Active Project Budgets":
			frappe.rename_doc("Number Card", doc.name, "VMG Active Project Budgets", force=True)
