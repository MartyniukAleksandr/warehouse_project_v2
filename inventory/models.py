# inventory/models.py
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Sum
from django.contrib.auth.models import User  # Імпортуємо модель User
from simple_history.models import HistoricalRecords

def get_current_date():
    """Повертає поточну дату, витягнуту з об'єкта datetime, що враховує часовий пояс."""
    return timezone.now().date()

class Car(models.Model):
    number = models.CharField(_("Номер авто"), max_length=50, unique=True)
    history = HistoricalRecords(inherit=True, table_name='car_history')

    class Meta:
        verbose_name = _("Автомобіль")
        verbose_name_plural = _("Автомобілі")
        ordering = ['number']

    def __str__(self):
        return self.number

class Driver(models.Model):
    name = models.CharField(_("Ім'я водія"), max_length=255)
    history = HistoricalRecords(inherit=True, table_name='driver_history')

    class Meta:
        verbose_name = _("Водій")
        verbose_name_plural = _("Водії")
        ordering = ['name']

    def __str__(self):
        return self.name


#--- Модель WorkShift ---

class WorkShift(models.Model):
    start_time = models.DateTimeField(_("Час початку"), default=timezone.now)
    end_time = models.DateTimeField(_("Час закінчення"), null=True, blank=True)
    is_active = models.BooleanField(_("Активна"), default=True, db_index=True)
    history = HistoricalRecords(inherit=True, table_name='work_shift_history')

    class Meta:
        verbose_name = _("Робоча зміна")
        verbose_name_plural = _("Робочі зміни")
        ordering = ['-start_time']
        db_table = 'inventory_workshift'

    def __str__(self):
        # 1. Конвертуємо час початку (start_time) з UTC у локальний часовий пояс
        local_start = timezone.localtime(self.start_time)

        # 2. Конвертуємо час закінчення (end_time), якщо він існує
        if self.end_time:
            local_end = timezone.localtime(self.end_time)
            end_str = local_end.strftime('%Y-%m-%d %H:%M')
        else:
            end_str = _("ще активна")

        # 3. Використовуємо локалізований час для виведення
        return _("Зміна від {start} до {end}").format(
            start=local_start.strftime('%Y-%m-%d %H:%M'),
            end=end_str
        )
#---Модель продукту ---
class Product(models.Model):
    name = models.CharField(_("Назва"), max_length=200)
    company = models.CharField(_("Фірма"), max_length=200)
    quantity_per_pallet = models.IntegerField(_("Кількість на палеті"), validators=[MinValueValidator(1)],
                                              help_text=_("Скільки одиниць товару міститься на одній повній палеті."))
    total_units = models.IntegerField(_("Загальний залишок (шт.)"), default=0, validators=[MinValueValidator(0)],
                                      help_text=_("Загальна кількість картонів <в штуках>"))
    notes = models.TextField(_("Примітки"), blank=True, null=True)  # Додано поле примітки
    # Порогові значення для кожного товару
    low_threshold = models.IntegerField(_("Рівень мінімальної кількості шт."), default=15000,
                                        help_text=_(
                                            "Мінімальне порогове значення наповнюваності для цього продукту <в штуках>"))  # Наприклад, 10 одиниць
    normal_threshold = models.IntegerField(_("Рівень максимальної кількості шт."), default=66000,
                                           help_text=_(
                                               "Максимальне порогове значення наповнюваності для цього продукту <в штуках>"))  # Наприклад, 50 одиниць
    history = HistoricalRecords(inherit=True, table_name='product_history')

    class Meta:
        verbose_name = _("Продукт")
        verbose_name_plural = _("Продукти")
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.company})"

    @property
    def full_pallets(self):
        if self.quantity_per_pallet > 0:
            return self.total_units // self.quantity_per_pallet
        return 0

    full_pallets.fget.short_description = _("Повних палет")


