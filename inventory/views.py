# inventory/views.py
from itertools import groupby

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView
from django.db.models import Sum, F, Q
from django.contrib import messages
from django.db import transaction
from django.utils.translation import gettext as _
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.forms import inlineformset_factory
from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from datetime import datetime
from .models import Product, Order, OrderItem, WorkShift, Supply, SupplyItem, StockMovement
from .forms import ProductForm, OrderForm, OrderItemForm, SupplyForm, SupplyItemForm, DriverInfoForm
from .pdf_utils import generate_pdf_response
from datetime import date
from collections import defaultdict
from django.contrib.auth.decorators import user_passes_test



# Допоміжна функція для створення записів у журналі
def create_stock_movement(user, product, quantity_change, movement_type, order=None, supply=None, notes=""):
    """Створює запис про рух товару на складі."""
    StockMovement.objects.create(
        user=user,
        product=product,
        quantity_change=quantity_change,
        new_total_units=product.total_units,
        movement_type=movement_type,
        related_order=order,
        related_supply=supply,
        notes=notes
    )

#--- Report Management ---
class OrderSummaryManager:
    """
    Клас, що інкапсулює логіку отримання та агрегації
    даних замовлень на основі моделей Product, Order та OrderItem.
    """
    def __init__(self, request):
        """
        Ініціалізує менеджер з об'єктом запиту.
        """
        self.request = request
        self.time_period = self.request.GET.get('time_period', 'month')
        self.start_date_str = self.request.GET.get('start_date')
        self.end_date_str = self.request.GET.get('end_date')

    def _get_filtered_queryset(self):
        """
        Створює початковий QuerySet, фільтруючи його по статусу замовлення
        та діапазону дат.
        """
        queryset = OrderItem.objects.all()

        # Фільтруємо замовлення за статусом і статусом архіву.
        # Враховуються:
        # 1. Замовлення зі статусом 'Відправлено' (SHIPPED), незалежно від того, чи воно в архіві.
        # 2. Замовлення зі статусом 'В очікуванні' (PENDING), але лише ті, які НЕ в архіві.
        # Скасовані замовлення не враховуються.
        queryset = queryset.filter(
            Q(order__status=Order.OrderStatus.SHIPPED) | (
                    Q(order__status=Order.OrderStatus.LOADED) & Q(order__is_deleted=False)
            )
        )

        # Застосовуємо фільтрацію по датах, якщо вони передані
        if self.start_date_str:
            start_date = datetime.strptime(self.start_date_str, '%Y-%m-%d').date()
            queryset = queryset.filter(order__created_at__gte=start_date)

        if self.end_date_str:
            end_date = datetime.strptime(self.end_date_str, '%Y-%m-%d').date()
            end_datetime = datetime.combine(end_date, datetime.max.time())
            queryset = queryset.filter(order__created_at__lte=end_datetime)

        return queryset

    def get_summary_data(self):
        """
        Виконує агрегацію даних на основі відфільтрованого QuerySet.
        """
        queryset = self._get_filtered_queryset()

        trunc_map = {
            'day': TruncDay,
            'month': TruncMonth,
            'year': TruncYear
        }

        trunc_func = trunc_map.get(self.time_period)
        if not trunc_func:
            return []

        summary = queryset.annotate(
            period=trunc_func('order__created_at')
        ).values(
            'period', 'product__name'
        ).annotate(
            total_quantity=Sum('ordered_units')
        ).order_by('period')

        return summary

    def _get_table_title(self):
        """
        Формує заголовок таблиці відповідно до вибраного періоду.
        """
        title_map = {
            'day': _("Щоденна статистика"),
            'month': _("Щомісячна статистика"),
            'year': _("Щорічна статистика")
        }
        return title_map.get(self.time_period, _("Статистика замовлень"))


    def get_context(self):
        """
        Формує словник контексту для шаблону.
        """
        return {
            'summary_data': self.get_summary_data(),
            'selected_period': self.time_period,
            'start_date': self.start_date_str,
            'end_date': self.end_date_str,
            'table_title': self._get_table_title(),
        }

# Створюємо функцію-перевірку. Вона перевіряє, чи є користувач суперкористувачем.
# Використовуємо декоратор @user_passes_test
@user_passes_test(lambda user: user.is_superuser)
def order_summary_view(request):
    """
    Представлення для відображення статистики замовлень.
    """
    manager = OrderSummaryManager(request)
    context = manager.get_context()
    return render(request, 'inventory/order_report.html', context)

