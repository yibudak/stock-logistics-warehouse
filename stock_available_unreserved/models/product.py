# Copyright 2018 Camptocamp SA
# Copyright 2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2016 ForgeFlow S.L. (https://www.forgeflow.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.addons.stock.models.product import OPERATORS
from odoo.tools.float_utils import float_round
from odoo.exceptions import UserError

UNIT = dp.get_precision('Product Unit of Measure')


class ProductTemplate(models.Model):
    _inherit = "product.template"

    qty_available_not_res = fields.Float(
        string='Quantity On Hand Unreserved',
        digits=UNIT,
        compute='_compute_product_available_not_res',
        search='_search_quantity_unreserved',
    )

    @api.multi
    @api.depends('product_variant_ids.qty_available_not_res')
    def _compute_product_available_not_res(self):
        for tmpl in self:
            if isinstance(tmpl.id, models.NewId):
                continue
            tmpl.qty_available_not_res = sum(
                tmpl.mapped('product_variant_ids.qty_available_not_res')
            )

    @api.multi
    def action_open_quants_unreserved(self):
        products_ids = self.mapped('product_variant_ids').ids
        quants = self.env['stock.quant'].search([
            ('product_id', 'in', products_ids),
        ])
        quant_ids = quants.filtered(
            lambda x: x.product_id.qty_available_not_res > 0
        ).ids
        result = self.env.ref('stock.product_open_quants').read()[0]
        result['domain'] = [('id', 'in', quant_ids)]
        result['context'] = {
            'search_default_locationgroup': 1,
            'search_default_internal_loc': 1,
        }
        return result

    def _search_quantity_unreserved(self, operator, value):
        domain = [('qty_available_not_res', operator, value)]
        product_variant_ids = self.env['product.product'].search(domain)
        return [('product_variant_ids', 'in', product_variant_ids.ids)]


