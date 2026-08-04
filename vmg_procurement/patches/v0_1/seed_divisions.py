# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe

DIVISIONS = [
	{"division_name": "Valve", "prefix": "VLV"},
	{"division_name": "Scaffolding", "prefix": "SCF"},
	{"division_name": "Enterprise", "prefix": "ENT"},
	{"division_name": "Rental", "prefix": "RNT"},
]


def execute():
	"""Seed the four VMG divisions.

	Insert-only: existing divisions (by name or prefix) are left untouched, so
	the client can freely rename divisions or change prefixes afterwards.
	"""
	for row in DIVISIONS:
		if frappe.db.exists("VMG Division", row["division_name"]) or frappe.db.exists(
			"VMG Division", {"prefix": row["prefix"]}
		):
			continue
		frappe.get_doc(
			{
				"doctype": "VMG Division",
				"division_type": "Division",
				"is_active": 1,
				**row,
			}
		).insert(ignore_permissions=True)
