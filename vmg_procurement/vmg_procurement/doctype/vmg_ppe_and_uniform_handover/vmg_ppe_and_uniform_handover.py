# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt
from frappe.model.document import Document

from vmg_procurement.utils.naming import make_vmg_name


class VMGPPEandUniformHandover(Document):
	def autoname(self):
		if not self.division:
			frappe.throw(_("Select a Division first: it drives the handover number"))
		prefix = frappe.db.get_value("VMG Division", self.division, "prefix")
		if not prefix:
			frappe.throw(_("Division {0} has no prefix set").format(frappe.bold(self.division)))
		self.name = make_vmg_name("PPE", prefix, "#####", self.handover_date)

	def validate(self):
		for row in self.items:
			if flt(row.qty) <= 0:
				frappe.throw(_("Row {0}: Quantity must be greater than zero").format(row.idx))
			if not row.issue_date:
				row.issue_date = self.handover_date
		if self.docstatus.is_draft():
			self.status = "Draft"

	def on_submit(self):
		self.db_set("status", "Issued", update_modified=False)

	def on_update_after_submit(self):
		if self.status in ("Issued", "Acknowledged"):
			acknowledged = all(cint(row.employee_acknowledged) for row in self.items)
			target = "Acknowledged" if acknowledged else "Issued"
			if self.status != target:
				self.db_set("status", target, update_modified=False)

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	@frappe.whitelist()
	def get_items_from_uniform_request(self):
		"""Pull the employee lines from the linked Staff Uniform and PPE
		purchase requisition (its uniform_employees table)."""
		if self.docstatus != 0:
			frappe.throw(_("Items can only be pulled into a draft handover"))
		if not self.purchase_requisition:
			frappe.throw(_("Select a Purchase Requisition first"))
		requisition = frappe.get_doc("VMG Purchase Requisition", self.purchase_requisition)
		if requisition.requisition_type != "Staff Uniform and PPE":
			frappe.throw(
				_("{0} is a {1} requisition: only Staff Uniform and PPE requisitions carry employee lines").format(
					requisition.name, requisition.requisition_type
				),
				title=_("Wrong Requisition Type"),
			)
		if requisition.docstatus != 1 or requisition.workflow_state != "Approved":
			frappe.throw(
				_("{0} is not Approved: only approved requisitions can be handed over").format(
					requisition.name
				),
				title=_("Not Approved"),
			)
		self.division = self.division or requisition.division
		self.project = self.project or requisition.project
		self.cost_center = self.cost_center or requisition.cost_center
		self.set("items", [])
		for row in requisition.uniform_employees:
			self.append(
				"items",
				{
					"employee": row.employee,
					"employee_name": row.employee_name,
					"designation": row.designation,
					"item_type": row.item_type,
					"item_code": row.item_code,
					"size": row.size,
					"qty": row.qty,
					"issue_date": self.handover_date,
				},
			)


def get_last_issue_date(employee, item_type):
	"""Latest submitted handover of this item type to the employee: drives the
	previous-issue-date column and early-reissue warning on the requisition."""
	if not (employee and item_type):
		return None
	return frappe.db.sql(
		"""
		select max(coalesce(item.issue_date, handover.handover_date))
		from `tabVMG PPE Handover Item` item
		join `tabVMG PPE and Uniform Handover` handover on handover.name = item.parent
		where handover.docstatus = 1 and item.employee = %s and item.item_type = %s
		""",
		(employee, item_type),
	)[0][0]
