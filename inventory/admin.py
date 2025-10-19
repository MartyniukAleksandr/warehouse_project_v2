# inventory/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Product, Order, OrderItem, WorkShift, Supply, SupplyItem, Driver, Car
from simple_history.admin import SimpleHistoryAdmin
from django.utils.translation import gettext_lazy as _

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    # Видалено 'nickname' з list_display та search_fields
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ('number',)
    search_fields = ('number',)

@admin.register(Product)
class ProductAdmin(SimpleHistoryAdmin):
    """
    Налаштування відображення моделі Product в адмін-панелі.
    """
    list_display = ('name', 'company', 'total_units', "low_threshold", "normal_threshold")
    search_fields = ('name', 'company')
    list_filter = ('company',)
    ordering = ('name',)
    fieldsets = (
        (None, {
            'fields': ('name', 'company')
        }),
        (_('Залишки на складі'), {
            'fields': ('total_units', 'quantity_per_pallet')
        }),
        (_('Додаткова інформація'), {
            'classes': ('collapse',),  # Робить секцію згортаємою
            'fields': ('notes',)
        }),
        (_("Рівень наповнюваності"),{
            'classes': ('collapse',), 'fields': ('low_threshold', 'normal_threshold')
        })
    )


class OrderItemInline(admin.TabularInline):
    """
    Дозволяє редагувати позиції замовлення безпосередньо на сторінці Order.
    """
    model = OrderItem
    extra = 1  # Кількість порожніх форм для додавання нових позицій
    readonly_fields = ('product_link',)
    fields = ('product', 'ordered_units')

    def product_link(self, instance):
        if instance.product_id:
            url = reverse("admin:inventory_product_change", args=(instance.product.id,))
            return format_html('<a href="{}">{}</a>', url, instance.product)
        return "-"

    product_link.short_description = _('Продукт')


@admin.register(Order)
class OrderAdmin(SimpleHistoryAdmin):
    """
    Налаштування відображення моделі Order в адмін-панелі.
    """
    list_display = ('id', 'customer', 'status', 'is_deleted', 'work_shift', 'created_at',)
    list_filter = ('status', 'is_deleted', 'created_at', 'work_shift')
    search_fields = ('customer', 'items__product__name', 'driver__name', 'car__number')
    ordering = ('-created_at',)
    list_display_links = ('id', 'customer')
    readonly_fields = ('created_at',)
    inlines = [OrderItemInline]  # Додаємо редагування позицій

    fieldsets = (
        (_('Основна інформація'), {
            'fields': ('customer', 'notes')
        }),
        (_('Статус'), {
            'fields': ('status', 'is_deleted', 'work_shift', 'created_at')
        }),
    )

    def get_queryset(self, request):
        # Оптимізуємо запити до бази даних
        return super().get_queryset(request).prefetch_related('items__product', 'work_shift')


@admin.register(WorkShift)
class WorkShiftAdmin(SimpleHistoryAdmin):
    list_display = ('start_time', 'end_time', 'is_active')
    list_filter = ('is_active',)
    readonly_fields = ('start_time', 'end_time')


class SupplyItemInline(admin.TabularInline):
    """
    Дозволяє редагувати позиції постачання на сторінці Supply.
    """
    model = SupplyItem
    extra = 1


@admin.register(Supply)
class SupplyAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'supplier', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('supplier',)
    inlines = [SupplyItemInline]
    readonly_fields = ('created_at',)
