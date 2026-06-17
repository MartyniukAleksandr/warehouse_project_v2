from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Order, OrderItem, Product
from .telegram_utils import send_to_telegram

# створенн я сигналів для сповіщень у Telegram про зміни в замовленнях та товарах перенесено 
# до telegram_utils.py, щоб уникнути циклічних імпортів. 
# Тепер сигнали викликають функції з telegram_utils.py для надсилання повідомлень.

# --- 1. СТВОРЕННЯ/ОНОВЛЕННЯ ЗАМОВЛЕННЯ ---
# --- 2. ДОДАВАННЯ ТОВАРУ ДО ЗАМОВЛЕННЯ (РЯДКА) ---
# --------------------------------------------------


    # --- 3. ВИДАЛЕННЯ ТОВАРУ ІЗ ЗАМОВЛЕННЯ (РЯДКА) ---
# @receiver(post_delete, sender=OrderItem)
# def order_item_deleted_notification(sender, instance, **kwargs):
#     """
#     Спрацьовує, коли менеджер повністю прибирає якийсь товар із замовлення.
#     """
#     order = instance.order
#     product = instance.product

#     if order.is_deleted:
#         return

#     text = (
#         f"➖ <b>З замовлення №{order.id} ВИДАЛЕНО ТОВАР</b>\n"
#         f"👤 Замовник: {order.customer}\n"
#         f"❌ <b>Прибрано:</b> {product.name} ({product.company})\n"
#         f"📉 <i>Цей товар більше збирати НЕ потрібно!</i>"
#     )
    
#     send_to_telegram(text)


# --- 4. КОНТРОЛЬ ЗАЛИШКІВ ПРОДУКТУ ---
# @receiver(post_save, sender=Product)
# def product_stock_alert(sender, instance, **kwargs):
#     """
#     Стежить за складом і б'є на сполох, якщо товар закінчується.
#     """
#     if instance.total_units <= instance.low_threshold:
#         text = (
#             f"⚠️ <b>КРИТИЧНИЙ ЗАЛИШОК ТОВАРУ!</b>\n"
#             f"📦 <b>Товар:</b> {instance.name} ({instance.company})\n"
#             f"📉 <b>Поточний залишок:</b> {instance.total_units} шт. ({instance.full_pallets} палет)\n"
#             f"🛑 <b>Поріг мінімуму:</b> {instance.low_threshold} шт."
#         )
#         send_to_telegram(text)