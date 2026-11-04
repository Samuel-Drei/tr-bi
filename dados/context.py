from django.conf import settings

from .models import Importacao


def loja(request):
    ctx = {"loja_nome": settings.LOJA_NOME, "loja_local": settings.LOJA_LOCAL}
    if getattr(request, "user", None) and request.user.is_authenticated:
        ult = Importacao.objects.order_by("-criado_em").values_list("criado_em", flat=True).first()
        ctx["ultima_importacao"] = ult.astimezone().strftime("%d/%m %H:%M") if ult else None
    return ctx
