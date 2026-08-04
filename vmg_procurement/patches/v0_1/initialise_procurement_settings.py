# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe

DEFAULTS = {
	"quote_threshold_amount": 1000,
	"min_suppliers_above_threshold": 3,
	"min_suppliers_for_new_item": 3,
	"threshold_enforcement": "Warn",
	"max_suppliers_in_comparison": 5,
	"terms_mandatory_on_lpo": 1,
	"budget_action_on_requisition": "Warn",
	"budget_action_on_lpo": "Warn",
	"budget_action_on_payment": "Warn",
	"notify_by_email": 1,
}


def execute():
	"""Persist the shipped defaults once, so get_settings() returns real values
	even before anyone opens and saves the settings form. Only empty fields are
	filled; values the client has already set are never overwritten."""
	doc = frappe.get_single("VMG Procurement Settings")

	for field, value in DEFAULTS.items():
		if doc.get(field) in (None, ""):
			doc.set(field, value)

	if not doc.default_currency and frappe.db.exists("Currency", "AED"):
		doc.default_currency = "AED"

	doc.flags.ignore_permissions = True
	doc.save()
