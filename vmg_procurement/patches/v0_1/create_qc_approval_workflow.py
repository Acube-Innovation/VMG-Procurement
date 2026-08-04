# Copyright (c) 2026, VMG and contributors
# For license information, please see license.txt

import frappe

WORKFLOW_NAME = "VMG Quotation Comparison Approval"


def execute():
	"""Create the comparison approval workflow. The six Workflow States and
	the three Workflow Action Masters already exist from step 03."""
	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		return

	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": WORKFLOW_NAME,
			"document_type": "VMG Quotation Comparison",
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 1,
			"states": [
				{"state": "Draft", "doc_status": "0", "allow_edit": "VMG Procurement User"},
				{
					"state": "Pending Division Approval",
					"doc_status": "1",
					"allow_edit": "VMG Division Manager",
				},
				{"state": "Pending CFO Approval", "doc_status": "1", "allow_edit": "VMG CFO"},
				{
					"state": "Pending GM Approval",
					"doc_status": "1",
					"allow_edit": "VMG General Manager",
				},
				{"state": "Approved", "doc_status": "1", "allow_edit": "VMG Procurement User"},
				{"state": "Rejected", "doc_status": "1", "allow_edit": "VMG Procurement User"},
			],
			"transitions": [
				{
					"state": "Draft",
					"action": "Submit",
					"next_state": "Pending Division Approval",
					"allowed": "VMG Procurement User",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending Division Approval",
					"action": "Approve",
					"next_state": "Pending CFO Approval",
					"allowed": "VMG Division Manager",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending Division Approval",
					"action": "Reject",
					"next_state": "Rejected",
					"allowed": "VMG Division Manager",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending CFO Approval",
					"action": "Approve",
					"next_state": "Pending GM Approval",
					"allowed": "VMG CFO",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending CFO Approval",
					"action": "Reject",
					"next_state": "Rejected",
					"allowed": "VMG CFO",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending GM Approval",
					"action": "Approve",
					"next_state": "Approved",
					"allowed": "VMG General Manager",
					"allow_self_approval": 1,
				},
				{
					"state": "Pending GM Approval",
					"action": "Reject",
					"next_state": "Rejected",
					"allowed": "VMG General Manager",
					"allow_self_approval": 1,
				},
			],
		}
	).insert(ignore_permissions=True)
