# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

from frappe import _

# All connections are internal links (no + button): creation happens through
# the forms' Create buttons. Reverse connections use a fieldname absent on
# this doctype so counting falls back to the external query via fieldname.


def get_data():
	return {
		"fieldname": "request_for_quotation",
		"internal_links": {
			"VMG Purchase Requisition": "purchase_requisition",
			"VMG Supplier Quotation": "request_for_quotation",
			"VMG Quotation Comparison": "request_for_quotation",
		},
		"transactions": [
			{
				"label": _("Reference"),
				"items": ["VMG Purchase Requisition"],
			},
			{
				"label": _("Quotations"),
				"items": ["VMG Supplier Quotation", "VMG Quotation Comparison"],
			},
		],
	}
