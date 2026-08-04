# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt
#
# Everything sitting in an approval state across the whole chain, with the
# role that has to act and how long it has been waiting.

import frappe
from frappe import _
from frappe.utils import date_diff, nowdate

PENDING_STATES_TO_ROLE = {
	"Pending Division Approval": "VMG Division Manager",
	"Pending CFO Approval": "VMG CFO",
	"Pending GM Approval": "VMG General Manager",
	"Pending Procurement Approval": "VMG Procurement User",
	"Pending Procurement Verification": "VMG Procurement User",
	"Pending Accounts Approval": "VMG Accounts User",
}

SOURCES = [
	# (doctype, date field, value field, supplier field)
	("VMG Purchase Requisition", "requisition_date", "total_estimated_value", None),
	("VMG Quotation Comparison", "transaction_date", "awarded_value", "selected_supplier"),
	("VMG Local Purchase Order", "order_date", "grand_total", "supplier"),
	("VMG Purchase Receipt", "receipt_date", "grand_total", "supplier"),
	("VMG Supplier Invoice", "posting_date", "grand_total", "supplier"),
]


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = [
		{"label": _("Document Type"), "fieldname": "document_type", "fieldtype": "Data", "width": 190},
		{"label": _("Document"), "fieldname": "document", "fieldtype": "Dynamic Link", "options": "document_type", "width": 170},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
		{"label": _("Division"), "fieldname": "division", "fieldtype": "Link", "options": "VMG Division", "width": 100},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Data", "width": 160},
		{"label": _("Value (AED)"), "fieldname": "value", "fieldtype": "Currency", "width": 120},
		{"label": _("Waiting State"), "fieldname": "workflow_state", "fieldtype": "Data", "width": 190},
		{"label": _("Pending With Role"), "fieldname": "pending_role", "fieldtype": "Data", "width": 170},
		{"label": _("Days Waiting"), "fieldname": "days_waiting", "fieldtype": "Int", "width": 100},
	]

	rows = []
	for doctype, date_field, value_field, supplier_field in SOURCES:
		conditions = {
			"docstatus": ["<", 2],
			"workflow_state": ["in", list(PENDING_STATES_TO_ROLE)],
		}
		if filters.get("division"):
			conditions["division"] = filters.division
		if filters.get("supplier") and supplier_field:
			conditions[supplier_field] = filters.supplier
		elif filters.get("supplier") and not supplier_field:
			continue
		if filters.get("from_date") and filters.get("to_date"):
			conditions[date_field] = ["between", [filters.from_date, filters.to_date]]
		elif filters.get("from_date"):
			conditions[date_field] = [">=", filters.from_date]
		elif filters.get("to_date"):
			conditions[date_field] = ["<=", filters.to_date]

		fields = ["name", "division", "workflow_state", "modified", f"{date_field} as date", f"{value_field} as value"]
		if supplier_field:
			fields.append(f"{supplier_field} as supplier")
		for doc in frappe.get_all(doctype, filters=conditions, fields=fields):
			rows.append(
				{
					"document_type": doctype,
					"document": doc.name,
					"date": doc.date,
					"division": doc.division,
					"supplier": doc.get("supplier"),
					"value": doc.value,
					"workflow_state": doc.workflow_state,
					"pending_role": PENDING_STATES_TO_ROLE.get(doc.workflow_state),
					"days_waiting": date_diff(nowdate(), doc.modified),
				}
			)

	rows.sort(key=lambda r: r["days_waiting"], reverse=True)
	return columns, rows
