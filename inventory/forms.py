# inventory/forms.py
from django import forms
from .models import Product, Order, OrderItem, Supply, SupplyItem, Driver, Car
from django.utils.translation import gettext_lazy as _

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'company', 'quantity_per_pallet', 'total_units', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'company': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity_per_pallet': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_units': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class OrderForm(forms.ModelForm):
    """Форма для основної інформації про замовлення."""
    # Визначаємо delivery_date явно, щоб мати повний контроль над віджетом (наприклад, для DatePicker)
    # Якщо використовуєте Django 4.0+ і Input type="date", це забезпечує найкращу сумісність.
    delivery_date = forms.DateField(
        label=_('Дата доставки'),
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        required=True)# Робимо поле обов'язковим
    class Meta:
        model = Order
        fields = ['customer', 'delivery_date', 'notes', 'driver', 'car']
        widgets = {
            'customer': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'driver': forms.Select(attrs={'class': 'form-select product-select'}),
            'car': forms.Select(attrs={'class': 'form-select product-select'}),
            # 'delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, ),
        }
        labels = {
            'customer': _('Замовник'),
            'notes': _('Примітки до замовлення'),
            'driver':_('Водій'),
            'car':_('Реєстраційний номер'),
            # 'delivery_date': _('Дата доставки')
        }


class OrderItemForm(forms.ModelForm):
    """Форма для позицій замовлення."""
    class Meta:
        model = OrderItem
        fields = ['product', 'ordered_units']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select product-select'}),
            'ordered_units': forms.NumberInput(attrs={'class': 'form-control'}),

        }

class SupplyForm(forms.ModelForm):
    """Форма для основної інформації про постачання."""
    class Meta:
        model = Supply
        fields = ['supplier']
        widgets = {
            'supplier': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'supplier': _('Постачальник'),
        }

class SupplyItemForm(forms.ModelForm):
    """Форма для позицій постачання."""
    class Meta:
        model = SupplyItem
        fields = ['product', 'quantity']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select product-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
        }


# Оновлена форма для модального вікна
class DriverInfoForm(forms.ModelForm):
    class Meta:
        model = Order
        # Використовуємо нові поля
        fields = ['driver', 'car']
        widgets = {
            'driver': forms.Select(attrs={'class': 'form-select'}),
            'car': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['driver'].required = True
        self.fields['car'].required = False  # Номер авто не є обов'язковим
        # Заповнюємо списки
        self.fields['driver'].queryset = Driver.objects.order_by('name')
        self.fields['car'].queryset = Car.objects.order_by('number')