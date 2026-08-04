# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt
#
# One row per requisition following the custom chain end to end, with the
# age in days at each stage.

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = [
		{"label": _("Requisition"), "fieldname": "name", "fieldtype": "Link", "options": "VMG Purchase Requisition", "width": 150},
		{"label": _("Date"), "fieldname": "requisition_date", "fieldtype": "Date", "width": 95},
		{"label": _("Requester"), "fieldname": "requested_by", "fieldtype": "Data", "width": 140},
		{"label": _("Division"), "fieldname": "division", "fieldtype": "Link", "options": "VMG Division", "width": 95},
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 110},
		{"label": _("Req. Value"), "fieldname": "total_estimated_value", "fieldtype": "Currency", "width": 105},
		{"label": _("RFQ"), "fieldname": "rfq", "fieldtype": "Link", "options": "VMG Request for Quotation", "width": 150},
		{"label": _("Comparison"), "fieldname": "comparison", "fieldtype": "Link", "options": "VMG Quotation Comparison", "width": 150},
		{"label": _("Selected Supplier"), "fieldname": "selected_supplier", "fieldtype": "Data", "width": 150},
		{"label": _("LPO"), "fieldname": "lpo", "fieldtype": "Link", "options": "VMG Local Purchase Order", "width": 150},
		{"label": _("LPO Value"), "fieldname": "lpo_value", "fieldtype": "Currency", "width": 110},
		{"label": _("Received %"), "fieldname": "per_received", "fieldtype": "Percent", "width": 90},
		{"label": _("Invoice"), "fieldname": "invoice", "fieldtype": "Link", "options": "VMG Supplier Invoice", "width": 150},
		{"label": _("Invoice Value"), "fieldname": "invoice_value", "fieldtype": "Currency", "width": 110},
		{"label": _("Paid"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 100},
		{"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 110},
		{"label": _("Req>RFQ d"), "fieldname": "age_req_rfq", "fieldtype": "Int", "width": 85},
		{"label": _("RFQ>Comp d"), "fieldname": "age_rfq_comparison", "fieldtype": "Int", "width": 90},
		{"label": _("Comp>LPO d"), "fieldname": "age_comparison_lpo", "fieldtype": "Int", "width": 90},
		{"label": _("LPO>Inv d"), "fieldname": "age_lpo_invoice", "fieldtype": "Int", "width": 85},
	]

	conditions = {"docstatus": ["<", 2]}
	if filters.get("division"):
		conditions["division"] = filters.division
	if filters.get("project"):
		conditions["project"] = filters.project
	if filters.get("from_date") and filters.get("to_date"):
		conditions["requisition_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		conditions["requisition_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		conditions["requisition_date"] = ["<=", filters.to_date]

	requisitions = frappe.get_all(
		"VMG Purchase Requisition",
		filters=conditions,
		fields=["name", "requisition_date", "requested_by", "division", "project", "total_estimated_value"],
		order_by="requisition_date asc, name asc",
	)

	def age(a, b):
		return date_diff(b, a) if (a and b) else None

	rows = []
	for req in requisitions:
		rfq = frappe.db.get_value(
			"VMG Request for Quotation",
			{"purchase_requisition": req.name, "docstatus": ["<", 2]},
			["name", "transaction_date"],
			as_dict=True,
		)
		comparison = None
		if rfq:
			comparison = frappe.db.get_value(
				"VMG Quotation Comparison",
				{"request_for_quotation": rfq.name, "docstatus": ["<", 2]},
				["name", "transaction_date", "selected_supplier"],
				as_dict=True,
			)
		lpos = frappe.get_all(
			"VMG Local Purchase Order",
			filters={"purchase_requisition": req.name, "docstatus": 1},
			fields=["name", "order_date", "grand_total", "per_received", "supplier"],
			order_by="order_date asc",
		)
		lpo = lpos[0] if lpos else None
		if filters.get("supplier") and (not lpo or lpo.supplier != filters.supplier):
			continue

		invoice = None
		if lpos:
			invoice = frappe.db.get_value(
				"VMG Supplier Invoice",
				{"local_purchase_order": ["in", [l.name for l in lpos]], "docstatus": 1},
				["name", "posting_date", "grand_total", "outstanding_amount"],
				as_dict=True,
			)

		rows.append(
			{
				"name": req.name,
				"requisition_date": req.requisition_date,
				"requested_by": req.requested_by,
				"division": req.division,
				"project": req.project,
				"total_estimated_value": req.total_estimated_value,
				"rfq": rfq and rfq.name,
				"comparison": comparison and comparison.name,
				"selected_supplier": comparison and comparison.selected_supplier,
				"lpo": lpo and lpo.name,
				"lpo_value": sum(flt(l.grand_total) for l in lpos) if lpos else None,
				"per_received": lpo and lpo.per_received,
				"invoice": invoice and invoice.name,
				"invoice_value": invoice and invoice.grand_total,
				"paid_amount": invoice and flt(invoice.grand_total) - flt(invoice.outstanding_amount),
				"outstanding": invoice and invoice.outstanding_amount,
				"age_req_rfq": age(req.requisition_date, rfq and rfq.transaction_date),
				"age_rfq_comparison": age(rfq and rfq.transaction_date, comparison and comparison.transaction_date),
				"age_comparison_lpo": age(comparison and comparison.transaction_date, lpo and lpo.order_date),
				"age_lpo_invoice": age(lpo and lpo.order_date, invoice and invoice.posting_date),
			}
		)

	return columns, rows
