"""Notes vault — el contenido vive en disco (archivos .md por usuario).

Esta app es 'view-only' para Django ORM: las notas son archivos Markdown
bajo settings.VAULT_ROOT/<user_id>/. No definimos modelos."""
