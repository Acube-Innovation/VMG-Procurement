# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

"""Asset procurement branch on core ERPNext DocTypes (step 11).

No core file is touched: everything here runs through hooks doc_events,
Custom Fields and Property Setters. Only Asset-type VMG requisitions may
enter this chain; ordinary purchases belong on the VMG Local Purchase Order.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from vmg_procurement.setup import ASSET_SERIES

PO_CREATOR_ROLES = {"VMG Procurement User", "VMG Procurement Manager", "System Manager"}

# where each core doctype's items point to their upstream document
UPSTREAM_SOURCE = {
	"Supplier Quotation": [("material_request", "Material Request")],
	"Purchase Order": [("material_request", "Material Request")],
	"Purchase Receipt": [("purchase_order", "Purchase Order")],
	"Purchase Invoice": [
		("purchase_receipt", "Purchase Receipt"),
		("purchase_order", "Purchase Order"),
	],
}


def _requisition_type(requisition):
	return frappe.db.get_value("VMG Purchase Requisition", requisition, "requisition_type")


def apply_asset_chain_rules(doc, method=None):
	"""before_insert + validate on MR / SQ / PO / PR / PI: propagate the
	requisition trace from the upstream document and pin the ASSET-* series."""
	propagate_requisition_link(doc)
	set_asset_naming_series(doc)


def propagate_requisition_link(doc):
	if doc.get("vmg_purchase_requisition"):
		return
	for item_field, source_doctype in UPSTREAM_SOURCE.get(doc.doctype, []):
		source_names = {row.get(item_field) for row in doc.get("items") or [] if row.get(item_field)}
		for source_name in source_names:
			requisition, division = frappe.db.get_value(
				source_doctype, source_name, ["vmg_purchase_requisition", "vmg_division"]
			) or (None, None)
			if requisition:
				doc.vmg_purchase_requisition = requisition
				doc.vmg_division = doc.get("vmg_division") or division
				return


def set_asset_naming_series(doc, method=None):
	series = ASSET_SERIES.get(doc.doctype)
	if not series or not doc.get("vmg_purchase_requisition"):
		return
	if _requisition_type(doc.vmg_purchase_requisition) == "Asset":
		doc.naming_series = series


def validate_purchase_order(doc, method=None):
	apply_asset_chain_rules(doc)
	restrict_core_po_creators(doc)

	if not doc.get("vmg_purchase_requisition"):
		return

	if _requisition_type(doc.vmg_purchase_requisition) != "Asset":
		frappe.throw(
			_(
				"Requisition {0} is not an Asset requisition: material and service"
				" purchases must use a VMG Local Purchase Order, not a core"
				" Purchase Order"
			).format(doc.vmg_purchase_requisition),
			title=_("Wrong Chain"),
		)

	for item in doc.items:
		if not item.item_code or not frappe.db.get_value("Item", item.item_code, "is_fixed_asset"):
			frappe.throw(
				_(
					"Row {0}: {1} is not a fixed asset item. Every line of an asset"
					" order must be a fixed asset item."
				).format(item.idx, frappe.bold(item.item_code or item.item_name or "?")),
				title=_("Fixed Asset Item Required"),
			)


def restrict_core_po_creators(doc, method=None):
	"""Core Purchase Orders are the asset chain: keep ordinary users out."""
	if not doc.is_new():
		return
	if PO_CREATOR_ROLES.intersection(frappe.get_roles()):
		return
	frappe.throw(
		_(
			"Core Purchase Orders are reserved for the fixed asset chain and may"
			" only be created by {0}. Material and service purchases go through"
			" the VMG Local Purchase Order."
		).format(_(" or ").join(sorted(PO_CREATOR_ROLES - {"System Manager"}))),
		frappe.PermissionError,
		title=_("Not Permitted"),
	)


def on_purchase_order_submit(doc, method=None):
	if not doc.get("vmg_purchase_requisition"):
		return
	from vmg_procurement.utils.routing import update_requisition_status
	from vmg_procurement.vmg_procurement.doctype.vmg_local_purchase_order.vmg_local_purchase_order import (
		update_requisition_ordered_qty,
	)

	update_requisition_ordered_qty(doc.vmg_purchase_requisition)
	update_requisition_status(doc.vmg_purchase_requisition)


def on_purchase_order_cancel(doc, method=None):
	on_purchase_order_submit(doc, method)


def on_purchase_receipt_submit(doc, method=None):
	"""Asset-chain receipts: confirm one Asset per unit was created, report the
	names, copy the manufacturer serial and stamp the traceability fields."""
	if not doc.get("vmg_purchase_requisition"):
		return
	if _requisition_type(doc.vmg_purchase_requisition) != "Asset":
		return

	messages = []
	for item in doc.items:
		if not frappe.db.get_value("Item", item.item_code, "is_fixed_asset"):
			continue
		assets = frappe.get_all(
			"Asset",
			filters={"purchase_receipt": doc.name, "item_code": item.item_code},
			pluck="name",
		)
		grouped = cint(frappe.db.get_value("Item", item.item_code, "is_grouped_asset"))
		expected = 1 if grouped else cint(flt(item.qty))
		if len(assets) != expected:
			frappe.throw(
				_(
					"Row {0}: expected {1} Asset record(s) for {2} (one per unit) but"
					" found {3}. Enable 'Auto Create Assets on Purchase' on the Item"
					" and check the Asset Category setup."
				).format(item.idx, expected, frappe.bold(item.item_code), len(assets)),
				title=_("Asset Creation Mismatch"),
			)
		for asset in assets:
			values = {
				"vmg_purchase_requisition": doc.vmg_purchase_requisition,
				"vmg_division": doc.get("vmg_division"),
			}
			if item.get("vmg_manufacturer_serial_no"):
				values["vmg_manufacturer_serial_no"] = item.vmg_manufacturer_serial_no
			frappe.db.set_value("Asset", asset, values, update_modified=False)
		messages.append(
			_("Row {0} ({1}): created {2}").format(
				item.idx, item.item_code, ", ".join(frappe.bold(a) for a in assets)
			)
		)

	if messages:
		frappe.msgprint(
			"<br>".join(messages), title=_("Assets Created"), indicator="green"
		)
