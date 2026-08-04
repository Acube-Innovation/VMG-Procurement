# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# --- asset chain (step 11) -------------------------------------------------

ASSET_SERIES = {
	"Material Request": "ASSET-MR-.YYYY.-.#####",
	"Supplier Quotation": "ASSET-SQ-.YYYY.-.#####",
	"Purchase Order": "ASSET-PO-.YYYY.-.#####",
	"Purchase Receipt": "ASSET-PR-.YYYY.-.#####",
	"Purchase Invoice": "ASSET-PI-.YYYY.-.#####",
}


def create_asset_naming_series():
	"""Append the ASSET-* naming series to the core doctypes (Property Setter
	on naming_series options, keeping every existing series) and make the
	series read-only on documents that trace back to a VMG requisition.

	Run on this site with:
	        bench --site vmg execute vmg_procurement.setup.create_asset_naming_series
	New sites get the same property setters from fixtures/property_setter.json.
	"""
	for doctype, series in ASSET_SERIES.items():
		meta_field = frappe.get_meta(doctype).get_field("naming_series")
		options = (meta_field.options or "").split("\n")
		if series not in options:
			options.append(series)
		_make_vmg_property_setter(
			doctype, "naming_series", "options", "\n".join(o for o in options if o), "Text"
		)
		_make_vmg_property_setter(
			doctype,
			"naming_series",
			"read_only_depends_on",
			"eval:doc.vmg_purchase_requisition",
			"Data",
		)


def _make_vmg_property_setter(doctype, fieldname, prop, value, property_type):
	make_property_setter(doctype, fieldname, prop, value, property_type)
	name = f"{doctype}-{fieldname}-{prop}"
	if frappe.db.exists("Property Setter", name):
		frappe.db.set_value("Property Setter", name, "module", "VMG Procurement")


ASSET_CUSTOM_FIELDS = {
	"Asset": [
		{
			"fieldname": "vmg_purchase_requisition",
			"fieldtype": "Link",
			"label": "VMG Purchase Requisition",
			"options": "VMG Purchase Requisition",
			"insert_after": "amended_from",
			"read_only": 1,
			"allow_on_submit": 1,
		},
		{
			"fieldname": "vmg_division",
			"fieldtype": "Link",
			"label": "VMG Division",
			"options": "VMG Division",
			"insert_after": "vmg_purchase_requisition",
			"read_only": 1,
			"allow_on_submit": 1,
		},
		{
			"fieldname": "vmg_manufacturer_serial_no",
			"fieldtype": "Data",
			"label": "Manufacturer Serial No",
			"insert_after": "vmg_division",
			"allow_on_submit": 1,
		},
	],
	"Purchase Receipt Item": [
		{
			"fieldname": "vmg_manufacturer_serial_no",
			"fieldtype": "Data",
			"label": "Manufacturer Serial No",
			"insert_after": "vmg_requisition_item",
			"description": "Copied to the created Asset(s) on submit",
		}
	],
}


def create_asset_custom_fields():
	"""Manufacturer serial + traceability fields for the asset chain.

	Run on this site with:
	        bench --site vmg execute vmg_procurement.setup.create_asset_custom_fields
	"""
	fields = {
		dt: [dict(df, module="VMG Procurement", is_system_generated=0) for df in dfs]
		for dt, dfs in ASSET_CUSTOM_FIELDS.items()
	}
	create_custom_fields(fields, update=True)


PAYMENT_CUSTOM_FIELDS = {
	"Payment Entry Reference": [
		{
			"fieldname": "vmg_supplier_invoice",
			"fieldtype": "Link",
			"label": "VMG Supplier Invoice",
			"options": "VMG Supplier Invoice",
			"read_only": 1,
			"insert_after": "reference_name",
		}
	],
	"Payment Entry": [
		{
			"fieldname": "vmg_budget_override_by",
			"fieldtype": "Link",
			"label": "Budget Override By",
			"options": "User",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "amended_from",
		},
		{
			"fieldname": "vmg_budget_override_on",
			"fieldtype": "Datetime",
			"label": "Budget Override On",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "vmg_budget_override_by",
		},
	],
}


def create_payment_custom_fields():
	"""Trace field so a Payment Entry row points back at the custom invoice.

	Run on this site with:
	        bench --site vmg execute vmg_procurement.setup.create_payment_custom_fields
	"""
	fields = {
		dt: [dict(df, module="VMG Procurement", is_system_generated=0) for df in dfs]
		for dt, dfs in PAYMENT_CUSTOM_FIELDS.items()
	}
	create_custom_fields(fields, update=True)


ASSET_CATEGORY_ACCOUNT_FIELDS = [
	"fixed_asset_account",
	"accumulated_depreciation_account",
	"depreciation_expense_account",
	"capital_work_in_progress_account",
]


