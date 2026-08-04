# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, fmt_money, getdate, nowdate

from vmg_procurement.utils.naming import make_vmg_name
from vmg_procurement.utils.settings import get_settings

MAX_COLUMNS = 5  # fixed column design of VMG Comparison Item (VMG-PRO-F02)

WORKFLOW_STATE_TO_STATUS = {
	"Pending Division Approval": "Pending Approval",
	"Pending CFO Approval": "Pending Approval",
	"Pending GM Approval": "Pending Approval",
	"Approved": "Approved",
	"Rejected": "Rejected",
}

APPROVAL_STAMPS = {
	("Pending Division Approval", "Pending CFO Approval"): (
		"division_approved_by",
		"division_approved_on",
	),
	("Pending CFO Approval", "Pending GM Approval"): ("cfo_approved_by", "cfo_approved_on"),
	("Pending GM Approval", "Approved"): ("gm_approved_by", "gm_approved_on"),
}


class VMGQuotationComparison(Document):
	def autoname(self):
		division = self.division or frappe.db.get_value(
			"VMG Request for Quotation", self.request_for_quotation, "division"
		)
		if not division:
			frappe.throw(
				_("Select a Request for Quotation first: its division drives the comparison number")
			)
		prefix = frappe.db.get_value("VMG Division", division, "prefix")
		if not prefix:
			frappe.throw(_("Division {0} has no prefix set").format(frappe.bold(division)))
		self.name = make_vmg_name("QC", prefix, "#####", self.transaction_date)

	def before_insert(self):
		if not self.prepared_by:
			self.prepared_by = frappe.session.user

	def validate(self):
		self.validate_supplier_rows()
		self.enforce_minimum_suppliers()
		self.sync_selection()
		self.compute_lowest_flags()
		self.warn_unapproved_selection()
		if self.docstatus.is_draft():
			self.status = "Draft"
		self.suppress_notifications_if_disabled()

	@property
	def is_split_award(self):
		return self.award_mode == "Split by Item"

	def before_submit(self):
		self.validate_selection_complete()
		self.validate_selected_quotation_not_expired()
		self.validate_justification()

	def before_update_after_submit(self):
		self.validate_rejection_reason()
		self.suppress_notifications_if_disabled()

	def on_update_after_submit(self):
		self.stamp_approval()
		self.sync_status_with_workflow_state()

	def on_submit(self):
		self.db_set("status", "Pending Approval", update_modified=False)
		self.propagate_selection(selected=True)

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
		self.propagate_selection(selected=False)

	def validate_rejection_reason(self):
		if self.workflow_state == "Rejected" and not (self.rejection_reason or "").strip():
			frappe.throw(
				_("Rejection Reason is mandatory when rejecting a comparison"),
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

	# --- validation -------------------------------------------------------

	def validate_supplier_rows(self):
		if len(self.suppliers) < 2:
			frappe.throw(
				_("A comparison needs at least 2 supplier quotations"),
				title=_("Too Few Suppliers"),
			)
		max_columns = min(cint(get_settings().max_suppliers_in_comparison) or 5, MAX_COLUMNS)
		if len(self.suppliers) > max_columns:
			frappe.throw(
				_("A comparison can hold at most {0} suppliers").format(max_columns),
				title=_("Too Many Suppliers"),
			)
		seen = set()
		for row in self.suppliers:
			if row.supplier_quotation in seen:
				frappe.throw(
					_("Row {0}: Quotation {1} appears more than once").format(
						row.idx, frappe.bold(row.supplier_quotation)
					)
				)
			seen.add(row.supplier_quotation)

	def enforce_minimum_suppliers(self):
		"""Same threshold rule as the RFQ (step 05), read from the linked
		requisition and applied per threshold_enforcement."""
		requisition = self.purchase_requisition or frappe.db.get_value(
			"VMG Request for Quotation", self.request_for_quotation, "purchase_requisition"
		)
		if not requisition:
			return
		value, is_new = frappe.db.get_value(
			"VMG Purchase Requisition",
			requisition,
			["total_estimated_value", "is_new_product_or_service"],
		)
		settings = get_settings()
		threshold = flt(settings.quote_threshold_amount)
		if flt(value) > threshold:
			required = cint(settings.min_suppliers_above_threshold) or 3
			reason = _("value AED {0} exceeds AED {1}").format(fmt_money(value), fmt_money(threshold))
		elif cint(is_new):
			required = cint(settings.min_suppliers_for_new_item) or 3
			reason = _("new product or service")
		else:
			required = 1
			reason = ""
		if len(self.suppliers) >= required:
			return
		action = settings.threshold_enforcement or "Warn"
		message = _("Only {0} quotation(s) compared: at least {1} suppliers required ({2})").format(
			len(self.suppliers), required, reason
		)
		if action == "Stop":
			frappe.throw(message, title=_("Minimum Suppliers Not Met"))
		elif action == "Warn":
			frappe.msgprint(message, title=_("Minimum Suppliers Not Met"), indicator="orange")

	def sync_selection(self):
		"""Keep selected_supplier / row flags consistent with the award. In
		Split by Item mode multiple supplier rows can be selected (one per
		awarded column), mirroring the Comparative Statement pattern."""
		if self.is_split_award:
			self.sync_item_awards()
			return
		for row in self.items:
			row.awarded_column = None
			row.awarded_supplier = None
		if self.selected_quotation:
			row = next(
				(r for r in self.suppliers if r.supplier_quotation == self.selected_quotation),
				None,
			)
			if not row:
				frappe.throw(
					_("Selected quotation {0} is not one of the compared quotations").format(
						frappe.bold(self.selected_quotation)
					),
					title=_("Invalid Selection"),
				)
			self.selected_supplier = row.supplier
		for row in self.suppliers:
			row.is_selected = 1 if (
				self.selected_quotation and row.supplier_quotation == self.selected_quotation
			) else 0
		if self.selected_quotation:
			self.awarded_value = frappe.db.get_value(
				"VMG Supplier Quotation", self.selected_quotation, "grand_total"
			)

	def sync_item_awards(self):
		"""Split by Item: validate each awarded column, stamp the supplier name
		on the line, flag every awarded supplier row as selected and total up
		the awarded value (net of VAT: each LPO carries its own VAT)."""
		by_column = {cint(row.column_no): row for row in self.suppliers}
		awarded_columns = set()
		awarded_value = 0.0
		for row in self.items:
			if not cint(row.awarded_column):
				row.awarded_column = None
				row.awarded_supplier = None
				continue
			column = cint(row.awarded_column)
			supplier_row = by_column.get(column)
			if not supplier_row:
				frappe.throw(
					_("Item row {0}: award column {1} does not match any supplier column").format(
						row.idx, frappe.bold(column)
					),
					title=_("Invalid Award"),
				)
			if row.get(f"rate_{column}") is None:
				frappe.throw(
					_("Item row {0}: {1} (column {2}) did not quote this line").format(
						row.idx,
						frappe.bold(supplier_row.supplier_name or supplier_row.supplier),
						column,
					),
					title=_("Invalid Award"),
				)
			row.awarded_supplier = supplier_row.supplier_name or supplier_row.supplier
			awarded_columns.add(column)
			awarded_value += flt(row.get(f"amount_{column}"))
		for row in self.suppliers:
			row.is_selected = 1 if cint(row.column_no) in awarded_columns else 0
		self.selected_supplier = None
		self.selected_quotation = None
		self.awarded_value = awarded_value

	def get_awarded_supplier_rows(self):
		"""Supplier rows holding at least one awarded line (Split by Item)."""
		awarded_columns = {
			cint(row.awarded_column) for row in self.items if cint(row.awarded_column)
		}
		return [r for r in self.suppliers if cint(r.column_no) in awarded_columns]

	def compute_lowest_flags(self):
		totals = [flt(row.grand_total) for row in self.suppliers if row.grand_total is not None]
		lowest_total = min(totals) if totals else 0
		for row in self.suppliers:
			row.is_lowest_total = 1 if flt(row.grand_total) == lowest_total else 0
		if self.is_split_award:
			awarded = [row for row in self.items if cint(row.awarded_column)]
			self.is_lowest_price = 1 if awarded and all(
				cint(row.awarded_column) == cint(row.lowest_column) for row in awarded
			) else 0
		elif self.selected_quotation:
			selected_row = next(
				(r for r in self.suppliers if r.supplier_quotation == self.selected_quotation), None
			)
			self.is_lowest_price = 1 if selected_row and selected_row.is_lowest_total else 0
		else:
			self.is_lowest_price = 0

	def awarded_or_selected_suppliers(self):
		if self.is_split_award:
			return [(r.supplier, r.supplier_name) for r in self.get_awarded_supplier_rows()]
		if self.selected_supplier:
			return [(self.selected_supplier, self.selected_supplier)]
		return []

	def warn_unapproved_selection(self):
		for supplier, label in self.awarded_or_selected_suppliers():
			if not cint(frappe.db.get_value("Supplier", supplier, "vmg_is_approved")):
				frappe.msgprint(
					_(
						"Selected supplier {0} is not on the Approved Supplier List:"
						" a justification is required"
					).format(frappe.bold(label or supplier)),
					title=_("Unapproved Supplier Selected"),
					indicator="orange",
				)

	def validate_selection_complete(self):
		if self.is_split_award:
			unawarded = [str(row.idx) for row in self.items if not cint(row.awarded_column)]
			if unawarded:
				frappe.throw(
					_(
						"Every line must be awarded to a supplier column before submitting:"
						" item row(s) {0} have no Award Col"
					).format(frappe.bold(", ".join(unawarded))),
					title=_("Award Incomplete"),
				)
			if not self.selection_basis:
				frappe.throw(
					_("Selection Basis is mandatory before submitting the comparison"),
					title=_("Selection Incomplete"),
				)
			return
		for fieldname in ("selected_supplier", "selected_quotation", "selection_basis"):
			if not self.get(fieldname):
				frappe.throw(
					_("{0} is mandatory before submitting the comparison").format(
						_(self.meta.get_label(fieldname))
					),
					title=_("Selection Incomplete"),
				)

	def validate_selected_quotation_not_expired(self):
		if self.is_split_award:
			quotations = [r.supplier_quotation for r in self.get_awarded_supplier_rows()]
		else:
			quotations = [self.selected_quotation]
		for quotation in quotations:
			status, valid_till = frappe.db.get_value(
				"VMG Supplier Quotation", quotation, ["status", "valid_till"]
			)
			if status == "Expired" or (valid_till and getdate(valid_till) < getdate(nowdate())):
				frappe.throw(
					_(
						"Selected quotation {0} has expired (valid till {1}): obtain a"
						" revalidation or select another quotation"
					).format(
						frappe.bold(quotation),
						frappe.utils.formatdate(valid_till) if valid_till else "-",
					),
					title=_("Quotation Expired"),
				)

	def validate_justification(self):
		reasons = []
		if not self.is_lowest_price:
			reasons.append(
				_("the award is not the lowest price on every line")
				if self.is_split_award
				else _("the selection is not the lowest price")
			)
		unapproved = [
			label or supplier
			for supplier, label in self.awarded_or_selected_suppliers()
			if not cint(frappe.db.get_value("Supplier", supplier, "vmg_is_approved"))
		]
		if unapproved:
			reasons.append(
				_("supplier(s) {0} are not on the Approved Supplier List").format(
					", ".join(unapproved)
				)
			)
		if reasons and not (self.justification or "").strip():
			frappe.throw(
				_("Justification is mandatory because {0}").format(_(" and ").join(reasons)),
				title=_("Justification Required"),
			)

	# --- generation -------------------------------------------------------

	@frappe.whitelist()
	def get_quotations(self):
		"""Rebuild the suppliers and items tables from every submitted,
		non-expired quotation of the linked RFQ. Safe to re-run."""
		if self.docstatus != 0:
			frappe.throw(_("Get Quotations only works on a draft comparison"))
		if not self.request_for_quotation:
			frappe.throw(_("Select a Request for Quotation first"))

		names = frappe.get_all(
			"VMG Supplier Quotation",
			filters={
				"request_for_quotation": self.request_for_quotation,
				"docstatus": 1,
				"status": ["!=", "Expired"],
			},
			order_by="creation asc",
			pluck="name",
		)
		max_columns = min(cint(get_settings().max_suppliers_in_comparison) or 5, MAX_COLUMNS)
		if len(names) > max_columns:
			frappe.msgprint(
				_(
					"{0} quotations found but the comparison holds at most {1}:"
					" the first {1} were pulled"
				).format(len(names), max_columns),
				indicator="orange",
			)
			names = names[:max_columns]
		if not names:
			frappe.throw(
				_("No submitted, non-expired quotations found for {0}").format(
					self.request_for_quotation
				),
				title=_("Nothing to Compare"),
			)

		quotations = [frappe.get_doc("VMG Supplier Quotation", name) for name in names]

		rfq_item_names = set(
			frappe.get_all(
				"VMG RFQ Item", filters={"parent": self.request_for_quotation}, pluck="name"
			)
		)
		total_items = len(rfq_item_names)

		self.set("suppliers", [])
		for column_no, quotation in enumerate(quotations, 1):
			quoted_ids = [row.rfq_item for row in quotation.items]
			quoted = len({q for q in quoted_ids if q in rfq_item_names})
			extra = sum(1 for q in quoted_ids if not q or q not in rfq_item_names)
			items_quoted = f"{quoted} / {total_items}" + (f" (+{extra})" if extra else "")
			self.append(
				"suppliers",
				{
					"column_no": column_no,
					"supplier": quotation.supplier,
					"supplier_name": quotation.supplier_name,
					"supplier_quotation": quotation.name,
					"quotation_ref": quotation.supplier_quotation_ref,
					"items_quoted": items_quoted,
					"grand_total": quotation.grand_total,
					"delivery_days": quotation.delivery_days,
					"payment_terms": quotation.payment_terms,
					"is_approved_supplier": quotation.is_approved_supplier,
					"valid_till": quotation.valid_till,
				},
			)

		self.build_item_matrix(quotations)
		self.sync_selection()
		self.compute_lowest_flags()

	def build_item_matrix(self, quotations):
		"""One row per distinct line, matched on rfq_item first and description
		second; unmatched supplier lines become their own rows."""
		self.set("items", [])
		rows, order = {}, []

		for rfq_row in frappe.get_all(
			"VMG RFQ Item",
			filters={"parent": self.request_for_quotation},
			fields=["name", "description", "qty", "uom"],
			order_by="idx asc",
		):
			key = ("rfq", rfq_row.name)
			rows[key] = {"description": rfq_row.description, "qty": rfq_row.qty, "uom": rfq_row.uom}
			order.append(key)

		def find_by_description(description):
			needle = (description or "").strip().lower()
			for key in order:
				if (rows[key]["description"] or "").strip().lower() == needle:
					return key
			return None

		for column_no, quotation in enumerate(quotations, 1):
			for line in quotation.items:
				key = None
				if line.rfq_item and ("rfq", line.rfq_item) in rows:
					key = ("rfq", line.rfq_item)
				if not key:
					key = find_by_description(line.description)
				if not key:
					key = ("extra", line.name)
					rows[key] = {"description": line.description, "qty": line.qty, "uom": line.uom}
					order.append(key)
				rows[key][f"rate_{column_no}"] = flt(line.rate)
				rows[key][f"amount_{column_no}"] = flt(line.amount)

		for key in order:
			data = rows[key]
			quoted = [
				(column_no, data.get(f"rate_{column_no}"))
				for column_no in range(1, len(quotations) + 1)
				if data.get(f"rate_{column_no}") is not None
			]
			if quoted:
				lowest_column = min(quoted, key=lambda pair: pair[1])[0]
				data["lowest_column"] = lowest_column
				data["lowest_supplier"] = (
					quotations[lowest_column - 1].supplier_name
					or quotations[lowest_column - 1].supplier
				)
			self.append("items", data)

	# --- status propagation ------------------------------------------------

	def propagate_selection(self, selected):
		"""Stamp Selected / Not Selected on the quotations (reverse on cancel)
		and keep the RFQ status in step. In Split by Item mode every quotation
		holding an awarded line counts as Selected."""
		if self.is_split_award:
			selected_quotations = {r.supplier_quotation for r in self.get_awarded_supplier_rows()}
		else:
			selected_quotations = {self.selected_quotation}
		for row in self.suppliers:
			if selected:
				status = "Selected" if row.supplier_quotation in selected_quotations else "Not Selected"
			else:
				valid_till = frappe.db.get_value(
					"VMG Supplier Quotation", row.supplier_quotation, "valid_till"
				)
				expired = valid_till and getdate(valid_till) < getdate(nowdate())
				status = "Expired" if expired else "Submitted"
			frappe.db.set_value(
				"VMG Supplier Quotation", row.supplier_quotation, "status", status,
				update_modified=False,
			)

		rfq_status = frappe.db.get_value(
			"VMG Request for Quotation", self.request_for_quotation, ["docstatus", "status"], as_dict=True
		)
		if rfq_status and rfq_status.docstatus == 1:
			if selected and rfq_status.status != "Comparison Created":
				frappe.db.set_value(
					"VMG Request for Quotation", self.request_for_quotation,
					"status", "Comparison Created", update_modified=False,
				)
			elif not selected and rfq_status.status == "Comparison Created":
				frappe.db.set_value(
					"VMG Request for Quotation", self.request_for_quotation,
					"status", "Quotations Received", update_modified=False,
				)


def compute_ordered_status(comparison_name):
	"""Recompute the post-approval status from the submitted LPOs against the
	comparison. Single mode: any LPO -> Ordered. Split by Item: every awarded
	quotation needs its own submitted LPO -> Ordered; some -> Partially
	Ordered; none -> Approved."""
	comparison = frappe.get_doc("VMG Quotation Comparison", comparison_name)
	ordered_quotations = set(
		frappe.get_all(
			"VMG Local Purchase Order",
			filters={"quotation_comparison": comparison_name, "docstatus": 1},
			pluck="supplier_quotation",
		)
	)
	if comparison.award_mode == "Split by Item":
		awarded = {r.supplier_quotation for r in comparison.get_awarded_supplier_rows()}
		if awarded and awarded <= ordered_quotations:
			return "Ordered"
		if ordered_quotations:
			return "Partially Ordered"
		return "Approved"
	return "Ordered" if ordered_quotations else "Approved"


def _match_quotation_line(lines, used, comparison_row, column):
	"""Find the quotation line behind a comparison matrix row: description
	first (build_item_matrix's rule), then rate as a fallback."""
	needle = (comparison_row.description or "").strip().lower()
	for line in lines:
		if line.name not in used and (line.description or "").strip().lower() == needle:
			return line
	rate = flt(comparison_row.get(f"rate_{column}"))
	for line in lines:
		if line.name not in used and flt(line.rate) == rate:
			return line
	return None


@frappe.whitelist()
def make_lpo_from_comparison(source_name, target_doc=None, supplier_quotation=None):
	"""Approved comparison -> VMG Local Purchase Order (route: From Comparison).
	Server-enforced: only a submitted comparison in workflow state Approved may
	create an LPO. Single mode copies the selected quotation's items; Split by
	Item mode needs supplier_quotation (one of the awarded quotations) and
	copies only the lines awarded to that supplier, so each awarded supplier
	gets their own LPO (Comparative Statement pattern)."""
	from frappe.model.mapper import get_mapped_doc

	docstatus, workflow_state = frappe.db.get_value(
		"VMG Quotation Comparison", source_name, ["docstatus", "workflow_state"]
	)
	if docstatus != 1 or workflow_state != "Approved":
		frappe.throw(
			_(
				"Only an Approved comparison may create a Local Purchase Order"
				" (current state: {0})"
			).format(frappe.bold(workflow_state or "Draft")),
			title=_("Not Approved"),
		)

	def set_missing_values(source, target):
		target.quotation_comparison = source.name
		target.purchase_requisition = source.purchase_requisition
		target.order_route = "From Comparison"
		target.is_direct_order = 0
		if source.purchase_requisition:
			required_by, job_number = frappe.db.get_value(
				"VMG Purchase Requisition",
				source.purchase_requisition,
				["required_by_date", "job_number"],
			)
			target.required_delivery_date = required_by
			if not target.job_number:
				target.job_number = job_number

		if source.award_mode == "Split by Item":
			awarded_rows = {r.supplier_quotation: r for r in source.get_awarded_supplier_rows()}
			if not supplier_quotation:
				frappe.throw(
					_(
						"This comparison is awarded item-wise: pick which awarded"
						" supplier the LPO is for"
					),
					title=_("Supplier Required"),
				)
			supplier_row = awarded_rows.get(supplier_quotation)
			if not supplier_row:
				frappe.throw(
					_("Quotation {0} holds no awarded lines on this comparison").format(
						frappe.bold(supplier_quotation)
					),
					title=_("Not Awarded"),
				)
			target.supplier = supplier_row.supplier
			target.supplier_quotation = supplier_row.supplier_quotation
			quotation = frappe.get_doc("VMG Supplier Quotation", supplier_row.supplier_quotation)
			column = cint(supplier_row.column_no)
			lines, used, awarded_net = list(quotation.items), set(), 0.0
			for row in source.items:
				if cint(row.awarded_column) != column:
					continue
				line = _match_quotation_line(lines, used, row, column)
				if not line:
					frappe.throw(
						_("Could not match item row {0} back to a line of {1}").format(
							row.idx, frappe.bold(quotation.name)
						),
						title=_("Line Mismatch"),
					)
				used.add(line.name)
				awarded_net += flt(line.amount)
				target.append(
					"items",
					{
						"item_code": line.item_code,
						"description": line.description,
						"qty": line.qty,
						"uom": line.uom,
						"rate": line.rate,
						"remarks": line.remarks,
						"requisition_item": line.requisition_item,
					},
				)
			# prorate a quotation-level discount by the awarded share
			if flt(quotation.discount_amount) and flt(quotation.total):
				target.discount_amount = flt(
					flt(quotation.discount_amount) * awarded_net / flt(quotation.total), 2
				)
			target.vat_rate = quotation.vat_rate
		else:
			target.supplier = source.selected_supplier
			target.supplier_quotation = source.selected_quotation
			quotation = frappe.get_doc("VMG Supplier Quotation", source.selected_quotation)
			target.discount_amount = quotation.discount_amount
			target.vat_rate = quotation.vat_rate
			for line in quotation.items:
				target.append(
					"items",
					{
						"item_code": line.item_code,
						"description": line.description,
						"qty": line.qty,
						"uom": line.uom,
						"rate": line.rate,
						"remarks": line.remarks,
						"requisition_item": line.requisition_item,
					},
				)

		if target.supplier and not frappe.db.get_value(
			"Supplier", target.supplier, "vmg_is_approved"
		):
			# the approved comparison already justified the unapproved supplier
			target.non_approved_supplier_justification = source.justification

	return get_mapped_doc(
		"VMG Quotation Comparison",
		source_name,
		{
			"VMG Quotation Comparison": {
				"doctype": "VMG Local Purchase Order",
				"field_map": {"name": "quotation_comparison"},
				"validation": {"docstatus": ["=", 1]},
			},
		},
		target_doc,
		set_missing_values,
	)


@frappe.whitelist()
def make_local_purchase_order(source_name, target_doc=None):
	"""Backwards-compatible alias used by the step 08 form button."""
	return make_lpo_from_comparison(source_name, target_doc)
