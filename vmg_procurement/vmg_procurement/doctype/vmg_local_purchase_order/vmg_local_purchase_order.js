// Copyright (c) 2026, VMG and contributors
// For license information, please see license.txt

// Mirrors ADDRESS_SLOTS in vmg_local_purchase_order.py.
const ADDRESS_SLOTS = [
	{
		link_field: "delivery_address",
		display_field: "delivery_address_display",
		preferred_key: "is_shipping_address",
	},
	{
		link_field: "invoicing_address",
		display_field: "invoicing_address_display",
		preferred_key: "is_primary_address",
	},
];

frappe.ui.form.on("VMG Local Purchase Order", {
	onload(frm) {
		// mapped drafts (from comparison / requisition / repeat order) arrive
		// without expense accounts: apply the settings default right away
		if (frm.is_new()) {
			apply_default_expense_account(frm, frm.doc.items || []);
		}
	},

	items_add(frm, cdt, cdn) {
		apply_default_expense_account(frm, [locals[cdt][cdn]]);
	},

	supplier(frm) {
		// delivery wants the supplier's shipping address, invoicing its primary
		// one; an address already on the order (a repeat order, say) wins
		ADDRESS_SLOTS.forEach((slot) => fill_default_address(frm, slot));
	},

	delivery_address(frm) {
		set_address_display(frm, "delivery_address", "delivery_address_display");
	},

	invoicing_address(frm) {
		set_address_display(frm, "invoicing_address", "invoicing_address_display");
	},

	refresh(frm) {
		frm.set_query("expense_account", "items", () => ({
			filters: { root_type: "Expense", is_group: 0 },
		}));
		// only ever offer addresses that belong to the supplier
		["delivery_address", "invoicing_address"].forEach((field) => {
			frm.set_query(field, () => ({
				query: "frappe.contacts.doctype.address.address.address_query",
				filters: { link_doctype: "Supplier", link_name: frm.doc.supplier || "" },
			}));
		});
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__("Get Items from Previous Order"), () => {
				if (!frm.doc.supplier) {
					frappe.msgprint(__("Pick a Supplier first"));
					return;
				}
				frappe.prompt(
					{
						fieldname: "previous_order",
						fieldtype: "Link",
						label: __("Previous Order"),
						options: "VMG Local Purchase Order",
						reqd: 1,
						get_query: () => ({
							filters: {
								supplier: frm.doc.supplier,
								docstatus: 1,
								name: ["!=", frm.doc.name],
							},
						}),
					},
					(values) => {
						frm.call({
							doc: frm.doc,
							method: "get_items_from_previous_order",
							args: { previous_order: values.previous_order },
						}).then(() => {
							frm.dirty();
							frm.refresh_fields();
						});
					},
					__("Repeat a Previous Order")
				);
			});
		}

		if (!frm.is_new()) {
			// the client's "copy to clipboard": an unsaved copy with a new number
			frm.add_custom_button(__("Duplicate"), () => {
				const copy = frappe.model.copy_doc(frm.doc);
				frappe.set_route("Form", copy.doctype, copy.name);
			});
		}

		if (frm.doc.docstatus === 1 && frm.doc.workflow_state === "Approved") {
			if (["To Receive", "Partially Received"].includes(frm.doc.status)) {
				frm.add_custom_button(
					__("Purchase Receipt"),
					() =>
						frappe.model.open_mapped_doc({
							method: "vmg_procurement.vmg_procurement.doctype.vmg_local_purchase_order.vmg_local_purchase_order.make_purchase_receipt",
							frm: frm,
						}),
					__("Create")
				);
			}
			if (flt(frm.doc.per_billed) < 100 && frm.doc.status !== "Completed") {
				frm.add_custom_button(
					__("Supplier Invoice"),
					() =>
						frappe.model.open_mapped_doc({
							method: "vmg_procurement.vmg_procurement.doctype.vmg_local_purchase_order.vmg_local_purchase_order.make_supplier_invoice",
							frm: frm,
						}),
					__("Create")
				);
			}

			frm.add_custom_button(__("Send to Supplier"), () => {
				const send = () =>
					frappe.xcall(
						"vmg_procurement.vmg_procurement.doctype.vmg_local_purchase_order.vmg_local_purchase_order.send_to_supplier",
						{ lpo_name: frm.doc.name }
					).then((r) => {
						frappe.msgprint(
							r.queued
								? __("Emailed to {0}", [r.recipient])
								: __(
										"Email account not configured: the issue was logged"
											+ " on the timeline - download the PDF and send it"
											+ " to {0} manually",
										[r.recipient]
								  ),
							__("Send to Supplier")
						);
						frm.reload_doc();
					});
				if (frm.doc.sent_to_supplier_on) {
					frappe.confirm(
						__("This order was already sent on {0}. Send again?", [
							frappe.datetime.str_to_user(frm.doc.sent_to_supplier_on),
						]),
						send
					);
				} else {
					send();
				}
			});
		}
	},

	required_delivery_date(frm) {
		set_week_number(frm);
	},

	purchase_requisition(frm) {
		if (frm.doc.purchase_requisition && !frm.doc.required_delivery_date) {
			frappe.db
				.get_value("VMG Purchase Requisition", frm.doc.purchase_requisition, "required_by_date")
				.then((r) => {
					if (r.message && r.message.required_by_date && !frm.doc.required_delivery_date) {
						frm.set_value("required_delivery_date", r.message.required_by_date);
					}
				});
		}
	},

	service_visit_date(frm) {
		if (!frm.doc.required_delivery_date) {
			set_week_number(frm);
		}
	},
});

function set_week_number(frm) {
	const anchor = frm.doc.required_delivery_date || frm.doc.service_visit_date;
	if (anchor) {
		frm.set_value("delivery_week_number", "WK" + String(moment(anchor).isoWeek()).padStart(2, "0"));
	}
}

// Default Expense Account from VMG Procurement Settings, applied to draft
// rows that have none (the server applies the same default again on save)
// Pull the supplier's default address into one slot, leaving it empty when the
// supplier has none on file: the address lines on the form then take over.
function fill_default_address(frm, slot) {
	if (!frm.doc.supplier || frm.doc[slot.link_field]) return;
	frappe.call({
		method:
			"vmg_procurement.vmg_procurement.doctype.vmg_local_purchase_order" +
			".vmg_local_purchase_order.get_supplier_default_address",
		args: { supplier: frm.doc.supplier, preferred_key: slot.preferred_key },
		callback(r) {
			if (r.message) frm.set_value(slot.link_field, r.message);
		},
	});
}

// Render the chosen address into its read-only text area straight away, rather
// than waiting for the server to fill it in on save.
function set_address_display(frm, link_field, display_field) {
	const address = frm.doc[link_field];
	if (!address) {
		frm.set_value(display_field, "");
		return;
	}
	frappe.call({
		method: "frappe.contacts.doctype.address.address.get_address_display",
		args: { address_dict: address },
		callback(r) {
			frm.set_value(display_field, r.message || "");
		},
	});
}

function apply_default_expense_account(frm, rows) {
	if (frm.doc.docstatus !== 0 || !rows.length) {
		return;
	}
	frappe.db
		.get_single_value("VMG Procurement Settings", "default_expense_account")
		.then((account) => {
			if (!account) {
				return;
			}
			rows.forEach((row) => {
				if (!row.expense_account) {
					frappe.model.set_value(row.doctype, row.name, "expense_account", account);
				}
			});
		});
}
