from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta, SU, MO
import json
from random import random
import numpy as np
import pytz
import babel
import pandas as pd


class KsSalesForecastChanges(models.Model):
    _inherit = "ks.sales.forecast"

    ks_forecast_period = fields.Selection(
        selection_add=[('week', 'Week')], ondelete={'week': 'cascade'}
    )
    ks_is_qty = fields.Selection([('amount', 'Sales'), ('qty', 'Quantity')], string="Sales/Quantity")

    def ks_check_sufficient_data(self, result):
        if self.ks_forecast_period == 'week':
            ks_result = {}
            ks_product = []
            ks_product_id = []
            if len(result) == 0:
                raise UserError(_("Sales data is not available for these products."))

            for rec in result:
                if rec[2] not in ks_result:
                    ks_result[rec[2]] = [rec[0]]
                elif rec[0] not in ks_result[rec[2]]:
                    ks_result[rec[2]].append(rec[0])

            for key in ks_result:
                if len(ks_result[key]) < 9:
                    product_id = self.env['product.product'].browse(key)
                    ks_product.append(product_id.display_name)
                    ks_product_id.append(product_id.id)
            if ks_product:
                if self.ks_forecast_base == 'product':
                    raise UserError(
                        _('You do not have sufficient data for "%s" products. We need minimum 9 "%ss" data.') % (
                            ks_product, self.ks_forecast_period))
                else:
                    self.show_rejected_products(ks_product_id)
            ks_product_not_in_ks_result = [i.display_name for i in self.ks_product_ids if i.id not in ks_result.keys()]
            if ks_product_not_in_ks_result:
                raise UserError(_("Sales data is not available for '%s' products.") % ks_product_not_in_ks_result)
        else:
            super(KsSalesForecastChanges, self).ks_check_sufficient_data(result)

    def ks_predict_sales(self):
        if self.ks_forecast_period == 'week':
            vals = []
            end_date = self.ks_end_date
            if self.ks_is_file:
                self.ks_forecast_from_file(vals)
            else:
                result = self.ks_get_data_from_database()
                temp = result
                data_dict = self.ks_create_data_dict(vals, result)
                temp2 = data_dict
                product_keys = data_dict.keys()
                temp3 = product_keys
                for product in product_keys:
                    product_id = self.env['product.product'].browse(product)
                    product_sales_data = data_dict[product]
                    sales_list = product_sales_data.get('sales')
                    cost_list = product_sales_data.get('cost')
                    forecast_method = self.env['ir.config_parameter'].sudo().get_param('ks_forecast_method')
                    if self.ks_is_method_change:
                        forecast_method = self.ks_forecast_method
                    data_frame = np.array(sales_list)
                    cost_factor = np.array([x + random() for x in cost_list])
                    if forecast_method and len(data_frame) >= 9:
                        results = 0
                        try:
                            forecast_method_name = 'ks_%s_method' % forecast_method
                            if hasattr(self, forecast_method_name):
                                p = self.ks_p
                                q = self.ks_q
                                d = self.ks_d
                                sp = self.ks_P
                                sq = self.ks_Q
                                sd = self.ks_D
                                m = self.ks_m
                                trend = self.ks_trend
                                method = getattr(self, forecast_method_name)
                                results = method(data_frame, cost_factor, p, q, d, trend, sp, sq, sd, m)
                        except Exception as e:
                            return self.env['ks.message.wizard'].ks_pop_up_message(names='Error', message=e)
                        for (i, value) in zip(range(0, len(results)), results):
                            i = i + 1
                            ks_date = end_date + relativedelta(weeks=i)
                            forecast_data = {
                                'ks_forecast_id': self.id,
                                'ks_date': ks_date,
                                'ks_value': round(value, 3),
                                'ks_product_id': product_id.id,
                            }
                            data_dict[product_id.id]['date'].append(ks_date)
                            data_dict[product_id.id]['sales'].append(0.0)
                            data_dict[product_id.id]['forecast_sales'].append(value)
                            vals.append(forecast_data)
                    elif not forecast_method:
                        raise UserError(_('Please select a forecast method.'))
                ks_sale_order_sum = self.ks_get_sum_of_same_date_sale_order(result)
                keys = data_dict.keys()
                final_dict = {}
                dict_data = {}
                if keys:
                    dates = []
                    for product in keys:
                        dates.extend(data_dict[product]['date'])
                    dates = list(set(dates))
                    dates.sort()
                    labels = [self.format_label(values) for values in dates]
                    final_dict.update({
                        'labels': labels,
                        'datasets': []
                    })
                    product_keys = data_dict.keys()
                    for product in product_keys:
                        dict_data[product] = {
                            'sales': {},
                            'forecast_sales': {},
                        }
                        for final_date in dates:
                            if final_date in data_dict[product]['date']:
                                data_index = data_dict[product]['date'].index(final_date)
                                sales_value = [i for i in ks_sale_order_sum[product] if
                                               final_date in i] if ks_sale_order_sum else False
                                sales = sales_value[0][1] if sales_value else data_dict[product]['sales'][data_index]
                                dict_data[product]['sales'][final_date] = sales
                                dict_data[product]['forecast_sales'][final_date] = data_dict[product]['forecast_sales'][
                                    data_index]
                            else:
                                dict_data[product]['sales'][final_date] = 0.0
                                dict_data[product]['forecast_sales'][final_date] = 0.0
                if dict_data:
                    product_keys = data_dict.keys()
                    for product in product_keys:
                        product_id = self.env['product.product'].browse(product)
                        # product_name = product_id.code + ' ' + product_id.name if product_id.code else product_id.name
                        product_name = product_id.display_name
                        final_dict['datasets'] = final_dict['datasets'] + [{
                            'data': list(dict_data[product]['sales'].values()),
                            'label': product_name + '/Previous',
                        }, {
                            'data': [round(x, 3) for x in dict_data[product]['forecast_sales'].values()],
                            'label': product_name + '/Forecast'
                        }]
                    self.ks_chart_data = json.dumps(final_dict)
                forecast_result = self.env['ks.sales.forecast.result']
                forecast_records = forecast_result.search([('ks_forecast_id', '=', self.id)])
                if forecast_records.ids:
                    for forecast_record in forecast_records:
                        forecast_record.unlink()
                    forecast_result.create(vals)
                else:
                    forecast_result.create(vals)
                self.ks_is_predicted = True
                self.ks_predicted_forecast_method = self.ks_default_forecast_method

        else:
            return super(KsSalesForecastChanges, self).ks_predict_sales()

    @api.model
    def format_label(self, value, ftype='datetime', display_format='MMMM yyyy'):
        if self.ks_forecast_period == 'week':

            display_format = 'YYYY'
            week_no = value.isocalendar()[1]

            tz_convert = self._context.get('tz')
            locale = self._context.get('lang') or 'en_US'
            tzinfo = None
            if ftype == 'datetime':
                if tz_convert:
                    value = pytz.timezone(self._context['tz']).localize(value)
                    tzinfo = value.tzinfo
                year = babel.dates.format_datetime(value, format=display_format, tzinfo=tzinfo, locale=locale)
            else:
                if tz_convert:
                    value = pytz.timezone(self._context['tz']).localize(value)
                    tzinfo = value.tzinfo
                year = babel.dates.format_date(value, format=display_format, locale=locale)
            return "W" + str(week_no) + ' ' + year
        else:
            return super(KsSalesForecastChanges, self).format_label(value, ftype=ftype, display_format=display_format)

    def ks_get_data_from_database(self):
        if self.ks_is_qty == 'qty':
            user_tz = pytz.timezone(self.env.user.tz)
            start_date = pytz.utc.localize(self.ks_start_date).astimezone(user_tz)
            end_date = pytz.utc.localize(self.ks_end_date).astimezone(user_tz)
            query_data = {}

            if self.ks_forecast_base == 'product':
                query_data['product_condition'] = tuple(self.ks_product_ids.ids)
            else:
                query_data['product_condition'] = tuple(self.env['product.product'].search([]).ids)

            query = """
                        select
                            date_trunc(%(unit)s, so.date_order) as date,
                            sum(sol.product_uom_qty),
                            sol.product_id,sol.price_unit,so.partner_id
                        from sale_order_line as sol
                            inner join sale_order as so
                                on sol.order_id = so.id
                        where
                            date_order >= %(start_date)s and date_order <= %(end_date)s  and sol.product_id in %(product_condition)s     
                            group by date, sol.product_id, sol.price_unit, so.partner_id
                            order by date
                    """
            if self.ks_forecast_period == 'month':
                if end_date.day > 15:
                    end_date = end_date + relativedelta(day=31)
                else:
                    end_date = end_date + relativedelta(day=1)

            query_data.update({
                'unit': self.ks_forecast_period,
                'start_date': start_date,
                'end_date': end_date
            })
            self.env.cr.execute(query, query_data)
            result = self.env.cr.fetchall()  # now also contains unit price, handle it for [VAR]
            self.ks_check_sufficient_data(result)
            return result
        else:
            return super(KsSalesForecastChanges, self).ks_get_data_from_database()

    def _ks_generate_xlsx_report(self, workbook):
        if self.ks_is_qty == 'qty':
            merge_format = workbook.add_format({
                'border': 1,
                'align': 'center',
                'font_size': 26,
                'bold': True})
            raw_data = self._ks_get_data_to_reportify()
            format_sub_head = workbook.add_format({'font_size': 12, 'bold': True, 'align': 'center'})
            format_sub_head.set_border()
            format_sub_head.set_text_wrap()
            format_product_names = workbook.add_format()
            format_product_names.set_border()
            format_product_names.set_text_wrap()
            format_product_names.set_align('center')
            format_h_date = workbook.add_format()
            format_h_date.set_border()
            format_h_date.set_text_wrap()
            format_h_date.set_align('center')
            format_h_date.set_font_color('#800000')
            format_h_value = workbook.add_format()
            format_h_value.set_text_wrap()
            format_h_value.set_border()
            format_h_value.set_align('center')
            format_h_value.set_font_color('#800000')
            format_f_date = workbook.add_format()
            format_f_date.set_text_wrap()
            format_f_date.set_border()
            format_f_date.set_align('center')
            format_f_date.set_font_color('#008000')
            format_f_value = workbook.add_format()
            format_f_value.set_text_wrap()
            format_f_value.set_border()
            format_f_value.set_align('center')
            format_f_value.set_font_color('#008000')

            format_merge = workbook.add_format({'border': 1,
                                                'align': 'center',
                                                'font_size': 15,
                                                'bold': True})
            model_format = workbook.add_format({
                'border': 1,
                'align': 'center',
                'font_size': 15
            })

            ks_forecast_model = ''
            if self.ks_predicted_forecast_method or self.ks_default_forecast_method:
                ks_forecast_model = self.ks_predicted_forecast_method.upper() if self.ks_predicted_forecast_method else self.ks_default_forecast_method.upper()
            sheet = workbook.add_worksheet("Sales Forecast")
            sheet.merge_range(0, 0, 0, 4, "Sales Forecast Report", merge_format)
            sheet.merge_range(1, 0, 1, 4, "Forecasting model used :- " + str(ks_forecast_model), model_format)
            sheet.merge_range(2, 1, 2, 2, "Historical", format_merge)
            sheet.merge_range(2, 3, 2, 4, "Forecasted", format_merge)
            if not self.ks_is_predicted:
                sheet.merge_range(3, 0, 3, 4, "Data not Found, Probably you have not predicted the sales", model_format)
            if self.ks_is_predicted:
                sub_heads = ["Product Name", "Date", "Quantity",
                             "Date", "Quantity"]
                for i in range(len(sub_heads)):
                    if i == 0:
                        sheet.merge_range(2, 0, 3, 0, sub_heads[0], format_sub_head)
                        sheet.set_column(0, 0, 20)
                        continue
                    sheet.write(3, i, sub_heads[i], format_sub_head)
                    sheet.set_column(i, i, 15)

                product_index = h_date_index = h_value_index = f_date_index = f_value_index = 4
                for key, values in raw_data.items():
                    parent_key = key
                    sheet.write(product_index, 0, key, format_product_names)
                    for key, value in values.items():
                        if key == "Past Date":
                            for item in value:
                                sheet.write(h_date_index, 1, str(item), format_h_date)
                                h_date_index += 1
                        elif key == "Past Sales":
                            for item in value:
                                sheet.write(h_value_index, 2, str(round(item, 2)), format_h_value)
                                h_value_index += 1
                        elif key == "Future Date":
                            for item in value:
                                sheet.write(f_date_index, 3, str(item), format_f_date)
                                f_date_index += 1
                        elif key == 'Future Sales':
                            for item in value:
                                sheet.write(f_value_index, 4, str(round(item, 2)), format_f_value)
                                f_value_index += 1
                    if abs(h_date_index - f_date_index) != 0:
                        merge_format = workbook.add_format({
                            'border': 1,
                            'align': 'vcenter'})
                        merge_format.set_text_wrap()
                        max_index = max(h_date_index, f_date_index)
                        min_index = min(h_date_index, f_date_index)
                        sheet.merge_range(first_row=product_index, first_col=0, last_row=max_index - 1,
                                          last_col=0,
                                          data=parent_key, cell_format=merge_format)
                        if max_index == h_date_index:
                            to_write_index = [3, 4]
                            for l in to_write_index:
                                for k in range(min_index, max_index):
                                    sheet.write(k, l, '', merge_format)
                        elif max_index == f_date_index:
                            to_write_index = [1, 2]
                            for j in to_write_index:
                                for i in range(min_index, max_index):
                                    sheet.write(i, j, '', merge_format)
                    product_index = max(h_date_index, f_date_index) + 1
                    h_date_index = h_value_index = f_value_index = f_date_index = product_index

        else:
            super(KsSalesForecastChanges, self)._ks_generate_xlsx_report(workbook)