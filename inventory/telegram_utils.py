import requests
from django.conf import settings
from django.apps import apps

def send_to_telegram(text: str):
    """Синхронна функція відправки повідомлень у чат складу."""
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = getattr(settings, 'TELEGRAM_SKLAD_CHAT_ID', None)
    
    if not token or not chat_id:
        print("Telegram маніфест: Токен або Chat ID не налаштовані в settings.py")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Помилка зв'язку з Telegram API: {e}")
        return False


def send_order_telegram_notification(order_id, is_created=False):
    """Збирає шапку замовлення та всі його товари в ОДНЕ сповіщення (Створення/Редагування)."""
    Order = apps.get_model('inventory', 'Order')
    
    try:
        order = Order.objects.prefetch_related('items__product', 'car', 'driver').get(id=order_id)
    except Order.DoesNotExist:
        return False

    # Збираємо товари
    items = order.items.all()
    items_text = ""
    for index, item in enumerate(items, start=1):
        items_text += f"{index}. {item.product.name} ({item.product.company}) — <b>{item.ordered_units} szt.</b>\n"
    
    if not items_text:
        items_text = "<i>(Brak towarów w zamówieniu)</i>\n"

    status_translations = dict(order.OrderStatus.choices)
    readable_status = status_translations.get(order.status, order.status)

    if is_created:
        title = f"🆕 <b>NOWE ZAMÓWIENIE №{order.id}</b>"
        footer = "📦 <b>Magazyn, można przystąpić do pracy!</b>"
    else:
        title = f"✏️ <b>ZAKTUALIZOWANO ZAMÓWIENIE №{order.id}</b>"
        footer = "⚠️ <b>Magazyn, sprawdź zgodność kompletacji z tą listą!</b>"

    text = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Klient:</b> {order.customer}\n"
        f"🚦 <b>Status:</b> {readable_status}\n"
        f"📅 <b>Data dostawy:</b> {order.delivery_date}\n"
    )
    
    if order.car:
        text += f"🚚 <b>Samochód:</b> {order.car.number}\n"
    if order.driver:
        text += f"👨‍✈️ <b>Kierowca:</b> {order.driver.name}\n"
    if order.notes:
        text += f"📝 <b>Uwagi:</b> {order.notes}\n"
        
    text += (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>LISTA TOWARÓW:</b>\n"
        f"{items_text}"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{footer}"
    )

    return send_to_telegram(text)

def send_order_cancelled_simple_notification(order_id, customer_name):
    """
    Надсилає коротке сповіщення про скасування замовлення в чат складу.
    """
    telegram_text = (
        f"❌ <b>ZAMÓWIENIE ANULOWANE I ODWOŁANE</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔢 <b>Numer zamówienia:</b> №{order_id}\n"
        f"👤 <b>Klient:</b> {customer_name}\n\n"
        f"🚨 <i>Magazyn, praca nad tym zamówieniem została wstrzymana.</i>"
    )
    return send_to_telegram(telegram_text)