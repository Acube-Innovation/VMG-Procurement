# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from vmg_procurement.utils.naming import make_vmg_name
from vmg_procurement.utils.settings import get_settings
from vmg_procurement.vmg_procurement.doctype.vmg_local_purchase_order.vmg_local_purchase_order import (
	validate_lpo_ready_for_receipt,
)

# Submitting a receipt goes straight to Approved: procurement approval was
# dropped by patches/v0_1/drop_grn_procurement_approval.py, since receiving is a
# record of what arrived rather than a decision. "Rejected" is kept because the
# state is still defined on the workflow, but nothing routes to it today.
WORKFLOW_STATE_TO_STATUS = {
	"Approved": "To Bill",
	"Rejected": "Rejected",
}


class VMGPurchaseReceipt(Document):
	def autoname(self):
		if not self.division:
			frappe.throw(_("Select a Division first: it drives the receipt number"))
		prefix = frappe.db.get_value("VMG Division", self.division, "prefix")
		if not prefix:
			frappe.throw(_("Division {0} has no prefix set").format(frappe.bold(self.division)))
		self.name = make_vmg_name("GRN", prefix, "#####", self.receipt_date)

	def validate(self):
		self.validate_quantities()
		self.validate_expense_accounts()
		self.compute_row_values()
		self.compute_totals()
		self.compute_acceptance_status()
		self.validate_rejection_reason()
		if self.docstatus.is_draft():
			self.status = "Draft"
		self.suppress_notifications_if_disabled()

	def validate_expense_accounts(self):
		for item in self.items:
			if not item.expense_account:
				continue
			account_type = frappe.db.get_value("Account", item.expense_account, "account_type")
			if account_type in ("Receivable", "Payable"):
				frappe.throw(
					_(
						"Row {0}: {1} is a {2} account and cannot be used as the Expense Account"
						" (it would need a party on every posting). Pick an expense ledger instead."
					).format(item.idx, frappe.bold(item.expense_account), account_type),
					title=_("Invalid Expense Account"),
				)

	def before_submit(self):
		if self.local_purchase_order:
			validate_lpo_ready_for_receipt(
				self.local_purchase_order, action=_("received against")
			)
		if not self.delivery_note_attachment:
			frappe.throw(
				_("The signed delivery note must be attached before submitting for approval"),
				title=_("Signed Delivery Note Required"),
			)

	def before_update_after_submit(self):
		if self.workflow_state == "Rejected" and not (self.rejection_reason or "").strip():
			frappe.throw(
				_("Rejection Reason is mandatory when rejecting a receipt"),
				title=_("Rejection Reason Required"),
			)
		self.suppress_notifications_if_disabled()

	def on_update_after_submit(self):
		self.sync_status_with_workflow_state()

	def on_submit(self):
		# Submitting lands straight on Approved now that procurement approval is
		# gone, so the status has to come from the workflow state. Hardcoding
		# "Pending Approval" here left submitted receipts unbillable.
		self.sync_status_with_workflow_state()
		update_lpo_receipt_status(self.local_purchase_order)

	def sync_status_with_workflow_state(self):
		status = WORKFLOW_STATE_TO_STATUS.get(self.workflow_state)
		if status and self.status != status:
			self.db_set("status", status, update_modified=False)

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
		update_lpo_receipt_status(self.local_purchase_order)

	def suppress_notifications_if_disabled(self):
		if not get_settings().notify_by_email:
			self.flags.notifications = []

	# --- quantities ---------------------------------------------------------

	def validate_quantities(self):
		tolerance = flt(get_settings().get("over_receipt_tolerance_percent"))
		for item in self.items:
			if flt(item.received_qty) <= 0:
				frappe.throw(_("Row {0}: Received Qty must be greater than zero").format(item.idx))
			if item.accepted_qty is None:
				item.accepted_qty = item.received_qty
			if flt(item.accepted_qty) > flt(item.received_qty):
				frappe.throw(
					_("Row {0}: Accepted Qty cannot exceed Received Qty").format(item.idx)
				)
			if flt(item.accepted_qty) < 0:
				frappe.throw(_("Row {0}: Accepted Qty cannot be negative").format(item.idx))
			if item.lpo_item and flt(item.ordered_qty):
				allowed = flt(item.ordered_qty) * (1 + tolerance / 100.0)
				cumulative = flt(item.previously_received_qty) + flt(item.received_qty)
				if cumulative > allowed + 1e-9:
					frappe.throw(
						_(
							"Row {0}: received {1} plus previously received {2} exceeds"
							" the ordered quantity {3} (allowed with {4}% tolerance: {5})"
						).format(
							item.idx,
							item.received_qty,
							item.previously_received_qty,
							item.ordered_qty,
							tolerance,
							allowed,
						),
						title=_("Over Receipt"),
					)

	def compute_row_values(self):
		partial = 0
		for item in self.items:
			item.rejected_qty = flt(item.received_qty) - flt(item.accepted_qty)
			item.amount = flt(item.accepted_qty) * flt(item.rate)
			if item.lpo_item and flt(item.ordered_qty):
				item.pending_qty = max(
					flt(item.ordered_qty)
					- flt(item.previously_received_qty)
					- flt(item.received_qty),
					0,
				)
				if item.pending_qty > 0:
					partial = 1
			else:
				item.pending_qty = 0
		self.is_partial = partial

	def compute_totals(self):
		self.total = sum(flt(item.amount) for item in self.items)
		vat_rate = 5.0
		if self.local_purchase_order:
			vat_rate = flt(
				frappe.db.get_value("VMG Local Purchase Order", self.local_purchase_order, "vat_rate")
			)
		self.vat_amount = flt(self.total) * vat_rate / 100.0
		self.grand_total = flt(self.total) + flt(self.vat_amount)

	def compute_acceptance_status(self):
		received = sum(flt(item.received_qty) for item in self.items)
		accepted = sum(flt(item.accepted_qty) for item in self.items)
		rejected = sum(flt(item.rejected_qty) for item in self.items)
		if not received:
			self.acceptance_status = "Pending"
		elif rejected == 0:
			self.acceptance_status = "Accepted"
		elif accepted == 0:
			self.acceptance_status = "Rejected"
		else:
			self.acceptance_status = "Partially Accepted"

	def validate_rejection_reason(self):
		rejected = sum(flt(item.rejected_qty) for item in self.items)
		if rejected > 0 and not (self.rejection_reason or "").strip():
			frappe.throw(
				_("Rejection Reason is mandatory: {0} unit(s) were rejected").format(rejected),
				title=_("Rejection Reason Required"),
			)

	# --- pull from LPO -------------------------------------------------------

	@frappe.whitelist()
	def get_items_from_lpo(self):
		"""Pull only LPO lines with a pending quantity; received_qty defaults
		to the pending quantity."""
		if self.docstatus != 0:
			frappe.throw(_("Items can only be pulled into a draft receipt"))
		if not self.local_purchase_order:
			frappe.throw(_("Select a Local Purchase Order first"))
		validate_lpo_ready_for_receipt(self.local_purchase_order, action=_("received against"))

		lpo = frappe.get_doc("VMG Local Purchase Order", self.local_purchase_order)
		self.supplier = lpo.supplier
		self.set("items", [])
		for row in lpo.items:
			pending = flt(row.qty) - flt(row.received_qty)
			if pending <= 0:
				continue
			self.append(
				"items",
				{
					"lpo_item": row.name,
					"item_code": row.item_code,
					"description": row.description,
					"uom": row.uom,
					"ordered_qty": row.qty,
					"previously_received_qty": row.received_qty,
					"received_qty": pending,
					"accepted_qty": pending,
					"rate": row.rate,
					"expense_account": row.expense_account,
				},
			)
		if not self.items:
			frappe.throw(
				_("{0} is already fully received: nothing is pending").format(
					self.local_purchase_order
				),
				title=_("Nothing Pending"),
			)
		self.compute_row_values()
		self.compute_totals()
		self.compute_acceptance_status()


