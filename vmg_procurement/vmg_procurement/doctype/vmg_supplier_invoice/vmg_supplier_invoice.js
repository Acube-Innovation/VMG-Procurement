// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

frappe.ui.form.on("VMG Supplier Invoice", {
	refresh(frm) {
		frm.set_query("credit_to", () => ({
			filters: {
				account_type: "Payable",
				is_group: 0,
				company: frm.doc.company,
			},
		}));
		frm.set_query("input_vat_account", () => ({
			filters: { is_group: 0, company: frm.doc.company },
		}));
		frm.set_query("expense_account", "items", () => ({
			filters: { root_type: "Expense", is_group: 0, company: frm.doc.company },
		}));

		if (frm.doc.journal_entry) {
			frm.add_custom_button(__("Journal Entry"), () =>
				frappe.set_route("Form", "Journal Entry", frm.doc.journal_entry)
			, __("View"));
		}

		if (
			frm.doc.docstatus === 1 &&
			frm.doc.posting_status === "Posted" &&
			["Unpaid", "Partly Paid", "Overdue"].includes(frm.doc.status)
		) {
			frm.add_custom_button(
				__("Payment"),
				() =>
					frappe.xcall(
						"vmg_procurement.vmg_procurement.doctype.vmg_supplier_invoice.vmg_supplier_invoice.make_payment_entry",
						{ invoice_name: frm.doc.name }
					).then((doc) => {
						frappe.model.sync(doc);
						frappe.set_route("Form", doc.doctype, doc.name);
					}),
				__("Create")
			);
		}
	},
});