# --- Нове представлення для історії руху товару ---
class ProductMovementHistoryView(LoginRequiredMixin, ListView):
    model = StockMovement
    template_name = 'inventory/product_movement_history.html'
    context_object_name = 'movements'
    paginate_by = 25

    def get_queryset(self):
        self.product = get_object_or_404(Product, pk=self.kwargs['pk'])
        # Оптимізуємо запит, додавши prefetch для користувача
        return StockMovement.objects.filter(product=self.product).select_related('user').order_by('-timestamp')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product'] = self.product
        return context

# --- Shift Management Views ---

@login_required
@require_POST
def start_shift(request):
    if WorkShift.objects.filter(is_active=True).exists():
        messages.error(request, _("Неможливо почати нову зміну, поки активна попередня."))
    else:
        WorkShift.objects.create()
        messages.success(request, _("Нову робочу зміну розпочато."))
    return redirect('inventory:order_list')


@login_required
@require_POST
def end_shift(request):
    try:
        with transaction.atomic():
            active_shift = WorkShift.objects.get(is_active=True)
            active_shift.end_time = timezone.now()
            active_shift.is_active = False
            active_shift.save()

            messages.success(request, _(" Робочу зміну успішно закрито"))
    except WorkShift.DoesNotExist:
        messages.error(request, _("Не знайдено активної зміни для закриття."))

    return redirect('inventory:order_list')