#--- Модель Замовлення ---
class Order(models.Model):
    class OrderStatus(models.TextChoices):
        PENDING = 'PENDING', _('В очікуванні')
        SHIPPED = 'SHIPPED', _('Виїхало')
        LOADED = 'LOADED', _('Готове/Завантажено')  # Додано новий статус
        CANCELLED = 'CANCELLED', _('Скасовано')

    customer = models.CharField(_("Замовник"), max_length=200)
    created_at = models.DateTimeField(_("Дата створення"), auto_now_add=True)
    status = models.CharField(
        _("Статус"), max_length=10, choices=OrderStatus.choices, default=OrderStatus.PENDING
    )
    work_shift = models.ForeignKey(
        WorkShift, on_delete=models.PROTECT, verbose_name=_("Робоча зміна"),
        null=True, blank=True
    )
    is_deleted = models.BooleanField(_("В архіві"), default=False, db_index=True)
    notes = models.TextField(_("Примітки"), blank=True, null=True)  # Додано поле
    # Нові поля
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Водій"))
    car = models.ForeignKey(Car, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Автомобіль"))
    delivery_date = models.DateField(_("Дата доставки"), default=get_current_date)  # <-- Додаємо це поле!
    history = HistoricalRecords(inherit=True, table_name='order_history')
    class Meta:
        verbose_name = _("Замовлення")
        verbose_name_plural = _("Замовлення")
        ordering = ['-created_at']

    def __str__(self):
        return _("Замовлення №{id} для {customer}").format(id=self.id, customer=self.customer)

    @property
    def total_units(self):
        """Обчислює загальну кількість одиниць у замовленні, підсумовуючи всі позиції."""
        result = self.items.aggregate(total=Sum('ordered_units'))
        return result['total'] or 0

    total_units.fget.short_description = _("Всього (шт.)")

    # @property
    # def car_number(self):
    #     return self.car.number if self.car else ''
    #

#--- Модель позицій замовлення ---
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE, verbose_name=_("Замовлення"))
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name=_("Товар"))
    ordered_units = models.IntegerField(_("Замовлено (шт.)"), validators=[MinValueValidator(1)])
    history = HistoricalRecords(inherit=True, table_name='order_item_history')

    class Meta:
        verbose_name = _("Позиція замовлення")
        verbose_name_plural = _("Позиції замовлення")
        unique_together = ('order', 'product')

    def __str__(self):
        return _("{units} шт. товару '{product}'").format(units=self.ordered_units, product=self.product.name)


# --- Моделі для Постачання ---

class Supply(models.Model):
    """
    Модель для відстеження постачань товару на склад.
    """

    class SupplyStatus(models.TextChoices):
        PENDING = 'PENDING', _('В очікуванні')
        COMPLETED = 'COMPLETED', _('Завершено')

    supplier = models.CharField(_("Постачальник"), max_length=200,
                                help_text=_("Назва компанії або особи, що доставила товар"))
    created_at = models.DateTimeField(_("Дата створення"), auto_now_add=True)
    status = models.CharField(
        _("Статус"), max_length=10, choices=SupplyStatus.choices, default=SupplyStatus.PENDING
    )
    history = HistoricalRecords(inherit=True, table_name='supply_history')

    class Meta:
        verbose_name = _("Постачання")
        verbose_name_plural = _("Постачання")
        ordering = ['-created_at']

    def __str__(self):
        return _("Постачання №{id} від {supplier}").format(id=self.id, supplier=self.supplier)

    @property
    def total_units(self):
        """Обчислює загальну кількість одиниць у постачанні."""
        result = self.items.aggregate(total=Sum('quantity'))
        return result['total'] or 0


class SupplyItem(models.Model):
    """
    Модель для окремої позиції в постачанні.
    """
    supply = models.ForeignKey(Supply, related_name='items', on_delete=models.CASCADE, verbose_name=_("Постачання"))
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name=_("Товар"))
    quantity = models.IntegerField(_("Кількість (шт.)"), validators=[MinValueValidator(1)])
    history = HistoricalRecords(inherit=True, table_name='supply_item_history')

    class Meta:
        verbose_name = _("Позиція постачання")
        verbose_name_plural = _("Позиції постачання")
        unique_together = ('supply', 'product')

    def __str__(self):
        return _("{units} шт. товару '{product}'").format(units=self.quantity, product=self.product.name)


class StockMovement(models.Model):
    """
    Модель для запису кожної транзакції по товару на складі (журнал).
    """

    class MovementType(models.TextChoices):
        SUPPLY_IN = 'SUPPLY_IN', _('Надходження від постачання')
        ORDER_OUT = 'ORDER_OUT', _('Резервування під замовлення')
        ORDER_RETURN = 'ORDER_RETURN', _('Повернення (скасування/редагування)')
        MANUAL_ADJUST = 'MANUAL_ADJUST', _('Ручне коригування')

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements', verbose_name=_("Продукт"))
    quantity_change = models.IntegerField(_("Зміна кількості"))  # Позитивне - прихід, негативне - розхід
    new_total_units = models.IntegerField(_("Новий залишок (шт.)"))
    movement_type = models.CharField(_("Тип транзакції"), max_length=20, choices=MovementType.choices)
    timestamp = models.DateTimeField(_("Час транзакції"), default=timezone.now)
    # Додано поле для відстеження користувача
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Користувач")
    )

    # Посилання на пов'язані документи для кращої звітності
    related_order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True,
                                      verbose_name=_("Пов'язане замовлення"))
    related_supply = models.ForeignKey(Supply, on_delete=models.SET_NULL, null=True, blank=True,
                                       verbose_name=_("Пов'язане постачання"))

    notes = models.CharField(_("Примітки"), max_length=255, blank=True)
    history = HistoricalRecords(inherit=True, table_name='stock_history')

    class Meta:
        verbose_name = _("Рух по складу")
        verbose_name_plural = _("Рух по складу")
        ordering = ['-timestamp']

    def __str__(self):
        return _("Рух товару {product} на {quantity}").format(product=self.product.name, quantity=self.quantity_change)
