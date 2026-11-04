from django.conf import settings

from .models import EstoqueSnapshot, Importacao


def loja(request):
    ctx = {"loja_nome": settings.LOJA_NOME, "loja_local": settings.LOJA_LOCAL}
    if getattr(request, "user", None) and request.user.is_authenticated:
        ult = Importacao.objects.order_by("-criado_em").values_list("criado_em", flat=True).first()
        ctx["ultima_importacao"] = ult.astimezone().strftime("%d/%m %H:%M") if ult else None
        ref = EstoqueSnapshot.objects.order_by("-data_ref").values_list("data_ref", flat=True).first()
        parados = EstoqueSnapshot.objects.filter(data_ref=ref, dias__gt=90).order_by("-dias") if ref else EstoqueSnapshot.objects.none()
        ctx["alertas"] = parados.count() or None
        ctx["alertas_itens"] = [{"modelo": e.modelo.title(), "placa": e.placa, "dias": e.dias} for e in parados[:5]]
    return ctx
