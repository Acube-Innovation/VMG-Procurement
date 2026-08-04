// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

frappe.ui.form.on("VMG PPE and Uniform Handover", {
	refresh(frm) {
		frm.set_query("purchase_requisition", () => ({
			filters: {
				requisition_type: "Staff Uniform and PPE",
				docstatus: 1,
			},
		}));

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Items from Requisition"), () => {
				if (!frm.doc.purchase_requisition) {
					frappe.msgprint(__("Select a Staff Uniform and PPE Purchase Requisition first"));
					return;
				}
				frm.call({ doc: frm.doc, method: "get_items_from_uniform_request" }).then(() => {
					frm.dirty();
					frm.refresh_fields();
				});
			});
		}
	},
});
