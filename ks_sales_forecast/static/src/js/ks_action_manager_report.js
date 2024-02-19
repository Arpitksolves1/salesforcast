odoo.define("ks_sales_forecast.report", function (require) {
    "use strict";

    var core = require('web.core');
    var ks_framework = require('web.framework');
    var ks_session = require('web.session');

     function ks_executexlsxReportDownloadAction(parent, action) {
        var data = action.params || {};
        ks_framework.blockUI();
        var def = $.Deferred();
        ks_session.get_file({
            url: '/ks_sale_forecast_xlsx_report',
            data: data,
            success: def.resolve.bind(def),
            error: (error) => console.log(error),
            complete: ks_framework.unblockUI,
        });
        return def;
    };
    core.action_registry.add("ks_executexlsxReportDownloadAction", ks_executexlsxReportDownloadAction);
 });