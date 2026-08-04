# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

from frappe import _

# All connections are internal links (no + button): creation happens through
# the forms' Create buttons. Reverse connections use a fieldname absent on
# this doctype so counting falls back to the external query via fieldname.


def get_data():
	return {
		"fieldname": "supplier_quotation",
		"non_standard_fieldnames": {
			"VMG Quotation Comparison": "selected_quotation",
		},
		"internal_links": {
			"VMG Purchase Requisition": "purchase_requisition",
			"VMG Request for Quotation": "request_for_quotation",
			"VMG Quotation Comparison": "selected_quotation",
			"VMG Local Purchase Order": "supplier_quotation",
		},
		"transactions": [
			{
				"label": _("Reference"),
				"items": ["VMG Purchase Requisition", "VMG Request for Quotation"],
			},
			{
				"label": _("Downstream"),
				"items": ["VMG Quotation Comparison", "VMG Local Purchase Order"],
			},
		],
	}