# --- Views for Product ---

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'inventory/product_list.html'
    context_object_name = 'products'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(company__icontains=query))

        # Забарвлення рядків на основі кількості повних палет
        for product in queryset:
            if product.total_units <= product.low_threshold:
                product.level_class = 'table-danger'
            elif product.total_units >= product.normal_threshold:
                product.level_class = 'table-success'
                #product.level_class = 'table-warning'
            else:
                product.level_class = 'table-warning'
                #product.level_class = 'table-success'
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        # Загальна сума всіх одиниць на складі
        total_items_agg = Product.objects.aggregate(total=Sum('total_units'))
        context['grand_total_units'] = total_items_agg['total'] or 0
        return context


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('inventory:product_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _("Додати новий продукт")
        return context


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('inventory:product_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _("Редагувати продукт")
        return context


@login_required
@require_POST
def delete_selected_products(request):
    """
    View для видалення кількох обраних продуктів.
    """
    product_ids = request.POST.getlist('product_ids')
    if not product_ids:
        messages.warning(request, _("Ви не обрали жодного продукту для видалення."))
        return redirect('inventory:product_list')

    # Перевіряємо, чи не пов'язані продукти з існуючими замовленнями через OrderItem
    protected_items = OrderItem.objects.filter(product_id__in=product_ids).select_related('product')

    if protected_items.exists():
        # Отримуємо унікальні імена захищених продуктів
        protected_product_names = list(set(item.product.name for item in protected_items))
        msg = _("Неможливо видалити продукти: {products}, оскільки вони є в існуючих замовленнях.").format(
            products=', '.join(protected_product_names)
        )
        messages.error(request, msg)
        return redirect('inventory:product_list')

    products_to_delete = Product.objects.filter(pk__in=product_ids)
    count = products_to_delete.count()
    products_to_delete.delete()
    messages.success(request, _("Успішно видалено {count} продукт(ів).").format(count=count))
    return redirect('inventory:product_list')

# --- Views for Order ---

# --- Order Views (оновлено) ---

class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'inventory/order_list.html'
    context_object_name = 'orders'
    paginate_by = 10

    def get_queryset(self):
        # 1. Початковий queryset (тільки неархівовані замовлення)
        queryset = super().get_queryset().filter(is_deleted=False).prefetch_related('items', 'items__product')

        # Отримуємо GET-параметри
        query = self.request.GET.get('q')
        filter_date_str = self.request.GET.get('delivery_date_filter')

        # --- 2. Фільтрація за пошуковим запитом (customer, product) ---
        if query:
            queryset = queryset.filter(
                Q(customer__icontains=query) | Q(items__product__name__icontains=query)
            ).distinct()

        # --- 3. Фільтрація за датою доставки (НОВИЙ ФУНКЦІОНАЛ) ---
        if filter_date_str:
            try:
                # Перетворюємо рядок дати на об'єкт date
                filter_date = date.fromisoformat(filter_date_str)

                # Фільтруємо замовлення, де delivery_date точно дорівнює вибраній даті
                queryset = queryset.filter(delivery_date=filter_date)

            except ValueError:
                # Обробка помилки, якщо користувач ввів некоректний формат дати
                # Можна ігнорувати або додати повідомлення про помилку через messages framework,
                # але для простоти поки ігноруємо.
                pass

                # Сортування: за датою доставки (від найближчої до найдальшої)
        # та за датою створення (якщо delivery_date однакові)
        queryset = queryset.order_by('delivery_date', 'created_at')

        return queryset

    def get_context_data(self, **kwargs):
        # Викликаємо батьківський метод для отримання стандартного контексту (включно з пагінацією)
        context = super().get_context_data(**kwargs)

        # 1. Отримуємо ЗАМОВЛЕННЯ З ПОТОЧНОЇ СТОРІНКИ пагінації
        page_obj = context.get('page_obj')
        orders_on_page = page_obj.object_list if page_obj else self.get_queryset()
        # Визначаємо початковий індекс для поточної сторінки
        start_index = page_obj.start_index if page_obj else 1
        current_index = 0  # Індекс зміщення (0, 1, 2...) відносно початку сторінки

        # 2. Групуємо замовлення за датою доставки
        grouped_orders = defaultdict(list)
        for order in orders_on_page:
            order.forloop_counter0 = current_index
            # Використовуємо дату доставки як ключ
            grouped_orders[order.delivery_date].append(order)
            current_index += 1

        # 3. Конвертуємо defaultdict у відсортований список кортежів (дата, список_замовлень)
        # Оскільки queryset вже відсортовано, групування буде відбуватися у правильному порядку.
        # Але явне сортування ключами забезпечить порядок, якщо пагінатор розіб'є групу.
        sorted_groups = sorted(grouped_orders.items(), key=lambda item: item[0] if item[0] is not None else date.max)

        # 4. Передаємо нові дані в контекст
        context['grouped_orders'] = sorted_groups
        context['driver_form'] = DriverInfoForm()
        context['today'] = date.today()  # Для порівняння в шаблоні

        # Передаємо вибрану дату для фільтра (як було)
        selected_date_str = self.request.GET.get('delivery_date_filter')
        context['selected_delivery_date'] = selected_date_str

        # Видаляємо 'orders' з контексту, щоб у шаблоні ітерувати лише по 'grouped_orders'
        # context.pop('orders', None)
        # Примітка: Ми не видаляємо 'orders' повністю, оскільки пагінатор може його використовувати,
        # але в шаблоні ми ітеруємо по 'grouped_orders'.

        return context


class ArchivedOrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'inventory/archived_order_list.html'
    context_object_name = 'orders'
    paginate_by = 10

    def get_queryset(self):
        # ... (Логіка get_queryset залишається незмінною) ...
        queryset = super().get_queryset().filter(is_deleted=True).select_related(
            'car', 'driver'
        ).prefetch_related(
            'items', 'items__product', 'work_shift'
        )

        query = self.request.GET.get('q')
        delivery_date_filter = self.request.GET.get('delivery_date_filter')

        if query:
            queryset = queryset.filter(
                Q(customer__icontains=query) | Q(items__product__name__icontains=query)
            ).distinct()

        if delivery_date_filter:
            try:
                filter_date = datetime.strptime(delivery_date_filter, '%Y-%m-%d').date()
                queryset = queryset.filter(delivery_date=filter_date)
            except ValueError:
                pass

        # Сортуємо для коректного групування за МІСЯЦЕМ.
        queryset = queryset.order_by('-delivery_date')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        archived_orders_page = context.get('object_list')
        grouped_orders = {}

        # 1. Визначення ключа групування. ПОВЕРТАЄМО ОБ'ЄКТ date
        def get_month_key(order):
            if order.delivery_date:
                # 💡 ВИПРАВЛЕННЯ: Повертаємо об'єкт date, що представляє 1-ше число місяця
                return date(order.delivery_date.year, order.delivery_date.month, 1)
            # Групуємо замовлення без дати доставки в окрему групу (рядок)
            return 'No-Date'

        # 2. Сортування: Сортуємо на рівні Python-списку за новим ключем групування.
        # reverse=True гарантує, що нові місяці будуть першими.
        sorted_orders = sorted(archived_orders_page, key=get_month_key, reverse=True)

        # 3. Групування
        for month_key, group in groupby(sorted_orders, key=get_month_key):
            # 💡 month_key тепер буде або об'єктом date, або рядком 'No-Date'
            grouped_orders[month_key] = list(group)

        context['grouped_orders'] = grouped_orders

        # 4. Передача значень фільтрів (без змін)
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_delivery_date'] = self.request.GET.get('delivery_date_filter', '')

        return context
OrderItemFormSet = inlineformset_factory(
    Order, OrderItem, form=OrderItemForm,
    extra=1, can_delete=True, can_delete_extra=True
)
# inventory/views.py (Адаптований код)

@login_required
def order_create(request):
    from datetime import date
    today = date.today()

    # Активна зміна потрібна лише для логіки прив'язки та повідомлень про негайне виконання.
    active_shift = WorkShift.objects.filter(is_active=True).first()

    if request.method == 'POST':
        order_form = OrderForm(request.POST)
        formset = OrderItemFormSet(request.POST)

        if order_form.is_valid() and formset.is_valid():

            # --- 1. Перевірка на унікальність товарів ---
            product_ids = [
                form.cleaned_data['product'].id
                for form in formset
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
            ]
            if len(product_ids) != len(set(product_ids)):
                messages.error(request, _("У замовленні не може бути однакових позицій. Будь ласка, об'єднайте їх."))
                context = {
                    'order_form': order_form,
                    'formset': formset,
                    'page_title': _("Створити замовлення")
                }
                return render(request, 'inventory/order_form.html', context)

            # Отримуємо дату доставки з форми
            delivery_date = order_form.cleaned_data.get('delivery_date')

            # Визначаємо, чи замовлення на сьогодні/раніше
            is_immediate_fulfillment = delivery_date and delivery_date <= today

            # Якщо замовлення на сьогодні/раніше, вимагаємо активну зміну
            if is_immediate_fulfillment and not active_shift:
                messages.error(request,
                               _("Неможливо створити замовлення з датою доставки сьогодні або раніше. Спочатку відкрийте робочу зміну."))
                context = {
                    'order_form': order_form,
                    'formset': formset,
                    'page_title': _("Створити замовлення")
                }
                return render(request, 'inventory/order_form.html', context)

            try:
                with transaction.atomic():

                    # --- 2. Перевірка наявності товару (ЗАВЖДИ ПРОВОДИМО ДЛЯ РЕЗЕРВУВАННЯ) ---
                    for form in formset:
                        if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                            product = form.cleaned_data['product']
                            ordered_units = form.cleaned_data['ordered_units']
                            # Перевірка, оскільки резервування/списання відбувається одразу
                            if product.total_units < ordered_units:
                                raise ValueError(
                                    _("Недостатньо товару '{product}' на складі для резервування.").format(
                                        product=product.name))

                    # --- 3. Збереження замовлення ---
                    order = order_form.save(commit=False)

                    # Призначаємо work_shift лише якщо це замовлення на сьогодні/раніше
                    if is_immediate_fulfillment and active_shift:
                        order.work_shift = active_shift
                    else:
                        order.work_shift = None  # Для майбутніх замовлень

                    order.save()

                    # --- 4. Збереження позицій та списання/резервування товару ---
                    formset.instance = order

                    # Тип руху завжди "Резервування під замовлення" (ORDER_OUT)
                    movement_type = StockMovement.MovementType.ORDER_OUT

                    for form_data in formset.cleaned_data:
                        if form_data and not form_data.get('DELETE', False):
                            product = form_data['product']
                            ordered_units = form_data['ordered_units']

                            # Зменшення загальної кількості (СПИСАННЯ/РЕЗЕРВУВАННЯ)
                            product.total_units -= ordered_units
                            product.save()

                            # Створення руху запасу
                            # Примітки вказують, чи це "негайний вихід" чи "майбутній резерв"
                            if is_immediate_fulfillment:
                                notes_message = _("Прийняте замовлення (виконано одразу, датою - %(date)s) для "
                                                  "клієнта: %(customer)s")
                            else:
                                notes_message = _(
                                    "Резервування замовлення (доставка %(date)s) для клієнта: %(customer)s")

                            formatted_notes = notes_message % {'customer': order.customer, 'date': delivery_date}

                            # Створення руху запасу з типом ORDER_OUT (Резервування під замовлення)
                            create_stock_movement(request.user, product, -ordered_units,
                                                  movement_type,
                                                  order=order, notes=formatted_notes)

                    # Зберігаємо позиції замовлення
                    formset.save()

                    # Формуємо повідомлення для користувача
                    status_message = _("Товар успішно зарезервовано для доставки {date}.").format(
                        date=delivery_date.strftime('%Y-%m-%d'))
                    if is_immediate_fulfillment:
                        status_message = _("Товар списано зі складу, замовлення оформлено до виконання.")

                    messages.success(request, _("Замовлення успішно створено. %s") % status_message)
                    return redirect('inventory:order_list')
            except ValueError as e:
                messages.error(request, str(e))
                # Повертаємо користувача на сторінку з його даними
                context = {
                    'order_form': order_form,
                    'formset': formset,
                    'page_title': _("Створити замовлення")
                }
                return render(request, 'inventory/order_form.html', context)
    else:
        # GET-запит
        order_form = OrderForm(initial={'delivery_date': today})  # Встановлюємо сьогоднішню дату за замовчуванням
        formset = OrderItemFormSet()

    context = {
        'order_form': order_form,
        'formset': formset,
        'page_title': _("Створити замовлення")
    }
    return render(request, 'inventory/order_form.html', context)

@login_required
# inventory/views.py
@login_required
def order_update(request, pk):
    order = get_object_or_404(Order, pk=pk)

    if request.method == 'POST':
        if order.is_deleted:
            messages.info(request, _('Це замовлення знаходиться в архіві і не може бути відредаговане.'))
            return redirect('inventory:product_list')

        if order.status == Order.OrderStatus.SHIPPED:
            messages.error(request, _("Неможливо редагувати замовлення, яке вже було відправлено."))
            return redirect('inventory:order_list')

        order_form = OrderForm(request.POST, instance=order)
        formset = OrderItemFormSet(request.POST, instance=order)

        if order.status == Order.OrderStatus.LOADED:
            if order_form.is_valid():
                order_form.save()
                messages.success(request, _("Інформацію про водія оновлено."))
                return redirect('inventory:order_list')

        elif order.status == Order.OrderStatus.PENDING:
            if order_form.is_valid() and formset.is_valid():
                # 1. Додана перевірка на унікальність товарів
                product_ids = [
                    form.cleaned_data['product'].id
                    for form in formset
                    if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
                ]
                if len(product_ids) != len(set(product_ids)):
                    messages.error(request,
                                   _("У замовленні не може бути однакових позицій. Будь ласка, об'єднайте їх."))
                    context = {
                        'order_form': order_form,
                        'formset': formset,
                        'order': order,
                        'page_title': _("Перегляд/Редагувати замовлення")
                    }
                    return render(request, 'inventory/order_form.html', context)

                try:
                    with transaction.atomic():
                        # Складна логіка для розрахунку змін на складі
                        new_items = {item['product'].id: item['ordered_units'] for item in formset.cleaned_data if
                                     item and not item.get('DELETE')}
                        old_items = {item.product.id: item.ordered_units for item in order.items.all()}

                        all_products_ids = set(new_items.keys()) | set(old_items.keys())
                        products = Product.objects.in_bulk(list(all_products_ids))

                        # 1. Перевірка наявності товару перед змінами
                        for prod_id in all_products_ids:
                            delta = new_items.get(prod_id, 0) - old_items.get(prod_id, 0)
                            if delta > 0 and products[prod_id].total_units < delta:
                                raise ValueError(
                                    _("Недостатньо товару '{product}' для збільшення замовлення.").format(
                                        product=products[prod_id].name))
                        # 2. Застосування змін до залишків на складі
                        for prod_id in all_products_ids:
                            delta = new_items.get(prod_id, 0) - old_items.get(prod_id, 0)
                            if delta != 0:
                                products[prod_id].total_units -= delta
                                products[prod_id].save()
                                # Створюємо запис у журналі
                                movement_type = StockMovement.MovementType.ORDER_OUT if delta > 0 else StockMovement.MovementType.ORDER_RETURN
                                notes_message = _("Редагування замовлення для клієнта: %(customer)s")
                                formatted_notes = notes_message % {'customer': order.customer}
                                create_stock_movement(request.user, products[prod_id], -delta, movement_type,
                                                      order=order,
                                                      notes=formatted_notes)
                        # 3. Збереження форм
                        order_form.save()
                        formset.save()

                        messages.success(request, _("Замовлення успішно оновлено."))
                        return redirect('inventory:order_list')
                except ValueError as e:
                    messages.error(request, str(e))
    else:
        # GET-запит
        order_form = OrderForm(instance=order)
        formset = OrderItemFormSet(instance=order)

        # Логіка для вимкнення полів
        if order.status == Order.OrderStatus.SHIPPED:
            for field in order_form.fields.values():  # Corrected line
                field.disabled = True
            for form in formset:
                for field in form.fields.values():  # Corrected line
                    field.disabled = True
        elif order.status == Order.OrderStatus.LOADED:
            order_form.fields['customer'].disabled = True
            order_form.fields['notes'].disabled = True
            order_form.fields['delivery_date'].disabled = True
            for form in formset:
                # Corrected lines
                form.fields['product'].disabled = True
                form.fields['ordered_units'].disabled = True

    context = {
        'order_form': order_form,
        'formset': formset,
        'order': order,
        'page_title': _("Перегляд/Редагувати замовлення"),
    }
    return render(request, 'inventory/order_form.html', context)


@login_required
@require_POST
def soft_delete_order(request, pk):
    """
    Переміщує замовлення до архіву (м'яке видалення).
    Якщо замовлення було "В очікуванні", товар повертається на склад.
    """
    order = get_object_or_404(Order.objects.prefetch_related('items__product'), pk=pk)

    if order.is_deleted:
        messages.warning(request, _("Це замовлення вже в архіві."))
        return redirect('inventory:order_list')

    try:
        with transaction.atomic():
            # Повертаємо товар на склад, тільки якщо замовлення було активним (не відправленим і не скасованим)
            if order.status == Order.OrderStatus.PENDING:
                for item in order.items.all():
                    item.product.total_units += item.ordered_units
                    item.product.save()
                    # Створюємо запис у журналі
                    notes_message = _("Архівування замовлення для клієнта: %(customer)s")
                    formatted_notes = notes_message % {'customer': order.customer}
                    create_stock_movement(request.user, item.product, item.ordered_units,
                                          StockMovement.MovementType.ORDER_RETURN,
                                          order=order, notes=formatted_notes)
                messages.info(request, _("Товар із замовлення №{id} повернуто на склад.").format(id=order.id))

            order.is_deleted = True
            order.save()
            messages.success(request, _("Замовлення №{id} переміщено до архіву.").format(id=order.id))
    except Exception as e:
        messages.error(request, _("Сталася помилка при архівуванні замовлення: {}").format(e))

    return redirect('inventory:order_list')


@login_required
@require_POST
def cancel_order(request, pk):
    """
    Скасовує замовлення та повертає зарезервований товар на склад.
    """
    order = get_object_or_404(Order.objects.prefetch_related('items__product'), pk=pk)

    if order.status != Order.OrderStatus.PENDING:
        messages.warning(request, _("Неможливо скасувати замовлення зі статусом '{status}'.").format(
            status=order.get_status_display()))
        return redirect('inventory:order_list')

    try:
        with transaction.atomic():
            # Повертаємо кожну позицію товару на склад
            for item in order.items.all():
                product = item.product
                product.total_units += item.ordered_units
                product.save()
                # Створюємо запис у журналі
                notes_message = _("Скасування замовлення для клієнта: %(customer)s")
                formatted_notes = notes_message % {'customer': order.customer}
                create_stock_movement(request.user, product, item.ordered_units,
                                      StockMovement.MovementType.ORDER_RETURN, order=order,
                                      notes=formatted_notes)

            # Змінюємо статус замовлення на "Скасовано"
            order.status = Order.OrderStatus.CANCELLED
            order.save()
            messages.success(request, _("Замовлення №{id} скасовано. Товар повернуто на склад.").format(id=order.id))
    except Exception as e:
        messages.error(request, _("Сталася помилка при скасуванні замовлення: {}").format(e))

    return redirect('inventory:order_list')


@login_required
@require_POST
def delete_cancelled_order(request, pk):
    """
    Остаточно видаляє скасоване замовлення з бази даних.
    """
    order = get_object_or_404(Order, pk=pk)

    if order.status != Order.OrderStatus.CANCELLED:
        messages.warning(request, _("Можна видаляти назавжди лише скасовані замовлення."))
        return redirect('inventory:order_list')

    try:
        order_id = order.id
        order.delete()  # Остаточне видалення

        messages.success(request, _("Скасоване замовлення №{id} було остаточно видалено.").format(id=order_id))
    except Exception as e:
        messages.error(request, _("Сталася помилка під час остаточного видалення замовлення: {}").format(e))

    return redirect('inventory:order_list')

@login_required
@require_POST
def load_order(request, pk):
    """
    Змінює статус замовлення на "Готове/Завантажено".
    """
    order = get_object_or_404(Order, pk=pk)
    if order.status == Order.OrderStatus.PENDING:
        order.status = Order.OrderStatus.LOADED
        order.save()
        messages.success(request, _("Статус замовлення №{id} змінено на 'Готове/Завантажено'.").format(id=order.id))
    else:
        messages.warning(request, _("Змінити статус на 'Готове/Завантажено' можна лише для замовлень в очікуванні."))
    return redirect('inventory:order_list')

@login_required
@require_POST
def reject_load(request, pk):
    """
    Повертає статус замовлення з "Готове/Завантажено" назад до "В очікуванні".
    """
    order = get_object_or_404(Order, pk=pk)
    if order.status == Order.OrderStatus.LOADED:
        order.status = Order.OrderStatus.PENDING
        order.save()
        messages.success(request, _("Статус замовлення №{id} повернуто до 'В очікуванні'.").format(id=order.id))
    else:
        messages.warning(request, _("Відхилити завантаження можна лише для замовлень зі статусом 'Готове/Завантажено'."))
    return redirect('inventory:order_list')


@login_required
@require_POST
def ship_with_driver_info(request, pk):
    """
    Приймає дані водія з модального вікна,
    зберігає їх та змінює статус замовлення на 'Виїхало'.
    """
    # 1. Знаходимо замовлення за ID, не перевіряючи статус
    order = get_object_or_404(Order, pk=pk)

    # 2. Якщо статус не "Готове/Завантажено", показуємо повідомлення про помилку
    if order.status != Order.OrderStatus.LOADED:
        messages.error(request, _("Неможливо відправити замовлення, яке не має статусу 'Готове/Завантажено'."))
        return redirect('inventory:order_list')

    # 3. Якщо статус правильний, продовжуємо обробку форми
    form = DriverInfoForm(request.POST, instance=order)
    if form.is_valid():
        form.save()
        order.status = Order.OrderStatus.SHIPPED
        order.save()
        messages.success(request, _("Замовлення №{id} відправлено. Інформацію про водія додано.").format(id=order.id))
    else:
        errors = ". ".join([f"{field}: {', '.join(error_list)}" for field, error_list in form.errors.items()])
        messages.error(request, _("Помилка валідації: {errors}").format(errors=errors))

    return redirect('inventory:order_list')

# --- Supply Management Views ---

class SupplyListView(LoginRequiredMixin, ListView):
    model = Supply
    template_name = 'inventory/supply_list.html'
    context_object_name = 'supplies'
    paginate_by = 10

    def get_queryset(self):
        """
        Оновлений метод для фільтрації списку постачань.
        Додає функціонал пошуку за назвою постачальника та назвою товару.
        """
        queryset = super().get_queryset().prefetch_related('items', 'items__product')

        # Отримуємо пошуковий запит з GET-параметрів
        query = self.request.GET.get('q')

        if query:
            # Використовуємо Q-об'єкти для створення складного запиту
            # для пошуку за назвою постачальника АБО назвою продукту
            queryset = queryset.filter(
                Q(supplier__icontains=query) |  # Пошук за назвою постачальника (регістронезалежний)
                Q(items__product__name__icontains=query)  # Пошук за назвою продукту в поставці
            ).distinct()  # Використовуємо distinct(), щоб уникнути дублювання постачань

        return queryset


SupplyItemFormSet = inlineformset_factory(
    Supply, SupplyItem, form=SupplyItemForm,
    extra=1, can_delete=True, can_delete_extra=True
)

@login_required
def supply_create(request):
    if request.method == 'POST':
        form = SupplyForm(request.POST)
        formset = SupplyItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            supply = form.save()
            formset.instance = supply
            formset.save()
            messages.success(request, _("Нове постачання успішно створено."))
            return redirect('inventory:supply_list')
    else:
        form = SupplyForm()
        formset = SupplyItemFormSet()

    context = {
        'form': form,
        'formset': formset,
        'page_title': _("Створити постачання")
    }
    return render(request, 'inventory/supply_form.html', context)


@login_required
@require_POST
def process_supply(request, pk):
    supply = get_object_or_404(Supply.objects.prefetch_related('items__product'), pk=pk)

    if supply.status == Supply.SupplyStatus.COMPLETED:
        messages.warning(request, _("Це постачання вже було оброблено."))
        return redirect('inventory:supply_list')

    try:
        with transaction.atomic():
            for item in supply.items.all():
                product = item.product
                product.total_units += item.quantity
                product.save()
                # Передаємо request.user
                notes_message = _("Постачання від постачальника: %(supplier)s")
                formatted_notes = notes_message % {'supplier': supply.supplier}
                create_stock_movement(request.user, product, item.quantity, StockMovement.MovementType.SUPPLY_IN,
                                      supply=supply, notes=formatted_notes)

            supply.status = Supply.SupplyStatus.COMPLETED
            supply.save()
            messages.success(request, _("Постачання №{id} прийнято. Залишки на складі оновлено.").format(id=supply.id))
    except Exception as e:
        messages.error(request, _("Сталася помилка при обробці постачання: {}").format(e))

    return redirect('inventory:supply_list')

@login_required
@require_POST
def supply_delete(request, pk):
    """
    Остаточно видаляє постачання, якщо воно знаходиться у статусі PENDING.
    """
    supply = get_object_or_404(Supply, pk=pk)

    if supply.status != Supply.SupplyStatus.PENDING:
        messages.error(request, _("Можна видаляти лише постачання зі статусом 'В очікуванні'. Оброблений товар потрібно повертати іншим методом."))
        return redirect('inventory:supply_list')

    try:
        supply_id = supply.id
        supply.delete() # Остаточне видалення
        messages.success(request, _("Постачання {id} успішно видалено.").format(id=supply_id))
    except Exception as e:
        messages.error(request, _("Сталася помилка під час видалення постачання: {}").format(e))

    return redirect('inventory:supply_list')

# --- PDF Export Views (Оновлено) ---

@login_required
def export_products_to_pdf(request):
    """
    Експортує список продуктів у PDF, включаючи примітки та порядковий номер.
    """
    query = request.GET.get('q')
    products = Product.objects.all().order_by('name')
    if query:
        products = products.filter(Q(name__icontains=query) | Q(company__icontains=query))

    title = _('Звіт по продуктах на складі')
    headers = [
        _('№'), _('Назва'), _('Фірма'), _('Загальний залишок (шт.)'), _('Примітки')
    ]

    # Використовуємо enumerate для додавання порядкового номера
    data = [
        [i, p.name, p.company, p.total_units, p.notes or '']
        for i, p in enumerate(products, 1)
    ]

    return generate_pdf_response('products_report.pdf', title, headers, data)


@login_required
def export_orders_to_pdf(request):
    """
    Експортує список замовлень у PDF, враховуючи пошук та фільтрацію за датою доставки.
    Замовлення сортуються за датою доставки.
    """
    # Отримуємо GET-параметри
    query = request.GET.get('q')
    filter_date_str = request.GET.get('delivery_date_filter')

    # 1. Початковий Queryset
    orders = Order.objects.filter(is_deleted=False).prefetch_related('items__product')

    # 2. Фільтрація за пошуковим запитом (як було)
    if query:
        orders = orders.filter(
            Q(customer__icontains=query) | Q(items__product__name__icontains=query)
        ).distinct()

    # 3. Фільтрація за датою доставки (НОВИЙ ФУНКЦІОНАЛ)
    if filter_date_str:
        try:
            filter_date = date.fromisoformat(filter_date_str)
            orders = orders.filter(delivery_date=filter_date)
            # Оновлюємо заголовок, щоб відобразити застосований фільтр
            title = _('Звіт по замовленнях на дату доставки: %(date)s') % {'date': filter_date.strftime('%d.%m.%Y')}
        except ValueError:
            # Якщо дата некоректна, просто ігноруємо фільтр
            title = _('Звіт по активних замовленнях')
    else:
        title = _('Звіт по активних замовленнях')

    # 4. Сортування Queryset (КЛЮЧОВЕ: СОРТУВАННЯ ЗА ДАТОЮ ДОСТАВКИ)
    # Сортуємо, щоб візуально згрупувати замовлення у звіті PDF, як на сторінці
    orders = orders.order_by('delivery_date', '-created_at')

    headers = [
        _('№'), _('Замовник'), _('Позиції'), _('Примітки'), _('Статус'), _('Дата доставки'), _('Дата створення')
    ]



    data = []
    # 5. Генерація даних
    # Використовуємо enumerate для додавання порядкового номера
    for i, o in enumerate(orders, 1):
        items_str = "\n".join(
            [f"- {item.product.name}: {item.ordered_units} {_('шт.')}" for item in o.items.all()]
        )
        if not items_str:
            items_str = _("Немає позицій")

        # Конвертуємо UTC-час у локальний часовий пояс, визначений у settings.py (TIME_ZONE)
        local_created_at = timezone.localtime(o.created_at)

        row = [
            i,  # Порядковий номер
            o.customer,
            items_str,
            o.notes or '',
            o.get_status_display(),
            # Додаємо нову колонку "Дата доставки"
            o.delivery_date.strftime('%d.%m.%Y') if o.delivery_date else _('Не вказано'),
            local_created_at.strftime('%d.%m.%Y %H:%M')
        ]
        data.append(row)

    return generate_pdf_response('orders_report.pdf', title, headers, data)