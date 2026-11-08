"""Comando de mantenimiento: asigna dueño a adjuntos antiguos sin registrar.

`vault.attachment_owner` sólo sabe responder para adjuntos subidos DESPUÉS de
que existiera ese control (ver `vault.save_upload` / `.owners.json` dentro de
`Adjuntos/`); todo lo anterior queda sin dueño a propósito, fail-closed, para
no publicar por error en el enlace público de una nota el adjunto que en
realidad subió otra (ver el docstring de
`apps.notes.views._resolve_asset_ref`). Esa postura por defecto es correcta,
pero como consecuencia deja a toda la bóveda histórica (cualquier nota
escrita antes de ese control) con sus imágenes sin resolver tanto en el
enlace público de sólo lectura como en el API de escritura pensado para una
IA (`/s/<token>/assets`): el embed sigue en el markdown, pero nadie fuera de
la bóveda autenticada puede verlo ni gestionarlo.

Este comando recorre la bóveda una vez y, para cada adjunto de
`Adjuntos/` sin dueño (sólo imágenes y PDF — los únicos tipos que el enlace
público llega a resolver, ver `apps.notes.views._SHARE_ASSET_EXTS`), mira qué
notas lo referencian por nombre (`vault.extract_asset_refs`, la misma
extracción que usa la resolución del enlace público). Si UNA SOLA nota lo
referencia, no hay ambigüedad real y se registra esa nota como dueña. Si lo
referencian dos o más notas (un adjunto genuinamente compartido entre varias,
o una simple coincidencia de nombre), se deja sin tocar — el mismo criterio
fail-closed de `_resolve_asset_ref`, aplicado ahora para decidir si rellenar
el registro en vez de sólo para leerlo.

Por defecto sólo informa de lo que haría; hace falta `--apply` para escribir
de verdad. Seguro de repetir: un adjunto que ya tiene dueño no se vuelve a
tocar.
"""
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.notes import vault

_SHARE_ASSET_EXTS = vault.IMAGE_EXTS | {".pdf"}


class Command(BaseCommand):
    help = "Asigna dueño a adjuntos antiguos sin registrar, cuando sólo una nota los referencia."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                             help="Escribe los cambios (por defecto sólo informa, en seco).")

    def handle(self, *args, **options):
        root = settings.VAULT_ROOT.resolve()
        attachments_dir = root / vault.ATTACHMENTS_DIR
        if not attachments_dir.is_dir():
            self.stdout.write(self.style.WARNING("No hay carpeta de adjuntos."))
            return

        # Una sola lectura de `.owners.json` para toda la carpeta, no una por
        # archivo (ver el aviso en `vault.attachment_owner`) — con varios
        # miles de adjuntos, repetirla por archivo es la diferencia entre
        # segundos y minutos.
        owners = vault.read_attachment_owners(root)
        orphans = {}  # nombre en minúsculas -> Path real
        for p in attachments_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in _SHARE_ASSET_EXTS:
                rel_key = str(p.relative_to(attachments_dir)).replace("\\", "/")
                if rel_key not in owners:
                    orphans[p.name.lower()] = p
                    orphans[p.stem.lower()] = p  # para refs sin extensión / cambiada

        if not orphans:
            self.stdout.write(self.style.SUCCESS("No hay adjuntos huérfanos. Nada que hacer."))
            return

        # path_del_adjunto -> {notas que lo referencian}
        referenced_by = defaultdict(set)
        for note in vault.iter_notes(root):
            try:
                content = note.read_text(encoding="utf-8")
            except OSError:
                continue
            note_rel = vault.rel_of(root, note)
            for ref in vault.extract_asset_refs(content):
                base = ref.replace("\\", "/").split("#")[0].strip().lstrip("./")
                if not base:
                    continue
                base = base.rsplit("/", 1)[-1].lower()
                hit = orphans.get(base)
                if hit is not None:
                    referenced_by[hit].add(note_rel)

        assigned, ambiguous = 0, 0
        for attachment, notes in sorted(referenced_by.items(), key=lambda kv: str(kv[0])):
            rel = attachment.relative_to(attachments_dir)
            if len(notes) == 1:
                owner = next(iter(notes))
                assigned += 1
                if options["apply"]:
                    vault.set_attachment_owner(root, attachment, owner)
                    self.stdout.write(f"  asignado  {rel}  →  {owner}")
                else:
                    self.stdout.write(f"  asignaría {rel}  →  {owner}")
            else:
                ambiguous += 1
                self.stdout.write(self.style.WARNING(
                    f"  ambiguo   {rel}  — referenciado por {len(notes)} notas, se deja sin dueño:"))
                for n in sorted(notes):
                    self.stdout.write(f"              · {n}")

        untouched = len(set(orphans.values())) - len(referenced_by)
        self.stdout.write("")
        verb = "Asignados" if options["apply"] else "Se asignarían"
        self.stdout.write(self.style.SUCCESS(
            f"{verb}: {assigned}  ·  Ambiguos (sin tocar): {ambiguous}  ·  "
            f"Sin ninguna nota que los referencie: {untouched}"))
        if not options["apply"] and assigned:
            self.stdout.write(self.style.WARNING(
                "Ejecución en seco — repite con --apply para escribir de verdad."))
