# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, add_months, flt, get_last_day, getdate, money_in_words, nowdate
from frappe.model.document import Document

from vmg_procurement.utils.naming import make_vmg_name
from vmg_procurement.utils.settings import get_settings

WORKFLOW_STATE_TO_STATUS = {
	"Pending Procurement Verification": "Pending Approval",
	"Pending Accounts Approval": "Pending Approval",
	"Rejected": "Rejected",
	# Approved maps to Unpaid after posting: handled in post_journal_entry
}


class VMGSupplierInvoice(Document):
	def autoname(self):
		if not self.division:
			frappe.throw(_("Select a Division first: it drives the invoice number"))
		prefix = frappe.db.get_value("VMG Division", self.division, "prefix")
		if not prefix:
			frappe.throw(_("Division {0} has no prefix set").format(frappe.bold(self.division)))
		self.name = make_vmg_name("SINV", prefix, "#####", self.posting_date)

	def before_insert(self):
		if not self.company:
			self.company = frappe.defaults.get_global_default("company")

	def validate(self):
		self.set_defaults()
		self.validate_items()
		self.calculate_totals()
		self.set_due_date()
		self.validate_duplicate_supplier_invoice()
		self.match_against_receipt()
		if self.docstatus.is_draft():
			self.status = "Draft"
		self.suppress_notifications_if_disabled()

	def before_submit(self):
		self.validate_accounts()

	def before_update_after_submit(self):
		self.suppress_notifications_if_disabled()

	def on_update_after_submit(self):
		status = WORKFLOW_STATE_TO_STATUS.get(self.workflow_state)
		if status and self.status != status:
			self.db_set("status", status, update_modified=False)
		if self.workflow_state == "Approved":
			self.post_journal_entry()

	def on_submit(self):
		self.db_set("status", "Pending Approval", update_modified=False)
		update_billing_status(self.local_purchase_order, self.purchase_receipt)

	def before_cancel(self):
		self.validate_no_allocated_payments()

	def on_cancel(self):
		self.reverse_journal_entry()
		self.db_set("status", "Cancelled", update_modified=False)
		update_billing_status(self.local_purchase_order, self.purchase_receipt)

	def suppress_notifications_if_disabled(self):
		if not get_settings().notify_by_email:
			self.flags.notifications = []

	# --- defaults and validation -------------------------------------------

	def set_defaults(self):
		settings = get_settings()
		if not self.company:
			self.company = frappe.defaults.get_global_default("company")
		if not self.credit_to:
			self.credit_to = (
				frappe.db.get_value(
					"Party Account",
					{"parenttype": "Supplier", "parent": self.supplier, "company": self.company},
					"account",
				)
				or settings.default_payable_account
			)
		if not self.input_vat_account:
			self.input_vat_account = settings.default_input_vat_account
		for item in self.items:
			if not item.expense_account:
				item.expense_account = settings.default_expense_account
			if not item.cost_center:
				item.cost_center = self.cost_center
			if not item.project:
				item.project = self.project

	def validate_items(self):
		for item in self.items:
			if flt(item.qty) <= 0:
				frappe.throw(_("Row {0}: Quantity must be greater than zero").format(item.idx))
			if flt(item.rate) <= 0:
				frappe.throw(_("Row {0}: Rate must be greater than zero").format(item.idx))

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

	def set_due_date(self):
		if self.due_date and not self.payment_terms_template:
			return
		base = getdate(self.posting_date)
		due = base
		if self.payment_terms_template:
			template = frappe.get_doc("Payment Terms Template", self.payment_terms_template)
			for row in template.terms:
				if row.due_date_based_on == "Day(s) after invoice date":
					candidate = add_days(base, row.credit_days)
				elif row.due_date_based_on == "Day(s) after the end of the invoice month":
					candidate = add_days(get_last_day(base), row.credit_days)
				else:  # Month(s) after the end of the invoice month
					candidate = get_last_day(add_months(base, row.credit_months))
				due = max(due, getdate(candidate))
		self.due_date = self.due_date or due
		if self.payment_terms_template:
			self.due_date = due
		if getdate(self.due_date) < base:
			frappe.throw(_("Due Date cannot be before the Posting Date"))

	def validate_duplicate_supplier_invoice(self):
		duplicate = frappe.db.exists(
			"VMG Supplier Invoice",
			{
				"supplier": self.supplier,
				"company": self.company,
				"supplier_invoice_no": self.supplier_invoice_no,
				"docstatus": ["<", 2],
				"name": ["!=", self.name],
			},
		)
		if duplicate:
			frappe.throw(
				_(
					"Supplier invoice number {0} is already recorded for {1} on {2}"
				).format(
					frappe.bold(self.supplier_invoice_no),
					self.supplier,
					frappe.bold(duplicate),
				),
				title=_("Duplicate Supplier Invoice"),
			)

	def match_against_receipt(self):
		"""Three-way match: invoice vs receipt accepted qty vs ordered rate."""
		if not self.purchase_receipt:
			return
		settings = get_settings()
		rate_tolerance = flt(settings.get("rate_tolerance_percent"))
		qty_tolerance = flt(settings.get("qty_tolerance_percent"))
		problems = []
		for item in self.items:
			if not item.receipt_item:
				continue
			accepted_qty, ordered_rate = frappe.db.get_value(
				"VMG Purchase Receipt Item", item.receipt_item, ["accepted_qty", "rate"]
			) or (None, None)
			if accepted_qty is None:
				continue
			qty_allowed = flt(accepted_qty) * (1 + qty_tolerance / 100.0)
			rate_allowed = flt(ordered_rate) * (1 + rate_tolerance / 100.0)
			qty_off = flt(item.qty) > qty_allowed + 1e-9
			rate_off = flt(ordered_rate) and flt(item.rate) > rate_allowed + 1e-9
			if qty_off or rate_off:
				problems.append(
					_("Row {0} ({1}): ordered rate {2}, invoice rate {3}, accepted qty {4}, invoice qty {5}").format(
						item.idx,
						(item.description or "")[:40],
						frappe.utils.fmt_money(ordered_rate),
						frappe.utils.fmt_money(item.rate),
						accepted_qty,
						item.qty,
					)
				)
		if not problems:
			return
		message = _("Invoice does not match the receipt / order:") + "<br>" + "<br>".join(problems)
		if (settings.get("invoice_matching_action") or "Warn") == "Stop":
			frappe.throw(message, title=_("Invoice Matching Failed"))
		frappe.msgprint(message, title=_("Invoice Matching"), indicator="orange")

	def validate_accounts(self):
		# (label, account, allow_party_account) — only credit_to may be Payable
		accounts = [(_("Supplier Credit Account"), self.credit_to, True)]
		if flt(self.vat_amount) > 0:
			if not self.input_vat_account:
				frappe.throw(
					_("Input VAT Account is mandatory when VAT applies (set it here or in VMG Procurement Settings)"),
					title=_("Account Missing"),
				)
			accounts.append((_("Input VAT Account"), self.input_vat_account, False))
		for item in self.items:
			accounts.append((_("Row {0} Expense Account").format(item.idx), item.expense_account, False))

		for label, account, allow_party_account in accounts:
			company, is_group, account_type = frappe.db.get_value(
				"Account", account, ["company", "is_group", "account_type"]
			)
			if is_group:
				frappe.throw(
					_("{0} {1} is a group account: pick a ledger account").format(label, frappe.bold(account))
				)
			if company != self.company:
				frappe.throw(
					_("{0} {1} belongs to {2}, not {3}").format(
						label, frappe.bold(account), company, self.company
					)
				)
			if not allow_party_account and account_type in ("Receivable", "Payable"):
				frappe.throw(
					_(
						"{0} {1} is a {2} account and cannot take direct expense/VAT postings"
						" (it would need a party on every Journal Entry row). Pick an expense ledger instead."
					).format(label, frappe.bold(account), account_type),
					title=_("Invalid Account"),
				)
		if frappe.db.get_value("Account", self.credit_to, "account_type") != "Payable":
			frappe.throw(
				_("Supplier Credit Account {0} must be of type Payable").format(
					frappe.bold(self.credit_to)
				)
			)

	# --- journal entry posting ---------------------------------------------

	def build_journal_entry_rows(self):
		"""Debit expenses (prorated for the discount) + input VAT; credit the
		supplier. Returns balanced rows."""
		rows = []
		factor = flt(self.net_total) / flt(self.total) if flt(self.total) else 1.0
		debited = 0.0
		for item in self.items:
			debit = round(flt(item.amount) * factor, 2)
			debited += debit
			rows.append(
				{
					"account": item.expense_account,
					"debit_in_account_currency": debit,
					"cost_center": item.cost_center,
					"project": item.project,
				}
			)
		residual = round(flt(self.net_total) - debited, 2)
		if rows and residual:
			rows[-1]["debit_in_account_currency"] = round(
				rows[-1]["debit_in_account_currency"] + residual, 2
			)
		if flt(self.vat_amount) > 0:
			rows.append(
				{
					"account": self.input_vat_account,
					"debit_in_account_currency": round(flt(self.vat_amount), 2),
					"cost_center": self.cost_center,
				}
			)
		rows.append(
			{
				"account": self.credit_to,
				"credit_in_account_currency": round(flt(self.grand_total), 2),
				"party_type": "Supplier",
				"party": self.supplier,
				"cost_center": self.cost_center,
			}
		)
		debits = sum(flt(r.get("debit_in_account_currency")) for r in rows)
		credits = sum(flt(r.get("credit_in_account_currency")) for r in rows)
		if abs(debits - credits) > 0.005:
			frappe.throw(
				_("Journal Entry does not balance: debits {0} vs credits {1}").format(debits, credits)
			)
		return rows

	def post_journal_entry(self):
		"""Create + submit the core Journal Entry exactly once (idempotent)."""
		if self.journal_entry or self.docstatus != 1:
			return
		self.validate_accounts()
		journal_entry = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"posting_date": self.posting_date,
				"company": self.company,
				"due_date": self.due_date,
				"user_remark": _(
					"VMG Supplier Invoice {0} | LPO {1} | Supplier Invoice No {2}"
				).format(self.name, self.local_purchase_order or "-", self.supplier_invoice_no),
				"accounts": self.build_journal_entry_rows(),
			}
		)
		journal_entry.flags.ignore_permissions = True
		journal_entry.insert()
		journal_entry.submit()
		self.db_set("journal_entry", journal_entry.name, update_modified=False)
		self.db_set("posting_status", "Posted", update_modified=False)
		self.db_set("status", "Unpaid", update_modified=False)
		self.db_set("outstanding_amount", flt(self.grand_total), update_modified=False)

	def validate_no_allocated_payments(self):
		if not self.journal_entry:
			return
		payments = frappe.db.sql(
			"""
			select distinct payment.parent
			from `tabPayment Entry Reference` payment
			join `tabPayment Entry` entry on entry.name = payment.parent
			where payment.reference_doctype = 'Journal Entry'
			  and payment.reference_name = %s and entry.docstatus = 1
			""",
			self.journal_entry,
		)
		if payments:
			frappe.throw(
				_(
					"Payment(s) {0} are allocated against Journal Entry {1}: cancel the"
					" payment first"
				).format(
					", ".join(frappe.bold(p[0]) for p in payments),
					self.journal_entry,
				),
				title=_("Payments Exist"),
			)

	def reverse_journal_entry(self):
		if not self.journal_entry:
			return
		journal_entry = frappe.get_doc("Journal Entry", self.journal_entry)
		if journal_entry.docstatus == 1:
			journal_entry.flags.ignore_permissions = True
			journal_entry.cancel()
		self.db_set("posting_status", "Reversed", update_modified=False)