def update_lpo_receipt_status(lpo_name):
	"""Recompute LPO item received/pending quantities, per_received and the
	receipt status ladder from all submitted receipts. Idempotent: submit and
	cancel both just call it."""
	if not lpo_name:
		return
	lpo = frappe.get_doc("VMG Local Purchase Order", lpo_name)
	if lpo.docstatus != 1:
		return

	total_ordered = total_received = 0.0
	for row in lpo.items:
		received = flt(
			frappe.db.sql(
				"""
				select sum(item.accepted_qty)
				from `tabVMG Purchase Receipt Item` item
				join `tabVMG Purchase Receipt` receipt on receipt.name = item.parent
				where receipt.docstatus = 1 and item.lpo_item = %s
				""",
				row.name,
			)[0][0]
		)
		row.db_set("received_qty", received, update_modified=False)
		row.db_set("pending_qty", max(flt(row.qty) - received, 0), update_modified=False)
		total_ordered += flt(row.qty)
		total_received += min(received, flt(row.qty))

	per_received = (total_received / total_ordered * 100.0) if total_ordered else 0
	lpo.db_set("per_received", per_received, update_modified=False)

	if lpo.status in ("To Receive", "Partially Received", "Fully Received"):
		if per_received >= 100:
			target = "Fully Received"
		elif per_received > 0:
			target = "Partially Received"
		else:
			target = "To Receive"
		if lpo.status != target:
			lpo.db_set("status", target, update_modified=False)


