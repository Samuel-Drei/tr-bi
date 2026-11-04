from django.conf import settings

from .models import EstoqueSnapshot, Importacao


def loja(request):
    ctx = {"loja_nome": settings.LOJA_NOME, "loja_local": settings.LOJA_LOCAL}
    if getattr(request, "user", None) and request.user.is_authenticated:
        ult = Importacao.objects.order_by("-criado_em").values_list("criado_em", flat=True).first()
        ctx["ultima_importacao"] = ult.astimezone().strftime("%d/%m %H:%M") if ult else None
        ref = EstoqueSnapshot.objects.order_by("-data_ref").values_list("data_ref", flat=True).first()
        ctx["alertas"] = (EstoqueSnapshot.objects.filter(data_ref=ref, dias__gt=90).count() or None) if ref else None
    return ctx
