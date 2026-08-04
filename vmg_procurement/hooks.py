app_name = "vmg_procurement"
app_title = "VMG Procurement"
app_publisher = "VMG"
app_description = "Custom procurement system for VMG: non-stock purchase cycle as custom DocTypes plus core fixed asset chain"
app_email = "saaspurchases@acube.co"
app_license = "mit"

# Fixtures
# --------
# Mandatory rule 7: every Custom Field, Property Setter, Workflow, Role and
# Print Format created for this build is exported with
# `bench --site <site> export-fixtures` and version controlled inside this app.
# Filters scope the export to VMG Procurement records only, so records owned by
# other apps on this bench are never touched.
# Note: fixture sync never overwrites a record the client has modified after
# the export (frappe skips docs whose DB timestamp is newer than the file's),
# so seeded masters like VMG Division stay client-editable.
# Workflow State / Workflow Action Master filters will be added in step 03 when
# the first workflow is created.
fixtures = [
	{"dt": "Role", "filters": [["name", "like", "VMG %"]]},
	{
		"dt": "Custom Field",
		"filters": [
			[
				"dt",
				"in",
				[
					"Supplier",
					"Material Request",
					"Material Request Item",
					"Supplier Quotation",
					"Supplier Quotation Item",
					"Purchase Order",
					"Purchase Order Item",
					"Purchase Receipt",
					"Purchase Receipt Item",
					"Purchase Invoice",
					"Purchase Invoice Item",
					"Asset",
					"Payment Entry Reference",
					"Payment Entry",
				],
			],
			["fieldname", "like", "vmg_%"],
		],
	},
	{"dt": "Property Setter", "filters": [["module", "=", "VMG Procurement"]]},
	{"dt": "VMG Division"},
	{"dt": "Terms and Conditions"},
	{"dt": "Client Script", "filters": [["module", "=", "VMG Procurement"]]},
	{"dt": "Server Script", "filters": [["module", "=", "VMG Procurement"]]},
	{"dt": "Print Format", "filters": [["module", "=", "VMG Procurement"]]},
	{"dt": "Workflow", "filters": [["document_type", "like", "VMG %"]]},
	{
		"dt": "Workflow State",
		"filters": [
			[
				"name",
				"in",
				[
					"Draft",
					"Pending Division Approval",
					"Pending CFO Approval",
					"Pending GM Approval",
					"Pending Procurement Approval",
					"Pending Procurement Verification",
					"Pending Accounts Approval",
					"Approved",
					"Rejected",
				],
			]
		],
	},
	{
		"dt": "Workflow Action Master",
		"filters": [["name", "in", ["Submit", "Approve", "Reject"]]],
	},
	{"dt": "Number Card", "filters": [["name", "like", "VMG %"]]},
	{"dt": "Dashboard Chart", "filters": [["name", "like", "VMG %"]]},
]

# Apps
# ------------------

required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "vmg_procurement",
# 		"logo": "/assets/vmg_procurement/logo.png",
# 		"title": "VMG Procurement",
# 		"route": "/vmg_procurement",
# 		"has_permission": "vmg_procurement.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/vmg_procurement/css/vmg_procurement.css"
# app_include_js = "/assets/vmg_procurement/js/vmg_procurement.js"

# include js, css files in header of web template
# web_include_css = "/assets/vmg_procurement/css/vmg_procurement.css"
# web_include_js = "/assets/vmg_procurement/js/vmg_procurement.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "vmg_procurement/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "vmg_procurement/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "vmg_procurement.utils.jinja_methods",
# 	"filters": "vmg_procurement.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "vmg_procurement.install.before_install"
# after_install = "vmg_procurement.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "vmg_procurement.uninstall.before_uninstall"
# after_uninstall = "vmg_procurement.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "vmg_procurement.utils.before_app_install"
# after_app_install = "vmg_procurement.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "vmg_procurement.utils.before_app_uninstall"
# after_app_uninstall = "vmg_procurement.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "vmg_procurement.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Routing guards and requisition status sync (step 04). The VMG RFQ / LPO
# entries are inert until those DocTypes are built in steps 05 / 09.

doc_events = {
	"Material Request": {
		"before_insert": "vmg_procurement.utils.asset_chain.set_asset_naming_series",
		"validate": "vmg_procurement.utils.asset_chain.set_asset_naming_series",
		"on_submit": "vmg_procurement.utils.routing.on_material_request_submit",
		"on_cancel": "vmg_procurement.utils.routing.on_material_request_cancel",
	},
	"Supplier Quotation": {
		"before_insert": "vmg_procurement.utils.asset_chain.apply_asset_chain_rules",
		"validate": "vmg_procurement.utils.asset_chain.apply_asset_chain_rules",
	},
	"Purchase Order": {
		"before_insert": "vmg_procurement.utils.asset_chain.apply_asset_chain_rules",
		"validate": "vmg_procurement.utils.asset_chain.validate_purchase_order",
		"on_submit": "vmg_procurement.utils.asset_chain.on_purchase_order_submit",
		"on_cancel": "vmg_procurement.utils.asset_chain.on_purchase_order_cancel",
	},
	"Purchase Receipt": {
		"before_insert": "vmg_procurement.utils.asset_chain.apply_asset_chain_rules",
		"validate": "vmg_procurement.utils.asset_chain.apply_asset_chain_rules",
		"on_submit": "vmg_procurement.utils.asset_chain.on_purchase_receipt_submit",
	},
	"Purchase Invoice": {
		"before_insert": "vmg_procurement.utils.asset_chain.apply_asset_chain_rules",
		"validate": "vmg_procurement.utils.asset_chain.apply_asset_chain_rules",
	},
	"Payment Entry": {
		"validate": "vmg_procurement.utils.budget.check_payment_budget",
		"on_submit": "vmg_procurement.vmg_procurement.doctype.vmg_supplier_invoice.vmg_supplier_invoice.on_payment_entry_change",
		"on_cancel": "vmg_procurement.vmg_procurement.doctype.vmg_supplier_invoice.vmg_supplier_invoice.on_payment_entry_change",
	},
	"VMG Request for Quotation": {
		"on_submit": "vmg_procurement.utils.routing.on_vmg_rfq_submit",
		"on_cancel": "vmg_procurement.utils.routing.on_vmg_rfq_cancel",
	},
	"VMG Local Purchase Order": {
		"on_submit": "vmg_procurement.utils.routing.on_vmg_lpo_submit",
		"on_cancel": "vmg_procurement.utils.routing.on_vmg_lpo_cancel",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"vmg_procurement.vmg_procurement.doctype.vmg_supplier_quotation.vmg_supplier_quotation.mark_expired_quotations",
		"vmg_procurement.vmg_procurement.doctype.vmg_supplier_invoice.vmg_supplier_invoice.update_payment_status_daily",
	],
}

# Testing
# -------

# before_tests = "vmg_procurement.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "vmg_procurement.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
	"Supplier": "vmg_procurement.utils.dashboards.supplier_dashboard",
}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["vmg_procurement.utils.before_request"]
# after_request = ["vmg_procurement.utils.after_request"]

# Job Events
# ----------
# before_job = ["vmg_procurement.utils.before_job"]
# after_job = ["vmg_procurement.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"vmg_procurement.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

