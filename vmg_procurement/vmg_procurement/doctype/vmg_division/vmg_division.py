# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document


class VMGDivision(Document):
	def validate(self):
		self.validate_prefix()
		self.ensure_cost_center()

	def validate_prefix(self):
		self.prefix = (self.prefix or "").strip().upper()
		if not re.fullmatch(r"[A-Z0-9]{1,6}", self.prefix):
			frappe.throw(
				_("Prefix must be 1 to 6 uppercase letters or digits. Got: {0}").format(
					frappe.bold(self.prefix or _("empty"))
				),
				title=_("Invalid Prefix"),
			)

	def ensure_cost_center(self):
		"""Divisions are cost centers in this project: every division is linked
		1:1 to a leaf Cost Center. An existing leaf with the same name is
		reused, otherwise one is created under the company root cost center."""
		if self.cost_center and not frappe.db.exists("Cost Center", self.cost_center):
			# e.g. fixture imported from another site whose cost center names differ
			self.cost_center = None

		if self.cost_center:
			return

		existing = frappe.db.get_value(
			"Cost Center", {"cost_center_name": self.division_name, "is_group": 0}
		)
		if existing:
			self.cost_center = existing
			return

		company = frappe.defaults.get_global_default("company")
		root = company and frappe.db.get_value(
			"Cost Center",
			{"company": company, "is_group": 1, "parent_cost_center": ("is", "not set")},
		)
		if not root:
			# a bare site being installed or migrated may not have a company
			# yet; leave the link empty instead of blocking the import
			if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch:
				return
			frappe.throw(
				_(
					"Cannot create a Cost Center for this division. Set a default Company"
					" first or pick a Cost Center manually."
				),
				title=_("Cost Center Required"),
			)

		self.cost_center = (
			frappe.get_doc(
				{
					"doctype": "Cost Center",
					"cost_center_name": self.division_name,
					"company": company,
					"parent_cost_center": root,
					"is_group": 0,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
