# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

"""Budget consumption engine (step 16).

One set-based query per component, never row by row:
  soft_committed = approved requisition lines not yet ordered
  firm_committed = approved LPO lines not yet invoiced
  actual         = posted supplier invoice lines straight from the GL
Requisition lines carry no expense account, so their commitment is attributed
to the settings Default Expense Account: budgets for that account therefore
see requisition-stage consumption, all others start at the LPO stage.
"""

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, now

from vmg_procurement.utils.settings import get_settings


def get_budget_position(
	project, cost_center, expense_account, posting_date=None,
	exclude_requisition=None, exclude_lpo=None,
):
	"""Return {budget, soft_committed, firm_committed, actual, available} for
	one project + cost center + expense account combination."""
	budget = flt(
		frappe.db.sql(
			"""
			select sum(line.budget_amount)
			from `tabVMG Project Budget Line` line
			join `tabVMG Project Budget` budget on budget.name = line.parent
			join `tabFiscal Year` fy on fy.name = budget.fiscal_year
			where budget.docstatus = 1 and budget.status = 'Active'
			  and budget.project = %(project)s
			  and budget.cost_center = %(cost_center)s
			  and line.expense_account = %(account)s
			  and (
				%(posting_date)s is null
				or %(posting_date)s between coalesce(budget.from_date, fy.year_start_date)
				and coalesce(budget.to_date, fy.year_end_date)
			  )
			""",
			{
				"project": project,
				"cost_center": cost_center,
				"account": expense_account,
				"posting_date": posting_date,
			},
		)[0][0]
	)

	soft_committed = 0.0
	if expense_account == get_settings().default_expense_account:
		soft_committed = flt(
			frappe.db.sql(
				"""
				select sum((item.qty - coalesce(item.ordered_qty, 0)) * coalesce(item.estimated_rate, 0))
				from `tabVMG Purchase Requisition Item` item
				join `tabVMG Purchase Requisition` pr on pr.name = item.parent
				where pr.docstatus = 1 and pr.workflow_state = 'Approved'
				  and pr.status in ('Approved', 'RFQ Created', 'Partially Ordered')
				  and coalesce(pr.project, '') = %(project)s
				  and pr.cost_center = %(cost_center)s
				  and item.qty > coalesce(item.ordered_qty, 0)
				  and pr.name != %(exclude)s
				""",
				{
					"project": project,
					"cost_center": cost_center,
					"exclude": exclude_requisition or "",
				},
			)[0][0]
		)

	firm_committed = flt(
		frappe.db.sql(
			"""
			select sum((item.qty - coalesce(item.billed_qty, 0)) * coalesce(item.rate, 0))
			from `tabVMG LPO Item` item
			join `tabVMG Local Purchase Order` lpo on lpo.name = item.parent
			where lpo.docstatus = 1 and lpo.workflow_state = 'Approved'
			  and coalesce(item.project, '') = %(project)s
			  and item.cost_center = %(cost_center)s
			  and item.expense_account = %(account)s
			  and item.qty > coalesce(item.billed_qty, 0)
			  and lpo.name != %(exclude)s
			""",
			{
				"project": project,
				"cost_center": cost_center,
				"account": expense_account,
				"exclude": exclude_lpo or "",
			},
		)[0][0]
	)

	actual = flt(
		frappe.db.sql(
			"""
			select sum(gl.debit - gl.credit)
			from `tabGL Entry` gl
			join `tabVMG Supplier Invoice` invoice on invoice.journal_entry = gl.voucher_no
			where gl.is_cancelled = 0 and gl.voucher_type = 'Journal Entry'
			  and invoice.docstatus = 1
			  and gl.account = %(account)s
			  and gl.cost_center = %(cost_center)s
			  and coalesce(gl.project, '') = %(project)s
			""",
			{"project": project, "cost_center": cost_center, "account": expense_account},
		)[0][0]
	)

	return {
		"budget": budget,
		"soft_committed": soft_committed,
		"firm_committed": firm_committed,
		"actual": actual,
		"available": budget - soft_committed - firm_committed - actual,
	}


def _document_budget_rows(doc):
	"""Group the document's lines into (project, cost_center, account) -> amount."""
	rows = {}
	default_account = get_settings().default_expense_account
	if doc.doctype == "VMG Purchase Requisition":
		cost_center = doc.cost_center or frappe.db.get_value(
			"VMG Division", doc.division, "cost_center"
		)
		for item in doc.items:
			key = (doc.project or "", cost_center, default_account)
			rows[key] = rows.get(key, 0) + flt(item.qty) * flt(item.estimated_rate)
	elif doc.doctype == "VMG Local Purchase Order":
		for item in doc.items:
			key = (item.project or doc.project or "", item.cost_center or doc.cost_center, item.expense_account)
			rows[key] = rows.get(key, 0) + flt(item.amount)
	return rows


