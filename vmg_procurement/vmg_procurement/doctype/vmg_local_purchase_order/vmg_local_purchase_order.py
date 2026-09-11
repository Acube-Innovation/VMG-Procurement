# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

from typing import NamedTuple

import frappe
from frappe import _
from frappe.contacts.doctype.address.address import (
	get_address_display,
	get_default_address,
	get_preferred_address,
)
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, money_in_words

from vmg_procurement.utils.naming import make_vmg_name
from vmg_procurement.utils.routing import DIRECT_ORDER_ROLE
from vmg_procurement.utils.settings import get_settings

PRINT_FORMAT = "VMG Local Purchase Order VMG-PRO-F04"


class AddressSlot(NamedTuple):
	"""One address on the order: the link, its read-only rendering, the fields
	used to type a new one, and which Address flag makes it the supplier's
	default for that purpose."""

	link_field: str
	display_field: str
	prefix: str
	address_type: str
	preferred_key: str
	label: str


ADDRESS_SLOTS = (
	AddressSlot(
		"delivery_address",
		"delivery_address_display",
		"new_delivery_address",
		"Shipping",
		"is_shipping_address",
		"Delivery Address",
	),
	AddressSlot(
		"invoicing_address",
		"invoicing_address_display",
		"new_invoicing_address",
		"Billing",
		"is_primary_address",
		"Invoicing Address",
	),
)

WORKFLOW_STATE_TO_STATUS = {
	"Pending CFO Approval": "Pending Approval",
	"Pending GM Approval": "Pending Approval",
	"Approved": "To Receive",
	"Rejected": "Rejected",
}

APPROVAL_STAMPS = {
	("Pending CFO Approval", "Pending GM Approval"): ("cfo_approved_by", "cfo_approved_on"),
	("Pending GM Approval", "Approved"): ("gm_approved_by", "gm_approved_on"),
}


