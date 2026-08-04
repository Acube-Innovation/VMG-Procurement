# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt
#
# Full asset chain per created Asset: requisition -> material request ->
# purchase order -> receipt -> asset, with value, location and custodian.

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = [
		{
			"label": _("Requisition"),
			"fieldname": "vmg_purchase_requisition",
			"fieldtype": "Link",
			"options": "VMG Purchase Requisition",
			"width": 160,
		},
		{
			"label": _("Material Request"),
			"fieldname": "material_request",
			"fieldtype": "Link",
			"options": "Material Request",
			"width": 160,
		},
		{
			"label": _("Purchase Order"),
			"fieldname": "purchase_order",
			"fieldtype": "Link",
			"options": "Purchase Order",
			"width": 160,
		},
		{
			"label": _("Receipt"),
			"fieldname": "purchase_receipt",
			"fieldtype": "Link",
			"options": "Purchase Receipt",
			"width": 160,
		},
		{
			"label": _("Asset"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Asset",
			"width": 160,
		},
		{
			"label": _("Serial / Asset No"),
			"fieldname": "serial_no",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 170,
		},
		{
			"label": _("Purchase Value (AED)"),
			"fieldname": "gross_purchase_amount",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("Location"),
			"fieldname": "location",
			"fieldtype": "Link",
			"options": "Location",
			"width": 130,
		},
		{
			"label": _("Custodian"),
			"fieldname": "custodian",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 130,
		},
	]

	conditions = {"vmg_purchase_requisition": ["is", "set"]}
	if filters.get("from_date") and filters.get("to_date"):
		conditions["purchase_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		conditions["purchase_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		conditions["purchase_date"] = ["<=", filters.to_date]
	if filters.get("division"):
		conditions["vmg_division"] = filters.division

	data = frappe.get_all(
		"Asset",
		filters=conditions,
		fields=[
			"name",
			"vmg_purchase_requisition",
			"vmg_manufacturer_serial_no",
			"purchase_receipt",
			"item_code",
			"supplier",
			"gross_purchase_amount",
			"location",
			"custodian",
		],
		order_by="purchase_date asc, name asc",
	)

	for row in data:
		row.serial_no = row.vmg_manufacturer_serial_no or row.name
		if row.purchase_receipt:
			row.purchase_order = frappe.db.get_value(
				"Purchase Receipt Item",
				{"parent": row.purchase_receipt, "item_code": row.item_code},
				"purchase_order",
			)
		if row.get("purchase_order"):
			row.material_request = frappe.db.get_value(
				"Purchase Order Item",
				{"parent": row.purchase_order, "item_code": row.item_code},
				"material_request",
			)

	return columns, data
