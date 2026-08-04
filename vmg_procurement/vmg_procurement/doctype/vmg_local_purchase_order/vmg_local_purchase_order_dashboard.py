# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

from frappe import _

# All connections are internal links (no + button): creation happens through
# the forms' Create buttons. Reverse connections use a fieldname absent on
# this doctype so counting falls back to the external query via fieldname.


def get_data():
	return {
		"fieldname": "local_purchase_order",
		"internal_links": {
			"VMG Purchase Requisition": "purchase_requisition",
			"VMG Quotation Comparison": "quotation_comparison",
			"VMG Supplier Quotation": "supplier_quotation",
			"VMG Purchase Receipt": "local_purchase_order",
			"VMG Supplier Invoice": "local_purchase_order",
		},
		"transactions": [
			{
				"label": _("Reference"),
				"items": [
					"VMG Purchase Requisition",
					"VMG Quotation Comparison",
					"VMG Supplier Quotation",
				],
			},
			{
				"label": _("Fulfilment"),
				"items": ["VMG Purchase Receipt", "VMG Supplier Invoice"],
			},
		],
	}
