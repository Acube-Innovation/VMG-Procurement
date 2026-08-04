// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

frappe.ui.form.on("VMG Request for Quotation", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.status === "Cancelled") return;

		frm.add_custom_button(__("Send Enquiry"), () => {
			frappe.confirm(
				__("Email the enquiry to all suppliers that have an email address?"),
				() => {
					frappe.xcall(
						"vmg_procurement.vmg_procurement.doctype.vmg_request_for_quotation.vmg_request_for_quotation.send_enquiry",
						{ rfq_name: frm.doc.name }
					).then((r) => {
						let parts = [];
						if (r.emailed.length) {
							parts.push(__("Emailed: {0}", [r.emailed.join(", ")]));
						}
						if (r.manual.length) {
							parts.push(
								__(
									"No email / sending failed - print the enquiry and send manually: {0}",
									[r.manual.join(", ")]
								)
							);
						}
						frappe.msgprint(parts.join("<br>") || __("Nothing to send"), __("Enquiry Sent"));
						frm.reload_doc();
					});
				}
			);
		});

		// Create Comparison appears once two or more quotations are submitted
		frappe.db
			.count("VMG Supplier Quotation", {
				filters: { request_for_quotation: frm.doc.name, docstatus: 1 },
			})
			.then((count) => {
				if (count >= 2) {
					frm.add_custom_button(__("Create Comparison"), () => {
						frappe.model.open_mapped_doc({
							method: "vmg_procurement.vmg_procurement.doctype.vmg_request_for_quotation.vmg_request_for_quotation.make_vmg_quotation_comparison",
							frm: frm,
						});
					}, __("Create"));
				}
			});

		frm.add_custom_button(__("Enter Supplier Quotation"), () => {
			const suppliers = (frm.doc.suppliers || []).map((row) => row.supplier);
			frappe.prompt(
				{
					fieldname: "supplier",
					fieldtype: "Select",
					label: __("Supplier"),
					options: suppliers.join("\n"),
					reqd: 1,
				},
				(values) => {
					frappe.xcall(
						"vmg_procurement.vmg_procurement.doctype.vmg_request_for_quotation.vmg_request_for_quotation.make_vmg_supplier_quotation",
						{ source_name: frm.doc.name, supplier: values.supplier }
					).then((doc) => {
						frappe.model.sync(doc);
						frappe.set_route("Form", doc.doctype, doc.name);
					});
				},
				__("Select Supplier")
			);
		}, __("Create"));
	},
});