class VMGLocalPurchaseOrder(Document):
	def autoname(self):
		if not self.division:
			frappe.throw(_("Select a Division first: it drives the LPO number"))
		prefix = frappe.db.get_value("VMG Division", self.division, "prefix")
		if not prefix:
			frappe.throw(_("Division {0} has no prefix set").format(frappe.bold(self.division)))
		self.name = make_vmg_name("LPO", prefix, "#####", self.order_date)

	def validate(self):
		self.set_order_route()
		self.validate_direct_order_permission()
		self.set_supplier_not_approved()
		self.validate_unapproved_supplier_route()
		self.set_required_date_from_requisition()
		self.set_week_number()
		self.set_addresses_from_supplier()
		self.set_address_displays()
		self.set_terms_defaults()
		self.set_item_defaults()
		self.validate_items()
		self.validate_duplicate_comparison_order()
		self.calculate_totals()
		self.set_budget_position()
		self.set_notification_flags()
		self.validate_amendment_receipts()
		if self.docstatus.is_draft():
			self.status = "Draft"
		self.suppress_notifications_if_disabled()

	def before_submit(self):
		# runs after validate, so the address exists before the rest of the
		# submit checks look at it
		self.create_addresses_if_needed()
		self.validate_addresses()
		self.validate_mandatory_policy_fields()
		self.validate_justifications()
		self.validate_terms()
		self.run_budget_check()

	def run_budget_check(self, exclude_self=False):
		from vmg_procurement.utils.budget import check_budget, record_budget_override

		if check_budget(self, "budget_action_on_lpo", exclude_self=exclude_self):
			record_budget_override(self)

	def set_budget_position(self):
		from vmg_procurement.utils.budget import get_position_summary

		if self.project and self.cost_center and self.items:
			self.budget_position = get_position_summary(
				self.project,
				self.cost_center,
				expense_account=self.items[0].expense_account,
				posting_date=self.order_date,
			)
		else:
			self.budget_position = None

	def before_update_after_submit(self):
		self.validate_rejection_reason()
		if self.workflow_state == "Approved" and self.has_value_changed("workflow_state"):
			self.run_budget_check(exclude_self=True)
		self.suppress_notifications_if_disabled()

	def on_update_after_submit(self):
		self.stamp_approval()
		self.sync_status_with_workflow_state()

	def on_submit(self):
		self.db_set("status", "Pending Approval", update_modified=False)
		update_requisition_ordered_qty(self.purchase_requisition)
		self.update_comparison_status(ordered=True)

	def before_cancel(self):
		self.validate_no_active_receipts(_("cancelled"))

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
		update_requisition_ordered_qty(self.purchase_requisition)
		self.update_comparison_status(ordered=False)

	# --- workflow (step 10) --------------------------------------------------

	def validate_rejection_reason(self):
		if self.workflow_state == "Rejected" and not (self.rejection_reason or "").strip():
			frappe.throw(
				_("Rejection Reason is mandatory when rejecting a Local Purchase Order"),
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
			self.flags.notifications = []

	def set_notification_flags(self):
		"""Subject prefix for the CFO/GM workflow notifications (the 140-char
		subject template cannot hold the jinja conditions itself)."""
		parts = []
		if self.is_direct_order:
			parts.append("DIRECT ORDER")
		if self.supplier_not_approved:
			parts.append("NON APPROVED SUPPLIER")
		self.notification_flags = (" + ".join(parts) + ": ") if parts else ""

	# --- receipt guards (step 12 hooks into these) ---------------------------

	def validate_amendment_receipts(self):
		if not self.amended_from or not frappe.db.exists("DocType", "VMG Purchase Receipt"):
			return
		receipts = frappe.get_all(
			"VMG Purchase Receipt",
			filters={"local_purchase_order": self.amended_from, "docstatus": ["<", 2]},
			pluck="name",
		)
		if receipts:
			frappe.throw(
				_(
					"{0} cannot be amended: receipt(s) {1} exist against it. Cancel"
					" the receipt(s) first."
				).format(self.amended_from, ", ".join(frappe.bold(r) for r in receipts)),
				title=_("Receipts Exist"),
			)

	def validate_no_active_receipts(self, action_label):
		if not frappe.db.exists("DocType", "VMG Purchase Receipt"):
			return
		receipts = frappe.get_all(
			"VMG Purchase Receipt",
			filters={"local_purchase_order": self.name, "docstatus": ["<", 2]},
			pluck="name",
		)
		if receipts:
			frappe.throw(
				_(
					"This order cannot be {0}: receipt(s) {1} exist against it."
					" Cancel the receipt(s) first."
				).format(action_label, ", ".join(frappe.bold(r) for r in receipts)),
				title=_("Receipts Exist"),
			)

	# --- routing rules ------------------------------------------------------

	def set_order_route(self):
		if self.docstatus != 0:
			return
		if not self.order_route:
			self.order_route = "From Comparison" if self.quotation_comparison else "Direct Order"
		self.is_direct_order = 1 if self.order_route == "Direct Order" else 0

	def validate_direct_order_permission(self):
		if self.docstatus != 0 or not self.is_direct_order:
			return
		if DIRECT_ORDER_ROLE not in frappe.get_roles():
			frappe.throw(
				_(
					"Direct orders (skipping the quotation comparison) are restricted"
					" to the role {0}"
				).format(frappe.bold(DIRECT_ORDER_ROLE)),
				frappe.PermissionError,
				title=_("Not Permitted"),
			)

	def set_supplier_not_approved(self):
		self.supplier_not_approved = 0 if cint(
			frappe.db.get_value("Supplier", self.supplier, "vmg_is_approved")
		) else 1

	def validate_unapproved_supplier_route(self):
		if not self.supplier_not_approved:
			return
		if self.order_route == "Repeat Order":
			frappe.throw(
				_(
					"Supplier {0} is not on the Approved Supplier List: only a Direct"
					" Order (or an approved comparison) may use an unapproved supplier"
				).format(frappe.bold(self.supplier_name or self.supplier)),
				title=_("Unapproved Supplier"),
			)
		frappe.msgprint(
			_(
				"Supplier {0} is not on the Approved Supplier List: a justification"
				" is required"
			).format(frappe.bold(self.supplier_name or self.supplier)),
			indicator="orange",
		)

	# --- field computation --------------------------------------------------

	def set_required_date_from_requisition(self):
		"""Default the required delivery date from the linked requisition's
		Required By date (only when neither delivery nor service date is set)."""
		if self.required_delivery_date or self.service_visit_date or not self.purchase_requisition:
			return
		self.required_delivery_date = frappe.db.get_value(
			"VMG Purchase Requisition", self.purchase_requisition, "required_by_date"
		)

	def set_week_number(self):
		anchor = self.required_delivery_date or self.service_visit_date
		if anchor and not self.delivery_week_number:
			self.delivery_week_number = f"WK{getdate(anchor).isocalendar()[1]:02d}"

	def set_addresses_from_supplier(self):
		"""Pick up the supplier's own addresses when none have been chosen.

		Mirrors what the form does on the client, so an order created by API or
		by `make_local_purchase_order` gets the same defaults.
		"""
		if not self.supplier:
			return
		for slot in ADDRESS_SLOTS:
			if self.get(slot.link_field):
				continue
			self.set(
				slot.link_field, get_supplier_default_address(self.supplier, slot.preferred_key)
			)

	def create_addresses_if_needed(self):
		"""Turn address lines typed on the order into real Address documents.

		A supplier nobody has ordered from yet has no Address on file, so the
		lines are captured on the order itself and become an Address linked to
		the supplier on submit. The next order for that supplier finds it.
		"""
		if not self.supplier:
			return

		created = False
		for slot in ADDRESS_SLOTS:
			if self.get(slot.link_field):
				continue
			line1 = (self.get(f"{slot.prefix}_line1") or "").strip()
			if not line1:
				continue  # validate_addresses reports this

			address = frappe.get_doc(
				{
					"doctype": "Address",
					"address_title": self.supplier_name or self.supplier,
					"address_type": slot.address_type,
					"address_line1": line1,
					"address_line2": (self.get(f"{slot.prefix}_line2") or "").strip(),
					"city": (self.get(f"{slot.prefix}_city") or "").strip(),
					"state": (self.get(f"{slot.prefix}_state") or "").strip(),
					"pincode": (self.get(f"{slot.prefix}_pincode") or "").strip(),
					"country": self.get(f"{slot.prefix}_country"),
					slot.preferred_key: 1,
					"links": [{"link_doctype": "Supplier", "link_name": self.supplier}],
				}
			).insert(ignore_permissions=True)

			self.set(slot.link_field, address.name)
			# the address now lives as its own document; keep one copy, not two
			for part in ("line1", "line2", "city", "state", "pincode", "country"):
				self.set(f"{slot.prefix}_{part}", None)
			created = True

		if created:
			self.set_address_displays()

	def validate_addresses(self):
		for slot in ADDRESS_SLOTS:
			if self.get(slot.link_field):
				continue
			frappe.throw(
				_(
					"Select {0}, or fill in its Address Line 1 and one will be created"
					" against {1}."
				).format(
					frappe.bold(_(slot.label)),
					frappe.bold(self.supplier_name or self.supplier or _("the supplier")),
				),
				title=_("{0} Required").format(_(slot.label)),
			)

	def set_address_displays(self):
		self.delivery_address_display = (
			get_address_display(self.delivery_address) if self.delivery_address else None
		)
		self.invoicing_address_display = (
			get_address_display(self.invoicing_address) if self.invoicing_address else None
		)
		if self.supplier_contact:
			contact = frappe.db.get_value(
				"Contact",
				self.supplier_contact,
				["first_name", "last_name", "email_id", "mobile_no"],
				as_dict=True,
			)
			parts = [
				" ".join(filter(None, [contact.first_name, contact.last_name])),
				contact.email_id,
				contact.mobile_no,
			]
			self.contact_display = "\n".join(p for p in parts if p)
		else:
			self.contact_display = None

	def set_terms_defaults(self):
		settings = get_settings()
		if not self.terms_template and settings.default_terms:
			self.terms_template = settings.default_terms
		if not self.terms and self.terms_template:
			self.terms = frappe.db.get_value("Terms and Conditions", self.terms_template, "terms")

	def set_item_defaults(self):
		default_expense_account = get_settings().default_expense_account
		for item in self.items:
			if not item.expense_account and default_expense_account:
				item.expense_account = default_expense_account
			if not item.cost_center:
				item.cost_center = self.cost_center
			if not item.project:
				item.project = self.project
			item.pending_qty = flt(item.qty) - flt(item.received_qty)

	def validate_items(self):
		for item in self.items:
			if not (item.description or "").strip():
				frappe.throw(_("Row {0}: Description is mandatory").format(item.idx))
			if flt(item.qty) <= 0:
				frappe.throw(_("Row {0}: Quantity must be greater than zero").format(item.idx))
			if flt(item.rate) <= 0:
				frappe.throw(_("Row {0}: Rate must be greater than zero").format(item.idx))
			if item.expense_account:
				account_type = frappe.db.get_value("Account", item.expense_account, "account_type")
				if account_type in ("Receivable", "Payable"):
					frappe.throw(
						_(
							"Row {0}: {1} is a {2} account and cannot be used as the Expense Account"
							" (it would need a party on every posting). Pick an expense ledger instead."
						).format(item.idx, frappe.bold(item.expense_account), account_type),
						title=_("Invalid Expense Account"),
					)

	def validate_duplicate_comparison_order(self):
		"""One active LPO per awarded quotation of a comparison: a split award
		creates several LPOs, but never two against the same quotation."""
		if not (self.quotation_comparison and self.supplier_quotation):
			return
		duplicate = frappe.db.exists(
			"VMG Local Purchase Order",
			{
				"quotation_comparison": self.quotation_comparison,
				"supplier_quotation": self.supplier_quotation,
				"docstatus": ["<", 2],
				"name": ["!=", self.name],
			},
		)
		if duplicate:
			frappe.throw(
				_(
					"{0} already covers quotation {1} of comparison {2}: cancel it"
					" first or amend it instead"
				).format(
					frappe.bold(duplicate),
					frappe.bold(self.supplier_quotation),
					frappe.bold(self.quotation_comparison),
				),
				title=_("Duplicate Order"),
			)

	def calculate_totals(self):
		total = 0.0
		for item in self.items:
			item.amount = flt(item.qty) * flt(item.rate)
			total += item.amount
		self.total = total
		self.net_total = flt(self.total) - flt(self.discount_amount)
		self.vat_amount = flt(self.net_total) * flt(self.vat_rate) / 100.0
		self.grand_total = flt(self.net_total) + flt(self.vat_amount)
		self.in_words = money_in_words(self.grand_total, "AED")

	# --- submit-time policy checks -----------------------------------------

	def validate_mandatory_policy_fields(self):
		"""LPO policy (F04): order no+date, project/job number, delivery and
		invoicing address, required delivery date or service visit date."""
		if not (self.project or self.job_number):
			frappe.throw(
				_("Either a Project or a Job Number is mandatory on a Local Purchase Order"),
				title=_("Policy Field Missing"),
			)
		if not (self.required_delivery_date or self.service_visit_date):
			frappe.throw(
				_("Either a Required Delivery Date or a Service Visit Date is mandatory"),
				title=_("Policy Field Missing"),
			)

	def validate_justifications(self):
		if self.is_direct_order and not (self.direct_order_justification or "").strip():
			frappe.throw(
				_("Direct Order Justification is mandatory: this order skipped the comparison stage"),
				title=_("Justification Required"),
			)
		if self.supplier_not_approved and not (
			self.non_approved_supplier_justification or ""
		).strip():
			frappe.throw(
				_(
					"Non Approved Supplier Justification is mandatory: {0} is not on"
					" the Approved Supplier List"
				).format(frappe.bold(self.supplier_name or self.supplier)),
				title=_("Justification Required"),
			)

	def validate_terms(self):
		if not cint(get_settings().terms_mandatory_on_lpo):
			return
		if not self.terms_template:
			frappe.throw(
				_("Terms Template is mandatory on Local Purchase Orders (see VMG Procurement Settings)"),
				title=_("Terms Required"),
			)
		if not frappe.utils.strip_html(self.terms or "").strip():
			frappe.throw(
				_("Terms and Conditions must not be empty"),
				title=_("Terms Required"),
			)

	# --- status propagation ---------------------------------------------------

	def update_comparison_status(self, ordered):
		if not self.quotation_comparison:
			return
		comparison = frappe.db.get_value(
			"VMG Quotation Comparison",
			self.quotation_comparison,
			["docstatus", "status"],
			as_dict=True,
		)
		if not comparison or comparison.docstatus != 1:
			return
		if comparison.status in ("Rejected", "Cancelled"):
			return
		from vmg_procurement.vmg_procurement.doctype.vmg_quotation_comparison.vmg_quotation_comparison import (
			compute_ordered_status,
		)

		new_status = compute_ordered_status(self.quotation_comparison)
		if comparison.status != new_status:
			frappe.db.set_value(
				"VMG Quotation Comparison", self.quotation_comparison, "status", new_status,
				update_modified=False,
			)

	# --- repeat order route ---------------------------------------------------

	@frappe.whitelist()
	def get_items_from_previous_order(self, previous_order):
		"""Repeat Order route: copy items, rates, expense accounts and terms
		from a previous submitted LPO of the same supplier. Quantities stay
		editable on the draft."""
		if self.docstatus != 0:
			frappe.throw(_("Items can only be pulled into a draft order"))
		previous = frappe.get_doc("VMG Local Purchase Order", previous_order)
		if previous.docstatus != 1:
			frappe.throw(_("{0} is not submitted: pick a submitted order").format(previous_order))
		if previous.supplier != self.supplier:
			frappe.throw(
				_("{0} belongs to {1}, not to this supplier").format(
					previous_order, frappe.bold(previous.supplier_name or previous.supplier)
				)
			)

		self.set("items", [])
		for row in previous.items:
			self.append(
				"items",
				{
					"item_code": row.item_code,
					"description": row.description,
					"qty": row.qty,
					"uom": row.uom,
					"rate": row.rate,
					"expense_account": row.expense_account,
					"remarks": row.remarks,
				},
			)
		self.terms_template = previous.terms_template
		self.terms = previous.terms
		self.vat_rate = previous.vat_rate
		self.discount_amount = previous.discount_amount
		self.order_route = "Repeat Order"
		self.is_direct_order = 0
		self.set_item_defaults()
		self.calculate_totals()


@frappe.whitelist()
def get_supplier_default_address(supplier, preferred_key="is_shipping_address"):
	"""The supplier's address for one purpose on the order.

	Delivery prefers the supplier's shipping address, invoicing prefers its
	primary one; either falls back to the other flag and then to any address
	linked to the supplier. Returns None when the supplier has none on file,
	which is what puts the address lines on the order itself.
	"""
	if not supplier:
		return None
	if preferred_key not in ("is_shipping_address", "is_primary_address"):
		preferred_key = "is_shipping_address"
	other_key = (
		"is_primary_address" if preferred_key == "is_shipping_address" else "is_shipping_address"
	)
	return (
		get_preferred_address("Supplier", supplier, preferred_key)
		or get_preferred_address("Supplier", supplier, other_key)
		or get_default_address("Supplier", supplier, preferred_key)
	)


@frappe.whitelist()
def send_to_supplier(lpo_name):
	"""Email the F04 PDF to the supplier contact, log a Communication on the
	timeline and stamp sent_to_supplier_on / sent_by. Only Approved orders may
	go out. Re-sending is allowed (the UI confirms first)."""
	doc = frappe.get_doc("VMG Local Purchase Order", lpo_name)
	doc.check_permission("email")
	validate_lpo_ready_for_receipt(lpo_name, action=_("sent to the supplier"))

	recipient = (
		doc.supplier_contact
		and frappe.db.get_value("Contact", doc.supplier_contact, "email_id")
	) or frappe.db.get_value("Supplier", doc.supplier, "email_id")
	if not recipient:
		frappe.throw(
			_(
				"No email address found: set a Supplier Contact with an email (or a"
				" primary contact on the supplier) before sending"
			),
			title=_("No Email Address"),
		)

	from frappe.core.doctype.communication.email import make as make_communication

	subject = _("Local Purchase Order {0}").format(doc.name)
	content = _(
		"Dear {0},<br><br>Please find attached our Local Purchase Order {1}."
		" Kindly acknowledge within 48 hours, otherwise the order is considered"
		" accepted.<br><br>Regards,<br>VMG Procurement Department"
	).format(doc.supplier_name or doc.supplier, doc.name)

	queued = True
	try:
		make_communication(
			doctype=doc.doctype,
			name=doc.name,
			recipients=recipient,
			subject=subject,
			content=content,
			send_email=True,
			print_format=PRINT_FORMAT,
			attach_document_print=True,
			communication_medium="Email",
			send_me_a_copy=False,
		)
	except Exception:
		# no outgoing Email Account (or SMTP failure): still log the issue on
		# the timeline so the manual send is on record
		frappe.log_error(title=f"LPO {doc.name}: email to supplier failed")
		queued = False
		make_communication(
			doctype=doc.doctype,
			name=doc.name,
			recipients=recipient,
			subject=subject,
			content=content
			+ "<br><i>"
			+ _("Automatic email failed: sent manually outside the system")
			+ "</i>",
			send_email=False,
			communication_medium="Email",
		)

	doc.db_set("sent_to_supplier_on", frappe.utils.now(), update_modified=False)
	doc.db_set("sent_by", frappe.session.user, update_modified=False)
	return {"recipient": recipient, "queued": queued}


def validate_lpo_ready_for_receipt(lpo_name, action=None):
	"""Server guard shared by Send to Supplier (step 10) and the purchase
	receipt (step 12): the LPO must be submitted AND workflow-Approved."""
	docstatus, workflow_state = frappe.db.get_value(
		"VMG Local Purchase Order", lpo_name, ["docstatus", "workflow_state"]
	)
	if docstatus != 1 or workflow_state != "Approved":
		frappe.throw(
			_(
				"Local Purchase Order {0} must be Approved before it can be {1}"
				" (current state: {2})"
			).format(
				lpo_name,
				action or _("processed further"),
				frappe.bold(workflow_state or "Draft"),
			),
			title=_("Not Approved"),
		)


def update_requisition_ordered_qty(purchase_requisition):
	"""Recompute ordered_qty and row status on the requisition items from all
	submitted LPOs. Idempotent, so submit and cancel both just call it."""
	if not purchase_requisition:
		return
	for row in frappe.get_all(
		"VMG Purchase Requisition Item",
		filters={"parent": purchase_requisition},
		fields=["name", "qty"],
	):
		ordered = flt(
			frappe.db.sql(
				"""
				select sum(item.qty)
				from `tabVMG LPO Item` item
				join `tabVMG Local Purchase Order` lpo on lpo.name = item.parent
				where lpo.docstatus = 1 and item.requisition_item = %s
				""",
				row.name,
			)[0][0]
		) + flt(
			# asset chain: core Purchase Orders carry vmg_requisition_item too
			frappe.db.sql(
				"""
				select sum(item.qty)
				from `tabPurchase Order Item` item
				join `tabPurchase Order` po on po.name = item.parent
				where po.docstatus = 1 and item.vmg_requisition_item = %s
				""",
				row.name,
			)[0][0]
		)
		frappe.db.set_value(
			"VMG Purchase Requisition Item",
			row.name,
			{
				"ordered_qty": ordered,
				"status": "Ordered" if ordered and ordered >= flt(row.qty) else "Pending",
			},
			update_modified=False,
		)


@frappe.whitelist()
def make_purchase_receipt(source_name, target_doc=None):
	"""Approved LPO -> VMG Purchase Receipt with the pending lines pulled in."""
	validate_lpo_ready_for_receipt(source_name, action=_("received against"))
	lpo = frappe.get_doc("VMG Local Purchase Order", source_name)

	receipt = frappe.new_doc("VMG Purchase Receipt")
	receipt.local_purchase_order = lpo.name
	receipt.purchase_requisition = lpo.purchase_requisition
	receipt.division = lpo.division
	receipt.project = lpo.project
	receipt.cost_center = lpo.cost_center
	receipt.get_items_from_lpo()
	return receipt


@frappe.whitelist()
def make_supplier_invoice(source_name, target_doc=None):
	"""Approved LPO -> VMG Supplier Invoice over the unbilled quantities.
	Rows carry lpo_item so billing status flows back to the order; when the
	goods came through a receipt, prefer creating the invoice from there so
	rows also carry the receipt reference."""
	lpo = frappe.get_doc("VMG Local Purchase Order", source_name)
	if lpo.docstatus != 1 or lpo.workflow_state != "Approved":
		frappe.throw(
			_("Only an Approved order may be billed (current state: {0})").format(
				frappe.bold(lpo.workflow_state or "Draft")
			),
			title=_("Not Approved"),
		)

	invoice = frappe.new_doc("VMG Supplier Invoice")
	invoice.local_purchase_order = lpo.name
	invoice.purchase_requisition = lpo.purchase_requisition
	invoice.supplier = lpo.supplier
	invoice.division = lpo.division
	invoice.project = lpo.project
	invoice.cost_center = lpo.cost_center
	invoice.vat_rate = lpo.vat_rate
	for row in lpo.items:
		unbilled = flt(row.qty) - flt(row.billed_qty)
		if unbilled <= 0:
			continue
		invoice.append(
			"items",
			{
				"lpo_item": row.name,
				"item_code": row.item_code,
				"description": row.description,
				"uom": row.uom,
				"qty": unbilled,
				"rate": row.rate,
				"expense_account": row.expense_account,
			},
		)
	if not invoice.items:
		frappe.throw(
			_("{0} is already fully billed: nothing is pending").format(lpo.name),
			title=_("Nothing Pending"),
		)
	return invoice
