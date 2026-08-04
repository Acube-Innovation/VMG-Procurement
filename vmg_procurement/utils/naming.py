# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import getdate, nowdate


def make_vmg_name(doctype_prefix, division_prefix, docname_pattern="#####", posting_date=None):
	"""Return the next name in the series PREFIX-DIVISION-YYYY-#####.

	Example: make_vmg_name("PR", "VLV") -> "PR-VLV-2026-00001"

	The running number is tracked per document prefix, division and year, so
	every division gets its own sequence that restarts each year. All VMG
	transaction DocTypes call this from their autoname method.

	:param doctype_prefix: short code of the document, e.g. "PR" for
	        VMG Purchase Requisition
	:param division_prefix: prefix of the VMG Division, e.g. "VLV"
	:param docname_pattern: series digits pattern, default "#####" (5 digits)
	:param posting_date: date that decides the year segment, defaults to today
	"""
	if not doctype_prefix or not division_prefix:
		frappe.throw(_("Both a document prefix and a division prefix are required for naming"))

	year = getdate(posting_date or nowdate()).year
	pattern = (docname_pattern or "#####").strip(".")
	return make_autoname(f"{doctype_prefix.upper()}-{division_prefix.upper()}-{year}-.{pattern}.")