# ---------------------------------------------------------------------------
# outstanding / payment status


def update_invoice_outstanding(invoice_name):
	"""Outstanding straight from the ledger: the original credit on the
	journal entry minus everything allocated against it."""
	invoice = frappe.db.get_value(
		"VMG Supplier Invoice",
		invoice_name,
		["journal_entry", "credit_to", "supplier", "grand_total", "due_date", "docstatus", "status"],
		as_dict=True,
	)
	if not invoice or invoice.docstatus != 1 or not invoice.journal_entry:
		return
	outstanding = flt(
		frappe.db.sql(
			"""
			select sum(credit) - sum(debit)
			from `tabGL Entry`
			where account = %(account)s and party_type = 'Supplier' and party = %(party)s
			  and is_cancelled = 0
			  and (voucher_no = %(je)s or against_voucher = %(je)s)
			""",
			{"account": invoice.credit_to, "party": invoice.supplier, "je": invoice.journal_entry},
		)[0][0]
	)
	if outstanding <= 0.005:
		status = "Paid"
		outstanding = 0
	elif outstanding < flt(invoice.grand_total) - 0.005:
		status = "Partly Paid"
	elif invoice.due_date and getdate(invoice.due_date) < getdate(nowdate()):
		status = "Overdue"
	else:
		status = "Unpaid"
	frappe.db.set_value(
		"VMG Supplier Invoice",
		invoice_name,
		{"outstanding_amount": outstanding, "status": status},
		update_modified=False,
	)


