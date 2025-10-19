# inventory/context_processors.py
from .models import WorkShift

def shift_status(request):
    """
    Додає інформацію про активну зміну в контекст кожного шаблону.
    """
    active_shift = WorkShift.objects.filter(is_active=True).first()
    return {'active_shift': active_shift}
