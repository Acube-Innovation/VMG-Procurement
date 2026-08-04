# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt
#
# Who was issued what and when, with the latest issue per employee + item
# type and whether a replacement is due (per the reissue period setting).

import frappe
from frappe import _
from frappe.utils import add_months, cint, getdate, nowdate

from vmg_procurement.utils.settings import get_settings


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = [
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 170},
		{"label": _("Item Type"), "fieldname": "item_type", "fieldtype": "Data", "width": 140},
		{"label": _("Size"), "fieldname": "size", "fieldtype": "Data", "width": 70},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 70},
		{"label": _("Issue Date"), "fieldname": "issue_date", "fieldtype": "Date", "width": 100},
		{"label": _("Handover"), "fieldname": "handover", "fieldtype": "Link", "options": "VMG PPE and Uniform Handover", "width": 160},
		{"label": _("Division"), "fieldname": "division", "fieldtype": "Link", "options": "VMG Division", "width": 100},
		{"label": _("Latest Issue"), "fieldname": "is_latest", "fieldtype": "Check", "width": 90},
		{"label": _("Replacement Due"), "fieldname": "replacement_due", "fieldtype": "Check", "width": 110},
	]

	conditions = ["handover.docstatus = 1"]
	values = {}
	if filters.get("employee"):
		conditions.append("item.employee = %(employee)s")
		values["employee"] = filters.employee
	if filters.get("item_type"):
		conditions.append("item.item_type = %(item_type)s")
		values["item_type"] = filters.item_type
	if filters.get("division"):
		conditions.append("handover.division = %(division)s")
		values["division"] = filters.division
	if filters.get("from_date"):
		conditions.append("coalesce(item.issue_date, handover.handover_date) >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("coalesce(item.issue_date, handover.handover_date) <= %(to_date)s")
		values["to_date"] = filters.to_date

	rows = frappe.db.sql(
		f"""
		select
			item.employee, item.employee_name, item.item_type, item.size, item.qty,
			coalesce(item.issue_date, handover.handover_date) as issue_date,
			handover.name as handover, handover.division
		from `tabVMG PPE Handover Item` item
		join `tabVMG PPE and Uniform Handover` handover on handover.name = item.parent
		where {" and ".join(conditions)}
		order by item.employee asc, item.item_type asc, issue_date desc
		""",
		values,
		as_dict=True,
	)

	months = cint(get_settings().get("uniform_reissue_months")) or 12
	due_cutoff = add_months(getdate(nowdate()), -months)
	seen = set()
	for row in rows:
		key = (row.employee, row.item_type)
		row.is_latest = 0 if key in seen else 1
		seen.add(key)
		row.replacement_due = (
			1 if row.is_latest and row.issue_date and getdate(row.issue_date) <= due_cutoff else 0
		)

	return columns, rows
