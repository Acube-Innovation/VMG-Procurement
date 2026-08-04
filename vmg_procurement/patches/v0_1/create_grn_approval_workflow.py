# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe

WORKFLOW_NAME = "VMG Purchase Receipt Approval"


def execute():
	"""Receipt approval: the site submits the signed delivery note and the
	Procurement Department (not finance) approves or rejects it."""
	if not frappe.db.exists("Workflow State", "Pending Procurement Approval"):
		frappe.get_doc(
			{
				"doctype": "Workflow State",
				"workflow_state_name": "Pending Procurement Approval",
				"style": "Warning",
			}
		).insert(ignore_permissions=True)

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		return

	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": WORKFLOW_NAME,
			"document_type": "VMG Purchase Receipt",
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 1,
			"states": [
				{"state": "Draft", "doc_status": "0", "allow_edit": "VMG Site User"},
				{"state": "Draft", "doc_status": "0", "allow_edit": "VMG Procurement User"},
				{
					"state": "Pending Procurement Approval",
					"doc_status": "1",
					"allow_edit": "VMG Procurement User",
				},
				{"state": "Approved", "doc_status": "1", "allow_edit": "VMG Procurement User"},
				{"state": "Rejected", "doc_status": "1", "allow_edit": "VMG Procurement User"},
			],
			"transitions": [
				{
					"state": "Draft",
					"action": "Submit",
					"next_state": "Pending Procurement Approval",
					"allowed": "VMG Site User",
					"allow_self_approval": 1,
				},
				{
					"state": "Draft",
					"action": "Submit",
					"next_state": "Pending Procurement Approval",
					"allowed": "VMG Procurement User",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending Procurement Approval",
					"action": "Approve",
					"next_state": "Approved",
					"allowed": "VMG Procurement User",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending Procurement Approval",
					"action": "Reject",
					"next_state": "Rejected",
					"allowed": "VMG Procurement User",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending Procurement Approval",
					"action": "Approve",
					"next_state": "Approved",
					"allowed": "VMG Procurement Manager",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending Procurement Approval",
					"action": "Reject",
					"next_state": "Rejected",
					"allowed": "VMG Procurement Manager",
					"allow_self_approval": 1,
				},
			],
		}
	).insert(ignore_permissions=True)
