# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

"""Routing of an Approved VMG Purchase Requisition into the correct chain.

Asset requisitions go to the core chain (Material Request of type Purchase);
everything else goes to the custom non-stock chain (VMG Request for Quotation,
or VMG Local Purchase Order for the direct order case). The custom chain
targets are built in later steps, so every mapper checks that its target
DocType exists and raises a clear message if it does not.
"""

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc

DIRECT_ORDER_ROLE = "VMG Procurement Manager"

# downstream doctype -> (link field pointing back to the requisition,
#                        status bucket applied when a submitted one exists)
# MR/RFQ mean "sourcing started" -> RFQ Created; LPO/PO mean "Ordered".
DOWNSTREAM_DOCTYPES = {
	"Material Request": ("vmg_purchase_requisition", "RFQ Created"),
	"VMG Request for Quotation": ("purchase_requisition", "RFQ Created"),
	"VMG Local Purchase Order": ("purchase_requisition", "Ordered"),
	"Purchase Order": ("vmg_purchase_requisition", "Ordered"),
	"Supplier Quotation": ("vmg_purchase_requisition", None),
	"Purchase Receipt": ("vmg_purchase_requisition", None),
	"Purchase Invoice": ("vmg_purchase_requisition", None),
}

TARGET_BUILD_STEP = {
	"VMG Request for Quotation": "05 request for quotation",
	"VMG Local Purchase Order": "09 local purchase order",
}


@frappe.whitelist()
def get_allowed_targets(requisition_name):
	"""Allowed next DocTypes for a requisition. Used by the Create buttons on
	the form and by every mapper below, so UI and server always agree."""
	requisition_type = frappe.db.get_value(
		"VMG Purchase Requisition", requisition_name, "requisition_type"
	)
	if requisition_type == "Asset":
		return ["Material Request"]

	targets = ["VMG Request for Quotation"]
	if DIRECT_ORDER_ROLE in frappe.get_roles():
		targets.append("VMG Local Purchase Order")
	return targets


def _get_validated_source(source_name, target_doctype):
	source = frappe.get_doc("VMG Purchase Requisition", source_name)

	if source.docstatus != 1 or source.workflow_state != "Approved":
		frappe.throw(
			_(
				"Requisition {0} must be submitted and Approved before creating a"
				" downstream document (current state: {1})"
			).format(source_name, frappe.bold(source.workflow_state or source.status)),
			title=_("Not Approved"),
		)

	if target_doctype not in get_allowed_targets(source_name):
		if source.requisition_type == "Asset":
			frappe.throw(
				_(
					"Requisition {0} is an Asset requisition: the only allowed next"
					" document is a core Material Request of type Purchase"
				).format(source_name),
				title=_("Wrong Chain"),
			)
		frappe.throw(
			_(
				"Requisition {0} ({1}) belongs to the custom non-stock chain: create a"
				" VMG Request for Quotation (or a direct VMG Local Purchase Order as"
				" {2}) instead of {3}"
			).format(
				source_name, source.requisition_type, DIRECT_ORDER_ROLE, target_doctype
			),
			title=_("Wrong Chain"),
		)

	if not frappe.db.exists("DocType", target_doctype):
		frappe.throw(
			_("{0} is not built yet: it arrives in build step {1}. Nothing was created.").format(
				target_doctype, frappe.bold(TARGET_BUILD_STEP.get(target_doctype, "?"))
			),
			title=_("Not Available Yet"),
		)

	return source


@frappe.whitelist()
def make_material_request(source_name, target_doc=None):
	"""Asset requisition -> core Material Request (type Purchase)."""
	source = _get_validated_source(source_name, "Material Request")

	for item in source.items:
		if not item.item_code or not frappe.db.get_value("Item", item.item_code, "is_fixed_asset"):
			frappe.throw(
				_("Row {0}: Item Code is mandatory and must be a fixed asset item").format(
					item.idx
				),
				title=_("Fixed Asset Item Required"),
			)

	def set_missing_values(source, target):
		target.material_request_type = "Purchase"
		target.company = (
			frappe.defaults.get_global_default("company")
			or frappe.db.get_single_value("Global Defaults", "default_company")
		)
		target.schedule_date = source.required_by_date
		target.vmg_purchase_requisition = source.name
		target.vmg_division = source.division
		target.run_method("set_missing_values")

	def update_item(obj, target, source_parent):
		target.schedule_date = obj.required_by_date or source_parent.required_by_date
		target.cost_center = source_parent.cost_center
		target.project = source_parent.project
		target.vmg_requisition_item = obj.name

	return get_mapped_doc(
		"VMG Purchase Requisition",
		source_name,
		{
			"VMG Purchase Requisition": {
				"doctype": "Material Request",
				"validation": {"docstatus": ["=", 1]},
			},
			"VMG Purchase Requisition Item": {
				"doctype": "Material Request Item",
				"field_map": {"name": "vmg_requisition_item"},
				"postprocess": update_item,
			},
		},
		target_doc,
		set_missing_values,
	)


@frappe.whitelist()
def make_vmg_rfq(source_name, target_doc=None):
	"""Non-asset requisition -> VMG Request for Quotation (built in step 05)."""
	source = _get_validated_source(source_name, "VMG Request for Quotation")

	def set_missing_values(source, target):
		target.purchase_requisition = source.name
		target.division = source.division
		target.project = source.project
		target.cost_center = source.cost_center

	return get_mapped_doc(
		"VMG Purchase Requisition",
		source_name,
		{
			"VMG Purchase Requisition": {
				"doctype": "VMG Request for Quotation",
				"validation": {"docstatus": ["=", 1]},
			},
			"VMG Purchase Requisition Item": {
				"doctype": "VMG RFQ Item",
				"field_map": {"name": "requisition_item"},
			},
		},
		target_doc,
		set_missing_values,
	)


