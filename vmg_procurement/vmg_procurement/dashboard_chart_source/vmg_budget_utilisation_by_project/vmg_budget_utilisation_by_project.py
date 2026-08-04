# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from vmg_procurement.utils.budget import get_budget_position


@frappe.whitelist()
@frappe.read_only()
def get_data(chart_name=None, chart=None, no_cache=None, filters=None, from_date=None,
	to_date=None, timespan=None, time_interval=None, heatmap_year=None):
	labels, budget_values, consumed_values = [], [], []
	for budget in frappe.get_all(
		"VMG Project Budget",
		filters={"docstatus": 1, "status": "Active"},
		fields=["name", "project", "cost_center"],
		order_by="project asc",
	):
		total_budget = total_consumed = 0.0
		for line in frappe.get_all(
			"VMG Project Budget Line",
			filters={"parent": budget.name},
			fields=["expense_account", "budget_amount"],
		):
			position = get_budget_position(budget.project, budget.cost_center, line.expense_account)
			total_budget += flt(line.budget_amount)
			total_consumed += (
				position["soft_committed"] + position["firm_committed"] + position["actual"]
			)
		labels.append(budget.project)
		budget_values.append(total_budget)
		consumed_values.append(total_consumed)

	return {
		"labels": labels,
		"datasets": [
			{"name": "Budget", "values": budget_values},
			{"name": "Consumed", "values": consumed_values},
		],
		"type": "bar",
	}
