# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, money_in_words, nowdate

from vmg_procurement.utils.naming import make_vmg_name


class VMGSupplierQuotation(Document):
	def autoname(self):
		division = self.division or frappe.db.get_value(
			"VMG Request for Quotation", self.request_for_quotation, "division"
		)
		if not division:
			frappe.throw(
				_("Select a Request for Quotation first: its division drives the quotation number")
			)
		prefix = frappe.db.get_value("VMG Division", division, "prefix")
		if not prefix:
			frappe.throw(_("Division {0} has no prefix set").format(frappe.bold(division)))
		self.name = make_vmg_name("SQ", prefix, "#####", self.transaction_date)

	def validate(self):
		self.validate_rates()
		self.validate_valid_till()
		self.calculate_totals()
		self.warn_on_item_mismatch()
		if self.docstatus.is_draft():
			self.status = "Draft"

	def before_submit(self):
		self.validate_duplicate_quotation()

	def on_submit(self):
		self.db_set("status", "Submitted", update_modified=False)
		self.update_rfq_supplier_row(received=True)

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
		self.update_rfq_supplier_row(received=False)

	def validate_rates(self):
		for item in self.items:
			if flt(item.rate) <= 0:
				frappe.throw(
					_("Row {0}: Rate must be greater than zero").format(item.idx),
					title=_("Invalid Rate"),
				)

	def validate_valid_till(self):
		quotation_date = self.supplier_quotation_date or self.transaction_date
		if (
			self.valid_till
			and quotation_date
			and getdate(self.valid_till) < getdate(quotation_date)
		):
			frappe.throw(
				_("Valid Till cannot be earlier than the quotation date ({0})").format(
					frappe.utils.formatdate(quotation_date)
				),
				title=_("Invalid Validity"),
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

	def warn_on_item_mismatch(self):
		"""Compare against the RFQ item set. Differences are allowed (suppliers
		often quote alternatives) but are pointed out."""
		if not self.request_for_quotation:
			return
		rfq_items = {
			row.name: row.description
			for row in frappe.get_all(
				"VMG RFQ Item",
				filters={"parent": self.request_for_quotation},
				fields=["name", "description"],
			)
		}
		quoted = {row.rfq_item for row in self.items if row.rfq_item}
		problems = []
		for name, description in rfq_items.items():
			if name not in quoted:
				problems.append(_("Not quoted: {0}").format(frappe.bold(description or name)))
		for row in self.items:
			if not row.rfq_item or row.rfq_item not in rfq_items:
				problems.append(
					_("Row {0} is not on the RFQ (alternative?): {1}").format(
						row.idx, frappe.bold(row.description)
					)
				)
		if problems:
			frappe.msgprint(
				_("This quotation does not match the RFQ item set:")
				+ "<br>"
				+ "<br>".join(problems),
				title=_("Item Set Differs from RFQ"),
				indicator="orange",
			)

	def validate_duplicate_quotation(self):
		duplicate = frappe.db.exists(
			"VMG Supplier Quotation",
			{
				"supplier": self.supplier,
				"request_for_quotation": self.request_for_quotation,
				"docstatus": 1,
				"name": ["!=", self.name],
			},
		)
		if duplicate and not self.amended_from:
			frappe.throw(
				_(
					"A submitted quotation ({0}) already exists for supplier {1} against"
					" {2}. Cancel it first or amend it."
				).format(
					frappe.bold(duplicate),
					frappe.bold(self.supplier_name or self.supplier),
					self.request_for_quotation,
				),
				title=_("Duplicate Quotation"),
			)

	def update_rfq_supplier_row(self, received):
		"""Tick/untick quotation_received + supplier_quotation on the matching
		VMG RFQ Supplier row and refresh the RFQ status and quoted counts."""
		from vmg_procurement.vmg_procurement.doctype.vmg_request_for_quotation.vmg_request_for_quotation import (
			update_items_quoted,
			update_status_from_quotations,
		)

		rfq = frappe.get_doc("VMG Request for Quotation", self.request_for_quotation)
		matched = False
		for row in rfq.suppliers:
			if row.supplier != self.supplier:
				continue
			if not received and row.supplier_quotation != self.name:
				continue  # another quotation owns this row
			matched = True
			row.db_set("quotation_received", 1 if received else 0, update_modified=False)
			row.db_set("supplier_quotation", self.name if received else None, update_modified=False)
		if received and not matched:
			frappe.msgprint(
				_(
					"Supplier {0} is not on the supplier list of {1}: the RFQ rows were"
					" left untouched"
				).format(frappe.bold(self.supplier_name or self.supplier), rfq.name),
				indicator="orange",
			)
		update_status_from_quotations(rfq.name)
		update_items_quoted(rfq.name)


def mark_expired_quotations():
	"""Daily scheduler job: expire submitted quotations past their validity."""
	expired = frappe.get_all(
		"VMG Supplier Quotation",
		filters={
			"docstatus": 1,
			"status": "Submitted",
			"valid_till": ["<", nowdate()],
		},
		pluck="name",
	)
	for name in expired:
		frappe.db.set_value("VMG Supplier Quotation", name, "status", "Expired", update_modified=False)
	if expired:
		frappe.db.commit()