@frappe.whitelist()
def make_vmg_lpo(source_name, target_doc=None):
	"""Non-asset requisition -> direct VMG Local Purchase Order (built in step
	09), skipping the quotation comparison stage. The mapper records the skip;
	step 09 validates that a justification is filled before submit."""
	source = _get_validated_source(source_name, "VMG Local Purchase Order")

	def set_missing_values(source, target):
		target.purchase_requisition = source.name
		target.division = source.division
		target.project = source.project
		target.cost_center = source.cost_center
		target.required_delivery_date = source.required_by_date
		target.order_route = "Direct Order"
		target.is_direct_order = 1

	return get_mapped_doc(
		"VMG Purchase Requisition",
		source_name,
		{
			"VMG Purchase Requisition": {
				"doctype": "VMG Local Purchase Order",
				"validation": {"docstatus": ["=", 1]},
			},
			"VMG Purchase Requisition Item": {
				"doctype": "VMG LPO Item",
				"field_map": {"name": "requisition_item", "estimated_rate": "rate"},
			},
		},
		target_doc,
		set_missing_values,
	)


def get_downstream_documents(requisition_name):
	"""All non-cancelled downstream documents of a requisition as
	[(doctype, name), ...]. Used to block cancellation."""
	found = []
	for doctype, (fieldname, _bucket) in DOWNSTREAM_DOCTYPES.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		for name in frappe.get_all(
			doctype,
			filters={fieldname: requisition_name, "docstatus": ["<", 2]},
			pluck="name",
		):
			found.append((doctype, name))
	return found


def update_requisition_status(requisition_name):
	"""Recompute the requisition status from its submitted downstream
	documents. Called on submit AND cancel of downstream documents, so the
	status also reverts (to Approved) when they are cancelled."""
	requisition = frappe.db.get_value(
		"VMG Purchase Requisition",
		requisition_name,
		["docstatus", "status", "workflow_state"],
		as_dict=True,
	)
	if not requisition or requisition.docstatus != 1:
		return

	status = "Approved" if requisition.workflow_state == "Approved" else requisition.status
	for doctype, (fieldname, bucket) in DOWNSTREAM_DOCTYPES.items():
		if not bucket or not frappe.db.exists("DocType", doctype):
			continue
		if frappe.db.exists(doctype, {fieldname: requisition_name, "docstatus": 1}):
			status = bucket
			if bucket == "Ordered":
				status = _ordered_or_partial(requisition_name)
				break

	if status != requisition.status:
		frappe.db.set_value(
			"VMG Purchase Requisition", requisition_name, "status", status, update_modified=False
		)


def _ordered_or_partial(requisition_name):
	"""Ordered when every requisition item is fully covered by submitted LPOs,
	otherwise Partially Ordered (ordered_qty is maintained by the LPO)."""
	pending = frappe.db.sql(
		"""
		select count(*) from `tabVMG Purchase Requisition Item`
		where parent = %s and ifnull(ordered_qty, 0) < ifnull(qty, 0)
		""",
		requisition_name,
	)[0][0]
	return "Partially Ordered" if pending else "Ordered"


# ---------------------------------------------------------------------------
# doc_events hooks (registered in hooks.py). The VMG RFQ / LPO hooks are
# registered already but only fire once those DocTypes exist.


def on_material_request_submit(doc, method=None):
	requisition = doc.get("vmg_purchase_requisition")
	if not requisition:
		return
	requisition_type = frappe.db.get_value(
		"VMG Purchase Requisition", requisition, "requisition_type"
	)
	if requisition_type != "Asset":
		frappe.throw(
			_(
				"Material Request {0} traces back to requisition {1} of type {2}."
				" Only Asset requisitions may enter the core chain: use a"
				" VMG Request for Quotation instead."
			).format(doc.name, requisition, frappe.bold(requisition_type)),
			title=_("Wrong Chain"),
		)
	update_requisition_status(requisition)


def on_material_request_cancel(doc, method=None):
	if doc.get("vmg_purchase_requisition"):
		update_requisition_status(doc.vmg_purchase_requisition)


def on_vmg_rfq_submit(doc, method=None):
	requisition = doc.get("purchase_requisition")
	if not requisition:
		return
	requisition_type = frappe.db.get_value(
		"VMG Purchase Requisition", requisition, "requisition_type"
	)
	if requisition_type == "Asset":
		frappe.throw(
			_(
				"Requisition {0} is an Asset requisition and must go through a core"
				" Material Request, not a VMG Request for Quotation"
			).format(requisition),
			title=_("Wrong Chain"),
		)
	update_requisition_status(requisition)


def on_vmg_rfq_cancel(doc, method=None):
	if doc.get("purchase_requisition"):
		update_requisition_status(doc.purchase_requisition)


def on_vmg_lpo_submit(doc, method=None):
	if doc.get("purchase_requisition"):
		update_requisition_status(doc.purchase_requisition)


def on_vmg_lpo_cancel(doc, method=None):
	if doc.get("purchase_requisition"):
		update_requisition_status(doc.purchase_requisition)
