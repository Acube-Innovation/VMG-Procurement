# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

from frappe import _

# All connections are internal links (no + button): both references live on
# this document itself.


def get_data():
	return {
		"internal_links": {
			"VMG Purchase Requisition": "purchase_requisition",
			"VMG Purchase Receipt": "purchase_receipt",
		},
		"transactions": [
			{
				"label": _("Reference"),
				"items": ["VMG Purchase Requisition", "VMG Purchase Receipt"],
			},
		],
	}
