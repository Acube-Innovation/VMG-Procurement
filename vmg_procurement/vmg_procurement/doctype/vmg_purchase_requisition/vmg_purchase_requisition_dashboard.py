# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

from frappe import _

# Every connection is declared in internal_links so the Connections tab shows
# no + (add) button: documents are created through the forms' Create buttons.
# For connections whose link field lives on the other doctype, the fieldname
# given here does not exist on this doctype, so the count falls back to the
# external reverse-link query driven by fieldname / non_standard_fieldnames.


def get_data():
	return {
		"fieldname": "purchase_requisition",
		"non_standard_fieldnames": {
			"Material Request": "vmg_purchase_requisition",
			"Purchase Order": "vmg_purchase_requisition",
			"Purchase Receipt": "vmg_purchase_requisition",
			"Purchase Invoice": "vmg_purchase_requisition",
			"Asset": "vmg_purchase_requisition",
		},
		"internal_links": {
			"VMG Request for Quotation": "purchase_requisition",
			"VMG Supplier Quotation": "purchase_requisition",
			"VMG Quotation Comparison": "purchase_requisition",
			"VMG Local Purchase Order": "purchase_requisition",
			"VMG Purchase Receipt": "purchase_requisition",
			"VMG Supplier Invoice": "purchase_requisition",
			"VMG PPE and Uniform Handover": "purchase_requisition",
			"Material Request": "vmg_purchase_requisition",
			"Purchase Order": "vmg_purchase_requisition",
			"Purchase Receipt": "vmg_purchase_requisition",
			"Purchase Invoice": "vmg_purchase_requisition",
			"Asset": "vmg_purchase_requisition",
		},
		"transactions": [
			{
				"label": _("Quotations"),
				"items": [
					"VMG Request for Quotation",
					"VMG Supplier Quotation",
					"VMG Quotation Comparison",
				],
			},
			{
				"label": _("Orders & Fulfilment"),
				"items": [
					"VMG Local Purchase Order",
					"VMG Purchase Receipt",
					"VMG Supplier Invoice",
				],
			},
			{
				"label": _("Asset Chain"),
				"items": [
					"Material Request",
					"Purchase Order",
					"Purchase Receipt",
					"Purchase Invoice",
					"Asset",
				],
			},
			{
				"label": _("Related"),
				"items": ["VMG PPE and Uniform Handover"],
			},
		],
	}
