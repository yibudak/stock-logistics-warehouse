# -*- coding: utf-8 -*-
# Copyright 2016 OdooMRP Team
# Copyright 2016 AvanzOSC
# Copyright 2016 Pedro M. Baeza <pedro.baeza@tecnativa.com>
# Copyright 2016 Serpent Consulting Services Pvt. Ltd.
# Copyright 2016 Eficent Business and IT Consulting Services, S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, fields, api


class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    @api.multi
    def _compute_product_available_qty(self):
        for rec in self:
            product_available = rec.product_id.with_context(
                location=rec.location_id.id
                )._product_available()[rec.product_id.id]
            rec.product_location_qty = product_available['qty_available']
            rec.incoming_location_qty = product_available['incoming_qty']
            rec.outgoing_location_qty = product_available['outgoing_qty']
            rec.virtual_location_qty = product_available['virtual_available']

    product_location_qty = fields.Float(
        string='Quantity On Location',
        compute='_compute_product_available_qty')
    incoming_location_qty = fields.Float(
        string='Incoming On Location',
        compute='_compute_product_available_qty')
    outgoing_location_qty = fields.Float(
        string='Outgoing On Location',
        compute='_compute_product_available_qty')
    virtual_location_qty = fields.Float(
        string='Forecast On Location',
        compute='_compute_product_available_qty')
    product_category = fields.Many2one(string='Product Category',
                                       related='product_id.categ_id',
                                       store=True)

    transfers_to_customer_ids = fields.Many2many('stock.move',string='Transfers to Customers',
                                                 compute='_compute_customer_transfers')
    production_ids = fields.Many2many('mrp.production',string='Manufacturing Orders', compute='_compute_productions')
    done_purchaseline_ids = fields.Many2many('purchase.order.line', string='Previous Purchases',
                                                 compute='_compute_done_purchaselines')
    done_orderline_ids = fields.Many2many('sale.order.line', string='Done Orders',
                                                 compute='_compute_done_orderlines')


    @api.multi
    @api.depends('product_id')
    def _compute_productions(self):
        for wizard in self:
            wizard.production_ids = self.env['mrp.production'].search([('product_id','=',wizard.product_id.id),('state','not in', ['cancel'])],limit=40,order='create_date desc')

    @api.multi
    @api.depends('product_id')
    def _compute_customer_transfers(self):
        for wizard in self:
            wizard.transfers_to_customer_ids = self.env['stock.move'].search([('product_id','=',wizard.product_id.id),('state','not in', ['draft','cancel'])],limit=40,order='create_date desc')

    @api.multi
    @api.depends('product_id')
    def _compute_done_purchaselines(self):
        for wizard in self:
            wizard.done_purchaseline_ids = self.env['purchase.order.line'].search([('product_id','=',wizard.product_id.id),('state','not in', ['draft','cancel'])],limit=40,order='create_date desc')

    @api.multi
    @api.depends('product_id')
    def _compute_done_orderlines(self):
        for wizard in self:
            wizard.done_orderline_ids = self.env['sale.order.line'].search([('product_id','=',wizard.product_id.id),('state','not in', ['draft','cancel'])],limit=40,order='create_date desc')
