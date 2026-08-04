// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

frappe.ui.form.on("VMG Purchase Receipt", {
	refresh(frm) {
		frm.set_query("expense_account", "items", () => ({
			filters: { root_type: "Expense", is_group: 0 },
		}));
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Items from Local Purchase Order"), () => {
				if (!frm.doc.local_purchase_order) {
					frappe.msgprint(__("Select a Local Purchase Order first"));
					return;
				}
				frm.call({ doc: frm.doc, method: "get_items_from_lpo" }).then(() => {
					frm.dirty();
					frm.refresh_fields();
				});
			});
		}

		if (frm.doc.docstatus === 1 && frm.doc.workflow_state === "Approved") {
			frm.add_custom_button(
				__("Supplier Invoice"),
				() =>
					frappe.model.open_mapped_doc({
						method: "vmg_procurement.vmg_procurement.doctype.vmg_purchase_receipt.vmg_purchase_receipt.make_vmg_supplier_invoice",
						frm: frm,
					}),
				__("Create")
			);
		}

		if (!frm.doc.local_purchase_order && !frm.is_new()) {
			frm.add_custom_button(
				__("Local Purchase Order"),
				() =>
					frappe.model.open_mapped_doc({
						method: "vmg_procurement.vmg_procurement.doctype.vmg_purchase_receipt.vmg_purchase_receipt.make_lpo_from_receipt",
						frm: frm,
					}),
				__("Create")
			);
		}
	},
});

frappe.ui.form.on("VMG Purchase Receipt Item", {
	received_qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "accepted_qty", row.received_qty);
	},
});
