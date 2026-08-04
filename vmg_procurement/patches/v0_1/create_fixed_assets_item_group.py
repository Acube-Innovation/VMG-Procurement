# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Item Group for all fixed asset items of the asset procurement branch."""
	if frappe.db.exists("Item Group", "Fixed Assets"):
		return
	parent = (
		frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ["in", ("", None)]})
		or "All Item Groups"
	)
	frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": "Fixed Assets",
			"parent_item_group": parent,
			"is_group": 0,
		}
	).insert(ignore_permissions=True)
