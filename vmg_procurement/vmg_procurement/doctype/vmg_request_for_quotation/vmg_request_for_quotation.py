# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cint, flt, fmt_money, now

from vmg_procurement.utils.naming import make_vmg_name
from vmg_procurement.utils.settings import get_settings

PRINT_FORMAT = "VMG Request for Quotation"

DEFAULT_RFQ_MESSAGE = (
	"<p>Dear Supplier,</p>"
	"<p>Please send us your best quotation for the items listed in the attached"
	" Request for Quotation, mentioning your price, delivery period, payment"
	" terms and quotation validity.</p>"
	"<p>Kindly reply to this email quoting the RFQ number.</p>"
	"<p>Thank you,<br>VMG Procurement Department</p>"
)


class VMGRequestforQuotation(Document):
	def autoname(self):
		division = self.division or frappe.db.get_value(
			"VMG Purchase Requisition", self.purchase_requisition, "division"
		)
		if not division:
			frappe.throw(_("Select a Purchase Requisition first: its division drives the RFQ number"))
		prefix = frappe.db.get_value("VMG Division", division, "prefix")
		if not prefix:
			frappe.throw(_("Division {0} has no prefix set").format(frappe.bold(division)))
		self.name = make_vmg_name("RFQ", prefix, "#####", self.transaction_date)

	def validate(self):
		self.validate_items()
		self.set_default_message()
		self.validate_duplicate_suppliers()
		self.fill_missing_emails()
		self.flag_unapproved_suppliers()
		self.compute_required_suppliers()
		self.enforce_threshold()
		if self.docstatus.is_draft():
			self.status = "Draft"

	def before_submit(self):
		self.validate_source_requisition()

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	def validate_items(self):
		for item in self.items:
			if not (item.description or "").strip():
				frappe.throw(_("Row {0}: Description is mandatory").format(item.idx))
			if flt(item.qty) <= 0:
				frappe.throw(_("Row {0}: Quantity must be greater than zero").format(item.idx))

	def set_default_message(self):
		if not self.message_to_supplier:
			self.message_to_supplier = get_settings().get("rfq_default_message") or DEFAULT_RFQ_MESSAGE

	def validate_duplicate_suppliers(self):
		seen = set()
		for row in self.suppliers:
			if row.supplier in seen:
				frappe.throw(
					_("Row {0}: Supplier {1} appears more than once").format(
						row.idx, frappe.bold(row.supplier)
					),
					title=_("Duplicate Supplier"),
				)
			seen.add(row.supplier)

	def fill_missing_emails(self):
		for row in self.suppliers:
			if not row.email_id:
				row.email_id = (
					row.contact_person
					and frappe.db.get_value("Contact", row.contact_person, "email_id")
				) or frappe.db.get_value("Supplier", row.supplier, "email_id")

	def flag_unapproved_suppliers(self):
		"""Warn (never block) about suppliers missing from the Approved
		Supplier List (VMG-PRO-F05) and record it in the row remarks."""
		note = _("Not on the Approved Supplier List")
		unapproved = []
		for row in self.suppliers:
			row.is_approved_supplier = cint(
				frappe.db.get_value("Supplier", row.supplier, "vmg_is_approved")
			)
			if not row.is_approved_supplier:
				unapproved.append(row.supplier_name or row.supplier)
				if note not in (row.remarks or ""):
					row.remarks = f"{row.remarks}\n{note}" if row.remarks else note
		if unapproved:
			frappe.msgprint(
				_("These suppliers are not on the Approved Supplier List: {0}").format(
					", ".join(frappe.bold(s) for s in unapproved)
				),
				title=_("Unapproved Suppliers"),
				indicator="orange",
			)

	def compute_required_suppliers(self):
		settings = get_settings()
		value = flt(self.estimated_value)
		threshold = flt(settings.quote_threshold_amount)

		if value > threshold:
			count = cint(settings.min_suppliers_above_threshold) or 3
			note = _("Value AED {0} exceeds AED {1}: at least {2} suppliers required").format(
				fmt_money(value), fmt_money(threshold), count
			)
		elif self.is_new_product_or_service:
			count = cint(settings.min_suppliers_for_new_item) or 3
			note = _(
				"New product or service: at least {0} suppliers required even below"
				" the AED {1} threshold"
			).format(count, fmt_money(threshold))
		else:
			count = 1
			note = _(
				"Value AED {0} is within the AED {1} threshold and the item is not"
				" new: 1 supplier is sufficient"
			).format(fmt_money(value), fmt_money(threshold))

		self.required_supplier_count = count
		self.threshold_note = note

	def enforce_threshold(self):
		if len(self.suppliers) >= cint(self.required_supplier_count):
			return
		action = get_settings().threshold_enforcement or "Warn"
		message = _("Only {0} supplier(s) added. {1}").format(len(self.suppliers), self.threshold_note)
		if action == "Stop":
			frappe.throw(message, title=_("Minimum Suppliers Not Met"))
		elif action == "Warn":
			frappe.msgprint(message, title=_("Minimum Suppliers Not Met"), indicator="orange")

	def validate_source_requisition(self):
		state, requisition_type = frappe.db.get_value(
			"VMG Purchase Requisition",
			self.purchase_requisition,
			["workflow_state", "requisition_type"],
		)
		if state != "Approved":
			frappe.throw(
				_(
					"Requisition {0} is not Approved (current state: {1}): the RFQ"
					" cannot be submitted"
				).format(self.purchase_requisition, frappe.bold(state)),
				title=_("Requisition Not Approved"),
			)
		if requisition_type == "Asset":
			frappe.throw(
				_(
					"Requisition {0} is an Asset requisition and must go through a"
					" core Material Request, not a VMG Request for Quotation"
				).format(self.purchase_requisition),
				title=_("Wrong Chain"),
			)


