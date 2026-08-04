# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe

WORKFLOW_NAME = "VMG Supplier Invoice Approval"

STATES = ["Pending Procurement Verification", "Pending Accounts Approval"]


def execute():
	"""Invoice approval: procurement verifies the paperwork, accounts approves
	and the Journal Entry posts on approval."""
	for state in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state, "style": "Warning"}
			).insert(ignore_permissions=True)

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		return

	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": WORKFLOW_NAME,
			"document_type": "VMG Supplier Invoice",
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 1,
			"states": [
				{"state": "Draft", "doc_status": "0", "allow_edit": "VMG Procurement User"},
				{"state": "Draft", "doc_status": "0", "allow_edit": "VMG Accounts User"},
				{
					"state": "Pending Procurement Verification",
					"doc_status": "1",
					"allow_edit": "VMG Procurement User",
				},
				{
					"state": "Pending Accounts Approval",
					"doc_status": "1",
					"allow_edit": "VMG Accounts User",
				},
				{"state": "Approved", "doc_status": "1", "allow_edit": "VMG Accounts User"},
				{"state": "Rejected", "doc_status": "1", "allow_edit": "VMG Procurement User"},
			],
			"transitions": [
				{
					"state": "Draft",
					"action": "Submit",
					"next_state": "Pending Procurement Verification",
					"allowed": "VMG Procurement User",
					"allow_self_approval": 1,
				},
				{
					"state": "Draft",
					"action": "Submit",
					"next_state": "Pending Procurement Verification",
					"allowed": "VMG Accounts User",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending Procurement Verification",
					"action": "Approve",
					"next_state": "Pending Accounts Approval",
					"allowed": "VMG Procurement User",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending Procurement Verification",
					"action": "Reject",
					"next_state": "Rejected",
					"allowed": "VMG Procurement User",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending Accounts Approval",
					"action": "Approve",
					"next_state": "Approved",
					"allowed": "VMG Accounts User",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending Accounts Approval",
					"action": "Reject",
					"next_state": "Rejected",
					"allowed": "VMG Accounts User",
					"allow_self_approval": 1,
				},
			],
		}
	).insert(ignore_permissions=True)
