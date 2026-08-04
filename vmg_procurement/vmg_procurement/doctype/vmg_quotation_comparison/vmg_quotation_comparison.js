// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

function set_awarded_supplier(frm, row) {
	const supplier_row = (frm.doc.suppliers || []).find(
		(s) => cint(s.column_no) === cint(row.awarded_column)
	);
	row.awarded_supplier = supplier_row
		? supplier_row.supplier_name || supplier_row.supplier
		: null;
}

function open_split_lpo_dialog(frm) {
	const awarded_columns = new Set(
		(frm.doc.items || [])
			.filter((row) => cint(row.awarded_column))
			.map((row) => cint(row.awarded_column))
	);
	const awarded_rows = (frm.doc.suppliers || []).filter((s) =>
		awarded_columns.has(cint(s.column_no))
	);
	if (!awarded_rows.length) {
		frappe.msgprint(__("No lines are awarded to any supplier column"));
		return;
	}

	// mark suppliers whose LPO already exists so the user picks the pending ones
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "VMG Local Purchase Order",
			filters: {
				quotation_comparison: frm.doc.name,
				docstatus: ["<", 2],
			},
			fields: ["name", "supplier_quotation", "docstatus"],
			limit_page_length: 0,
		},
		callback(r) {
			const existing = {};
			(r.message || []).forEach((lpo) => {
				existing[lpo.supplier_quotation] = lpo;
			});
			const options = awarded_rows.map((s) => {
				const count = (frm.doc.items || []).filter(
					(row) => cint(row.awarded_column) === cint(s.column_no)
				).length;
				const lpo = existing[s.supplier_quotation];
				const label = `${s.supplier_name || s.supplier} — ${count} ${__("line(s)")}${
					lpo ? ` (${__("already on")} ${lpo.name})` : ""
				}`;
				return { label: label, value: s.supplier_quotation };
			});

			const d = new frappe.ui.Dialog({
				title: __("Create LPO for Awarded Supplier"),
				fields: [
					{
						label: __("Awarded Supplier"),
						fieldname: "supplier_quotation",
						fieldtype: "Select",
						options: options,
						reqd: 1,
					},
				],
				primary_action_label: __("Create"),
				primary_action(values) {
					d.hide();
					frappe
						.call({
							method:
								"vmg_procurement.vmg_procurement.doctype.vmg_quotation_comparison.vmg_quotation_comparison.make_lpo_from_comparison",
							args: {
								source_name: frm.doc.name,
								supplier_quotation: values.supplier_quotation,
							},
						})
						.then((res) => {
							if (res.message) {
								const doclist = frappe.model.sync(res.message);
								frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
							}
						});
				},
			});
			d.show();
		},
	});
}

frappe.ui.form.on("VMG Quotation Comparison", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Quotations"), () => {
				frm.call({ doc: frm.doc, method: "get_quotations" }).then(() => {
					frm.dirty();
					frm.refresh_fields();
				});
			});

			if (frm.doc.award_mode === "Split by Item" && (frm.doc.items || []).length) {
				frm.add_custom_button(__("Award Lowest to Each Line"), () => {
					(frm.doc.items || []).forEach((row) => {
						if (row.lowest_column) {
							row.awarded_column = row.lowest_column;
							set_awarded_supplier(frm, row);
						}
					});
					frm.dirty();
					frm.refresh_field("items");
				});
			}
		}

		if (
			frm.doc.docstatus === 1 &&
			frm.doc.workflow_state === "Approved" &&
			frappe.user.has_role(["VMG Procurement User", "VMG Procurement Manager"])
		) {
			frm.add_custom_button(
				__("Local Purchase Order"),
				() => {
					if (frm.doc.award_mode === "Split by Item") {
						open_split_lpo_dialog(frm);
					} else {
						frappe.model.open_mapped_doc({
							method: "vmg_procurement.vmg_procurement.doctype.vmg_quotation_comparison.vmg_quotation_comparison.make_local_purchase_order",
							frm: frm,
						});
					}
				},
				__("Create")
			);
		}

		// restrict selected_quotation to the compared quotations
		frm.set_query("selected_quotation", () => ({
			filters: {
				name: [
					"in",
					(frm.doc.suppliers || []).map((row) => row.supplier_quotation),
				],
			},
		}));
	},

	award_mode(frm) {
		if (frm.doc.award_mode === "Split by Item") {
			frm.set_value("selected_supplier", null);
			frm.set_value("selected_quotation", null);
		} else {
			(frm.doc.items || []).forEach((row) => {
				row.awarded_column = null;
				row.awarded_supplier = null;
			});
			frm.refresh_field("items");
		}
	},

	selected_quotation(frm) {
		const row = (frm.doc.suppliers || []).find(
			(r) => r.supplier_quotation === frm.doc.selected_quotation
		);
		if (row) {
			frm.set_value("selected_supplier", row.supplier);
		}
	},
});

frappe.ui.form.on("VMG Comparison Item", {
	awarded_column(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!cint(row.awarded_column)) {
			row.awarded_column = null;
			row.awarded_supplier = null;
			frm.refresh_field("items");
			return;
		}
		const supplier_row = (frm.doc.suppliers || []).find(
			(s) => cint(s.column_no) === cint(row.awarded_column)
		);
		if (!supplier_row) {
			frappe.msgprint(
				__("Column {0} does not match any supplier column", [row.awarded_column])
			);
			row.awarded_column = null;
			row.awarded_supplier = null;
		} else if (row[`rate_${cint(row.awarded_column)}`] == null) {
			frappe.msgprint(
				__("{0} did not quote this line", [
					supplier_row.supplier_name || supplier_row.supplier,
				])
			);
			row.awarded_column = null;
			row.awarded_supplier = null;
		} else {
			row.awarded_supplier =
				supplier_row.supplier_name || supplier_row.supplier;
		}
		frm.refresh_field("items");
	},
});