class ProductProduct(models.Model):
    _inherit = 'product.product'

    qty_available_not_res = fields.Float(
        string='Qty Available Not Reserved',
        digits=UNIT,
        compute='_compute_quantities',
        search="_search_quantity_unreserved",
    )


    @api.depends('stock_move_ids.product_qty', 'stock_move_ids.state', 'stock_quant_ids.unreserved_quantity')
    def _compute_quantities(self):
        res = self._compute_quantities_dict(self._context.get('lot_id'), self._context.get('owner_id'),
                                            self._context.get('package_id'), self._context.get('from_date'),
                                            self._context.get('to_date'))
        for product in self:
            product.qty_available = res[product.id]['qty_available']
            product.incoming_qty = res[product.id]['incoming_qty']
            product.outgoing_qty = res[product.id]['outgoing_qty']
            product.virtual_available = res[product.id]['virtual_available']
            product.qty_available_not_res = res[product.id]['unreserved_quantity']

            # Explode set content and find unreserved quantity
            if product.product_tmpl_id.set_product:
                bom_obj = self.env["mrp.bom"].sudo()
                bom_id = bom_obj._bom_find(product=product)
                if bom_id:
                    boms, lines = bom_id.explode(
                        product, quantity=1, picking_type=bom_id.picking_type_id
                    )
                    exploded_set_qty = 0
                    for line in lines:
                        unreserved_qty = line[1]["target_product"].qty_available_not_res
                        factor = line[1]["qty"]
                        if unreserved_qty > 0 and factor > 0:
                            set_qty = unreserved_qty / factor
                        else:
                            set_qty = 0
                        exploded_set_qty = min(set_qty, exploded_set_qty) if exploded_set_qty else set_qty
                    product.qty_available_not_res = exploded_set_qty

                else:
                    product.qty_available_not_res = 0
        return res

    def _compute_quantities_dict(self, lot_id, owner_id, package_id, from_date=False, to_date=False):
        domain_quant_loc, domain_move_in_loc, domain_move_out_loc = self._get_domain_locations()
        domain_quant = [('product_id', 'in', self.ids)] + domain_quant_loc
        domain_non_reserved_quant = [('contains_unreserved', '=', True)] + domain_quant
        dates_in_the_past = False
        # only to_date as to_date will correspond to qty_available
        to_date = fields.Datetime.to_datetime(to_date)
        if to_date and to_date < fields.Datetime.now():
            dates_in_the_past = True

        domain_move_in = [('product_id', 'in', self.ids)] + domain_move_in_loc
        domain_move_out = [('product_id', 'in', self.ids)] + domain_move_out_loc
        if lot_id is not None:
            domain_quant += [('lot_id', '=', lot_id)]
        if owner_id is not None:
            domain_quant += [('owner_id', '=', owner_id)]
            domain_move_in += [('restrict_partner_id', '=', owner_id)]
            domain_move_out += [('restrict_partner_id', '=', owner_id)]
        if package_id is not None:
            domain_quant += [('package_id', '=', package_id)]
        if dates_in_the_past:
            domain_move_in_done = list(domain_move_in)
            domain_move_out_done = list(domain_move_out)
        if from_date:
            domain_move_in += [('date', '>=', from_date)]
            domain_move_out += [('date', '>=', from_date)]
        if to_date:
            domain_move_in += [('date', '<=', to_date)]
            domain_move_out += [('date', '<=', to_date)]

        Move = self.env['stock.move']
        Quant = self.env['stock.quant']
        domain_move_in_todo = [('state', 'in',
                                ('waiting', 'confirmed', 'assigned', 'partially_available'))] + domain_move_in
        domain_move_out_todo = [('state', 'in',
                                 ('waiting', 'confirmed', 'assigned', 'partially_available'))] + domain_move_out
        moves_in_res = dict((item['product_id'][0], item['product_qty']) for item in
                            Move.read_group(domain_move_in_todo, ['product_id', 'product_qty'], ['product_id'],
                                            orderby='id'))
        moves_out_res = dict((item['product_id'][0], item['product_qty']) for item in
                             Move.read_group(domain_move_out_todo, ['product_id', 'product_qty'], ['product_id'],
                                             orderby='id'))
        quants_res = dict((item['product_id'][0], item['quantity']) for item in
                          Quant.read_group(domain_quant, ['product_id', 'quantity'], ['product_id'], orderby='id'))
        quants_unres_res = dict((item['product_id'][0], item['unreserved_quantity']) for item in
                                Quant.read_group(domain_non_reserved_quant, ['product_id', 'unreserved_quantity'],
                                                 ['product_id'], orderby='id'))

        if dates_in_the_past:
            # Calculate the moves that were done before now to calculate back in time (as most questions will be recent ones)
            domain_move_in_done = [('state', '=', 'done'), ('date', '>', to_date)] + domain_move_in_done
            domain_move_out_done = [('state', '=', 'done'), ('date', '>', to_date)] + domain_move_out_done
            moves_in_res_past = dict((item['product_id'][0], item['product_qty']) for item in
                                     Move.read_group(domain_move_in_done, ['product_id', 'product_qty'], ['product_id'],
                                                     orderby='id'))
            moves_out_res_past = dict((item['product_id'][0], item['product_qty']) for item in
                                      Move.read_group(domain_move_out_done, ['product_id', 'product_qty'],
                                                      ['product_id'], orderby='id'))

        res = dict()
        for product in self.with_context(prefetch_fields=False):
            product_id = product.id
            rounding = product.uom_id.rounding
            res[product_id] = {}
            if dates_in_the_past:
                qty_available = quants_res.get(product_id, 0.0) - moves_in_res_past.get(product_id,
                                                                                        0.0) + moves_out_res_past.get(
                    product_id, 0.0)
            else:
                qty_available = quants_res.get(product_id, 0.0)
            res[product_id]['qty_available'] = float_round(qty_available, precision_rounding=rounding)
            res[product_id]['incoming_qty'] = float_round(moves_in_res.get(product_id, 0.0),
                                                          precision_rounding=rounding)
            res[product_id]['outgoing_qty'] = float_round(moves_out_res.get(product_id, 0.0),
                                                          precision_rounding=rounding)
            res[product_id]['virtual_available'] = float_round(
                qty_available + res[product_id]['incoming_qty'] - res[product_id]['outgoing_qty'],
                precision_rounding=rounding)
            res[product_id]['unreserved_quantity'] = float_round(quants_unres_res.get(product_id, 0.0),
                                                                 precision_rounding=rounding)

        return res

    def _compute_qty_available_not_reserved(self):
        return self._compute_quantities()

    def _get_domain_locations(self):
        rec = super(ProductProduct, self)._get_domain_locations()
        if self.env.context.get('has_unreserved_quantity', False):
            domain_quant = [
                ('contains_unreserved', '=', True),
            ]
            rec += (domain_quant,)
        return rec

    def _search_quantity_unreserved(self, operator, value):
        if operator not in OPERATORS:
            raise UserError(_('Invalid domain operator %s') % operator)
        if not isinstance(value, (float, int)):
            raise UserError(_('Invalid domain right operand %s') % value)
        if value and operator == '>' and not (
            {'from_date', 'to_date'} & set(self.env.context.keys())):
            product_ids = self.with_context(
                has_unreserved_quantity=True)._search_qty_available_new(
                operator, value, self.env.context.get('lot_id'),
                self.env.context.get('owner_id'),
                self.env.context.get('package_id')
            )
            return [('id', 'in', product_ids)]
        ids = []
        for product in self.search([]):
            if OPERATORS[operator](product.qty_available_not_res, value):
                ids.append(product.id)
        return [('id', 'in', ids)]
