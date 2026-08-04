# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt
#
# The Purchase Order Log maintained by the Procurement Department.

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = [
		{
			"label": _("LPO No"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "VMG Local Purchase Order",
			"width": 170,
		},
		{"label": _("Date"), "fieldname": "order_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Supplier"),
			"fieldname": "supplier_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Division"),
			"fieldname": "division",
			"fieldtype": "Link",
			"options": "VMG Division",
			"width": 110,
		},
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 130,
		},
		{
			"label": _("Grand Total (AED)"),
			"fieldname": "grand_total",
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"label": _("Workflow State"),
			"fieldname": "workflow_state",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Received (%)"),
			"fieldname": "per_received",
			"fieldtype": "Percent",
			"width": 110,
		},
		{
			"label": _("Billed (%)"),
			"fieldname": "per_billed",
			"fieldtype": "Percent",
			"width": 100,
		},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
	]

	conditions = {"docstatus": ["<", 2]}
	if filters.get("from_date") and filters.get("to_date"):
		conditions["order_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		conditions["order_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		conditions["order_date"] = ["<=", filters.to_date]
	if filters.get("division"):
		conditions["division"] = filters.division
	if filters.get("supplier"):
		conditions["supplier"] = filters.supplier
	if filters.get("status"):
		conditions["status"] = filters.status

	data = frappe.get_all(
		"VMG Local Purchase Order",
		filters=conditions,
		fields=[
			"name",
			"order_date",
			"supplier_name",
			"division",
			"project",
			"grand_total",
			"workflow_state",
			"per_received",
			"per_billed",
			"status",
		],
		order_by="order_date asc, name asc",
	)

	return columns, data
