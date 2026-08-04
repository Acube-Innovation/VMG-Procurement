frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["VMG Budget Utilisation by Project"] = {
	method: "vmg_procurement.vmg_procurement.dashboard_chart_source.vmg_budget_utilisation_by_project.vmg_budget_utilisation_by_project.get_data",
	filters: [],
};