def update_payment_status_daily():
	"""Daily scheduler: refresh outstanding and flag overdue invoices."""
	for name in frappe.get_all(
		"VMG Supplier Invoice",
		filters={"docstatus": 1, "posting_status": "Posted", "status": ["!=", "Paid"]},
		pluck="name",
	):
		update_invoice_outstanding(name)
	frappe.db.commit()


def on_payment_entry_change(doc, method=None):
	"""doc_events hook on Payment Entry submit/cancel: refresh every VMG
	invoice whose journal entry this payment touches (or that a row names
	directly via vmg_supplier_invoice)."""
	invoices = {
		row.vmg_supplier_invoice
		for row in doc.get("references") or []
		if row.get("vmg_supplier_invoice")
	}
	journal_entries = {
		row.reference_name
		for row in doc.get("references") or []
		if row.reference_doctype == "Journal Entry"
	}
	if journal_entries:
		invoices.update(
			frappe.get_all(
				"VMG Supplier Invoice",
				filters={"journal_entry": ["in", list(journal_entries)], "docstatus": 1},
				pluck="name",
			)
		)
	for invoice_name in invoices:
		update_invoice_outstanding(invoice_name)


@frappe.whitelist()
def make_payment_entry(invoice_name):
	"""Approved, unpaid invoice -> core Payment Entry (Pay) with the journal
	entry referenced and the outstanding amount allocated."""
	invoice = frappe.get_doc("VMG Supplier Invoice", invoice_name)
	if invoice.docstatus != 1 or invoice.posting_status != "Posted" or not invoice.journal_entry:
		frappe.throw(
			_("Only an approved, posted invoice can be paid (current status: {0})").format(
				frappe.bold(invoice.status)
			),
			title=_("Not Payable"),
		)
	update_invoice_outstanding(invoice.name)
	outstanding = flt(
		frappe.db.get_value("VMG Supplier Invoice", invoice.name, "outstanding_amount")
	)
	if outstanding <= 0:
		frappe.throw(_("Invoice {0} is already fully paid").format(invoice.name))

	company = invoice.company
	paid_from = frappe.db.get_value(
		"Company", company, "default_bank_account"
	) or frappe.db.get_value(
		"Account", {"account_type": ["in", ["Bank", "Cash"]], "company": company, "is_group": 0}
	)

	company_currency = frappe.db.get_value("Company", company, "default_currency")
	paid_from_currency = (
		frappe.db.get_value("Account", paid_from, "account_currency") if paid_from else None
	) or company_currency
	paid_to_currency = (
		frappe.db.get_value("Account", invoice.credit_to, "account_currency") or company_currency
	)

	payment = frappe.new_doc("Payment Entry")
	payment.update(
		{
			"payment_type": "Pay",
			"company": company,
			"posting_date": frappe.utils.nowdate(),
			"party_type": "Supplier",
			"party": invoice.supplier,
			"paid_from": paid_from,
			"paid_to": invoice.credit_to,
			"paid_from_account_currency": paid_from_currency,
			"paid_to_account_currency": paid_to_currency,
			"source_exchange_rate": 1 if paid_from_currency == company_currency else None,
			"target_exchange_rate": 1 if paid_to_currency == company_currency else None,
			"paid_amount": outstanding,
			"received_amount": outstanding,
			"base_paid_amount": outstanding if paid_from_currency == company_currency else None,
			"base_received_amount": outstanding if paid_to_currency == company_currency else None,
		}
	)
	payment.append(
		"references",
		{
			"reference_doctype": "Journal Entry",
			"reference_name": invoice.journal_entry,
			"total_amount": invoice.grand_total,
			"outstanding_amount": outstanding,
			"allocated_amount": outstanding,
			"vmg_supplier_invoice": invoice.name,
		},
	)
	return payment


