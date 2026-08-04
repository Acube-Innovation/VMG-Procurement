# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.naming import append_number_if_name_exists
from frappe.utils import flt
from frappe.model.document import Document

BUDGET_ROLES = {"VMG Project User", "VMG CFO", "System Manager"}


class VMGProjectBudget(Document):
	def autoname(self):
		name = f"BUD-{self.project}-{self.fiscal_year}"
		self.name = append_number_if_name_exists("VMG Project Budget", name)

	def validate(self):
		self.validate_roles()
		self.validate_accounts()
		self.validate_duplicate_active()
		self.refresh_consumption()
		if self.docstatus.is_draft():
			self.status = "Draft"

	def on_submit(self):
		self.db_set("status", "Active", update_modified=False)

	def on_cancel(self):
		self.db_set("status", "Closed", update_modified=False)

	def validate_roles(self):
		if not BUDGET_ROLES.intersection(frappe.get_roles()):
			frappe.throw(
				_("Only {0} may create or amend a project budget").format(
					_(" or ").join(sorted(BUDGET_ROLES - {"System Manager"}))
				),
				frappe.PermissionError,
				title=_("Not Permitted"),
			)

	def validate_accounts(self):
		seen = set()
		for line in self.budget_lines:
			root_type, is_group = frappe.db.get_value(
				"Account", line.expense_account, ["root_type", "is_group"]
			)
			if is_group:
				frappe.throw(
					_("Row {0}: {1} is a group account").format(line.idx, line.expense_account)
				)
			if root_type != "Expense":
				frappe.throw(
					_("Row {0}: {1} is not an expense account").format(line.idx, line.expense_account)
				)
			if line.expense_account in seen:
				frappe.throw(
					_("Row {0}: account {1} appears more than once").format(
						line.idx, line.expense_account
					)
				)
			seen.add(line.expense_account)

	def validate_duplicate_active(self):
		duplicate = frappe.db.exists(
			"VMG Project Budget",
			{
				"project": self.project,
				"cost_center": self.cost_center,
				"fiscal_year": self.fiscal_year,
				"docstatus": 1,
				"status": "Active",
				"name": ["!=", self.name],
			},
		)
		if duplicate:
			frappe.throw(
				_(
					"An active budget ({0}) already exists for project {1}, cost center"
					" {2}, fiscal year {3}"
				).format(
					frappe.bold(duplicate), self.project, self.cost_center, self.fiscal_year
				),
				title=_("Duplicate Budget"),
			)

	@frappe.whitelist()
	def refresh_consumption(self):
		from vmg_procurement.utils.budget import get_budget_position

		total_budget = total_committed = total_actual = 0.0
		for line in self.budget_lines:
			position = get_budget_position(self.project, self.cost_center, line.expense_account)
			line.committed_amount = position["soft_committed"] + position["firm_committed"]
			line.actual_amount = position["actual"]
			line.available_amount = (
				flt(line.budget_amount) - line.committed_amount - line.actual_amount
			)
			line.utilisation_percent = (
				(line.committed_amount + line.actual_amount) / flt(line.budget_amount) * 100.0
				if flt(line.budget_amount)
				else 0
			)
			total_budget += flt(line.budget_amount)
			total_committed += line.committed_amount
			total_actual += line.actual_amount
		self.total_budget = total_budget
		self.total_committed = total_committed
		self.total_actual = total_actual
		self.total_available = total_budget - total_committed - total_actual
