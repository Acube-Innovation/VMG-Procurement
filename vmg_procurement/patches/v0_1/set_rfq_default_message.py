# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Fill the RFQ default supplier message once; never overwrites a value
	the client has already set."""
	from vmg_procurement.vmg_procurement.doctype.vmg_request_for_quotation.vmg_request_for_quotation import (
		DEFAULT_RFQ_MESSAGE,
	)

	if not frappe.db.get_single_value("VMG Procurement Settings", "rfq_default_message"):
		frappe.db.set_single_value(
			"VMG Procurement Settings", "rfq_default_message", DEFAULT_RFQ_MESSAGE
		)