@frappe.whitelist()
def make_vmg_supplier_invoice(source_name, target_doc=None):
	"""Approved receipt -> VMG Supplier Invoice (built in step 13)."""
	from frappe.model.mapper import get_mapped_doc

	docstatus, workflow_state = frappe.db.get_value(
		"VMG Purchase Receipt", source_name, ["docstatus", "workflow_state"]
	)
	if docstatus != 1 or workflow_state != "Approved":
		frappe.throw(
			_(
				"Only an Approved receipt may be billed (current state: {0})"
			).format(frappe.bold(workflow_state or "Draft")),
			title=_("Not Approved"),
		)
	if not frappe.db.exists("DocType", "VMG Supplier Invoice"):
		frappe.throw(
			_(
				"VMG Supplier Invoice is not built yet: it arrives in build step {0}."
				" Nothing was created."
			).format(frappe.bold("13 supplier invoice and accounting")),
			title=_("Not Available Yet"),
		)

	def set_missing_values(source, target):
		target.purchase_receipt = source.name
		target.local_purchase_order = source.local_purchase_order
		target.purchase_requisition = source.purchase_requisition
		target.supplier = source.supplier

	def update_item(obj, target, source_parent):
		target.qty = obj.accepted_qty
		target.receipt_item = obj.name
		target.lpo_item = obj.lpo_item

	return get_mapped_doc(
		"VMG Purchase Receipt",
		source_name,
		{
			"VMG Purchase Receipt": {
				"doctype": "VMG Supplier Invoice",
				"field_map": {"name": "purchase_receipt"},
				"validation": {"docstatus": ["=", 1]},
			},
			"VMG Purchase Receipt Item": {
				"doctype": "VMG Supplier Invoice Item",
				"field_map": {"name": "receipt_item"},
				"postprocess": update_item,
			},
		},
		target_doc,
		set_missing_values,
	)


@frappe.whitelist()
def make_lpo_from_receipt(source_name, target_doc=None):
	"""Standalone receipt (goods arrived on a verbal/emergency instruction)
	-> direct VMG Local Purchase Order demanding a justification."""
	from frappe.model.mapper import get_mapped_doc

	if frappe.db.get_value("VMG Purchase Receipt", source_name, "local_purchase_order"):
		frappe.throw(
			_("This receipt already references a Local Purchase Order"),
			title=_("Order Exists"),
		)

	def set_missing_values(source, target):
		target.order_route = "Direct Order"
		target.is_direct_order = 1
		target.order_date = source.receipt_date

	def update_item(obj, target, source_parent):
		target.qty = obj.received_qty
		target.rate = obj.rate

	return get_mapped_doc(
		"VMG Purchase Receipt",
		source_name,
		{
			"VMG Purchase Receipt": {"doctype": "VMG Local Purchase Order"},
			"VMG Purchase Receipt Item": {
				"doctype": "VMG LPO Item",
				"postprocess": update_item,
			},
		},
		target_doc,
		set_missing_values,
	)
