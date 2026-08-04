# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import json

import frappe

CARDS = [
	{
		"name": "VMG Open Requisitions",
		"document_type": "VMG Purchase Requisition",
		"filters": [
			["VMG Purchase Requisition", "docstatus", "=", 1],
			["VMG Purchase Requisition", "status", "not in", ["Ordered", "Closed", "Cancelled", "Rejected"]],
		],
	},
	{
		"name": "VMG LPOs Pending Approval",
		"document_type": "VMG Local Purchase Order",
		"filters": [
			["VMG Local Purchase Order", "docstatus", "=", 1],
			["VMG Local Purchase Order", "workflow_state", "in", ["Pending CFO Approval", "Pending GM Approval"]],
		],
	},
	{
		"name": "VMG Orders Pending Receipt",
		"document_type": "VMG Local Purchase Order",
		"filters": [
			["VMG Local Purchase Order", "docstatus", "=", 1],
			["VMG Local Purchase Order", "status", "in", ["To Receive", "Partially Received"]],
		],
	},
	{
		"name": "VMG Invoices Outstanding",
		"document_type": "VMG Supplier Invoice",
		"filters": [
			["VMG Supplier Invoice", "docstatus", "=", 1],
			["VMG Supplier Invoice", "outstanding_amount", ">", 0],
		],
	},
]


def execute():
	for card in CARDS:
		if frappe.db.exists("Number Card", card["name"]):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Number Card",
				"label": card["name"].replace("VMG ", ""),
				"type": "Document Type",
				"document_type": card["document_type"],
				"function": "Count",
				"filters_json": json.dumps(card["filters"]),
				"is_public": 1,
				"show_percentage_stats": 0,
			}
		).insert(ignore_permissions=True)
		# Number Card autonames from the label: pin the VMG-prefixed name the
		# workspace references
		if doc.name != card["name"]:
			frappe.rename_doc("Number Card", doc.name, card["name"], force=True)