def check_asset_setup():
	"""List what is still missing for the asset branch: per Asset Category the
	unset accounts, and asset items missing their flags. Returns a dict and
	prints it, so it can be run with bench execute and sent to the client."""
	missing = {"asset_categories": {}, "items": {}}
	for category in frappe.get_all("Asset Category", pluck="name"):
		doc = frappe.get_doc("Asset Category", category)
		if not doc.accounts:
			missing["asset_categories"][category] = ["no accounts row at all"]
			continue
		for row in doc.accounts:
			absent = [f for f in ASSET_CATEGORY_ACCOUNT_FIELDS if not row.get(f)]
			if absent:
				missing["asset_categories"].setdefault(category, []).extend(
					f"{row.company_name}: {f}" for f in absent
				)
	for item in frappe.get_all(
		"Item",
		filters={"is_fixed_asset": 1},
		fields=["name", "is_stock_item", "asset_category", "asset_naming_series", "auto_create_assets"],
	):
		problems = []
		if item.is_stock_item:
			problems.append("is_stock_item must be 0")
		if not item.asset_category:
			problems.append("asset_category missing")
		if not item.asset_naming_series:
			problems.append("asset_naming_series missing")
		if not item.auto_create_assets:
			problems.append("auto_create_assets off (assets must then be made manually)")
		if problems:
			missing["items"][item.name] = problems
	print(frappe.as_json(missing))
	return missing

SUPPLIER_CUSTOM_FIELDS = {
	"Supplier": [
		{
			"fieldname": "vmg_approval_section",
			"fieldtype": "Section Break",
			"label": "VMG Supplier Approval",
			"insert_after": "supplier_primary_address",
		},
		{
			"fieldname": "vmg_is_approved",
			"fieldtype": "Check",
			"label": "Approved Supplier",
			"insert_after": "vmg_approval_section",
			"in_standard_filter": 1,
		},
		{
			"fieldname": "vmg_approved_on",
			"fieldtype": "Date",
			"label": "Approved On",
			"insert_after": "vmg_is_approved",
		},
		{
			"fieldname": "vmg_supplier_category",
			"fieldtype": "Select",
			"label": "Supplier Category",
			"options": "\nMaterial\nService\nSubcontractor\nRental\nOther",
			"insert_after": "vmg_approved_on",
			"in_standard_filter": 1,
		},
		{
			"description": "Items or materials this supplier provides, as on the Approved Supplier List, e.g. Hardware Items",
			"fieldname": "vmg_items_materials",
			"fieldtype": "Data",
			"label": "Item / Materials",
			"insert_after": "vmg_supplier_category",
		},
		{
			"fieldname": "vmg_approval_column",
			"fieldtype": "Column Break",
			"insert_after": "vmg_items_materials",
		},
		{
			"fieldname": "vmg_trade_licence_no",
			"fieldtype": "Data",
			"label": "Trade Licence No",
			"insert_after": "vmg_approval_column",
		},
		{
			"fieldname": "vmg_trade_licence_expiry",
			"fieldtype": "Date",
			"label": "Trade Licence Expiry",
			"insert_after": "vmg_trade_licence_no",
		},
		{
			"fieldname": "vmg_approval_remarks",
			"fieldtype": "Small Text",
			"label": "Approval Remarks",
			"insert_after": "vmg_trade_licence_expiry",
		},
	]
}


ROUTING_HEADER_DOCTYPES = [
	"Material Request",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
]

ROUTING_ITEM_DOCTYPES = [
	"Material Request Item",
	"Supplier Quotation Item",
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
]


def routing_custom_fields():
	"""Trace-back fields linking core purchase documents to the requisition."""
	fields = {}
	for doctype in ROUTING_HEADER_DOCTYPES:
		fields[doctype] = [
			{
				"fieldname": "vmg_purchase_requisition",
				"fieldtype": "Link",
				"label": "VMG Purchase Requisition",
				"options": "VMG Purchase Requisition",
				"insert_after": "amended_from",
				"read_only": 1,
				"allow_on_submit": 1,
			},
			{
				"fieldname": "vmg_division",
				"fieldtype": "Link",
				"label": "VMG Division",
				"options": "VMG Division",
				"insert_after": "vmg_purchase_requisition",
				"read_only": 1,
			},
		]
	for doctype in ROUTING_ITEM_DOCTYPES:
		fields[doctype] = [
			{
				"fieldname": "vmg_requisition_item",
				"fieldtype": "Data",
				"label": "VMG Requisition Item",
				"hidden": 1,
			}
		]
	return fields


def create_routing_custom_fields():
	"""Create/refresh the routing trace fields on core doctypes. Idempotent.

	Run on this site with:
	        bench --site vmg execute vmg_procurement.setup.create_routing_custom_fields
	New sites get the same fields from fixtures/custom_field.json on migrate.
	"""
	fields = {
		dt: [dict(df, module="VMG Procurement", is_system_generated=0) for df in dfs]
		for dt, dfs in routing_custom_fields().items()
	}
	create_custom_fields(fields, update=True)


def create_supplier_custom_fields():
	"""Create or refresh the VMG custom fields on Supplier. Idempotent.

	Run on this site with:
	        bench --site vmg execute vmg_procurement.setup.create_supplier_custom_fields
	New sites get the same fields from fixtures/custom_field.json on migrate.
	"""
	fields = {
		dt: [dict(df, module="VMG Procurement", is_system_generated=0) for df in dfs]
		for dt, dfs in SUPPLIER_CUSTOM_FIELDS.items()
	}
	create_custom_fields(fields, update=True)
