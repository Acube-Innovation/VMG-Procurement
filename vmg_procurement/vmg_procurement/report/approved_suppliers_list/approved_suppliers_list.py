# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt
#
# VMG-PRO-F05 - Approved Supplier List
# Columns mirror the client form: Supplier Name, Address, Contact Person,
# Contact No., Email ID, Item / Materials, Remarks - plus the approval
# tracking fields (category, licence expiry, approved on).

import frappe
from frappe import _
from frappe.utils import strip_html


def execute(filters=None):
	columns = [
		{
			"label": _("Supplier"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 170,
		},
		{
			"label": _("Supplier Name"),
			"fieldname": "supplier_name",
			"fieldtype": "Data",
			"width": 220,
		},
		{"label": _("Address"), "fieldname": "address", "fieldtype": "Data", "width": 200},
		{
			"label": _("Contact Person"),
			"fieldname": "contact_person",
			"fieldtype": "Data",
			"width": 150,
		},
		{"label": _("Contact No."), "fieldname": "mobile_no", "fieldtype": "Data", "width": 130},
		{"label": _("Email ID"), "fieldname": "email_id", "fieldtype": "Data", "width": 180},
		{
			"label": _("Item / Materials"),
			"fieldname": "vmg_items_materials",
			"fieldtype": "Data",
			"width": 170,
		},
		{
			"label": _("Category"),
			"fieldname": "vmg_supplier_category",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Trade Licence Expiry"),
			"fieldname": "vmg_trade_licence_expiry",
			"fieldtype": "Date",
			"width": 140,
		},
		{
			"label": _("Approved On"),
			"fieldname": "vmg_approved_on",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": _("Remarks"),
			"fieldname": "vmg_approval_remarks",
			"fieldtype": "Data",
			"width": 180,
		},
	]

	data = frappe.get_all(
		"Supplier",
		filters={"vmg_is_approved": 1},
		fields=[
			"name",
			"supplier_name",
			"primary_address",
			"supplier_primary_contact",
			"mobile_no",
			"email_id",
			"vmg_items_materials",
			"vmg_supplier_category",
			"vmg_trade_licence_expiry",
			"vmg_approved_on",
			"vmg_approval_remarks",
		],
		order_by="supplier_name asc",
	)

	contact_names = {}
	contacts = {d.supplier_primary_contact for d in data if d.supplier_primary_contact}
	if contacts:
		for c in frappe.get_all(
			"Contact",
			filters={"name": ["in", list(contacts)]},
			fields=["name", "first_name", "last_name"],
		):
			contact_names[c.name] = " ".join(filter(None, [c.first_name, c.last_name]))

	for d in data:
		d.address = strip_html(d.primary_address or "").replace("\n", ", ").strip(", ")
		d.contact_person = contact_names.get(d.supplier_primary_contact, "")

	message = _("Form Ref: VMG-PRO-F05")
	return columns, data, message