def check_budget(doc, action_setting_field, exclude_self=False, already_posted=False, rows=None):
	"""Enforce the budget per the settings action. Returns True when a Warn
	breach happened (so the caller can record the override)."""
	action = get_settings().get(action_setting_field) or "Warn"
	if action == "Ignore":
		return False

	rows = rows if rows is not None else _document_budget_rows(doc)
	breaches = []
	uncontrolled = []
	posting_date = doc.get("posting_date") or doc.get("order_date") or doc.get("requisition_date")

	for (project, cost_center, account), amount in rows.items():
		if not project or not account:
			# nothing to control against: no project (or no account) on the line
			continue
		position = get_budget_position(
			project,
			cost_center,
			account,
			posting_date=posting_date,
			exclude_requisition=doc.name if (exclude_self and doc.doctype == "VMG Purchase Requisition") else None,
			exclude_lpo=doc.name if (exclude_self and doc.doctype == "VMG Local Purchase Order") else None,
		)
		if not position["budget"]:
			uncontrolled.append((project, account))
			continue
		consumed = position["soft_committed"] + position["firm_committed"] + position["actual"]
		excess = (0 if already_posted else amount) - position["available"]
		if excess > 0.005:
			breaches.append(
				_(
					"Project {0}, account {1}, budget AED {2}, already committed AED {3},"
					" this document AED {4}, exceeds by AED {5}."
				).format(
					frappe.bold(project),
					frappe.bold(account),
					fmt_money(position["budget"]),
					fmt_money(consumed),
					fmt_money(amount),
					frappe.bold(fmt_money(excess)),
				)
			)

	for project, account in uncontrolled:
		message = _(
			"No active budget for project {0} / account {1}: this spend is outside"
			" budget control"
		).format(project, account)
		# never add_comment on an unsaved doc: the comment machinery reads the
		# reference document and poisons the cache with a negative entry
		if doc.is_new():
			frappe.log_error(title=f"Budget control gap: {doc.doctype} {doc.name}", message=message)
			continue
		try:
			doc.add_comment("Comment", message)
		except Exception:
			frappe.log_error(title=f"Budget control gap: {doc.doctype} {doc.name}", message=message)

	if not breaches:
		return False

	message = _("Budget exceeded:") + "<br>" + "<br>".join(breaches)
	if action == "Stop":
		frappe.throw(message, title=_("Budget Exceeded"))
	frappe.msgprint(message, title=_("Budget Warning"), indicator="orange")
	return True


def record_budget_override(doc):
	"""A warning that leaves no trace is not a control."""
	values = {"budget_override_by": frappe.session.user, "budget_override_on": now()}
	if doc.docstatus == 0 and doc.meta.get_field("budget_override_by"):
		doc.update(values)
	elif doc.meta.get_field("budget_override_by"):
		for fieldname, value in values.items():
			doc.db_set(fieldname, value, update_modified=False)


@frappe.whitelist()
def get_position_summary(project, cost_center, expense_account=None, posting_date=None):
	"""Readable one-liner for the Budget section on requisition / LPO forms."""
	account = expense_account or get_settings().default_expense_account
	if not (project and cost_center and account):
		return _("No project, cost center or account: outside budget control")
	position = get_budget_position(project, cost_center, account, posting_date=posting_date)
	if not position["budget"]:
		return _("No active budget for project {0} / account {1}").format(project, account)
	consumed = position["soft_committed"] + position["firm_committed"] + position["actual"]
	return _(
		"Account {0}: budget AED {1}, consumed AED {2} (soft {3} / firm {4} / actual {5}), available AED {6}"
	).format(
		account,
		fmt_money(position["budget"]),
		fmt_money(consumed),
		fmt_money(position["soft_committed"]),
		fmt_money(position["firm_committed"]),
		fmt_money(position["actual"]),
		fmt_money(position["available"]),
	)


def check_payment_budget(doc, method=None):
	"""hooks doc_events validate on core Payment Entry: when a row references
	a VMG Supplier Invoice, check per budget_action_on_payment. The invoice is
	already posted to the GL, so the breach test is available < 0."""
	invoice_names = [
		row.vmg_supplier_invoice
		for row in doc.get("references") or []
		if row.get("vmg_supplier_invoice")
	]
	if not invoice_names:
		return
	rows = {}
	for invoice_name in invoice_names:
		invoice = frappe.get_doc("VMG Supplier Invoice", invoice_name)
		for item in invoice.items:
			key = (item.project or invoice.project or "", item.cost_center, item.expense_account)
			rows[key] = rows.get(key, 0) + flt(item.amount)
	if check_budget(doc, "budget_action_on_payment", already_posted=True, rows=rows):
		values = {"vmg_budget_override_by": frappe.session.user, "vmg_budget_override_on": now()}
		if doc.meta.get_field("vmg_budget_override_by"):
			doc.update(values)
