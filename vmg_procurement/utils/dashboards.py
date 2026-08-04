# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

from frappe import _


def supplier_dashboard(data):
	"""Everything for one supplier in one place: append the VMG procurement
	documents to the core Supplier dashboard."""
	data.setdefault("transactions", []).append(
		{
			"label": _("VMG Procurement"),
			"items": [
				"VMG Local Purchase Order",
				"VMG Purchase Receipt",
				"VMG Supplier Invoice",
			],
		}
	)
	return data