# ---------------------------------------------------------------------------
# billing status on LPO and receipt


def update_billing_status(lpo_name, receipt_name):
	"""Recompute billed quantities and statuses from submitted invoices."""
	if receipt_name:
		receipt = frappe.get_doc("VMG Purchase Receipt", receipt_name)
		if receipt.docstatus == 1:
			total_accepted = sum(flt(row.accepted_qty) for row in receipt.items)
			billed = flt(
				frappe.db.sql(
					"""
					select sum(item.qty)
					from `tabVMG Supplier Invoice Item` item
					join `tabVMG Supplier Invoice` invoice on invoice.name = item.parent
					where invoice.docstatus = 1 and invoice.purchase_receipt = %s
					""",
					receipt_name,
				)[0][0]
			)
			per_billed = min(billed / total_accepted * 100.0, 100) if total_accepted else 0
			receipt.db_set("per_billed", per_billed, update_modified=False)
			if receipt.status in ("To Bill", "Billed"):
				receipt.db_set(
					"status", "Billed" if per_billed >= 100 else "To Bill", update_modified=False
				)

	if lpo_name:
		lpo = frappe.get_doc("VMG Local Purchase Order", lpo_name)
		if lpo.docstatus != 1:
			return
		total_qty = billed_qty = 0.0
		for row in lpo.items:
			billed = flt(
				frappe.db.sql(
					"""
					select sum(item.qty)
					from `tabVMG Supplier Invoice Item` item
					join `tabVMG Supplier Invoice` invoice on invoice.name = item.parent
					where invoice.docstatus = 1 and item.lpo_item = %s
					""",
					row.name,
				)[0][0]
			)
			row.db_set("billed_qty", billed, update_modified=False)
			total_qty += flt(row.qty)
			billed_qty += min(billed, flt(row.qty))
		per_billed = (billed_qty / total_qty * 100.0) if total_qty else 0
		lpo.db_set("per_billed", per_billed, update_modified=False)
		if per_billed >= 100 and flt(lpo.per_received) >= 100 and lpo.status in (
			"Fully Received",
			"To Bill",
		):
			lpo.db_set("status", "Completed", update_modified=False)
