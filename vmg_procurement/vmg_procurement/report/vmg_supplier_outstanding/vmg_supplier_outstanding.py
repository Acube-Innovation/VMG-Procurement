# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = [
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 170},
		{"label": _("Invoice"), "fieldname": "name", "fieldtype": "Link", "options": "VMG Supplier Invoice", "width": 170},
		{"label": _("Supplier Invoice No"), "fieldname": "supplier_invoice_no", "fieldtype": "Data", "width": 130},
		{"label": _("Invoice Date"), "fieldname": "supplier_invoice_date", "fieldtype": "Date", "width": 100},
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 100},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 120},
		{"label": _("Paid"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Days Overdue"), "fieldname": "days_overdue", "fieldtype": "Int", "width": 100},
		{"label": _("Division"), "fieldname": "division", "fieldtype": "Link", "options": "VMG Division", "width": 100},
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 120},
	]

	conditions = {"docstatus": 1, "posting_status": "Posted"}
	if filters.get("supplier"):
		conditions["supplier"] = filters.supplier
	if filters.get("division"):
		conditions["division"] = filters.division
	if filters.get("from_date") and filters.get("to_date"):
		conditions["posting_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		conditions["posting_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		conditions["posting_date"] = ["<=", filters.to_date]

	data = frappe.get_all(
		"VMG Supplier Invoice",
		filters=conditions,
		fields=[
			"name", "supplier", "supplier_invoice_no", "supplier_invoice_date",
			"due_date", "grand_total", "outstanding_amount", "division", "project", "status",
		],
		order_by="due_date asc",
	)

	rows = []
	for row in data:
		row.paid_amount = flt(row.grand_total) - flt(row.outstanding_amount)
		row.days_overdue = (
			max(date_diff(nowdate(), row.due_date), 0)
			if row.due_date and flt(row.outstanding_amount) > 0
			else 0
		)
		if filters.get("only_overdue") and not (
			row.days_overdue > 0 and flt(row.outstanding_amount) > 0
		):
			continue
		rows.append(row)

	return columns, rows
