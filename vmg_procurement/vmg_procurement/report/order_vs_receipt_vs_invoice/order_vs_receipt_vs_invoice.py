# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt
#
# Quantity and value variance per LPO line across order, receipt and invoice.

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = [
		{"label": _("LPO"), "fieldname": "lpo", "fieldtype": "Link", "options": "VMG Local Purchase Order", "width": 160},
		{"label": _("Date"), "fieldname": "order_date", "fieldtype": "Date", "width": 95},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
		{"label": _("Division"), "fieldname": "division", "fieldtype": "Link", "options": "VMG Division", "width": 95},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 220},
		{"label": _("Ordered Qty"), "fieldname": "ordered_qty", "fieldtype": "Float", "width": 95},
		{"label": _("Received Qty"), "fieldname": "received_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Billed Qty"), "fieldname": "billed_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Qty Variance"), "fieldname": "qty_variance", "fieldtype": "Float", "width": 100},
		{"label": _("Ordered Value"), "fieldname": "ordered_value", "fieldtype": "Currency", "width": 115},
		{"label": _("Received Value"), "fieldname": "received_value", "fieldtype": "Currency", "width": 115},
		{"label": _("Billed Value"), "fieldname": "billed_value", "fieldtype": "Currency", "width": 115},
		{"label": _("Value Variance"), "fieldname": "value_variance", "fieldtype": "Currency", "width": 115},
	]

	conditions = ["lpo.docstatus = 1"]
	values = {}
	if filters.get("division"):
		conditions.append("lpo.division = %(division)s")
		values["division"] = filters.division
	if filters.get("project"):
		conditions.append("lpo.project = %(project)s")
		values["project"] = filters.project
	if filters.get("supplier"):
		conditions.append("lpo.supplier = %(supplier)s")
		values["supplier"] = filters.supplier
	if filters.get("from_date"):
		conditions.append("lpo.order_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("lpo.order_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	rows = frappe.db.sql(
		f"""
		select
			lpo.name as lpo, lpo.order_date, lpo.supplier, lpo.division,
			item.name as item_name, item.description, item.qty as ordered_qty,
			item.received_qty, item.billed_qty, item.rate
		from `tabVMG LPO Item` item
		join `tabVMG Local Purchase Order` lpo on lpo.name = item.parent
		where {" and ".join(conditions)}
		order by lpo.order_date asc, lpo.name asc, item.idx asc
		""",
		values,
		as_dict=True,
	)

	for row in rows:
		billed_value = flt(
			frappe.db.sql(
				"""
				select sum(item.amount)
				from `tabVMG Supplier Invoice Item` item
				join `tabVMG Supplier Invoice` invoice on invoice.name = item.parent
				where invoice.docstatus = 1 and item.lpo_item = %s
				""",
				row.item_name,
			)[0][0]
		)
		row.ordered_value = flt(row.ordered_qty) * flt(row.rate)
		row.received_value = flt(row.received_qty) * flt(row.rate)
		row.billed_value = billed_value
		row.qty_variance = flt(row.ordered_qty) - flt(row.received_qty)
		row.value_variance = row.ordered_value - billed_value

	return columns, rows
