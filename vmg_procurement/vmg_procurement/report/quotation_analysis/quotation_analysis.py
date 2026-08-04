# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt
#
# Per comparison: how many quoted, the lowest total, the awarded total and
# the saving or excess, flagging awards that were not the lowest price.

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = [
		{"label": _("Comparison"), "fieldname": "name", "fieldtype": "Link", "options": "VMG Quotation Comparison", "width": 160},
		{"label": _("Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 100},
		{"label": _("Division"), "fieldname": "division", "fieldtype": "Link", "options": "VMG Division", "width": 100},
		{"label": _("Suppliers"), "fieldname": "supplier_count", "fieldtype": "Int", "width": 85},
		{"label": _("Lowest Total"), "fieldname": "lowest_total", "fieldtype": "Currency", "width": 120},
		{"label": _("Awarded Total"), "fieldname": "awarded_total", "fieldtype": "Currency", "width": 120},
		{"label": _("Saving / (Excess)"), "fieldname": "saving_or_excess", "fieldtype": "Currency", "width": 130},
		{"label": _("Selected Supplier"), "fieldname": "selected_supplier", "fieldtype": "Link", "options": "Supplier", "width": 170},
		{"label": _("Lowest Not Selected"), "fieldname": "lowest_not_selected", "fieldtype": "Check", "width": 100},
		{"label": _("Justification"), "fieldname": "justification", "fieldtype": "Data", "width": 260},
	]

	conditions = {"docstatus": 1}
	if filters.get("division"):
		conditions["division"] = filters.division
	if filters.get("project"):
		conditions["project"] = filters.project
	if filters.get("supplier"):
		conditions["selected_supplier"] = filters.supplier
	if filters.get("from_date") and filters.get("to_date"):
		conditions["transaction_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		conditions["transaction_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		conditions["transaction_date"] = ["<=", filters.to_date]

	comparisons = frappe.get_all(
		"VMG Quotation Comparison",
		filters=conditions,
		fields=[
			"name", "transaction_date", "division", "selected_supplier",
			"awarded_value", "is_lowest_price", "justification",
		],
		order_by="transaction_date asc",
	)

	for row in comparisons:
		totals = frappe.get_all(
			"VMG Comparison Supplier",
			filters={"parent": row.name},
			pluck="grand_total",
		)
		row.supplier_count = len(totals)
		row.lowest_total = min((flt(t) for t in totals), default=0)
		row.awarded_total = flt(row.awarded_value)
		row.saving_or_excess = flt(row.lowest_total) - flt(row.awarded_total)
		row.lowest_not_selected = 0 if row.is_lowest_price else 1

	return columns, comparisons
