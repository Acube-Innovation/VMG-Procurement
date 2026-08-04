# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from vmg_procurement.utils.budget import get_budget_position


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = [
		{"label": _("Budget"), "fieldname": "budget_doc", "fieldtype": "Link", "options": "VMG Project Budget", "width": 200},
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 150},
		{"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 130},
		{"label": _("Account"), "fieldname": "expense_account", "fieldtype": "Link", "options": "Account", "width": 200},
		{"label": _("Budget"), "fieldname": "budget", "fieldtype": "Currency", "width": 120},
		{"label": _("Soft Committed"), "fieldname": "soft_committed", "fieldtype": "Currency", "width": 120},
		{"label": _("Firm Committed"), "fieldname": "firm_committed", "fieldtype": "Currency", "width": 120},
		{"label": _("Actual"), "fieldname": "actual", "fieldtype": "Currency", "width": 110},
		{"label": _("Available"), "fieldname": "available", "fieldtype": "Currency", "width": 120},
		{"label": _("Utilisation %"), "fieldname": "utilisation", "fieldtype": "Percent", "width": 110},
		{"label": _("Overrides"), "fieldname": "overrides", "fieldtype": "Data", "width": 240},
	]

	conditions = {"docstatus": 1, "status": "Active"}
	if filters.get("project"):
		conditions["project"] = filters.project
	if filters.get("division"):
		conditions["division"] = filters.division

	rows = []
	for budget in frappe.get_all(
		"VMG Project Budget",
		filters=conditions,
		fields=["name", "project", "cost_center"],
		order_by="project asc",
	):
		for line in frappe.get_all(
			"VMG Project Budget Line",
			filters={"parent": budget.name},
			fields=["expense_account", "budget_amount"],
			order_by="idx asc",
		):
			position = get_budget_position(budget.project, budget.cost_center, line.expense_account)
			consumed = position["soft_committed"] + position["firm_committed"] + position["actual"]
			available = flt(line.budget_amount) - consumed
			utilisation = consumed / flt(line.budget_amount) * 100.0 if flt(line.budget_amount) else 0
			if filters.get("only_breached") and available >= 0:
				continue
			overrides = frappe.db.sql(
				"""
				select name, budget_override_by from `tabVMG Local Purchase Order`
				where docstatus = 1 and project = %(project)s and budget_override_by is not null
				union all
				select name, budget_override_by from `tabVMG Purchase Requisition`
				where docstatus = 1 and project = %(project)s and budget_override_by is not null
				""",
				{"project": budget.project},
			)
			rows.append(
				{
					"budget_doc": budget.name,
					"project": budget.project,
					"cost_center": budget.cost_center,
					"expense_account": line.expense_account,
					"budget": line.budget_amount,
					"soft_committed": position["soft_committed"],
					"firm_committed": position["firm_committed"],
					"actual": position["actual"],
					"available": available,
					"utilisation": utilisation,
					"overrides": ", ".join(f"{n} ({u})" for n, u in overrides) or None,
				}
			)

	return columns, rows
