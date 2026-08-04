# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

from frappe import _

# All connections are internal links (no + button): creation happens through
# the forms' Create buttons and the posting flow.


def get_data():
	return {
		"internal_links": {
			"VMG Purchase Requisition": "purchase_requisition",
			"VMG Local Purchase Order": "local_purchase_order",
			"VMG Purchase Receipt": "purchase_receipt",
			"Journal Entry": "journal_entry",
		},
		"transactions": [
			{
				"label": _("Reference"),
				"items": [
					"VMG Purchase Requisition",
					"VMG Local Purchase Order",
					"VMG Purchase Receipt",
				],
			},
			{
				"label": _("Accounting"),
				"items": ["Journal Entry"],
			},
		],
	}
