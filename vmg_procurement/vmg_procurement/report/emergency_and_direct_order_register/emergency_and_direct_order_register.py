# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt
#
# The auditors' control report: every emergency requisition and every direct
# order, with the recorded justification and who approved it.

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = [
		{"label": _("Type"), "fieldname": "entry_type", "fieldtype": "Data", "width": 170},
		{"label": _("Document Type"), "fieldname": "document_type", "fieldtype": "Data", "width": 180},
		{"label": _("Document"), "fieldname": "document", "fieldtype": "Dynamic Link", "options": "document_type", "width": 170},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
		{"label": _("Division"), "fieldname": "division", "fieldtype": "Link", "options": "VMG Division", "width": 100},
		{"label": _("Requester / Supplier"), "fieldname": "party", "fieldtype": "Data", "width": 180},
		{"label": _("Value (AED)"), "fieldname": "value", "fieldtype": "Currency", "width": 120},
		{"label": _("Justification"), "fieldname": "justification", "fieldtype": "Data", "width": 280},
		{"label": _("Approved By"), "fieldname": "approved_by", "fieldtype": "Data", "width": 160},
	]

	def date_condition(field):
		if filters.get("from_date") and filters.get("to_date"):
			return {field: ["between", [filters.from_date, filters.to_date]]}
		if filters.get("from_date"):
			return {field: [">=", filters.from_date]}
		if filters.get("to_date"):
			return {field: ["<=", filters.to_date]}
		return {}

	rows = []

	if not filters.get("supplier"):
		conditions = {"docstatus": ["<", 2], "is_emergency": 1}
		conditions.update(date_condition("requisition_date"))
		if filters.get("division"):
			conditions["division"] = filters.division
		for req in frappe.get_all(
			"VMG Purchase Requisition",
			filters=conditions,
			fields=[
				"name", "requisition_date", "division", "requested_by",
				"total_estimated_value", "emergency_reference",
				"gm_approved_by", "cfo_approved_by", "division_approved_by",
			],
		):
			rows.append(
				{
					"entry_type": _("Emergency Requisition"),
					"document_type": "VMG Purchase Requisition",
					"document": req.name,
					"date": req.requisition_date,
					"division": req.division,
					"party": req.requested_by,
					"value": req.total_estimated_value,
					"justification": req.emergency_reference,
					"approved_by": req.gm_approved_by or req.cfo_approved_by or req.division_approved_by,
				}
			)

	conditions = {"docstatus": ["<", 2], "order_route": "Direct Order"}
	conditions.update(date_condition("order_date"))
	if filters.get("division"):
		conditions["division"] = filters.division
	if filters.get("supplier"):
		conditions["supplier"] = filters.supplier
	for lpo in frappe.get_all(
		"VMG Local Purchase Order",
		filters=conditions,
		fields=[
			"name", "order_date", "division", "supplier_name", "grand_total",
			"direct_order_justification", "non_approved_supplier_justification",
			"supplier_not_approved", "gm_approved_by", "cfo_approved_by",
		],
	):
		justification = lpo.direct_order_justification or ""
		if lpo.supplier_not_approved and lpo.non_approved_supplier_justification:
			justification += _(" | Unapproved supplier: {0}").format(
				lpo.non_approved_supplier_justification
			)
		rows.append(
			{
				"entry_type": _("Direct Order"),
				"document_type": "VMG Local Purchase Order",
				"document": lpo.name,
				"date": lpo.order_date,
				"division": lpo.division,
				"party": lpo.supplier_name,
				"value": lpo.grand_total,
				"justification": justification,
				"approved_by": lpo.gm_approved_by or lpo.cfo_approved_by,
			}
		)

	rows.sort(key=lambda r: (str(r["date"] or ""), r["document"]))
	return columns, rows
