# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate

from vmg_procurement.utils.naming import make_vmg_name
from vmg_procurement.utils.settings import get_settings

WORKFLOW_STATE_TO_STATUS = {
	"Pending Division Approval": "Pending Approval",
	"Pending CFO Approval": "Pending Approval",
	"Pending GM Approval": "Pending Approval",
	"Approved": "Approved",
	"Rejected": "Rejected",
}

# (state cleared by an Approve action, state entered) -> stamp fields
APPROVAL_STAMPS = {
	("Pending Division Approval", "Pending CFO Approval"): (
		"division_approved_by",
		"division_approved_on",
	),
	("Pending CFO Approval", "Pending GM Approval"): ("cfo_approved_by", "cfo_approved_on"),
	("Pending GM Approval", "Approved"): ("gm_approved_by", "gm_approved_on"),
}


class VMGPurchaseRequisition(Document):
	def autoname(self):
		if not self.division:
			frappe.throw(_("Select a Division first: it drives the requisition number"))
		prefix = frappe.db.get_value("VMG Division", self.division, "prefix")
		if not prefix:
			frappe.throw(_("Division {0} has no prefix set").format(frappe.bold(self.division)))
		self.name = make_vmg_name("PR", prefix, "#####", self.requisition_date)

	def before_insert(self):
		if not self.requested_by:
			self.requested_by = frappe.session.user

	def validate(self):
		self.sync_uniform_items()
		self.validate_dates()
		self.validate_items()
		self.validate_asset_items()
		self.validate_original_document()
		self.calculate_totals()
		self.set_budget_position()
		if self.docstatus.is_draft():
			self.status = "Draft"
		self.suppress_notifications_if_disabled()

	# --- staff uniform requisitions ----------------------------------------

	@property
	def is_uniform_requisition(self):
		return self.requisition_type == "Staff Uniform and PPE"

	def sync_uniform_items(self):
		"""Staff Uniform and PPE requisitions are captured per employee in
		uniform_employees; the requisition items are rebuilt from those rows
		(grouped by item type + size + item code) so the rest of the chain
		works on ordinary description lines."""
		if not self.is_uniform_requisition:
			self.set("uniform_employees", [])
			return
		if not self.uniform_employees:
			if self.docstatus.is_draft():
				return
			frappe.throw(
				_("Add at least one row to Uniform Employees for a Staff Uniform and PPE requisition"),
				title=_("Uniform Rows Missing"),
			)

		from vmg_procurement.vmg_procurement.doctype.vmg_ppe_and_uniform_handover.vmg_ppe_and_uniform_handover import (
			get_last_issue_date,
		)

		settings = get_settings()
		months = cint(settings.get("uniform_reissue_months")) or 12
		cutoff = frappe.utils.add_months(getdate(nowdate()), -months)
		early = []
		for row in self.uniform_employees:
			if flt(row.qty) <= 0:
				frappe.throw(
					_("Uniform row {0}: Quantity must be greater than zero").format(row.idx)
				)
			row.estimated_amount = flt(row.qty) * flt(row.estimated_rate)
			row.previous_issue_date = get_last_issue_date(row.employee, row.item_type)
			if row.previous_issue_date and getdate(row.previous_issue_date) > cutoff:
				early.append(
					_("Row {0}: {1} received a {2} on {3}").format(
						row.idx,
						frappe.bold(row.employee_name or row.employee),
						row.item_type,
						frappe.utils.formatdate(row.previous_issue_date),
					)
				)
		if early:
			frappe.msgprint(
				_("Issued within the last {0} months:").format(months)
				+ "<br>"
				+ "<br>".join(early),
				title=_("Early Reissue"),
				indicator="orange",
			)

		grouped, order = {}, []
		for row in self.uniform_employees:
			key = (row.item_type, row.size or "", row.item_code or "")
			if key not in grouped:
				grouped[key] = {"qty": 0.0, "value": 0.0}
				order.append(key)
			grouped[key]["qty"] += flt(row.qty)
			grouped[key]["value"] += flt(row.qty) * flt(row.estimated_rate)

		self.set("items", [])
		for key in order:
			item_type, size, item_code = key
			data = grouped[key]
			description = item_type + (f" - Size {size}" if size else "")
			self.append(
				"items",
				{
					"item_code": item_code or None,
					"description": _("{0} (staff uniform issue)").format(description),
					"qty": data["qty"],
					"uom": "Nos",
					"estimated_rate": (data["value"] / data["qty"]) if data["qty"] else 0,
				},
			)

	def before_update_after_submit(self):
		self.validate_rejection_reason()
		if self.workflow_state == "Approved" and self.has_value_changed("workflow_state"):
			self.run_budget_check(exclude_self=True)
		self.suppress_notifications_if_disabled()

	def on_update_after_submit(self):
		self.stamp_approval()
		self.sync_status_with_workflow_state()

	def before_submit(self):
		self.validate_policy_fields()
		self.run_budget_check()

	def validate_policy_fields(self):
		"""Same policy as the LPO (F04): the charge target must be known from
		the start of the chain."""
		if not (self.project or self.job_number):
			frappe.throw(
				_("Either a Project or a Job Number is mandatory on a Purchase Requisition"),
				title=_("Policy Field Missing"),
			)

	def on_submit(self):
		self.db_set("status", "Pending Approval", update_modified=False)

	def run_budget_check(self, exclude_self=False):
		from vmg_procurement.utils.budget import check_budget, record_budget_override

		if check_budget(self, "budget_action_on_requisition", exclude_self=exclude_self):
			record_budget_override(self)

	def set_budget_position(self):
		from vmg_procurement.utils.budget import get_position_summary

		cost_center = self.cost_center or frappe.db.get_value(
			"VMG Division", self.division, "cost_center"
		)
		if self.project and cost_center:
			self.budget_position = get_position_summary(
				self.project, cost_center, posting_date=self.requisition_date
			)
		else:
			self.budget_position = None

	def before_cancel(self):
		# before_cancel, so the block happens before any docstatus write
		self.validate_no_downstream_documents()

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	def validate_rejection_reason(self):
		if self.workflow_state == "Rejected" and not (self.rejection_reason or "").strip():
			frappe.throw(
				_("Rejection Reason is mandatory when rejecting a requisition"),
				title=_("Rejection Reason Required"),
			)

	def stamp_approval(self):
		before = self.get_doc_before_save()
		if not before or before.workflow_state == self.workflow_state:
			return
		stamp = APPROVAL_STAMPS.get((before.workflow_state, self.workflow_state))
		if stamp:
			by_field, on_field = stamp
			self.db_set(by_field, frappe.session.user, update_modified=False)
			self.db_set(on_field, frappe.utils.now(), update_modified=False)

	def sync_status_with_workflow_state(self):
		status = WORKFLOW_STATE_TO_STATUS.get(self.workflow_state)
		if status and self.status != status:
			self.db_set("status", status, update_modified=False)

	def suppress_notifications_if_disabled(self):
		if not get_settings().notify_by_email:
			# empty list short-circuits Document.run_notifications for this save
			self.flags.notifications = []

	def validate_dates(self):
		if (
			self.requisition_date
			and self.required_by_date
			and getdate(self.required_by_date) < getdate(self.requisition_date)
		):
			frappe.throw(
				_("Required By Date cannot be earlier than the Requisition Date"),
				title=_("Invalid Dates"),
			)

	def validate_items(self):
		for item in self.items:
			if not (item.description or "").strip():
				frappe.throw(_("Row {0}: Description is mandatory").format(item.idx))
			if flt(item.qty) <= 0:
				frappe.throw(_("Row {0}: Quantity must be greater than zero").format(item.idx))

	def validate_asset_items(self):
		if self.requisition_type != "Asset":
			return
		for item in self.items:
			if not item.item_code:
				frappe.throw(
					_(
						"Row {0}: Item Code is mandatory for an Asset requisition. Assets are"
						" received into inventory and must use a fixed asset Item."
					).format(item.idx),
					title=_("Fixed Asset Item Required"),
				)
			if not frappe.db.get_value("Item", item.item_code, "is_fixed_asset"):
				frappe.throw(
					_(
						"Row {0}: Item {1} is not a fixed asset item. Asset requisitions must"
						" use an Item with 'Is Fixed Asset' enabled so the purchase can flow"
						" through the core asset chain."
					).format(item.idx, frappe.bold(item.item_code)),
					title=_("Fixed Asset Item Required"),
				)

	def validate_original_document(self):
		if (self.source == "Procurement Offline" or self.is_emergency) and not self.original_document:
			frappe.throw(
				_(
					"Signed Copy or Email or WhatsApp Screenshot is mandatory when the source"
					" is Procurement Offline or the requisition is an emergency"
				),
				title=_("Attachment Required"),
			)

	def calculate_totals(self):
		total_qty = total_value = 0.0
		for item in self.items:
			item.estimated_amount = flt(item.qty) * flt(item.estimated_rate)
			total_qty += flt(item.qty)
			total_value += item.estimated_amount
		self.total_qty = total_qty
		self.total_estimated_value = total_value

	def validate_no_downstream_documents(self):
		"""Block cancellation once any downstream document exists."""
		from vmg_procurement.utils.routing import get_downstream_documents

		downstream = get_downstream_documents(self.name)
		if downstream:
			links = ", ".join(
				f"{doctype} {frappe.bold(name)}" for doctype, name in downstream
			)
			frappe.throw(
				_(
					"Cannot cancel this requisition: downstream documents exist ({0})."
					" Cancel those first."
				).format(links),
				title=_("Downstream Documents Exist"),
			)
