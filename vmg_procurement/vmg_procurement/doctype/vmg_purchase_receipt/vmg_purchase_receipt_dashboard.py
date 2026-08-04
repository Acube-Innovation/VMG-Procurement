# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

from frappe import _

# All connections are internal links (no + button): creation happens through
# the forms' Create buttons. Reverse connections use a fieldname absent on
# this doctype so counting falls back to the external query via fieldname.


def get_data():
	return {
		"fieldname": "purchase_receipt",
		"internal_links": {
			"VMG Purchase Requisition": "purchase_requisition",
			"VMG Local Purchase Order": "local_purchase_order",
			"VMG Supplier Invoice": "purchase_receipt",
			"VMG PPE and Uniform Handover": "purchase_receipt",
		},
		"transactions": [
			{
				"label": _("Reference"),
				"items": ["VMG Purchase Requisition", "VMG Local Purchase Order"],
			},
			{
				"label": _("Downstream"),
				"items": ["VMG Supplier Invoice", "VMG PPE and Uniform Handover"],
			},
		],
	}
