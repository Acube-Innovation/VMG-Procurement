# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

from frappe import _

# All connections are internal links (no + button): creation happens through
# the forms' Create buttons. Reverse connections use a fieldname absent on
# this doctype so counting falls back to the external query via fieldname.


def get_data():
	return {
		"fieldname": "quotation_comparison",
		"internal_links": {
			"VMG Purchase Requisition": "purchase_requisition",
			"VMG Request for Quotation": "request_for_quotation",
			"VMG Local Purchase Order": "quotation_comparison",
		},
		"transactions": [
			{
				"label": _("Reference"),
				"items": ["VMG Purchase Requisition", "VMG Request for Quotation"],
			},
			{
				"label": _("Orders"),
				"items": ["VMG Local Purchase Order"],
			},
		],
	}