@frappe.whitelist()
def send_enquiry(rfq_name):
	"""Email the enquiry (print format attached, no rates) to every supplier
	row with an email address. Rows without an email (or when sending fails,
	e.g. no outgoing Email Account) are reported back for manual printing.
	Every row is marked sent and the RFQ moves to Sent to Suppliers."""
	doc = frappe.get_doc("VMG Request for Quotation", rfq_name)
	doc.check_permission("email")
	if doc.docstatus != 1:
		frappe.throw(_("Submit the Request for Quotation before sending the enquiry"))

	attachment = None
	try:
		attachment = frappe.attach_print(
			doc.doctype, doc.name, file_name=doc.name, print_format=PRINT_FORMAT
		)
	except Exception:
		frappe.log_error(title=f"RFQ {doc.name}: PDF generation failed")

	subject = f"{doc.rfq_subject or _('Request for Quotation')} - {doc.name}"
	message = doc.message_to_supplier or DEFAULT_RFQ_MESSAGE
	emailed, manual = [], []

	for row in doc.suppliers:
		label = row.supplier_name or row.supplier
		if row.email_id:
			try:
				frappe.sendmail(
					recipients=[row.email_id],
					subject=subject,
					message=message,
					attachments=[attachment] if attachment else None,
					reference_doctype=doc.doctype,
					reference_name=doc.name,
				)
				emailed.append(label)
			except Exception:
				frappe.log_error(title=f"RFQ {doc.name}: email to {row.email_id} failed")
				manual.append(label)
		else:
			manual.append(label)
		row.db_set("sent_on", now(), update_modified=False)

	doc.db_set("status", "Sent to Suppliers", update_modified=False)
	return {"emailed": emailed, "manual": manual}


@frappe.whitelist()
def make_vmg_supplier_quotation(source_name, supplier=None, target_doc=None):
	"""RFQ + chosen supplier row -> VMG Supplier Quotation (built in step 06)."""
	if not frappe.db.exists("DocType", "VMG Supplier Quotation"):
		frappe.throw(
			_(
				"VMG Supplier Quotation is not built yet: it arrives in build step"
				" {0}. Nothing was created."
			).format(frappe.bold("06 supplier quotation")),
			title=_("Not Available Yet"),
		)

	def set_missing_values(source, target):
		target.request_for_quotation = source.name
		if supplier:
			target.supplier = supplier

	return get_mapped_doc(
		"VMG Request for Quotation",
		source_name,
		{
			"VMG Request for Quotation": {
				"doctype": "VMG Supplier Quotation",
				"field_map": {"name": "request_for_quotation"},
				"validation": {"docstatus": ["=", 1]},
			},
			"VMG RFQ Item": {
				"doctype": "VMG Supplier Quotation Item",
				"field_map": {"name": "rfq_item"},
			},
		},
		target_doc,
		set_missing_values,
	)


@frappe.whitelist()
def make_vmg_quotation_comparison(source_name, target_doc=None):
	"""RFQ -> VMG Quotation Comparison (built in step 07)."""
	if not frappe.db.exists("DocType", "VMG Quotation Comparison"):
		frappe.throw(
			_(
				"VMG Quotation Comparison is not built yet: it arrives in build step"
				" {0}. Nothing was created."
			).format(frappe.bold("07 quotation comparison")),
			title=_("Not Available Yet"),
		)

	def set_missing_values(source, target):
		target.request_for_quotation = source.name

	return get_mapped_doc(
		"VMG Request for Quotation",
		source_name,
		{
			"VMG Request for Quotation": {
				"doctype": "VMG Quotation Comparison",
				"field_map": {"name": "request_for_quotation"},
				"validation": {"docstatus": ["=", 1]},
			},
		},
		target_doc,
		set_missing_values,
	)


def update_items_quoted(rfq_name):
	"""Per supplier row: how many of the RFQ's lines their submitted quotation
	covers, shown as 'quoted / total' with '(+n)' for alternative lines that
	are not on the RFQ. Cleared when the row has no submitted quotation."""
	rfq = frappe.get_doc("VMG Request for Quotation", rfq_name)
	total = len(rfq.items)
	rfq_item_names = {row.name for row in rfq.items}

	for row in rfq.suppliers:
		value = None
		if row.supplier_quotation and frappe.db.get_value(
			"VMG Supplier Quotation", row.supplier_quotation, "docstatus"
		) == 1:
			quoted_rows = frappe.get_all(
				"VMG Supplier Quotation Item",
				filters={"parent": row.supplier_quotation},
				pluck="rfq_item",
			)
			quoted = len({r for r in quoted_rows if r in rfq_item_names})
			extra = sum(1 for r in quoted_rows if not r or r not in rfq_item_names)
			value = f"{quoted} / {total}" + (f" (+{extra})" if extra else "")
		if row.items_quoted != value:
			row.db_set("items_quoted", value, update_modified=False)


def update_status_from_quotations(rfq_name):
	"""Reusable: set status to Quotations Received once at least one supplier
	row has quotation_received. Called by VMG Supplier Quotation (step 06)."""
	doc = frappe.get_doc("VMG Request for Quotation", rfq_name)
	if doc.docstatus != 1 or doc.status in ("Comparison Created", "Cancelled"):
		return
	received = any(cint(row.quotation_received) for row in doc.suppliers)
	target = "Quotations Received" if received else ("Sent to Suppliers" if doc.status == "Quotations Received" else doc.status)
	if target != doc.status:
		doc.db_set("status", target, update_modified=False)
