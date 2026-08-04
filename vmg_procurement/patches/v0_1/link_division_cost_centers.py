# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Divisions are cost centers: re-save every division without a linked
	cost center so VMGDivision.ensure_cost_center creates or reuses one."""
	for name in frappe.get_all(
		"VMG Division", filters={"cost_center": ("is", "not set")}, pluck="name"
	):
		doc = frappe.get_doc("VMG Division", name)
		doc.flags.ignore_permissions = True
		doc.save()
