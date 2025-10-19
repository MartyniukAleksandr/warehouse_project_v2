# inventory/urls.py
from django.shortcuts import redirect
from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Shift Management
    path('shifts/start/', views.start_shift, name='shift_start'),
    path('shifts/end/', views.end_shift, name='shift_end'),

    # Products
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/add/', views.ProductCreateView.as_view(), name='product_add'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_edit'),
    path('products/delete-selected/', views.delete_selected_products, name='product_delete_selected'),
    path('products/export/pdf/', views.export_products_to_pdf, name='export_products_pdf'),

    # Orders
    path('orders/', views.OrderListView.as_view(), name='order_list'),

    path('orders/archived/', views.ArchivedOrderListView.as_view(), name='order_archive'),
    path('orders/add/', views.order_create, name='order_add'),

    path('orders/<int:pk>/edit/', views.order_update, name='order_edit'),
    path('order/<int:pk>/ship/', views.ship_with_driver_info, name='order_ship'), #new rout
    path('orders/<int:pk>/delete/', views.soft_delete_order, name='soft_delete_order'),
    path('orders/<int:pk>/load/', views.load_order, name='order_load'),
    path('orders/<int:pk>/reject-load/', views.reject_load, name='order_reject_load'),
    path('orders/export/pdf/', views.export_orders_to_pdf, name='export_orders_pdf'),
    path('orders/<int:pk>/cancel/', views.cancel_order, name='order_cancel'),
    path('products/<int:pk>/history/', views.ProductMovementHistoryView.as_view(), name='product_history'), # Новий URL
    path('orders/<int:pk>/delete-permanently/', views.delete_cancelled_order, name='delete_cancelled_order'),
    path('order_summary/', views.order_summary_view, name='order_report'),

    # Supply Management
    path('supplies/', views.SupplyListView.as_view(), name='supply_list'),
    path('supplies/add/', views.supply_create, name='supply_add'),
    path('supplies/<int:pk>/process/', views.process_supply, name='supply_process'),
    path('supplies/<int:pk>/delete/', views.supply_delete, name='supply_delete'),

    # Main page redirect
    path('', lambda request: redirect('inventory:product_list', permanent=True)),
]
